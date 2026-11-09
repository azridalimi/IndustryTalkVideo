"""Renders the 60 s Creative Thinking documentary at 3840x2160, 30 fps.

python video.py <scene-number> --raw DIR --assets DIR --fonts DIR --out DIR
python video.py all ...           (renders every scene in sequence)

Each scene is encoded on its own with identical x264 settings, so the
parts can be joined with the concat demuxer without re-encoding.
"""
import argparse, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 3840, 2160, 30
U = W / 100.0                      # 1 unit = 1% of width (the storyboard's cqw)
GOLD = (217, 164, 65)
WHITE = (255, 255, 255)
NAVY = (11, 22, 38)
PANEL = (18, 34, 56)
MAROON = (138, 21, 56)
SLATE = (44, 68, 102)

A = None  # parsed args

# ----------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)

def ease_out(x):
    return 1 - (1 - x) ** 3

def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def ease_back(x, s=1.6):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1

# ------------------------------------------------------------------ fonts
_fonts = {}
def font(name, px):
    key = (name, int(px))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(A.fonts, name + '.ttf'), int(px))
    return _fonts[key]

def text_img(runs, fname, px, tracking=0.0, line_gap=0.92, align='left'):
    """runs: list of lines; each line a list of (text, colour). Returns RGBA."""
    f = font(fname, px)
    asc, desc = f.getmetrics()
    lh = int(px * line_gap)
    widths = []
    for line in runs:
        w = 0
        for txt, _ in line:
            if tracking:
                w += sum(f.getlength(c) + tracking * px for c in txt)
            else:
                w += f.getlength(txt)
        widths.append(int(math.ceil(w)))
    tw = max(widths) + 8
    th = lh * (len(runs) - 1) + asc + desc + 8
    im = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, line in enumerate(runs):
        x = 4 if align == 'left' else (tw - widths[i]) / 2 if align == 'center' else tw - widths[i] - 4
        y = 4 + i * lh
        for txt, col in line:
            if tracking:
                for c in txt:
                    d.text((x, y), c, font=f, fill=col)
                    x += f.getlength(c) + tracking * px
            else:
                d.text((x, y), txt, font=f, fill=col)
                x += f.getlength(txt)
    return im

def T(s, col=WHITE):
    return [[(s, col)]]

# -------------------------------------------------------------- drawing
def with_alpha(img, a):
    if a >= 0.999:
        return img
    im = img.copy()
    im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
    return im

def place(frame, img, x, y, a=1.0, scale=1.0, blur=0.0, anchor='lt'):
    if a <= 0.002 or img is None:
        return
    im = img
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if blur > 0.3:
        pad = int(blur * 3)
        big = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
        big.paste(im, (pad, pad))
        im = big.filter(ImageFilter.GaussianBlur(blur))
        x -= pad * (1 if anchor[0] == 'l' else 0)
        y -= pad * (1 if anchor[1] == 't' else 0)
    im = with_alpha(im, a)
    if anchor[0] == 'c':
        x -= im.width / 2
    elif anchor[0] == 'r':
        x -= im.width
    if anchor[1] == 'c':
        y -= im.height / 2
    elif anchor[1] == 'b':
        y -= im.height
    frame.paste(im, (int(round(x)), int(round(y))), im)

def rise(frame, img, x, y, p, dist=None, anchor='lt'):
    """Mask reveal: the element slides up from behind its own baseline."""
    if p <= 0:
        return
    p = ease_out(p)
    h = img.height
    off = int((1 - p) * (dist or h))
    vis = h - off
    if vis <= 0:
        return
    crop = img.crop((0, 0, img.width, vis))
    yy = y
    if anchor[1] == 'c':
        yy = y - h / 2
    xx = x - (img.width / 2 if anchor[0] == 'c' else img.width if anchor[0] == 'r' else 0)
    place(frame, crop, xx, yy + off, a=min(1, p * 1.5))

def rect(frame, box, fill, a=1.0):
    x0, y0, x1, y1 = [int(v) for v in box]
    if x1 <= x0 or y1 <= y0 or a <= 0:
        return
    layer = Image.new('RGBA', (x1 - x0, y1 - y0), fill + (int(255 * a),))
    frame.paste(layer, (x0, y0), layer)

def circle_sprite(d, fill, ring=None, ring_w=0):
    s = 4
    im = Image.new('RGBA', (d * s, d * s), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if ring:
        dr.ellipse((0, 0, d * s - 1, d * s - 1), fill=ring)
        dr.ellipse((ring_w * s, ring_w * s, (d - ring_w) * s - 1, (d - ring_w) * s - 1), fill=fill)
    else:
        dr.ellipse((0, 0, d * s - 1, d * s - 1), fill=fill)
    return im.resize((d, d), Image.LANCZOS)

def face_sprite(path, d, ring_w, focus_y=0.4):
    src = Image.open(path).convert('RGB')
    side = min(src.width, src.height)
    top = int(clamp(focus_y * src.height - side / 2, 0, src.height - side))
    left = (src.width - side) // 2
    face = src.crop((left, top, left + side, top + side)).resize((d, d), Image.LANCZOS)
    face = face.filter(ImageFilter.UnsharpMask(radius=4, percent=60, threshold=2))
    mask = circle_sprite(d - 2 * ring_w, (255, 255, 255, 255)).getchannel('A')
    out = circle_sprite(d, (0, 0, 0, 0), ring=GOLD + (255,), ring_w=ring_w)
    inner = face.crop((ring_w, ring_w, d - ring_w, d - ring_w))
    out.paste(inner, (ring_w, ring_w), mask)
    return out

def gradient_bg(c0=(10, 26, 46), c1=(14, 42, 71)):
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    k = clamp_arr(0.75 * x + 0.25 * y)
    img = np.empty((H, W, 3), np.float32)
    for i in range(3):
        img[..., i] = c0[i] + (c1[i] - c0[i]) * k
    return Image.fromarray(img.astype(np.uint8))

def radial_bg(c_in=(22, 48, 79), c_out=(6, 13, 24), cx=0.5, cy=0.45, r=0.75):
    x = (np.arange(W, dtype=np.float32) / W - cx)[None, :] * (W / H)
    y = (np.arange(H, dtype=np.float32) / H - cy)[:, None]
    k = clamp_arr(np.sqrt(x * x + y * y) / r)
    img = np.empty((H, W, 3), np.float32)
    for i in range(3):
        img[..., i] = c_in[i] + (c_out[i] - c_in[i]) * k
    return Image.fromarray(img.astype(np.uint8))

def clamp_arr(a):
    return np.clip(a, 0, 1)

def dim_mask(kind='left', strength=0.9):
    """Multiplicative darkening mask (H,W,1) float32."""
    if kind == 'left':
        x = np.linspace(0, 1, W, dtype=np.float32)
        d = np.interp(x, [0, 0.55, 1], [0.92, 0.55, 0.15]) * strength
        m = (1 - d)[None, :, None]
        return np.broadcast_to(m, (H, W, 1)).astype(np.float32)
    if kind == 'bottom':
        y = np.linspace(0, 1, H, dtype=np.float32)
        d = np.interp(y, [0, 0.45, 1], [0.0, 0.0, 0.85]) * strength
        return (1 - d)[:, None, None].astype(np.float32) * np.ones((1, W, 1), np.float32)
    return np.full((1, 1, 1), 1 - strength, np.float32)

def apply_mask(frame_np, mask):
    return (frame_np.astype(np.float32) * mask).astype(np.uint8)

# ------------------------------------------------------------ footage
GRADE = "eq=contrast=1.07:saturation=0.9:gamma=0.97,colorbalance=rs=-0.03:bs=0.05:rh=0.03:bh=-0.03"

class Clip:
    """Streams graded RGB frames for one shot from ffmpeg."""
    def __init__(self, name, start, dur, speed=1.0, mode='cover', zoom=0.0, size=(W, H), xoff=0):
        self.size = size
        self.n = int(round(dur * FPS))
        path = os.path.join(A.raw, name + '.MOV')
        sw, sh = size
        src_dur = dur * speed + 0.5
        pre = f"setpts=(PTS-STARTPTS)/{speed},fps={FPS}"
        if mode == 'cover':
            if zoom:
                z = f"scale=w='trunc({sw}*(1+{zoom}*t/{dur})/2)*2':h=-2:eval=frame:flags=bicubic,crop={sw}:{sh}"
                vf = f"{pre},scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=bicubic,crop={sw}:{sh},{z},{GRADE}"
            else:
                vf = f"{pre},scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=bicubic,crop={sw}:{sh},{GRADE}"
            args = ['-vf', vf]
        else:  # portrait: blurred fill + sharp portrait at xoff from the right
            fc = (f"[0:v]{pre},{GRADE},split[a][b];"
                  f"[a]scale=960:540:force_original_aspect_ratio=increase,crop=960:540,boxblur=24:2,eq=brightness=-0.12,scale={sw}:{sh}[bg];"
                  f"[b]scale=-2:{sh}:flags=bicubic[fg];"
                  f"[bg][fg]overlay=x=W-w-{xoff}:y=0")
            args = ['-filter_complex', fc]
        cmd = ['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(src_dur), '-i', path,
               *args, '-frames:v', str(self.n), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=sw * sh * 3 * 2)
        self.last = None

    def next(self):
        sw, sh = self.size
        buf = self.p.stdout.read(sw * sh * 3)
        if len(buf) == sw * sh * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
        elif self.last is None:
            self.last = np.zeros((sh, sw, 3), np.uint8)
        return self.last

    def close(self):
        try:
            self.p.stdout.close(); self.p.kill()
        except Exception:
            pass

# -------------------------------------------------------------- assets
_cache = {}
def asset(name):
    if name not in _cache:
        _cache[name] = Image.open(os.path.join(A.assets, name)).convert('RGBA')
    return _cache[name]

def logo(name, h):
    key = (name, h)
    if key not in _cache:
        im = asset(name)
        _cache[key] = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    return _cache[key]

def logo_bug(frame, t, start=0.2):
    a = ease_out(prog(t, start, 0.4))
    u = logo('utm_white.png', int(2.4 * U))
    c = logo('centi_white.png', int(3.2 * U))
    x = W - 0.03 * W - c.width
    y = 0.04 * H
    shadow_strip(frame, x - u.width - 1.2 * U - 0.8 * U, y - 0.6 * U, W - 0.02 * W, y + c.height + 0.6 * U, a * 0.35)
    place(frame, c, x, y, a=a)
    place(frame, u, x - 1.2 * U, y + (c.height - u.height) / 2, a=a, anchor='rt')

def shadow_strip(frame, x0, y0, x1, y1, a):
    key = ('shadow', int(x1 - x0), int(y1 - y0))
    if key not in _cache:
        w, h = int(x1 - x0), int(y1 - y0)
        im = Image.new('RGBA', (w + 160, h + 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((80, 80, 80 + w, 80 + h), 30, fill=(0, 0, 0, 255))
        _cache[key] = im.filter(ImageFilter.GaussianBlur(50))
    place(frame, _cache[key], x0 - 80, y0 - 80, a=a)

def chip(txt, px=None, border=GOLD):
    px = px or 1.5 * U
    ti = text_img(T(txt.upper()), 'Mono500', px, tracking=0.08)
    padx, pady = int(1.0 * U), int(0.5 * U)
    im = Image.new('RGBA', (ti.width + 2 * padx, ti.height + 2 * pady), (6, 13, 24, 160))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, im.width - 1, im.height - 1), outline=border + (190,), width=4)
    im.paste(ti, (padx, pady), ti)
    return im

def card(label, body, width, label_col=GOLD, bar_col=GOLD):
    lab = text_img(T(label, label_col), 'Mono500', 1.15 * U, tracking=0.1)
    f = font('Sans500', 1.55 * U)
    words, lines, cur = body.split(), [], ''
    maxw = width - 2.6 * U
    for w_ in words:
        test = (cur + ' ' + w_).strip()
        if f.getlength(test) > maxw and cur:
            lines.append(cur); cur = w_
        else:
            cur = test
    lines.append(cur)
    bt = text_img([[(l, WHITE)] for l in lines], 'Sans500', 1.55 * U, line_gap=1.3)
    h = int(1.0 * U + lab.height + 0.3 * U + bt.height + 0.9 * U)
    im = Image.new('RGBA', (int(width), h), PANEL + (225,))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, int(0.4 * U), h), fill=bar_col + (255,))
    im.paste(lab, (int(1.4 * U), int(0.9 * U)), lab)
    im.paste(bt, (int(1.4 * U), int(0.9 * U + lab.height + 0.2 * U)), bt)
    return im

def flash(frame_np, t, at, dur=0.12, strength=0.55):
    p = prog(t, at, dur)
    if 0 < p < 1 or (t >= at and p == 0):
        k = strength * (1 - p)
        return (frame_np.astype(np.float32) * (1 - k) + 255 * k).astype(np.uint8)
    return frame_np

def fade_black(frame_np, k):
    if k <= 0:
        return frame_np
    return (frame_np.astype(np.float32) * (1 - k)).astype(np.uint8)

# ============================================================== SCENES
# Each scene: (duration, setup(), draw(i, t, state) -> np.uint8 HxWx3)

def s01():
    clip = Clip('IMG_7047', 8.0, 4.8, zoom=0.07)
    words = [('BERFIKIR', WHITE), ('JANGAN', WHITE), ('SYOK', GOLD), ('SENDIRI.', GOLD)]
    px = 8.5 * U
    imgs = [text_img(T(w, c), 'BC800', px) for w, c in words]
    sp = font('BC800', px).getlength(' ')
    l1w = imgs[0].width + sp + imgs[1].width
    l2w = imgs[2].width + sp + imgs[3].width
    y1, y2 = 0.36 * H, 0.36 * H + 0.88 * px
    pos = [((W - l1w) / 2, y1), ((W - l1w) / 2 + imgs[0].width + sp, y1),
           ((W - l2w) / 2, y2), ((W - l2w) / 2 + imgs[2].width + sp, y2)]
    m = dim_mask('all', 0.8)
    beats = [0.6, 1.2, 1.8, 2.4]

    def draw(i, t):
        f = apply_mask(clip.next(), m)
        fr = Image.fromarray(f)
        out_a = 1 - prog(t, 4.35, 0.4)
        for k in range(4):
            p = prog(t, beats[k], 0.22)
            if p > 0:
                s = 1.12 - 0.12 * ease_out(p)
                place(fr, imgs[k], pos[k][0] + imgs[k].width / 2, pos[k][1] + imgs[k].height / 2,
                      a=min(1, p * 2) * out_a, scale=s, anchor='cc')
        f = np.asarray(fr)
        f = flash(f, t, 2.4, 0.15, 0.25)
        return fade_black(f, prog(t, 4.5, 0.3) * 0.6)
    return 4.8, draw, [clip]

def s02():
    clip = Clip('IMG_7015', 0.4, 3.6, zoom=0.04)
    m = dim_mask('all', 0.76)
    u = logo('utm_white.png', int(8 * U))
    c = logo('centi_white.png', int(11 * U))
    gap = 4 * U
    total = u.width + gap + 0.25 * U + gap + c.width
    x0 = (W - total) / 2
    yc = 0.42 * H
    sub = text_img(T('MEMPERSEMBAHKAN'), 'BC500', 2.2 * U, tracking=0.35)

    def draw(i, t):
        fr = Image.fromarray(apply_mask(clip.next(), m))
        out_a = 1 - prog(t, 3.25, 0.35)
        p1 = ease_out(prog(t, 0.05, 0.6))
        place(fr, u, x0 + u.width / 2, yc, a=p1 * out_a, scale=0.94 + 0.06 * p1, blur=18 * (1 - p1), anchor='cc')
        dh = 9 * U * ease_in_out(prog(t, 0.3, 0.5))
        dx = x0 + u.width + gap
        rect(fr, (dx, yc - dh / 2, dx + 0.25 * U, yc + dh / 2), GOLD, out_a)
        p2 = ease_out(prog(t, 0.25, 0.6))
        place(fr, c, dx + 0.25 * U + gap + c.width / 2, yc, a=p2 * out_a, scale=0.94 + 0.06 * p2, blur=18 * (1 - p2), anchor='cc')
        p3 = prog(t, 0.9, 0.5)
        place(fr, sub, W / 2, 0.66 * H + 30 * (1 - ease_out(p3)), a=ease_out(p3) * out_a, anchor='ct')
        return np.asarray(fr)
    return 3.6, draw, [clip]

def perspective_coeffs(src, dst):
    M = []
    for (x, y), (X, Y) in zip(dst, src):
        M.append([x, y, 1, 0, 0, 0, -X * x, -X * y])
        M.append([0, 0, 0, x, y, 1, -Y * x, -Y * y])
    Bv = np.array(src).reshape(8)
    return np.linalg.solve(np.array(M, float), Bv).tolist()

def s03():
    bg = np.asarray(gradient_bg())
    poster = Image.open(os.path.join(A.assets, 'poster.png')).convert('RGB')
    ph = int(0.80 * H)
    pw = int(poster.width * ph / poster.height)
    poster = poster.resize((pw, ph), Image.LANCZOS).filter(ImageFilter.UnsharpMask(3, 50, 2)).convert('RGBA')
    sh = Image.new('RGBA', (pw + 300, ph + 300), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle((150, 150, 150 + pw, 150 + ph), fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(60))
    eyebrow = text_img(T('INDUSTRY TALK', GOLD), 'BC700', 2.6 * U, tracking=0.2)
    l1 = text_img(T('CREATIVE'), 'BC800', 10 * U)
    l2 = text_img(T('THINKING'), 'BC800', 10 * U)
    c1, c2 = chip('03.11.2026'), chip('Fakulti Komputeran · UTM')
    u = logo('utm_white.png', int(2.4 * U)); c = logo('centi_white.png', int(3.2 * U))
    X = 0.07 * W

    def draw(i, t):
        fr = Image.fromarray(bg.copy())
        # poster with perspective, sliding in and settling
        p = ease_out(prog(t, 0.0, 0.8))
        ang = 0.30 - 0.12 * p - 0.03 * (t / 4.8)          # perspective strength
        cx = W - 0.07 * W - pw / 2 + (1 - p) * 0.4 * W - t * 0.004 * W
        cy = H / 2
        k = 1 - ang * 0.35
        x0, x1 = cx - pw / 2, cx + pw / 2
        dst = [(x0, cy - ph / 2 * k), (x1, cy - ph / 2), (x1, cy + ph / 2), (x0, cy + ph / 2 * k)]
        bx0, by0 = int(min(q[0] for q in dst)), int(min(q[1] for q in dst))
        bx1, by1 = int(max(q[0] for q in dst)), int(max(q[1] for q in dst))
        loc = [(q[0] - bx0, q[1] - by0) for q in dst]
        co = perspective_coeffs([(0, 0), (pw, 0), (pw, ph), (0, ph)], loc)
        warped = poster.transform((bx1 - bx0, by1 - by0), Image.PERSPECTIVE, co, Image.BICUBIC)
        place(fr, sh, bx0 - 150 - 0.02 * W, by0 - 150 + 0.02 * W, a=p)
        place(fr, warped, bx0, by0, a=p)
        rise(fr, eyebrow, X, 0.20 * H, prog(t, 0.15, 0.4))
        rise(fr, l1, X, 0.26 * H, prog(t, 0.3, 0.45))
        rise(fr, l2, X, 0.26 * H + 0.88 * 10 * U, prog(t, 0.45, 0.45))
        rect(fr, (X, 0.63 * H, X + 0.22 * W * ease_in_out(prog(t, 0.8, 0.45)), 0.63 * H + 0.35 * U), GOLD)
        for ch, x, st in ((c1, X, 1.0), (c2, X + c1.width + 1.2 * U, 1.25)):
            q = prog(t, st, 0.35)
            if q > 0:
                place(fr, ch.crop((0, 0, max(1, int(ch.width * ease_out(q))), ch.height)), x, 0.67 * H)
        a = ease_out(prog(t, 1.5, 0.4))
        place(fr, u, X, 0.86 * H, a=a, anchor='lb')
        place(fr, c, X + u.width + 1.2 * U, 0.86 * H + 0.4 * U, a=a, anchor='lb')
        return np.asarray(fr)
    return 4.8, draw, []

def s04():
    xoff = int(0.06 * W)
    clip = Clip('IMG_7020', 9.0, 6.0, mode='portrait', xoff=xoff)
    m = dim_mask('left', 0.75)
    pw = int(H * 9 / 16)
    px_left = W - xoff - pw
    lab = text_img(T('PENCERAMAH', GOLD), 'BC700', 1.8 * U, tracking=0.2)
    n1 = text_img(T('DR ZAHARI'), 'BC800', 7 * U)
    n2 = text_img(T('OTHMAN'), 'BC800', 7 * U)
    k1 = card('KINI', 'Pengarah, Center for Teaching Thinking & Innovation (CenT-TI)', 0.46 * W)
    k2 = card('2014 – 2016 · UIAM', 'Pengasas bersama Center for Teaching Thinking', 0.46 * W)
    X = 0.06 * W

    def draw(i, t):
        fr = Image.fromarray(apply_mask(clip.next(), m))
        bh = H * ease_in_out(prog(t, 0.1, 0.6))
        rect(fr, (px_left - 0.4 * U, (H - bh) / 2, px_left, (H + bh) / 2), GOLD)
        rise(fr, lab, X, 0.16 * H, prog(t, 0.2, 0.4))
        rise(fr, n1, X, 0.21 * H, prog(t, 0.35, 0.45))
        rise(fr, n2, X, 0.21 * H + 0.88 * 7 * U, prog(t, 0.5, 0.45))
        for k_, y, st in ((k1, 0.53 * H, 1.2), (k2, 0.53 * H + k1.height + 1.2 * U, 2.4)):
            q = ease_out(prog(t, st, 0.5))
            place(fr, k_, X - 0.04 * W * (1 - q), y, a=q)
        logo_bug(fr, t)
        return np.asarray(fr)
    return 6.0, draw, [clip]

def s05():
    clip = Clip('IMG_7024', 0.2, 3.6, speed=0.8, zoom=0.05)
    m = dim_mask('left', 0.85)
    lebih = text_img(T('LEBIH', GOLD), 'BC700', 2.6 * U, tracking=0.2)
    plus = text_img(T('+', GOLD), 'BC800', 12 * U)
    l1 = text_img(T('PELAJAR FAKULTI KOMPUTERAN'), 'BC700', 3.6 * U)
    l2 = text_img(T('MEMENUHI DEWAN'), 'BC700', 3.6 * U)
    nums = {n: text_img(T(str(n)), 'BC800', 12 * U) for n in range(0, 61)}
    X = 0.06 * W

    def draw(i, t):
        fr = Image.fromarray(apply_mask(clip.next(), m))
        rise(fr, lebih, X, 0.22 * H, prog(t, 0.05, 0.35))
        q = prog(t, 0.15, 1.0)
        if q > 0:
            n = int(round(60 * ease_out(q)))
            im = nums[n]
            place(fr, im, X, 0.27 * H, a=min(1, q * 4))
            place(fr, plus, X + nums[60].width - 0.4 * U, 0.27 * H, a=ease_out(prog(t, 1.1, 0.25)))
        rise(fr, l1, X, 0.56 * H, prog(t, 0.9, 0.4))
        rise(fr, l2, X, 0.56 * H + 0.95 * 3.6 * U, prog(t, 1.05, 0.4))
        logo_bug(fr, t, 0.0)
        return np.asarray(fr)
    return 3.6, draw, [clip]

def s06():
    bg = np.asarray(radial_bg((19, 42, 70), (6, 13, 24), 0.5, 0.5, 0.8))
    S = W / 1600
    left_o = (240, 400); right_t = (1360, 400)
    lefts = [(640, 220), (660, 310), (670, 400), (660, 490), (640, 580)]
    rights = [(940, 220), (930, 310), (920, 400), (930, 490), (940, 580)]
    dot = circle_sprite(int(20 * S), WHITE + (255,))
    big = circle_sprite(int(34 * S), GOLD + (255,))
    kre = text_img(T('KREATIF'), 'BC800', 5.4 * U)
    kri = text_img(T('KRITIS'), 'BC800', 5.4 * U)
    s1 = text_img(T('Jana banyak idea'), 'Sans500', 1.9 * U)
    s2 = text_img(T('Pilih idea terbaik'), 'Sans500', 1.9 * U)
    lw = int(3 * S)

    def P(p):
        return (p[0] * S, p[1] * S)

    def draw(i, t):
        fr = Image.fromarray(bg.copy())
        d = ImageDraw.Draw(fr)
        # dashed divider
        g = ease_in_out(prog(t, 0.0, 0.6))
        y0, y1 = 160 * S, 160 * S + (600 * S) * g
        y = y0
        while y < y1:
            d.line((800 * S, y, 800 * S, min(y + 8 * S, y1)), fill=GOLD, width=lw)
            y += 18 * S
        # divergent
        if t > 0.3:
            place(fr, big, *P(left_o), scale=ease_back(prog(t, 0.3, 0.25)) if t < 0.55 else 1, anchor='cc')
        for k, e in enumerate(lefts):
            q = ease_out(prog(t, 0.6 + 0.15 * k, 0.35))
            if q > 0:
                a0, b0 = P(left_o); a1, b1 = P(e)
                d.line((a0, b0, a0 + (a1 - a0) * q, b0 + (b1 - b0) * q), fill=WHITE, width=lw)
                if q >= 1:
                    place(fr, dot, a1, b1, scale=ease_back(prog(t, 0.95 + 0.15 * k, 0.2)), anchor='cc')
        # convergent
        for k, e in enumerate(rights):
            pd = prog(t, 2.4 + 0.1 * k, 0.2)
            if pd > 0:
                place(fr, dot, *P(e), scale=ease_back(pd), anchor='cc')
            q = ease_out(prog(t, 2.8 + 0.1 * k, 0.4))
            if q > 0:
                a0, b0 = P(e); a1, b1 = P(right_t)
                d.line((a0, b0, a0 + (a1 - a0) * q, b0 + (b1 - b0) * q), fill=WHITE, width=lw)
        if t > 3.5:
            place(fr, big, *P(right_t), scale=ease_back(prog(t, 3.5, 0.25)), anchor='cc')
        rise(fr, kre, 0.06 * W, 0.70 * H, prog(t, 1.3, 0.4))
        place(fr, s1, 0.06 * W + 0.3 * U, 0.83 * H, a=ease_out(prog(t, 1.6, 0.4)))
        rise(fr, kri, 0.94 * W, 0.70 * H, prog(t, 3.6, 0.4), anchor='rt')
        place(fr, s2, 0.94 * W - 0.3 * U, 0.83 * H, a=ease_out(prog(t, 3.9, 0.4)), anchor='rt')
        f = np.asarray(fr)
        # push towards the drop
        z = prog(t, 5.3, 0.7)
        if z > 0:
            f = fade_black(f, ease_in_out(z) * 0.85)
        return f
    return 6.0, draw, []

def s07():
    bg = np.asarray(gradient_bg())
    iw = int(0.38 * W); ih = int(iw * 9 / 16)
    inset = Clip('IMG_7026', 1.5, 6.0, size=(iw, ih))
    head = text_img(T('HOTS · KEMAHIRAN BERFIKIR ARAS TINGGI', GOLD), 'BC700', 1.7 * U, tracking=0.2)
    sub = text_img(T('Higher Order Thinking Skills'), 'Sans500', 1.6 * U)
    levels = ['MENCIPTA', 'MENILAI', 'MENGANALISIS', 'MENGAPLIKASI', 'MEMAHAMI', 'MENGINGAT']
    widths = [0.34, 0.48, 0.62, 0.76, 0.88, 1.0]
    PW = 0.48 * W; bh = int(2 * U + 1.2 * U); gap = int(0.5 * U)
    top = 0.17 * H; cx = 0.06 * W + PW / 2
    labs_dark = [text_img(T(l, NAVY), 'BC700', 2 * U) for l in levels]
    labs_light = [text_img(T(l, WHITE), 'BC700', 2 * U) for l in levels]
    r1 = text_img([[('BUKAN SEKADAR INGAT', WHITE)], [('DAN FAHAM.', WHITE)]], 'BC700', 2.6 * U, line_gap=1.0)
    r2 = text_img([[('ANALISIS, NILAI, CIPTA.', GOLD)]], 'BC800', 3.2 * U)
    cap = text_img(T('Taksonomi Bloom (semakan Anderson & Krathwohl, 2001)'), 'Sans500', 1.5 * U)
    ix, iy = W - 0.05 * W - iw, 0.13 * H

    def draw(i, t):
        fr = Image.fromarray(bg.copy())
        inset_f = inset.next()
        q = ease_out(prog(t, 0.3, 0.5))
        if q > 0:
            rect(fr, (ix - 12 + (1 - q) * 300, iy - 12, ix + iw + 12 + (1 - q) * 300, iy + ih + 12), GOLD, q)
            im = Image.fromarray(inset_f).convert('RGBA')
            place(fr, im, ix + (1 - q) * 300, iy, a=q * 0.95)
        rise(fr, head, 0.06 * W, 0.075 * H, prog(t, 0.1, 0.4))
        place(fr, sub, 0.06 * W, 0.075 * H + head.height + 0.3 * U, a=ease_out(prog(t, 0.3, 0.4)) * 0.8)
        lit = ease_out(prog(t, 1.2, 0.3))
        for k in range(6):
            j = 5 - k                       # build from the bottom
            st = 0.15 + 0.12 * j
            q = ease_out(prog(t, st, 0.3))
            if q <= 0:
                continue
            w = PW * widths[k] * q
            y = top + k * (bh + gap)
            hot = k < 3
            col = tuple(int(SLATE[c] + (GOLD[c] - SLATE[c]) * lit) for c in range(3)) if hot else SLATE
            rect(fr, (cx - w / 2, y, cx + w / 2, y + bh), col, 1.0 if hot else 0.75)
            lab = labs_dark[k] if hot and lit > 0.5 else labs_light[k]
            place(fr, lab, cx, y + bh / 2, a=q * (1 if hot else 0.75), anchor='cc')
        rise(fr, r1, ix, 0.58 * H, prog(t, 2.0, 0.45))
        place(fr, r2, ix + r2.width / 2, 0.58 * H + r1.height + 0.6 * U + r2.height / 2,
              a=min(1, prog(t, 3.0, 0.1) * 2), scale=1.15 - 0.15 * ease_out(prog(t, 3.0, 0.2)), anchor='cc')
        place(fr, cap, 0.06 * W, 0.88 * H, a=0.7 * ease_out(prog(t, 1.6, 0.5)))
        f = np.asarray(fr)
        return flash(f, t, 0.0, 0.2, 0.6)
    return 6.0, draw, [inset]

def s08():
    clip = Clip('IMG_7024', 12.0, 5.4, speed=0.8, zoom=0.05)
    m = dim_mask('left', 0.9)
    lab = text_img(T('METACOGNITION', GOLD), 'BC700', 1.8 * U, tracking=0.2)
    l1 = text_img(T('BERFIKIR TENTANG'), 'BC800', 5.8 * U)
    l2 = text_img(T('CARA KITA BERFIKIR'), 'BC800', 5.8 * U)
    chips = [chip('Rancang'), chip('Pantau'), chip('Nilai semula')]
    arrow = text_img(T('→', GOLD), 'Sans600', 2.4 * U)
    X = 0.06 * W

    def draw(i, t):
        fr = Image.fromarray(apply_mask(clip.next(), m))
        rise(fr, lab, X, 0.22 * H, prog(t, 0.1, 0.4))
        rise(fr, l1, X, 0.27 * H, prog(t, 0.3, 0.45))
        rise(fr, l2, X, 0.27 * H + 0.9 * 5.8 * U, prog(t, 0.45, 0.45))
        x = X
        for k, ch in enumerate(chips):
            st = 1.8 + 0.6 * k
            q = ease_out(prog(t, st, 0.3))
            if k > 0:
                place(fr, arrow, x + 0.2 * U, 0.66 * H + ch.height / 2, a=ease_out(prog(t, st - 0.2, 0.3)), anchor='lc')
                x += arrow.width + 0.6 * U
            place(fr, ch, x, 0.66 * H + 20 * (1 - q), a=q)
            x += ch.width + 0.4 * U
        logo_bug(fr, t)
        return np.asarray(fr)
    return 5.4, draw, [clip]

def expert_card(face_path, focus, name, lines, src):
    D = int(0.26 * W)
    face = face_sprite(face_path, D, int(0.4 * U), focus)
    lab = text_img(T(name, GOLD), 'BC700', 1.8 * U, tracking=0.15)
    q = [text_img([l], 'BC800', 4.6 * U) for l in lines]
    s = text_img(T(src), 'Sans500', 1.5 * U)
    return face, lab, q, s

def draw_expert(fr, t, parts, dx):
    face, lab, q, s = parts
    fx, fy = 0.07 * W + dx, 0.17 * H
    p = ease_out(prog(t, 0.0, 0.45))
    place(fr, face, fx + face.width / 2, fy + face.height / 2, a=p, scale=0.85 + 0.15 * p, anchor='cc')
    X = 0.39 * W + dx
    rise(fr, lab, X, 0.20 * H, prog(t, 0.25, 0.35))
    y = 0.265 * H
    for k, im in enumerate(q):
        rise(fr, im, X, y, prog(t, 0.45 + 0.18 * k, 0.4))
        y += 0.95 * 4.6 * U
    place(fr, s, X, y + 1.5 * U, a=0.7 * ease_out(prog(t, 1.3, 0.4)))

def s09():
    bg = np.asarray(gradient_bg())
    perk = expert_card(os.path.join(A.assets, 'perkins.webp'), 0.42, 'DAVID PERKINS (1992)',
                       [[('PELAJAR TIDAK BELAJAR', WHITE)], [('DAHULU, BARU BERFIKIR.', WHITE)],
                        [('MEREKA BELAJAR ', WHITE), ('KERANA', GOLD)], [('BERFIKIR.', WHITE)]],
                       'Parafrasa idea dari Smart Schools  ·  foto: Harvard Project Zero')
    nick = expert_card(os.path.join(A.assets, 'nickerson.jpg'), 0.42, 'RAYMOND S. NICKERSON (1987)',
                       [[('BERFIKIR DENGAN BAIK', WHITE)], [('BUKAN BAKAT SEMULA JADI.', WHITE)],
                        [('IA KEMAHIRAN YANG', WHITE)], [('MESTI ', WHITE), ('DIAJAR.', GOLD)]],
                       'Parafrasa idea dari "Why teach thinking?"')

    def draw(i, t):
        fr = Image.fromarray(bg.copy())
        sw = ease_in_out(prog(t, 3.6, 0.4))
        if sw < 1:
            draw_expert(fr, t, perk, -W * sw)
        if t >= 3.6:
            draw_expert(fr, max(0, t - 3.75), nick, W * (1 - sw))
        return np.asarray(fr)
    return 7.2, draw, []

def s10():
    shots = [('IMG_7031', 47.0), ('IMG_7030', 4.0), ('IMG_7028', 5.0), ('IMG_7019', 11.0),
             ('IMG_7031', 8.0), ('IMG_7047', 14.0), ('IMG_7026', 14.0)]
    m = dim_mask('left', 0.8)
    qm = text_img(T('“', GOLD), 'BC800', 6 * U)
    q1 = [text_img(T('MENGGUNAKAN AKAL'), 'BC800', 6.4 * U),
          text_img([[('MENGATASI ', WHITE), ('NAFSU.', GOLD)]], 'BC800', 6.4 * U)]
    q2 = [text_img(T('INTEGRITI DAN'), 'BC800', 7 * U),
          text_img(T('OPEN MINDED.', GOLD), 'BC800', 7 * U)]
    att = text_img(T('— DR ZAHARI OTHMAN', GOLD), 'BC700', 1.8 * U, tracking=0.15)
    X = 0.06 * W
    st = {'k': -1, 'clip': None}
    clips = []

    def draw(i, t):
        k = min(len(shots) - 1, int(t / 1.2 + 1e-6))
        if k != st['k']:
            if st['clip']:
                st['clip'].close()
            name, s0 = shots[k]
            st['clip'] = Clip(name, s0, 1.2 if k < 6 else 0.6, zoom=0.04)
            st['k'] = k
            clips[:] = [st['clip']]
        fr = Image.fromarray(apply_mask(st['clip'].next(), m))
        # quote 1 : 0.0-3.5, quote 2 : 3.6-7.8
        if t < 3.55:
            a = 1 - prog(t, 3.35, 0.2)
            y = 0.36 * H
            place(fr, qm, X, y - 3.2 * U, a=a * ease_out(prog(t, 0.0, 0.2)))
            for j, im in enumerate(q1):
                p = prog(t, 0.05 + 0.3 * j, 0.18)
                if p > 0:
                    place(fr, im, X + im.width / 2, y + im.height / 2 + j * 0.92 * 6.4 * U, a=min(1, p * 2) * a,
                          scale=1.15 - 0.15 * ease_out(p), anchor='cc')
            place(fr, att, X, y + 2 * 0.92 * 6.4 * U + 1.4 * U, a=a * ease_out(prog(t, 0.9, 0.3)))
        else:
            tt = t - 3.6
            y = 0.38 * H
            for j, im in enumerate(q2):
                p = prog(tt, 0.0 + 0.3 * j, 0.18)
                if p > 0:
                    place(fr, im, X + im.width / 2, y + im.height / 2 + j * 0.92 * 7 * U, a=min(1, p * 2),
                          scale=1.15 - 0.15 * ease_out(p), anchor='cc')
            place(fr, att, X, y + 2 * 0.92 * 7 * U + 1.4 * U, a=ease_out(prog(tt, 0.9, 0.3)))
        logo_bug(fr, t, 0.0)
        f = np.asarray(fr)
        f = flash(f, t, 0.0, 0.12, 0.45)
        f = flash(f, t, 3.6, 0.12, 0.45)
        return f
    return 7.8, draw, clips

def s11():
    bg = np.asarray(radial_bg((22, 48, 79), (6, 13, 24), 0.5, 0.4, 0.7))
    px = 5 * U
    lines = [text_img(T('“BERFIKIR JANGAN SYOK SENDIRI.'), 'BC800', px),
             text_img(T('BUAT BENDA YANG BOLEH'), 'BC800', px),
             text_img(T('SOLVE COMPANY PUNYA PROBLEM.”', GOLD), 'BC800', px)]
    name = text_img(T('DR ZAHARI OTHMAN', GOLD), 'BC700', 1.9 * U, tracking=0.2)
    u = logo('utm_white.png', int(5.5 * U)); c = logo('centi_white.png', int(7.5 * U))
    date = text_img(T('INDUSTRY TALK · CREATIVE THINKING · 3 NOVEMBER 2026'), 'BC500', 1.7 * U, tracking=0.2)
    gap = 3 * U
    total = u.width + gap + 0.2 * U + gap + c.width
    x0 = (W - total) / 2; yl = 0.66 * H

    def draw(i, t):
        fr = Image.fromarray(bg.copy())
        y = 0.15 * H
        for k, im in enumerate(lines):
            rise(fr, im, W / 2, y, prog(t, 0.05 + 0.22 * k, 0.45), anchor='ct')
            y += 0.92 * px
        rise(fr, name, W / 2, 0.47 * H, prog(t, 0.9, 0.4), anchor='ct')
        a = ease_out(prog(t, 1.3, 0.6))
        place(fr, u, x0 + u.width / 2, yl, a=a, blur=14 * (1 - a), anchor='cc')
        dh = 6 * U * ease_in_out(prog(t, 1.4, 0.4))
        dx = x0 + u.width + gap
        rect(fr, (dx, yl - dh / 2, dx + 0.2 * U, yl + dh / 2), GOLD)
        place(fr, c, dx + 0.2 * U + gap + c.width / 2, yl, a=a, blur=14 * (1 - a), anchor='cc')
        place(fr, date, W / 2, 0.86 * H, a=0.7 * ease_out(prog(t, 1.8, 0.5)), anchor='ct')
        f = np.asarray(fr)
        return fade_black(f, ease_in_out(prog(t, 4.0, 0.8)))
    return 4.8, draw, []

SCENES = [s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11]

# ---------------------------------------------------------------- driver
def encoder(path, nframes):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-vf', 'noise=alls=5:allf=t,format=yuv420p', '-frames:v', str(nframes),
           '-c:v', 'libx264', '-preset', A.preset, '-crf', str(A.crf), '-profile:v', 'high', '-level', '5.2',
           '-g', '30', '-bf', '2', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
           '-movflags', '+faststart', path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)

def render_scene(idx, only_frames=None):
    dur, draw, clips = SCENES[idx]()
    n = int(round(dur * FPS))
    out = os.path.join(A.out, f's{idx + 1:02d}.mp4')
    enc = None if only_frames else encoder(out, n)
    for i in range(n):
        t = i / FPS
        f = draw(i, t)
        if only_frames is not None:
            if i in only_frames:
                Image.fromarray(np.ascontiguousarray(f)).resize((1920, 1080), Image.LANCZOS).save(
                    os.path.join(A.out, f'still_s{idx + 1:02d}_{i:03d}.jpg'), quality=88)
            if i >= max(only_frames):
                break
            continue
        enc.stdin.write(np.ascontiguousarray(f, dtype=np.uint8).tobytes())
    for c in clips:
        c.close()
    if enc:
        enc.stdin.close(); enc.wait()
        print('done', out, flush=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('scene')
    ap.add_argument('--raw', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--fonts', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--crf', type=int, default=17)
    ap.add_argument('--preset', default='medium')
    ap.add_argument('--stills', default='')
    A = ap.parse_args()
    os.makedirs(A.out, exist_ok=True)
    idxs = range(len(SCENES)) if A.scene == 'all' else [int(s) - 1 for s in A.scene.split(',')]
    stills = [int(x) for x in A.stills.split(',')] if A.stills else None
    for k in idxs:
        render_scene(k, stills)

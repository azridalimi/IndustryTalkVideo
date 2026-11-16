import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
DUR = 21.7
N = int(SR * DUR)
rng = np.random.default_rng(7)

music = np.zeros((N, 2))
drums = np.zeros((N, 2))
sfx = np.zeros((N, 2))
rev = np.zeros((N, 2))      # reverb send
duck = np.ones(N)           # sidechain envelope


def tt(d):
    return np.arange(int(SR * d)) / SR


def add(bus, x, t, gain=1.0, pan=0.0, send=0.0):
    i = int(round(t * SR))
    if i >= N:
        return
    if x.ndim == 1:
        l = x * np.sqrt((1 - pan) / 2) * 1.414
        r = x * np.sqrt((1 + pan) / 2) * 1.414
        x = np.stack([l, r], 1)
    x = x[: N - i] * gain
    bus[i:i + len(x)] += x
    if send:
        rev[i:i + len(x)] += x * send


def filt(x, kind, f, order=2):
    sos = signal.butter(order, f, kind, fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=0)


def env(n, a, d):
    """attack a sec, exponential decay time-constant d sec"""
    t = np.arange(n) / SR
    e = np.exp(-t / d)
    na = max(1, int(a * SR))
    e[:na] *= np.linspace(0, 1, na)
    return e


def fade_out(x, sec=0.01):
    k = min(len(x), int(sec * SR))
    x = x.copy()
    x[-k:] *= np.linspace(1, 0, k)
    return x


# ---------- instruments ----------
def kick(punch=1.0):
    t = tt(0.42)
    f = 46 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / 0.16)
    click = filt(rng.standard_normal(len(t)), 'high', 3000) * np.exp(-t / 0.004) * 0.25
    return fade_out(np.tanh((x + click * punch) * 1.6))


def clap():
    t = tt(0.3)
    n = filt(rng.standard_normal(len(t)), 'band', [900, 3800])
    e = np.zeros(len(t))
    for off in (0.0, 0.011, 0.023):
        k = int(off * SR)
        e[k:] += np.exp(-t[: len(t) - k] / 0.012)
    e += np.exp(-t / 0.09) * 0.6
    return fade_out(n * e * 0.5)


def hat(open_=False):
    t = tt(0.25 if open_ else 0.06)
    n = filt(rng.standard_normal(len(t)), 'high', 7500, 4)
    return fade_out(n * np.exp(-t / (0.07 if open_ else 0.014)))


def saw(freq, n, detune=(1.0,)):
    t = np.arange(n) / SR
    x = np.zeros(n)
    for d in detune:
        x += signal.sawtooth(2 * np.pi * freq * d * t + rng.uniform(0, 6.28))
    return x / len(detune)


def bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = saw(freq, n, (1.0, 1.006)) * 0.6 + np.sin(2 * np.pi * freq * t) * 0.9
    x = filt(x, 'low', 420, 2)
    return fade_out(x * env(n, 0.004, dur * 0.9), 0.015)


def stab(freqs, dur=0.45, cutoff=3200):
    n = int(dur * SR)
    x = sum(saw(f, n, (0.994, 1.0, 1.007)) for f in freqs) / len(freqs)
    x = filt(x, 'low', cutoff, 2)
    return fade_out(x * env(n, 0.003, dur * 0.35), 0.02)


def pluck(freq, dur=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t) * np.exp(-t / 0.05)
    return fade_out(x * env(n, 0.002, 0.09), 0.02)


def pad(freqs, dur, cutoff=900):
    n = int(dur * SR)
    out = np.zeros((n, 2))
    for f in freqs:
        out[:, 0] += saw(f, n, (0.995, 1.002))
        out[:, 1] += saw(f, n, (0.998, 1.005))
    return filt(out / len(freqs), 'low', cutoff, 2)


# ---------- sound effects ----------
def sweep_noise(dur, f0, f1, q=1.2, shape='hump', peak=0.5):
    """state-variable band-pass over noise with a moving centre frequency"""
    n = int(dur * SR)
    x = rng.standard_normal(n)
    p = np.linspace(0, 1, n)
    fc = f0 * (f1 / f0) ** p
    g = 2 * np.sin(np.pi * np.minimum(fc, SR / 6.5) / SR)
    low = band = 0.0
    y = np.empty(n)
    damp = 1 / q
    for i in range(n):
        low += g[i] * band
        high = x[i] - low - damp * band
        band += g[i] * high
        y[i] = band
    if shape == 'hump':
        e = np.where(p < peak, (p / peak) ** 2, ((1 - p) / (1 - peak)) ** 2)
    elif shape == 'rise':
        e = p ** 2.5
        k = int(0.012 * SR)
        e[-k:] *= np.linspace(1, 0, k)
    else:
        e = (1 - p) ** 2
    return y * e / (np.max(np.abs(y)) + 1e-9)


def whoosh(dur=0.5, f0=400, f1=4500, peak=0.55):
    a = sweep_noise(dur, f0, f1, 1.3, 'hump', peak)
    b = sweep_noise(dur, f0 * 1.3, f1 * 0.8, 1.3, 'hump', peak)
    return np.stack([a, b], 1)


def impact(deep=1.0):
    t = tt(2.4)
    f = 34 + 70 * np.exp(-t / 0.07)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    body = filt(rng.standard_normal(len(t)), 'low', 900) * np.exp(-t / 0.12) * 0.5
    crack = filt(rng.standard_normal(len(t)), 'band', [1500, 6000]) * np.exp(-t / 0.02) * 0.25
    return fade_out(np.tanh((sub * deep + body + crack) * 1.4), 0.1)


def riser(dur, f0=300, f1=9000):
    a = sweep_noise(dur, f0, f1, 2.0, 'rise')
    b = sweep_noise(dur, f0 * 1.2, f1, 2.0, 'rise')
    t = tt(dur)
    p = t / dur
    tone = np.sin(2 * np.pi * np.cumsum(180 * 4 ** p) / SR) * p ** 3 * 0.25
    tone = fade_out(tone, 0.012)
    return np.stack([a + tone, b + tone], 1)


def shatter():
    d = 1.3
    n = int(d * SR)
    out = np.zeros((n, 2))
    burst = filt(rng.standard_normal(n), 'high', 2500) * np.exp(-tt(d) / 0.05)
    out += burst[:, None] * 0.7
    for _ in range(46):
        t0 = abs(rng.normal(0, 0.22))
        if t0 > d - 0.3:
            continue
        f = rng.uniform(2200, 9500)
        ln = int(rng.uniform(0.05, 0.28) * SR)
        t = np.arange(ln) / SR
        ping = np.sin(2 * np.pi * f * t) * np.exp(-t / rng.uniform(0.012, 0.06))
        i = int(t0 * SR)
        pn = rng.uniform(-0.9, 0.9)
        amp = rng.uniform(0.15, 0.5) * np.exp(-t0 / 0.4)
        out[i:i + ln, 0] += ping[: n - i] * amp * (1 - pn) / 2 * 2
        out[i:i + ln, 1] += ping[: n - i] * amp * (1 + pn) / 2 * 2
    return out / np.max(np.abs(out))


def pop(f=520):
    t = tt(0.09)
    fr = f * (1 + 1.2 * np.exp(-t / 0.012))
    return fade_out(np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.025))


def tick():
    t = tt(0.03)
    return filt(rng.standard_normal(len(t)), 'band', [2500, 7000]) * np.exp(-t / 0.004)


def shimmer(dur=2.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for f in [1760, 2093, 2637, 3136, 3520, 4186, 5274]:
        for ch in (0, 1):
            a = np.sin(2 * np.pi * f * rng.uniform(0.998, 1.002) * t + rng.uniform(0, 6.28))
            trem = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(3, 9) * t + rng.uniform(0, 6.28))
            out[:, ch] += a * trem * (1760 / f)
    e = np.minimum(t / 0.25, 1) * np.exp(-t / 0.8)
    return out * e[:, None] / np.max(np.abs(out))


# ---------- notes ----------
A1, C2, D2, E2, F1, G1 = 55.0, 65.41, 73.42, 82.41, 43.65, 49.0
A3, C4, E4, F3, G3, B3, D4, A4, C5, E5, G4 = 220.0, 261.63, 329.63, 174.61, 196.0, 246.94, 293.66, 440.0, 523.25, 659.25, 392.0
AM, FM, GM = [A3, C4, E4], [F3, A3, C4], [G3, B3, D4]

K, CL, HH, OH = kick(), clap(), hat(), hat(True)


def hit_kick(t, g=1.0):
    add(drums, K, t, 0.95 * g)
    i = int(t * SR)
    k = int(0.22 * SR)
    seg = 1 - 0.75 * np.exp(-np.arange(k) / (0.07 * SR))
    duck[i:i + k] = np.minimum(duck[i:i + k], seg[: max(0, min(k, N - i))])


def groove(t0, t1, chords, hats=True, claps=True, stabs=True, bassline=True, kg=1.0):
    b = 0
    t = t0
    while t < t1 - 1e-6:
        hit_kick(t, kg)
        if claps and b % 2 == 1:
            add(drums, CL, t, 0.55, send=0.25)
        if hats:
            for s in range(4):
                g = (0.16, 0.07, 0.2, 0.09)[s]
                add(drums, HH, t + s * 0.125, g, pan=0.25 if s % 2 else -0.2)
            add(drums, OH, t + 0.25, 0.09, pan=0.3)
        ch, root = chords[int((t - t0) // 2) % len(chords)]
        if bassline:
            add(music, bass(root, 0.22), t + 0.25, 0.75)
            if b % 4 == 3:
                add(music, bass(root * 2, 0.11), t + 0.375, 0.5)
            else:
                add(music, bass(root, 0.11), t + 0.125, 0.45)
        if stabs and b % 4 in (0, 3):
            off = 0 if b % 4 == 0 else 0.25
            add(music, stab(ch), t + off, 0.32, pan=-0.15 if b % 4 == 0 else 0.2, send=0.35)
        b += 1
        t += 0.5


PROG = [(AM, A1), (FM, F1), (AM, A1), (GM, G1)]

# ===== 0-4 s : intro (shape morphs into the V) =====
p = pad([A1 * 2, A3, E4], 4.3, 700)
p *= (np.linspace(0, 1, len(p)) ** 1.5)[:, None]
p[-int(0.2 * SR):] *= np.linspace(1, 0, int(0.2 * SR))[:, None]
add(music, p, 0.0, 0.16, send=0.3)
for t, f in [(0.03, 440), (0.5, 523), (1.0, 392), (1.5, 659)]:
    add(sfx, pop(f), t, 0.4, send=0.5)
    add(music, pluck(f), t, 0.3, send=0.6)
for t in (0.0, 1.0, 2.0, 3.0):
    add(drums, filt(K, 'low', 180), t, 0.7)
add(sfx, whoosh(0.45, 500, 3500), 0.72, 0.28, send=0.3)     # circle -> square
add(sfx, whoosh(0.45, 600, 4200), 1.28, 0.3, send=0.3)      # square -> triangle
add(sfx, whoosh(0.6, 300, 5000, 0.6), 2.3, 0.5, send=0.3)   # triangle -> V
add(sfx, impact(0.7), 2.67, 0.4, send=0.2)
add(sfx, whoosh(0.4, 700, 3000), 2.85, 0.25)
add(sfx, riser(1.25), 2.75, 0.5, send=0.25)                 # zoom into black

# ===== 4-6.5 s : word hits =====
add(sfx, impact(1.0), 4.0, 0.75, send=0.3)
groove(4.0, 6.5, [(AM, A1)], stabs=False)
add(music, stab(AM, 0.5, 4200), 4.0, 0.45, send=0.4)             # GREEN
add(music, stab([A3, C4, E4, A4], 0.4, 3600), 4.5, 0.35, send=0.4)  # INNOVATION
add(sfx, whoosh(0.3, 900, 5000), 4.36, 0.3)
add(sfx, whoosh(0.35, 500, 6000, 0.7), 4.9, 0.45)                # cut to white
add(sfx, impact(0.6), 5.13, 0.4)
add(music, stab(FM, 0.4, 3600), 5.25, 0.4, send=0.4)             # FOR A
add(music, stab([F3, A3, C4, F3 * 2], 0.4, 3600), 5.5, 0.38, send=0.4)  # SUSTAINABLE
add(sfx, whoosh(0.3, 900, 5000), 5.36, 0.28)
add(music, stab([G3, B3, D4, G4], 0.6, 5000), 6.0, 0.5, send=0.5)  # FUTURE
add(sfx, impact(0.8), 6.0, 0.5, send=0.3)

# ===== 6.5-8 s : shatter + re-assemble =====
add(sfx, shatter(), 6.5, 0.55, send=0.5)
add(sfx, impact(0.9), 6.5, 0.45, send=0.4)
add(sfx, riser(1.25, 250, 7000), 6.75, 0.5, send=0.3)
for i, t in enumerate((7.0, 7.25, 7.5, 7.625, 7.75, 7.875)):
    add(drums, CL, t, 0.2 + 0.05 * i, send=0.3)
add(sfx, pop(700), 7.75, 0.4, send=0.5)

# ===== 8-12 s : 3D logo, full groove =====
add(sfx, impact(1.0), 8.0, 0.8, send=0.3)
groove(8.0, 12.0, PROG)
add(sfx, whoosh(0.5, 400, 5000), 9.5, 0.4, send=0.2)     # spin
add(sfx, whoosh(0.5, 400, 5000), 11.5, 0.4, send=0.2)    # spin
add(sfx, riser(0.5, 800, 8000), 11.5, 0.3)

# ===== 12-16 s : wordmark lock-up =====
add(sfx, impact(0.7), 12.0, 0.5, send=0.3)
groove(12.0, 15.5, PROG, stabs=False)
arp = [A4, C5, E5, C5, A4, E5, C5, E5]
for i in range(28):
    t = 12.0 + i * 0.125
    f = arp[i % 8] * (0.794 if 2.0 <= i * 0.125 < 4.0 and False else 1)
    add(music, pluck(f, 0.3), t, 0.16, pan=0.4 * np.sin(i), send=0.7)
for i in range(8):                                        # letters landing
    add(sfx, tick(), 12.15 + i * 0.1, 0.25, pan=-0.5 + i / 7)
for t in (13.25, 13.75, 14.25, 14.75, 15.25):             # tagline typing
    add(sfx, tick(), t, 0.3)
    add(sfx, tick(), t + 0.06, 0.2)
add(sfx, whoosh(0.4, 600, 4000), 12.75, 0.25)
hit_kick(15.5)
add(sfx, riser(0.75, 400, 9000), 15.25, 0.55, send=0.2)

# ===== 16-17 s : big V flip =====
add(sfx, impact(1.0), 16.0, 0.8, send=0.3)
add(music, stab([A3, E4, A4], 0.8, 5000), 16.0, 0.45, send=0.5)
hit_kick(16.0)
hit_kick(16.5)
for i in range(8):
    add(drums, CL, 16.0 + i * 0.125, 0.14 + 0.04 * i, send=0.2)
    add(drums, HH, 16.0 + i * 0.125 + 0.0625, 0.12)
add(sfx, whoosh(0.5, 300, 6000, 0.5), 16.3, 0.55, send=0.2)
add(sfx, riser(0.5, 600, 9000), 16.5, 0.4)

# ===== 17-18 s : final lock-up builds =====
add(sfx, impact(0.9), 17.0, 0.65, send=0.3)
groove(17.0, 18.0, [(FM, F1)], stabs=False)
add(music, stab(FM, 0.5, 3800), 17.0, 0.38, send=0.4)
add(music, stab(GM, 0.5, 4200), 17.5, 0.4, send=0.4)
for i in range(8):
    add(sfx, tick(), 16.9 + i * 0.07, 0.25, pan=-0.5 + i / 7)
add(sfx, riser(0.5, 800, 9000), 17.5, 0.4)

# ===== 18 s -> end : final hit and tail =====
add(sfx, impact(1.1), 18.0, 0.9, send=0.45)
hit_kick(18.0)
add(drums, CL, 18.0, 0.5, send=0.6)
add(music, stab([A3, C4, E4, A4, E5], 2.6, 4500), 18.0, 0.5, send=0.7)
add(music, bass(A1, 1.6), 18.0, 0.7)
fp = pad([A1 * 2, A3, E4, A4], 3.6, 1100)
fp *= np.exp(-np.arange(len(fp)) / (1.3 * SR))[:, None]
add(music, fp, 18.0, 0.22, send=0.5)
add(sfx, shimmer(), 18.02, 0.16, send=0.6)

# ---------- mix ----------
music *= duck[:, None]
ir_n = int(1.8 * SR)
ir = rng.standard_normal((ir_n, 2)) * np.exp(-np.arange(ir_n) / (0.45 * SR))[:, None]
ir = filt(ir, 'low', 6500)
ir = filt(ir, 'high', 250)
wet = np.stack([signal.fftconvolve(rev[:, c], ir[:, c])[:N] for c in (0, 1)], 1)
wet /= np.sqrt(np.sum(ir ** 2) / 2)

mix = music * 0.9 + drums * 0.85 + sfx * 0.8 + wet * 1.4
mix = filt(mix, 'high', 28)
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix /= np.max(np.abs(mix))
mix *= 10 ** (-1.0 / 20)
fo = int(1.2 * SR)
mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
fi = int(0.01 * SR)
mix[:fi] *= np.linspace(0, 1, fi)[:, None]
wavfile.write('audio.wav', SR, (mix * 32767).astype(np.int16))
for name, b in (('music', music), ('drums', drums), ('sfx', sfx), ("wet", wet * 1.4)):
    print(name, 'rms dB', round(20 * np.log10(np.sqrt(np.mean(b ** 2)) + 1e-9), 1), 'peak', round(float(np.max(np.abs(b))), 2))

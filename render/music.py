"""Original cinematic score for the 60 s Creative Thinking video.

100 BPM, A minor, bar = 2.4 s. Sections follow the storyboard:
  0.0-4.8   intro   piano + sub boom on the hook
  4.8-13.2  pulse   bass 8ths, pad
  13.2-28.8 build   half-time kick, hats, riser into the drop
  28.8-47.4 drop    full groove, piano arpeggio
  47.4-55.2 climax  lead + impacts on each quote
  55.2-60.0 outro   final piano chord, reverb tail
Usage: python music.py out.wav
"""
import sys
import numpy as np
from scipy.signal import butter, lfilter, fftconvolve
from scipy.io import wavfile

SR = 48000
DUR = 60.0
BEAT = 0.6
BAR = 2.4
N = int(SR * DUR)
rng = np.random.default_rng(7)

def t_arr(d):
    return np.arange(int(SR * d)) / SR

def lp(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2), 'low'); return lfilter(b, a, x)

def hp(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2), 'high'); return lfilter(b, a, x)

def bp(x, lo, hi, order=2):
    b, a = butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band'); return lfilter(b, a, x)

def add(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain

def saw(f, t):
    return 2 * ((f * t) % 1.0) - 1

# ---- instruments -------------------------------------------------------
def piano(f, d=3.0, vel=1.0):
    t = t_arr(d)
    s = np.zeros_like(t)
    for k in range(1, 8):
        s += np.sin(2 * np.pi * f * k * 1.0008 ** k * t) / k ** 1.4 * np.exp(-t * (1.2 + 0.9 * k))
    s *= np.minimum(1, t / 0.004)
    return s * vel

def pad(freqs, d):
    t = t_arr(d)
    s = np.zeros_like(t)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            s += saw(f * 2 ** (det / 12), t + rng.random())
    s = lp(s, 1400) / (len(freqs) * 3)
    env = np.minimum(1, t / 0.6) * np.minimum(1, (d - t) / 0.6)
    return s * env

def bass_note(f, d):
    t = t_arr(d)
    s = lp(saw(f, t) + 0.5 * saw(f * 2.002, t), 500)
    s += 0.8 * np.sin(2 * np.pi * f * t)
    return s * np.exp(-t * 6) * np.minimum(1, t / 0.003)

def kick():
    t = t_arr(0.5)
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7)
    s[:200] += rng.standard_normal(200) * np.linspace(0.5, 0, 200)
    return s

def snare():
    t = t_arr(0.3)
    n = bp(rng.standard_normal(len(t)), 1200, 7000) * np.exp(-t * 18)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
    return n * 1.4 + tone * 0.6

def hat(open_=False):
    d = 0.18 if open_ else 0.05
    t = t_arr(d)
    return hp(rng.standard_normal(len(t)), 7500) * np.exp(-t * (14 if open_ else 70))

def boom(d=3.0):
    t = t_arr(d)
    f = 28 + 40 * np.exp(-t * 3)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    s += lp(rng.standard_normal(len(t)), 300) * np.exp(-t * 4) * 0.8
    return s * np.minimum(1, t / 0.002)

def impact():
    t = t_arr(2.5)
    n = lp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 5)
    return boom(2.5) * 1.1 + n * 0.5

def riser(d):
    t = t_arr(d)
    x = t / d
    n = hp(rng.standard_normal(len(t)), 800) * x ** 2.2
    f = 180 * 2 ** (3 * x)
    sweep = np.sin(2 * np.pi * np.cumsum(f) / SR) * x ** 2 * 0.4
    return (n * 0.5 + sweep) * (1 - np.exp(-(d - t) * 60))

def lead(f, d):
    t = t_arr(d)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.4)
    s = saw(f * vib, t) + saw(f * 1.004 * vib, t + 0.3)
    s = lp(s, 2400) * 0.5
    return s * np.minimum(1, t / 0.05) * np.minimum(1, (d - t) / 0.15)

def reverb(x, rt=1.8, wet=0.3):
    t = t_arr(rt * 1.5)
    ir = rng.standard_normal(len(t)) * np.exp(-t * 6.9 / rt)
    ir = lp(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2))
    return x * (1 - wet) + fftconvolve(x, ir)[: len(x)] * wet * 1.6

# ---- harmony ------------------------------------------------------------
A1, F1, C2, G1 = 55.0, 43.65, 65.41, 49.0
CHORDS = [  # (bass root, pad triad, arpeggio notes)
    (A1, [220.0, 261.63, 329.63], [440.0, 523.25, 659.25, 523.25]),
    (F1, [174.61, 220.0, 261.63], [349.23, 440.0, 523.25, 440.0]),
    (C2, [196.0, 261.63, 329.63], [392.0, 523.25, 659.25, 523.25]),
    (G1, [196.0, 246.94, 293.66], [392.0, 493.88, 587.33, 493.88]),
]
LEAD = [659.25, 698.46, 659.25, 587.33]  # E5 F5 E5 D5 over Am F C G

def chord(b):
    return CHORDS[b % 4]

# ---- arrangement --------------------------------------------------------
def build():
    drums = np.zeros(N); music = np.zeros(N); fx = np.zeros(N)

    # intro
    for f in (A1 * 2, A1 * 4, 164.81):
        add(music, piano(f, 4.5), 0.0, 0.55)
    add(music, pad(CHORDS[0][1], 4.8), 0.0, 0.25)
    add(fx, boom(3.0), 2.4, 0.9)

    # pads + bass from 4.8 to 55.2
    for b in range(2, 23):
        t0 = b * BAR
        root, triad, arp = chord(b)
        add(music, pad(triad, BAR + 0.6), t0, 0.32 if t0 < 28.8 else 0.4)
        for e in range(8):
            add(music, bass_note(root * 2, 0.28), t0 + e * BEAT / 2, 0.55 if t0 < 13.2 else 0.65)
        # sparse piano motif in pulse/build, 8th arpeggio in drop/climax
        if t0 < 28.8:
            add(music, piano(arp[0], 2.0), t0, 0.22)
            add(music, piano(arp[2], 1.6), t0 + 3 * BEAT, 0.16)
        else:
            for e in range(8):
                add(music, piano(arp[e % 4] * (2 if e >= 4 else 1), 0.9), t0 + e * BEAT / 2, 0.14)

    add(fx, impact(), 8.4, 0.35)  # title hit

    # build drums (half-time) 13.2-28.8
    for b in range(5, 12):
        t0 = b * BAR
        add(drums, kick(), t0, 0.9)
        add(drums, kick(), t0 + 2 * BEAT, 0.7)
        if t0 >= 19.2:
            for e in range(8):
                add(drums, hat(), t0 + e * BEAT / 2, 0.18 + 0.08 * (e % 2 == 0))
    add(fx, riser(4.8), 24.0, 0.55)
    roll = 27.6
    for i in range(8):  # snare roll into drop
        add(drums, snare(), roll + i * BEAT / 4, 0.15 + i * 0.07)

    # drop + climax 28.8-55.2
    for b in range(12, 23):
        t0 = b * BAR
        for k in (0, 1.5, 2):
            add(drums, kick(), t0 + k * BEAT, 1.0)
        for k in (1, 3):
            add(drums, snare(), t0 + k * BEAT, 0.75)
        for e in range(8):
            add(drums, hat(open_=(e == 7)), t0 + e * BEAT / 2, 0.22)
    add(fx, impact(), 28.8, 1.0)
    for b in range(19, 23):  # climax lead 45.6.. but enter on 47.4 phrase
        t0 = b * BAR
        st = max(t0, 47.4)
        add(music, lead(LEAD[b % 4], t0 + BAR - st), st, 0.18)
    add(fx, impact(), 47.4, 0.8)
    add(fx, impact(), 51.0, 0.7)
    add(fx, riser(1.8), 53.4, 0.35)

    # outro
    add(fx, impact(), 55.2, 0.9)
    for f in (110.0, 164.81, 220.0, 261.63, 329.63):
        add(music, piano(f, 4.8), 55.2, 0.4)

    mix = reverb(music, 2.2, 0.32) + reverb(drums, 0.8, 0.12) + reverb(fx, 2.5, 0.25)
    # gentle fade at the very end
    t = np.arange(N) / SR
    mix *= np.clip((DUR - t) / 2.0, 0, 1) ** 1.5
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.6)
    mix = mix / np.max(np.abs(mix)) * 0.89
    # widen: tiny delay on right channel for the music bus
    right = np.roll(mix, int(0.012 * SR)) * 0.35 + mix * 0.65
    return np.stack([mix, right], 1)

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'music.wav'
    st = build()
    wavfile.write(out, SR, (st * 32767).astype(np.int16))
    print('wrote', out)

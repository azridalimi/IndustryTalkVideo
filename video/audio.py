"""Synthesises the soundtrack (drone, whooshes, ticks, hits) timed to the cuts in index.html."""
import sys, wave
import numpy as np

SR, DUR = 48000, 13.6
t = np.arange(int(SR * DUR)) / SR
rng = np.random.default_rng(7)
L = np.zeros_like(t); R = np.zeros_like(t)

def env(t0, attack, release):
    x = t - t0
    return np.where(x < 0, 0, np.where(x < attack, x / attack, np.exp(-(x - attack).clip(0) / release)))

def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); y = np.empty_like(x); acc = 0.0
    for i, v in enumerate(x): acc = (1 - a) * v + a * acc; y[i] = acc
    return y

# Drone: A1 with a fifth and octave, slow movement, fades in and out.
fade = np.clip(t / 1.2, 0, 1) * np.clip((DUR - t) / 1.0, 0, 1)
for f, g, ph in [(55, .30, 0), (82.41, .14, 1), (110, .12, 2), (164.81, .05, 3), (220, .035, 4)]:
    lfo = 1 + .25 * np.sin(2 * np.pi * .13 * t + ph)
    L += g * lfo * np.sin(2 * np.pi * f * t + ph) * fade
    R += g * lfo * np.sin(2 * np.pi * f * 1.003 * t + ph + .4) * fade

# Soft pulse at 120 bpm, so the cuts land on beats.
for b in np.arange(0.5, 13.0, 0.5):
    k = env(b, .004, .09) * np.sin(2 * np.pi * (48 + 40 * np.exp(-(t - b).clip(0) * 40)) * (t - b))
    L += .22 * k; R += .22 * k

# Whooshes: filtered-noise swells peaking at each camera move.
noise = lowpass(rng.standard_normal(t.size), 2600) - lowpass(rng.standard_normal(t.size), 300)
for peak, width, gain, pan in [(0.5, .45, .5, -.3), (1.95, .40, .8, .3), (2.75, .30, .6, -.2), (4.1, .40, .8, .2),
                               (5.55, .30, .6, -.3), (6.6, .40, .7, .3), (8.1, .30, .6, 0), (8.9, .40, .8, -.2),
                               (10.85, .30, .7, .2), (12.0, .30, .6, 0)]:
    w = np.exp(-((t - peak) / (width / 2)) ** 2) * gain * .5
    L += noise * w * (1 - pan) ; R += noise * w * (1 + pan)

# Rising tone while the ring counts 0 -> 100 (5.6s - 7.15s), then a confirm chime.
k = np.clip((t - 5.6) / 1.55, 0, 1); k = 1 - (1 - k) ** 3
rise = np.sin(2 * np.pi * np.cumsum(220 + 440 * k) / SR) * np.where((t > 5.6) & (t < 7.15), np.sin(np.pi * np.clip((t - 5.6) / 1.55, 0, 1)) ** .5, 0)
L += .07 * rise; R += .07 * rise
for f, g in [(880, .16), (1318.5, .10)]:
    c = env(7.15, .005, .45) * np.sin(2 * np.pi * f * t) * g
    L += c; R += c

# Key ticks while the message types (9.15s - 10.5s, 39 characters).
for i in range(39):
    t0 = 9.15 + 1.35 * i / 39
    c = env(t0, .001, .012) * np.sin(2 * np.pi * (2100 + 300 * rng.random()) * t) * .09
    L += c * (1.1 if i % 2 else .9); R += c * (.9 if i % 2 else 1.1)

# Hits: CTA button and logo.
for t0, f, g in [(11.0, 55, .7), (12.0, 41.2, .8)]:
    h = env(t0, .005, .5) * np.sin(2 * np.pi * f * (t - t0) * (1 + .6 * np.exp(-(t - t0).clip(0) * 18))) * g
    s = env(t0, .002, .9) * (np.sin(2 * np.pi * 440 * t) + .6 * np.sin(2 * np.pi * 659.25 * t) + .4 * np.sin(2 * np.pi * 880 * t)) * .06
    L += h + s; R += h + s
for f, g in [(440, .10), (659.25, .08), (880, .05)]:      # address reveal
    c = env(13.05, .01, .5) * np.sin(2 * np.pi * f * t) * g
    L += c; R += c

st = np.stack([L, R], 1); st = np.tanh(st * .9); st *= .89 / np.abs(st).max()
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())

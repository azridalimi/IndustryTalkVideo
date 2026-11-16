"""Synthesises the soundtrack (drone, whooshes, ticks, hits) timed to the cuts in index.html.

Usage: audio.py out.wav [--outro-only]   (--outro-only keeps just the end-card sounds, to lay after a music track)
"""
import sys, wave
import numpy as np

SR, DUR, MAIN = 48000, 12.4, 9.38
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
fade = np.clip(t / .8, 0, 1) * np.clip((DUR - t) / 1.0, 0, 1) * np.where(t > MAIN, .55, 1)
for f, g, ph in [(55, .30, 0), (82.41, .14, 1), (110, .12, 2), (164.81, .05, 3), (220, .035, 4)]:
    lfo = 1 + .25 * np.sin(2 * np.pi * .13 * t + ph)
    L += g * lfo * np.sin(2 * np.pi * f * t + ph) * fade
    R += g * lfo * np.sin(2 * np.pi * f * 1.003 * t + ph + .4) * fade

# Soft pulse at 120 bpm, so the cuts land on beats.
for b in np.arange(0.5, 9.0, 0.5):
    k = env(b, .004, .09) * np.sin(2 * np.pi * (48 + 40 * np.exp(-(t - b).clip(0) * 40)) * (t - b))
    L += .22 * k; R += .22 * k

# Whooshes: filtered-noise swells peaking at each camera move.
noise = lowpass(rng.standard_normal(t.size), 2600) - lowpass(rng.standard_normal(t.size), 300)
for peak, width, gain, pan in [(0.3, .40, .5, -.3), (1.05, .30, .8, .3), (1.55, .25, .6, -.2), (2.2, .30, .8, .2),
                               (2.95, .25, .6, -.3), (3.6, .30, .7, .3), (4.4, .25, .6, 0), (5.2, .30, .8, -.2),
                               (5.95, .25, .6, .2), (6.6, .25, .7, .2), (7.35, .25, .6, 0)]:
    w = np.exp(-((t - peak) / (width / 2)) ** 2) * gain * .5
    L += noise * w * (1 - pan) ; R += noise * w * (1 + pan)

# Rising tone while the ring counts 0 -> 100 (3.05s - 3.85s), then a confirm chime.
k = np.clip((t - 3.05) / .8, 0, 1); k = 1 - (1 - k) ** 3
rise = np.sin(2 * np.pi * np.cumsum(220 + 440 * k) / SR) * np.where((t > 3.05) & (t < 3.85), np.sin(np.pi * np.clip((t - 3.05) / .8, 0, 1)) ** .5, 0)
L += .07 * rise; R += .07 * rise
for f, g in [(880, .16), (1318.5, .10)]:
    c = env(3.85, .005, .45) * np.sin(2 * np.pi * f * t) * g
    L += c; R += c

# Key ticks while the message types (5.5s - 6.4s, 39 characters).
for i in range(39):
    t0 = 5.5 + .9 * i / 39
    c = env(t0, .001, .012) * np.sin(2 * np.pi * (2100 + 300 * rng.random()) * t) * .09
    L += c * (1.1 if i % 2 else .9); R += c * (.9 if i % 2 else 1.1)

# Hits: CTA button and logo.
for t0, f, g in [(6.75, 55, .7), (7.4, 41.2, .8)]:
    h = env(t0, .005, .5) * np.sin(2 * np.pi * f * (t - t0) * (1 + .6 * np.exp(-(t - t0).clip(0) * 18))) * g
    s = env(t0, .002, .9) * (np.sin(2 * np.pi * 440 * t) + .6 * np.sin(2 * np.pi * 659.25 * t) + .4 * np.sin(2 * np.pi * 880 * t)) * .06
    L += h + s; R += h + s
for f, g in [(440, .10), (659.25, .08), (880, .05)]:      # address reveal
    c = env(8.35, .01, .5) * np.sin(2 * np.pi * f * t) * g
    L += c; R += c

# End card (9.38s on): soft hit as the name lands, snap for the bar, key ticks, closing chime.
O = np.zeros_like(t)
h = env(9.4, .005, .6) * np.sin(2 * np.pi * 55 * (t - 9.4) * (1 + .5 * np.exp(-(t - 9.4).clip(0) * 18)))
O += .55 * h + env(9.4, .004, 1.2) * (np.sin(2 * np.pi * 220 * t) + .6 * np.sin(2 * np.pi * 329.63 * t)) * .07
O += noise * np.exp(-((t - 9.85) / .12) ** 2) * .35
for i in range(17):
    t0 = 10.25 + .75 * i / 17
    O += env(t0, .001, .012) * np.sin(2 * np.pi * (2100 + 300 * rng.random()) * t) * .09
for f, g in [(440, .10), (659.25, .08), (880, .06), (1318.5, .03)]:
    O += env(11.05, .01, .7) * np.sin(2 * np.pi * f * t) * g
O *= np.clip((DUR - t) / .4, 0, 1)

if '--outro-only' in sys.argv:
    st = np.stack([O, O], 1) * .8
else:
    st = np.stack([L + O, R + O], 1); st = np.tanh(st * .9); st *= .89 / np.abs(st).max()
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())

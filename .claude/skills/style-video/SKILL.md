---
name: style-video
description: The user's house style for promo videos ("my style video"). Use when asked to make a video "in my style", "like the Inotech one", or a promo/motion video from a website or product UI.
---

# My style video

The reference implementation is `video/` in this repo (the Inotech Studio promo). Copy it and change the content; do not redesign the look or the timing unless asked.

## Look

- Pure black background, dark-mode recreations of the real site UI (panels `#0c0d0e`, hairline borders `rgba(255,255,255,.10)`, text `#f6f7f8`), soft white glow behind panels.
- One brand accent colour used for glows and highlights (Inotech: teal `#19b8a6`).
- The site's own fonts (Inotech: Space Grotesk headings, Inter body, Geist Mono labels), bundled locally in `assets/fonts`.
- Every shot is a camera move on a UI element: blur-in, macro close-up, pull out to the full element, blur-out. Blur spikes mid-move stand in for motion blur.
- Only real content from the site: its nav labels, copy, product photos, prices. Flag anything invented (e.g. a typed demo message).

## Structure and timing (9.38 s main cut, 30 fps, 1920×1080)

Cut-for-cut with the user's reference clip and its music track, so keep these times:

| Shot | Time (s) | What happens |
|---|---|---|
| 1 Nav bar | 0.0–1.55 | blur in by 0.6, push in on the logo mark 0.9–1.2, mark glows |
| 2 Card | 1.5–2.95 | close-up on title, pull out 2.0–2.4 to the full card |
| 3 Ring | 2.9–4.4 | glowing ring counts 0→100 over 3.05–3.8, pull out 3.5–3.8 to reveal labels |
| 4 Input box | 4.35–6.6 | close-up on send button, pull out 5.0–5.4, text types 5.5–6.4 while pushing in |
| 5 CTA button | 6.55–7.35 | white glowing button snaps in from a blur |
| 6 Sign-off | 7.3–9.38 | logo mark to 8.2, then the web address 8.3–9.3 |

Then the user's own logo sting (`video/assets/outro.mp4`, 4.3 s, with its own sound) is appended. Total 13.7 s.

## Sound

- Preferred: the user's music track at `video/assets/audio/track.mp3` under the main cut (loudness-normalised, short fade at 8.95 s). It is deliberately not committed; ask for it if it is missing.
- Fallback: `audio.py` synthesises a soundtrack timed to the cuts.

## Deliverables

Run `video/build.sh [track.mp3]`. It produces the 16:9 video and a 9:16 version (1080×1920, the video centred on a black canvas). Send the 9:16 music version by default plus the 16:9 one.

## Making one for a different site

1. Read the site (screenshots, copy, logo SVG, fonts, accent colour, product images). If the host is blocked, ask to allow it.
2. Copy `video/` and rewrite only the scene markup and colours in `index.html`; keep the `scenes` keyframes and element timings.
3. Render stills with `node render.js --at=...` and check them against the table above before the full render.
4. Never copy watermarks, logos or branding from a reference clip; use the client's own outro.

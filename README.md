# IndustryTalkVideo

## Faculty of Computing, UTM — 60-second reel

`output/utm-fc-reel.mp4` — 1080×1920 (9:16), 30 fps, 60 s, with music.

The reel is a motion-graphics piece built as a single HTML page and rendered frame by frame.

- `reel/index.html` — the animation. Open it in a browser to preview it live; add `?t=33` to freeze on a given second. All copy and timings are in this file.
- `reel/render.mjs` — renders the page to MP4 with Playwright + ffmpeg: `node reel/render.mjs`.
- `reel/audio/music.mp3` — soundtrack (not committed). The render runs silent without it.

Music: "Exceeding Expectations" by Experia (Epidemic Sound), 60 s edit. Publishing the reel needs an Epidemic Sound licence covering the channel it is posted on.

### Facts used on screen

| Claim | Source |
| --- | --- |
| Began in 1981 as the Department of Computer Science; moved to the Skudai campus in 1995; renamed Faculty of Computing in 2013 | comp.utm.my "About us" |
| Five undergraduate programmes | comp.utm.my / admission.utm.my |
| #130 in QS World University Rankings by Subject 2026, Computer Science & Information Systems | comp.utm.my news post |
| UTM #153 in QS World University Rankings 2026 | UTM news |
| 100% graduate employability, 2024 | comp.utm.my facts & figures |
| Four departments | comp.utm.my |

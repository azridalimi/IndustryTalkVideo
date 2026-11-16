# Inotech Studio promo video

A 12.4 s, 1920×1080, 30 fps motion piece built from the UI and copy of inotechstudio.com.

- `index.html` — the animation. Open it in a browser to preview; every shot is a keyframe track in the `scenes` array.
- `render.js` — renders the page frame by frame with Playwright and encodes it with ffmpeg.
- `audio.py` — synthesises the soundtrack (needs numpy), timed to the cuts.
- `out/inotech-promo.mp4` — the finished video.

Rebuild:

    node render.js
    python3 audio.py out/soundtrack.wav
    ffmpeg -y -i out/inotech-promo-silent.mp4 -i out/soundtrack.wav -c:v copy -c:a aac -b:a 192k -shortest out/inotech-promo.mp4

To use a music track instead, put it at `assets/audio/track.mp3` (not committed). The track covers the first 9.4 s and the synthesised end-card sounds follow it:

    node render.js
    python3 audio.py out/outro.wav --outro-only
    ffmpeg -y -i out/inotech-promo-silent.mp4 -i assets/audio/track.mp3 -i out/outro.wav -filter_complex "[1:a]loudnorm=I=-14:TP=-1.5,afade=t=out:st=8.95:d=0.4,apad[m];[m][2:a]amix=inputs=2:duration=shortest:normalize=0[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest out/inotech-promo-music.mp4

# Inotech Studio promo video

A 9.4 s, 1920×1080, 30 fps motion piece built from the UI and copy of inotechstudio.com.

- `index.html` — the animation. Open it in a browser to preview; every shot is a keyframe track in the `scenes` array.
- `render.js` — renders the page frame by frame with Playwright and encodes it with ffmpeg.
- `audio.py` — synthesises the soundtrack (needs numpy), timed to the cuts.
- `out/inotech-promo.mp4` — the finished video.

Rebuild:

    node render.js
    python3 audio.py out/soundtrack.wav
    ffmpeg -y -i out/inotech-promo-silent.mp4 -i out/soundtrack.wav -c:v copy -c:a aac -b:a 192k -shortest out/inotech-promo.mp4

To cut the video to a music track instead, put the track at `assets/audio/track.mp3` (not committed) :

    node render.js
    ffmpeg -y -i out/inotech-promo-silent.mp4 -i assets/audio/track.mp3 -af "loudnorm=I=-14:TP=-1.5,afade=t=out:st=8.95:d=0.4" -c:v copy -c:a aac -b:a 192k -shortest out/inotech-promo-music.mp4

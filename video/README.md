# Inotech Studio promo video

A 13.7 s, 1920×1080, 30 fps motion piece built from the UI and copy of inotechstudio.com.

- `index.html` — the animation (first 9.4 s). Open it in a browser to preview; every shot is a keyframe track in the `scenes` array.
- `render.js` — renders the page frame by frame with Playwright and encodes it with ffmpeg.
- `audio.py` — synthesises a soundtrack for the animation (needs numpy), timed to the cuts.
- `assets/outro.mp4` — the logo sting appended at the end, with its own sound.
- `build.sh` — renders the animation, adds sound and appends the outro.
- `out/inotech-promo.mp4` — the finished video with the synthesised soundtrack.

Rebuild:

    ./build.sh                 # synthesised soundtrack -> out/inotech-promo.mp4
    ./build.sh path/to/track.mp3   # your music under the animation -> out/inotech-promo-music.mp4 (not committed)

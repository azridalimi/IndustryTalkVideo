# Industry Talk: Creative Thinking

A 60-second documentary video of the Industry Talk on Creative Thinking with Dr Zahari Othman, held on 3 November 2026 at the UTM Faculty of Computing and co-presented with CenT-TI. It is rendered at 3840×2160 (16:9), 30 fps, with an original music score and no voiceover.

## Contents

| Path | What it is |
|---|---|
| `storyboard/storyboard.html` | The approved storyboard (11 scenes) |
| `render/music.py` | Builds the original cinematic score (A minor, 100 BPM, -14 LUFS) |
| `render/video.py` | Renders each scene: footage, motion graphics and kinetic type |
| `render/build.sh` | Full build: music, all scenes, then join and mux |
| `render/finish.sh` | Joins the rendered scenes and adds the music |
| `assets/` | White logos, poster, expert photos, fonts (SIL OFL) |

## Build

Requirements: Python 3, `numpy`, `scipy`, `Pillow`, and `ffmpeg` with libx264.

The raw footage (11 `IMG_*.MOV` clips) is not stored in this repo. Download it from the Google Drive folder into one directory, then run:

```bash
render/build.sh /path/to/IndustryTalkCenTI out
```

To render stills of a single scene for checking:

```bash
python3 render/video.py 7 --raw /path/to/IndustryTalkCenTI --assets assets --fonts assets/fonts --out out --stills 0,60,120
```

## Credits

- Perkins photo: Harvard Project Zero.
- The Perkins (1992) and Nickerson (1987) lines are paraphrases, not direct quotes.

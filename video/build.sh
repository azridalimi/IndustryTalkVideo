#!/bin/sh
# Builds the finished video: rendered animation (9.4 s) + assets/outro.mp4 (logo sting, with its own sound).
# Usage: ./build.sh            -> out/inotech-promo.mp4        (synthesised soundtrack)
#        ./build.sh track.mp3  -> out/inotech-promo-music.mp4  (your music track under the animation)
set -e
cd "$(dirname "$0")"
node render.js out/main.mp4
if [ -n "$1" ]; then
  out=out/inotech-promo-music.mp4; music="$1"; mix="loudnorm=I=-14:TP=-1.5,afade=t=out:st=8.95:d=0.4,"
else
  out=out/inotech-promo.mp4; music=out/soundtrack.wav; mix=""; python3 audio.py "$music"
fi
len=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/main.mp4)
ffmpeg -v error -y -i out/main.mp4 -i "$music" -i assets/outro.mp4 -filter_complex "
  [2:v]scale=1920:1080:flags=lanczos,fps=30,setsar=1,format=yuv420p[ov];
  [0:v]setsar=1,format=yuv420p[mv];
  [1:a]${mix}aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:${len},asetpts=N/SR/TB[ma];
  [2:a]aresample=48000,aformat=channel_layouts=stereo[oa];
  [mv][ma][ov][oa]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$out"
rm out/main.mp4
echo "wrote $out"
# Vertical 9:16 version: the same video centred on a black 1080x1920 canvas.
tall="${out%.mp4}-9x16.mp4"
ffmpeg -v error -y -i "$out" -vf "scale=1080:-2:flags=lanczos,pad=1080:1920:0:(oh-ih)/2:black" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a copy -movflags +faststart "$tall"
echo "wrote $tall"

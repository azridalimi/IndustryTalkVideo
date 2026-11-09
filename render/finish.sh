#!/usr/bin/env bash
# Joins rendered scenes s01..s11 and adds the music track.
set -euo pipefail
OUT="$1"
: > "$OUT/list.txt"
for i in $(seq -w 1 11); do echo "file 's$i.mp4'" >> "$OUT/list.txt"; done
ffmpeg -v error -y -f concat -safe 0 -i "$OUT/list.txt" -c copy "$OUT/video_only.mp4"
ffmpeg -v error -y -i "$OUT/video_only.mp4" -i "$OUT/music.wav" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -ar 48000 -shortest -movflags +faststart \
  "$OUT/CreativeThinking_IndustryTalk_4K.mp4"
# 1080p copy for quick previewing on a phone
ffmpeg -v error -y -i "$OUT/CreativeThinking_IndustryTalk_4K.mp4" -vf scale=1920:1080:flags=lanczos \
  -c:v libx264 -preset medium -crf 20 -c:a copy -movflags +faststart "$OUT/CreativeThinking_IndustryTalk_1080p.mp4"
ls -lh "$OUT"/CreativeThinking_*.mp4

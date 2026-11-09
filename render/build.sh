#!/usr/bin/env bash
# Full build: music, 11 scenes (3 in parallel), then join and mux.
# Usage: render/build.sh <raw-footage-dir> <out-dir>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RAW="$1"; OUT="$2"
mkdir -p "$OUT"
python3 "$HERE/music.py" "$OUT/music.wav"
printf "%s\n" 10 9 7 4 6 3 8 1 5 2 11 | xargs -P 3 -I{} \
  python3 "$HERE/video.py" {} --raw "$RAW" --assets "$HERE/../assets" --fonts "$HERE/../assets/fonts" --out "$OUT"
"$HERE/finish.sh" "$OUT"

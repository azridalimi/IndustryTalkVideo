// Renders reel/index.html to a 1080x1920, 30 fps, 60 s MP4 with music.
//   node reel/render.mjs            full render -> output/utm-fc-reel.mp4
//   node reel/render.mjs --stills   contact-sheet stills only -> reel/.frames/still-*.png
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { spawn } from 'node:child_process';
import { mkdirSync, rmSync, existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const FPS = 30, DUR = 60, N = FPS * DUR, WORKERS = 4;
const frames = path.join(here, '.frames');
const out = path.join(here, '..', 'output', 'utm-fc-reel.mp4');
const music = path.join(here, 'audio', 'music.mp3');
const url = pathToFileURL(path.join(here, 'index.html')).href;
const stills = process.argv.includes('--stills');

rmSync(frames, { recursive: true, force: true });
mkdirSync(frames, { recursive: true });
mkdirSync(path.dirname(out), { recursive: true });

const browser = await chromium.launch();
async function page() {
  const p = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await p.goto(url);
  await p.evaluate(() => window.ready);
  return p;
}

if (stills) {
  const p = await page();
  const times = process.argv.slice(3).map(Number);
  for (const t of times.length ? times : [2.6, 7, 12, 16.5, 21, 31, 33.5, 36.5, 39.5, 44.5, 47.3, 48.3, 53.5, 58.5]) {
    await p.evaluate(t => window.seek(t), t);
    await p.screenshot({ path: path.join(frames, `still-${String(t).padStart(5, '0')}.png`) });
  }
  await browser.close();
  process.exit(0);
}

let done = 0;
await Promise.all(Array.from({ length: WORKERS }, async (_, w) => {
  const p = await page();
  for (let i = w; i < N; i += WORKERS) {
    await p.evaluate(t => window.seek(t), i / FPS);
    await p.screenshot({ path: path.join(frames, `f${String(i).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 95 });
    if (++done % 300 === 0) console.log(`${done}/${N} frames`);
  }
}));
await browser.close();

const args = ['-y', '-v', 'error', '-framerate', String(FPS), '-i', path.join(frames, 'f%05d.jpg')];
if (existsSync(music)) args.push('-i', music, '-af', `afade=t=out:st=${DUR - 2}:d=2`, '-c:a', 'aac', '-b:a', '192k');
else console.warn('No reel/audio/music.mp3 found - rendering without sound.');
args.push('-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS),
  '-t', String(DUR), '-movflags', '+faststart', out);
await new Promise((res, rej) => spawn('ffmpeg', args, { stdio: 'inherit' }).on('exit', c => c ? rej(new Error('ffmpeg ' + c)) : res()));
rmSync(frames, { recursive: true, force: true });
console.log('wrote', out);

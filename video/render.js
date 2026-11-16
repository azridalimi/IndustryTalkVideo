// Renders index.html frame by frame and pipes the frames into ffmpeg.
// Usage: node render.js [out.mp4] [--at=1.2,3.4]   (--at writes still PNGs instead of a video)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const FPS = 30;
const args = process.argv.slice(2);
const stills = (args.find(a => a.startsWith('--at=')) || '').slice(5);
const outFile = args.find(a => !a.startsWith('--')) || path.join(__dirname, 'out', 'inotech-promo-silent.mp4');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'index.html') + '?render');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState('networkidle');
  const duration = await page.evaluate(() => window.DURATION);

  if (stills) {
    fs.mkdirSync(path.join(__dirname, 'out', 'stills'), { recursive: true });
    for (const t of stills.split(',').map(Number)) {
      await page.evaluate(t => window.seek(t), t);
      await page.screenshot({ path: path.join(__dirname, 'out', 'stills', `t${t.toFixed(2)}.png`) });
    }
    await browser.close();
    return;
  }

  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outFile],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', c => (c ? rej(new Error('ffmpeg exit ' + c)) : res())));

  const frames = Math.round(duration * FPS);
  for (let i = 0; i < frames; i++) {
    await page.evaluate(t => window.seek(t), i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 100 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await done;
  await browser.close();
  console.log(`wrote ${outFile} (${frames} frames)`);
})();

// backdrop.mjs: load a 720 x 480 raw RGB file (backdrop.py) as the compositor's live-view stand-in (patch 0003 reads
// globalThis.__omBackdrop). RGB -> YCbCr with the firmware's integer BT.601, as the IMG2 path converts.
import fs from 'node:fs';
export function loadBackdrop(path, w = 720, h = 480) {
  const b = fs.readFileSync(path);
  if (b.length !== w * h * 3) throw new Error(`backdrop ${path}: ${b.length} bytes, not ${w} x ${h} RGB`);
  const ycc = new Uint32Array(w * h);
  for (let i = 0; i < w * h; i++) {
    const r = b[3 * i], g = b[3 * i + 1], bl = b[3 * i + 2];
    const y = ((19595 * r + 38470 * g + 7471 * bl) >> 16) & 0xFF;
    const cb = (((-11056 * r - 21712 * g + (bl << 15)) >> 16) + 128) & 0xFF;
    const cr = ((((r << 15) - 27440 * g - 5328 * bl) >> 16) + 128) & 0xFF;
    ycc[i] = cr << 16 | cb << 8 | y;
  }
  globalThis.__omBackdrop = { w, h, ycc };
}

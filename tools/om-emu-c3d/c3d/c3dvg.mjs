// c3dvg.mjs: our stand-in for the DMP EGL/OpenVG client the E-M5 III's c3d tasks call (2026-11-21).
// It hooks the library's call-site entries (func + prologue; c3d enters them with `call`) and does the work in
// JavaScript: an object model for paths, paints and images, the matrices and parameters, and a software rasteriser
// (4 x 4 supersampled coverage, source-over blending) into a float RGBA surface, written to the draw buffers at
// eglSwapBuffers. Layouts and entry points: notes docs/hardware/c3d-gpu.md (sections 2, 4, 4b).
// Arguments (Olympus ABI, seen in the calls): integers fill d0, d1; pointers take a0, a1 first and integers then fill
// the a registers left (vgSetParameterfv: values a0, count a1); the rest from the caller's (4,sp) up. Floats as raw bits.
// Images of format 0x401 are in the DMP native layout: 8x8 tiles in rows, Morton order inside, first row = VG y 0.
// Use: installC3dVg(lab, opts) after the session opens. opts.log(text) receives a one-line record per call.

const ENTRY = {   // call-site address (runtime) -> name
  0x6119b361: 'eglGetError', 0x6119b386: 'eglGetDisplay', 0x6119b3aa: 'eglInitialize', 0x6119b466: 'eglTerminate',
  0x6119b888: 'eglChooseConfig', 0x6119c2e7: 'eglCreateWindowSurface', 0x6119c737: 'eglDestroySurface',
  0x6119c907: 'eglBindAPI', 0x6119cb11: 'eglReleaseThread', 0x6119d4de: 'eglCreateContext',
  0x6119d883: 'eglDestroyContext', 0x6119db26: 'eglMakeCurrent', 0x6119e459: 'eglSwapBuffers',
  0x611bba35: 'vgLoadIdentity', 0x611bba63: 'vgGetMatrix', 0x611bba93: 'vgTranslate', 0x611bbaad: 'vgScale',
  0x611bbae1: 'vgRotate', 0x611bbaf9: 'vgSetf', 0x611bbb15: 'vgSeti', 0x611bbb31: 'vgSetfv',
  0x611bbcbd: 'vgSetParameteri', 0x611bbd84: 'vgSetParameterfv', 0x611bc2d8: 'vgClear', 0x611bc309: 'vgCreatePath',
  0x611bc337: 'vgClearPath', 0x611bc353: 'vgDestroyPath', 0x611bc3d5: 'vgAppendPathData',
  0x611bc3fa: 'vgModifyPathCoords', 0x611bc41b: 'vgTransformPath', 0x611bc47b: 'vgPointAlongPath',
  0x611bc4f8: 'vgDrawPath', 0x611bc541: 'vgCreatePaint', 0x611bc55a: 'vgDestroyPaint', 0x611bc589: 'vgSetPaint',
  0x611bc63b: 'vgDestroyImage', 0x611bce2a: 'vgDrawSubImageDMP', 0x611bcfd0: 'vgCreateImageDataDMP',
  // DMP memory manager (from 0x60c24bf5) and Olympus' native platform layer (from the EGL set-up / teardown)
  0x611bea11: 'dmpMemInit', 0x611bea93: 'dmpMem2', 0x611beb7b: 'dmpMem3', 0x611bed20: 'dmpMem4',
  0x611c01ec: 'nativeInit', 0x611c025b: 'nativeDisplay', 0x611c0aa0: 'nativeWindow', 0x611c0222: 'nativeDisplayFree',
  0x611c0b6f: 'nativeWindowFree',
  0x611bacda: 'vguRoundRect', 0x611bad0b: 'vguEllipse', 0x611bad34: 'vguArc',
};
const f32 = new Float32Array(1), u32v = new Uint32Array(f32.buffer);
const fl = (bits) => { u32v[0] = bits >>> 0; return f32[0]; };
const bits = (x) => { f32[0] = x; return u32v[0]; };
const h = (v) => '0x' + (v >>> 0).toString(16);

// 3x3 affine matrices as {a: sx, b: shy, c: shx, d: sy, e: tx, f: ty}: x' = a x + c y + e, y' = b x + d y + f
const ident = () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 });
const mul = (m, n) => ({ a: m.a * n.a + m.c * n.b, b: m.b * n.a + m.d * n.b, c: m.a * n.c + m.c * n.d,
  d: m.b * n.c + m.d * n.d, e: m.a * n.e + m.c * n.f + m.e, f: m.b * n.e + m.d * n.f + m.f });
const apply = (m, x, y) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
const invert = (m) => { const det = m.a * m.d - m.b * m.c; if (!det) return null;
  const a = m.d / det, b = -m.b / det, c = -m.c / det, d = m.a / det;
  return { a, b, c, d, e: -(a * m.e + c * m.f), f: -(b * m.e + d * m.f) }; };

// MORTON[y * 8 + x]: a texel's index inside an 8x8 tile (bits x0 y0 x1 y1 x2 y2)
const MORTON = Array.from({ length: 64 }, (_, k) => { const x = k & 7, y = k >> 3; let m = 0;
  for (let b = 0; b < 3; b++) m |= ((x >> b) & 1) << (2 * b) | ((y >> b) & 1) << (2 * b + 1); return m; });

export function installC3dVg(lab, opts = {}) {
  const log = opts.log ?? (() => {});
  const sim = lab.sim, u32 = (a) => sim.u32(a >>> 0), rd = (a, n) => sim.read(a >>> 0, n);
  const st = {
    next: 0x100, objs: new Map(), mode: 0x1400, mats: { 0x1400: ident(), 0x1401: ident(), 0x1402: ident(), 0x1403: ident() },
    params: new Map(), fill: 0, stroke: 0, clear: [0, 0, 0, 0], w: 256, h: 256, surf: null, swaps: 0, calls: 0, unknown: new Map(),
    targets: opts.targets ?? [],
  };
  const surface = () => { if (!st.surf || st.surf.length !== st.w * st.h * 4) st.surf = new Float32Array(st.w * st.h * 4); return st.surf; };
  const handle = (o) => { const k = st.next++; st.objs.set(k, o); return k; };
  // stack argument n (0 = the first one past the registers) of a function entered with `call ...,[regs],size`
  // Entered by `call label,[regs],size` (stock callers): the frame size is in the call. Entered by `calls (An)` (GCC
  // code through a function pointer): the frame is the callee's own prologue (movm + add) just before the hook.
  const MOVM = [[0x80, 4], [0x40, 4], [0x20, 4], [0x10, 4], [0x08, 28]];
  // the prologue between the proc-table address and the hook (the `call` entry): `movm [regs],(sp)` and/or `add -n,sp`
  const prologue = (pc) => { const b = rd(pc - 5, 5);
    if (b[0] === 0xcf && b[2] === 0xf8 && b[3] === 0xfe) return [b[1], 256 - b[4]];
    if (b[2] === 0xf8 && b[3] === 0xfe) return [0, 256 - b[4]];
    if (b[3] === 0xcf) return [b[4], 0];
    throw new Error(`no prologue before ${pc.toString(16)}`); };
  const frameOf = (r) => { const ra = r.mdr >>> 0, c2 = rd(ra - 2, 2);
    if (c2[0] === 0xf0 && (c2[1] & 0xfc) === 0xf0) { const [mask, add] = prologue(st.pc); let m = 0; for (const [b, n] of MOVM) if (mask & b) m += n;
      return m + add; }
    const call = rd(ra - 7, 7); return call[0] === 0xdd ? call[6] : rd(ra - 5, 5)[4]; };
  const stackArg = (r, n) => u32(r.sp + frameOf(r) + 4 + 4 * n);   // the caller's stack arguments start at its (4,sp) (seen at 0x60c27511, 0x60c274cb)
  // return: through lab.finish for a `call` (it rebuilds the caller's `ret`), and for a `calls` through the callee's own
  // epilogue `ret [movm regs], frame` (the prologue at the proc-table address ran before the hook)
  const ret = (r, v = 0) => { const c2 = rd((r.mdr >>> 0) - 2, 2);
    if (!(c2[0] === 0xf0 && (c2[1] & 0xfc) === 0xf0)) { lab.finish(r, { d0: v, a0: v }); return; }
    sim.write(opts.RETURN, new Uint8Array([0xdf, prologue(st.pc)[0], frameOf(r)]));
    if (sim.packet('G' + opts.packRegs({ ...r, pc: opts.RETURN, fault: 0, d0: v >>> 0, a0: v >>> 0 })) !== 'OK') throw new Error('regs'); };

  // ---- paths: segments (OpenVG command bytes) and coordinates (floats, after scale and bias)
  const NCOORD = { 0: 0, 2: 2, 4: 2, 6: 1, 8: 1, 10: 4, 12: 6, 14: 2, 16: 4, 18: 5, 20: 5, 22: 5, 24: 5 };
  const readCoords = (p, ptr, n) => { const out = []; const sz = [1, 2, 4, 4][p.dt];
    const b = rd(ptr, n * sz), dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    for (let i = 0; i < n; i++) { const raw = p.dt === 0 ? dv.getInt8(i) : p.dt === 1 ? dv.getInt16(2 * i, true) : p.dt === 2 ? dv.getInt32(4 * i, true) : dv.getFloat32(4 * i, true);
      out.push(raw * p.scale + p.bias); }
    return out; };
  const append = (p, segs, coords) => { p.segs.push(...segs); p.coords.push(...coords); };
  const countCoords = (segs) => segs.reduce((n, s) => n + (NCOORD[s & 0x1e] ?? 0), 0);

  // flatten a path to polylines in user space (closed subpaths flagged), with arcs and curves subdivided
  const flatten = (p) => {
    const polys = []; let cur = null, sx = 0, sy = 0, x = 0, y = 0, cx = 0, cy = 0, k = 0; const c = p.coords;
    const start = (nx, ny) => { cur = { pts: [nx, ny], closed: false }; polys.push(cur); sx = nx; sy = ny; };
    const line = (nx, ny) => { if (!cur) start(x, y); cur.pts.push(nx, ny); };
    const cubic = (x1, y1, x2, y2, x3, y3) => { for (let i = 1; i <= 16; i++) { const t = i / 16, u = 1 - t;
      line(u * u * u * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3, u * u * u * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3); } };
    const quad = (x1, y1, x2, y2) => { for (let i = 1; i <= 12; i++) { const t = i / 12, u = 1 - t;
      line(u * u * x + 2 * u * t * x1 + t * t * x2, u * u * y + 2 * u * t * y1 + t * t * y2); } };
    const arc = (rh, rv, rot, x2, y2, large, ccw) => {   // SVG endpoint-to-centre conversion
      if (!rh || !rv) { line(x2, y2); return; }
      const phi = rot * Math.PI / 180, cs = Math.cos(phi), sn = Math.sin(phi);
      const dx = (x - x2) / 2, dy = (y - y2) / 2, x1p = cs * dx + sn * dy, y1p = -sn * dx + cs * dy;
      let rx = Math.abs(rh), ry = Math.abs(rv); const lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
      if (lam > 1) { rx *= Math.sqrt(lam); ry *= Math.sqrt(lam); }
      const num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p, den = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
      let co = Math.sqrt(Math.max(0, num / den)); if (large === ccw) co = -co;     // OpenVG: CCW = positive sweep (y up)
      const cxp = co * rx * y1p / ry, cyp = -co * ry * x1p / rx;
      const ccx = cs * cxp - sn * cyp + (x + x2) / 2, ccy = sn * cxp + cs * cyp + (y + y2) / 2;
      const ang = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
      const t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry); let dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
      if (ccw && dt < 0) dt += 2 * Math.PI; if (!ccw && dt > 0) dt -= 2 * Math.PI;
      const n = Math.max(4, Math.ceil(Math.abs(dt) / (Math.PI / 32)));
      for (let i = 1; i <= n; i++) { const t = t1 + dt * i / n; const ex = rx * Math.cos(t), ey = ry * Math.sin(t);
        line(cs * ex - sn * ey + ccx, sn * ex + cs * ey + ccy); } };
    for (const seg of p.segs) {
      const cmd = seg & 0x1e, rel = seg & 1, ox = rel ? x : 0, oy = rel ? y : 0;
      switch (cmd) {
        case 0: if (cur) { cur.closed = true; x = sx; y = sy; cur = null; } break;
        case 2: x = c[k] + ox; y = c[k + 1] + oy; k += 2; start(x, y); cx = x; cy = y; break;
        case 4: { const nx = c[k] + ox, ny = c[k + 1] + oy; k += 2; line(nx, ny); x = cx = nx; y = cy = ny; break; }
        case 6: { const nx = c[k] + ox; k += 1; line(nx, y); x = cx = nx; cy = y; break; }
        case 8: { const ny = c[k] + oy; k += 1; line(x, ny); y = cy = ny; cx = x; break; }
        case 10: { const x1 = c[k] + ox, y1 = c[k + 1] + oy, x2 = c[k + 2] + ox, y2 = c[k + 3] + oy; k += 4; quad(x1, y1, x2, y2); cx = x1; cy = y1; x = x2; y = y2; break; }
        case 12: { const x1 = c[k] + ox, y1 = c[k + 1] + oy, x2 = c[k + 2] + ox, y2 = c[k + 3] + oy, x3 = c[k + 4] + ox, y3 = c[k + 5] + oy; k += 6; cubic(x1, y1, x2, y2, x3, y3); cx = x2; cy = y2; x = x3; y = y3; break; }
        case 14: { const x1 = 2 * x - cx, y1 = 2 * y - cy, x2 = c[k] + ox, y2 = c[k + 1] + oy; k += 2; quad(x1, y1, x2, y2); cx = x1; cy = y1; x = x2; y = y2; break; }
        case 16: { const x1 = 2 * x - cx, y1 = 2 * y - cy, x2 = c[k] + ox, y2 = c[k + 1] + oy, x3 = c[k + 2] + ox, y3 = c[k + 3] + oy; k += 4; cubic(x1, y1, x2, y2, x3, y3); cx = x2; cy = y2; x = x3; y = y3; break; }
        case 18: case 20: case 22: case 24: { const rh = c[k], rv = c[k + 1], rot = c[k + 2], nx = c[k + 3] + ox, ny = c[k + 4] + oy; k += 5;
          if (!cur) start(x, y); arc(rh, rv, rot, nx, ny, cmd >= 22, cmd === 18 || cmd === 22); x = cx = nx; y = cy = ny; break; }
        default: k += NCOORD[cmd] ?? 0;
      }
    }
    return polys;
  };
  // stroke outline as quads (one per segment) and round-ish joins as small discs, in user space
  const strokePolys = (polys, w) => { const out = [], r = w / 2;
    for (const p of polys) { const q = p.pts.slice(); if (p.closed) q.push(q[0], q[1]);
      for (let i = 0; i + 3 < q.length; i += 2) { const x0 = q[i], y0 = q[i + 1], x1 = q[i + 2], y1 = q[i + 3];
        const dx = x1 - x0, dy = y1 - y0, l = Math.hypot(dx, dy); if (!l) continue; const nx = -dy / l * r, ny = dx / l * r;
        out.push({ pts: [x0 + nx, y0 + ny, x1 + nx, y1 + ny, x1 - nx, y1 - ny, x0 - nx, y0 - ny], closed: true }); }
      for (let i = 0; i + 1 < q.length; i += 2) { const disc = []; for (let a = 0; a < 12; a++) disc.push(q[i] + r * Math.cos(a * Math.PI / 6), q[i + 1] + r * Math.sin(a * Math.PI / 6)); out.push({ pts: disc, closed: true }); }
    }
    // one orientation for every piece, so non-zero filling gives their union (mixed windings cancel to holes)
    for (const o of out) { const q = o.pts, n = q.length / 2; let a = 0; for (let i = 0; i < n; i++) { const j = (i + 1) % n; a += q[2 * i] * q[2 * j + 1] - q[2 * j] * q[2 * i + 1]; }
      if (a < 0) { const rev = []; for (let i = n - 1; i >= 0; i--) rev.push(q[2 * i], q[2 * i + 1]); o.pts = rev; } }
    return out; };
  // coverage raster: polygons already in surface coordinates (y up), 4 x 4 samples, non-zero or even-odd
  const raster = (polys, nonzero, paint) => {
    const S = surface(), W = st.w, H = st.h, SS = 4; let minx = W, miny = H, maxx = 0, maxy = 0;
    const edges = [];
    for (const p of polys) { const q = p.pts, n = q.length / 2; for (let i = 0; i < n; i++) { const j = (i + 1) % n;
      const x0 = q[2 * i], y0 = q[2 * i + 1], x1 = q[2 * j], y1 = q[2 * j + 1]; if (y0 === y1) continue;
      edges.push(y0 < y1 ? [x0, y0, x1, y1, 1] : [x1, y1, x0, y0, -1]);
      minx = Math.min(minx, x0, x1); maxx = Math.max(maxx, x0, x1); miny = Math.min(miny, y0, y1); maxy = Math.max(maxy, y0, y1); } }
    if (!edges.length) return;
    const X0 = Math.max(0, Math.floor(minx)), X1 = Math.min(W - 1, Math.ceil(maxx)), Y0 = Math.max(0, Math.floor(miny)), Y1 = Math.min(H - 1, Math.ceil(maxy));
    if (X0 > X1 || Y0 > Y1) return;
    const bw = X1 - X0 + 1, cov = new Float32Array(bw);
    for (let py = Y0; py <= Y1; py++) {
      cov.fill(0);
      for (let sy = 0; sy < SS; sy++) { const yy = py + (sy + 0.5) / SS; const xs = [];
        for (const [x0, y0, x1, y1, d] of edges) if (yy >= y0 && yy < y1) xs.push([x0 + (yy - y0) * (x1 - x0) / (y1 - y0), d]);
        xs.sort((a, b) => a[0] - b[0]); let wnd = 0;
        for (let i = 0; i + 1 < xs.length + 1 && i < xs.length; i++) { wnd += xs[i][1]; const inside = nonzero ? wnd !== 0 : (i % 2) === 0;
          if (!inside || i + 1 >= xs.length) continue; const xa = xs[i][0], xb = xs[i + 1][0];
          for (let sx = 0; sx < SS; sx++) { const off = (sx + 0.5) / SS; let s = Math.ceil(xa - off), e = Math.ceil(xb - off) - 1;
            s = Math.max(s, X0); e = Math.min(e, X1); for (let px = s; px <= e; px++) cov[px - X0] += 1 / (SS * SS); } } }
      for (let i = 0; i < bw; i++) if (cov[i] > 0) blend(S, (py * W + X0 + i) * 4, paint, Math.min(1, cov[i]));
    }
  };
  const blend = (S, o, c, k) => { const a = c[3] * k; if (a <= 0) return; const ia = 1 - a;   // premultiplied surface
    S[o] = c[0] * a + S[o] * ia; S[o + 1] = c[1] * a + S[o + 1] * ia; S[o + 2] = c[2] * a + S[o + 2] * ia; S[o + 3] = a + S[o + 3] * ia; };
  const paintColor = (hnd) => { const p = st.objs.get(hnd); return p?.color ?? [0, 0, 0, 1]; };
  const toSurf = (polys, m) => polys.map((p) => { const q = []; for (let i = 0; i < p.pts.length; i += 2) q.push(...apply(m, p.pts[i], p.pts[i + 1])); return { pts: q, closed: p.closed }; });

  // images: pixels read from the caller's buffer, 4 bytes a pixel in the layer's order (A, B, G, R) until a sheet
  // dump says otherwise; rows bottom-up as OpenVG's image space
  const texel = (img, x, y) => { if (x < 0 || y < 0 || x >= img.w || y >= img.h) return null;
    // format bit 10 (0x401) = the DMP native layout, read off the sheets (notes docs/hardware/c3d-gpu.md): 8x8 tiles in
    // rows, Morton (Z) order inside a tile (x bit 0 first), first tile row = VG y 0 (the bottom); else linear rows
    const o = img.fmt & 0x400 ? img.ptr + 4 * ((((y >> 3) * (img.w >> 3)) + (x >> 3)) * 64 + MORTON[(y & 7) * 8 + (x & 7)])
      : img.ptr + (opts.imageTopDown ? img.h - 1 - y : y) * img.stride + 4 * x;
    const b = rd(o, 4);
    const a = b[0] / 255; return [b[3] / 255, b[2] / 255, b[1] / 255, a]; };
  const drawSub = (img, sx, sy, w, hh) => {
    const m = st.mats[0x1401], inv = invert(m); if (!inv) return; const S = surface();
    const corners = [[0, 0], [w, 0], [w, hh], [0, hh]].map(([x, y]) => apply(m, x, y));
    const X0 = Math.max(0, Math.floor(Math.min(...corners.map((c) => c[0])))), X1 = Math.min(st.w - 1, Math.ceil(Math.max(...corners.map((c) => c[0]))));
    const Y0 = Math.max(0, Math.floor(Math.min(...corners.map((c) => c[1])))), Y1 = Math.min(st.h - 1, Math.ceil(Math.max(...corners.map((c) => c[1]))));
    for (let py = Y0; py <= Y1; py++) for (let px = X0; px <= X1; px++) {
      const [u, v] = apply(inv, px + 0.5, py + 0.5); if (u < 0 || v < 0 || u >= w || v >= hh) continue;
      const t = texel(img, sx + Math.floor(u), sy + Math.floor(v)); if (!t || t[3] <= 0) continue;
      blend(S, (py * st.w + px) * 4, t, 1); } };

  const swap = () => {
    const S = surface(), W = st.w, H = st.h, out = new Uint8Array(W * H * 4);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const s = (y * W + x) * 4, row = opts.surfaceTopDown ? y : H - 1 - y, d = (row * W + x) * 4;
      const a = S[s + 3], k = a > 0 ? 1 / a : 0;     // straight alpha out
      out[d] = Math.round(Math.min(1, a) * 255); out[d + 1] = Math.round(Math.min(1, S[s + 2] * k) * 255);
      out[d + 2] = Math.round(Math.min(1, S[s + 1] * k) * 255); out[d + 3] = Math.round(Math.min(1, S[s] * k) * 255); }
    for (const t of (typeof st.targets === 'function' ? st.targets() : st.targets)) if (t) sim.write(t >>> 0, out);
    st.swaps++; if (opts.onSwap) opts.onSwap(out, W, H);
  };

  const H = {
    eglGetError: (r) => ret(r, 0x3000), eglGetDisplay: (r) => ret(r, 1), eglInitialize: (r) => ret(r, 1), eglBindAPI: (r) => ret(r, 1),
    eglTerminate: (r) => ret(r, 1), eglReleaseThread: (r) => ret(r, 1), eglDestroySurface: (r) => ret(r, 1), eglDestroyContext: (r) => ret(r, 1),
    eglChooseConfig: (r) => { const cfg = r.a1, num = stackArg(r, 1); if (cfg) sim.write(cfg, new Uint8Array([1, 0, 0, 0])); if (num) sim.write(num, new Uint8Array([1, 0, 0, 0])); ret(r, 1); },
    eglCreateWindowSurface: (r) => ret(r, 2), eglCreateContext: (r) => ret(r, 3), eglMakeCurrent: (r) => ret(r, 1),
    eglSwapBuffers: (r) => { swap(); ret(r, 1); },
    // the DMP memory manager: two pools (d0/d1 and a0/a1 at init), bump allocation, frees ignored
    dmpMemInit: (r) => { st.pools = [[r.d0 >>> 0, (r.d0 + r.d1) >>> 0], [r.a0 >>> 0, (r.a0 + r.a1) >>> 0]]; log(`dmp pools ${st.pools.map((p) => p.map(h))}`); ret(r, 0); },
    dmpMem2: (r) => ret(r, 0),
    dmpMem3: (r) => { const pool = st.pools?.[r.a0 ? 1 : 0]; if (!pool) { ret(r, 0); return; } const mask = r.d1 >>> 0, at = ((pool[0] + ~mask) & mask) >>> 0;
      if (at + r.d0 > pool[1]) { log(`dmp pool ${r.a0} full`); ret(r, 0); return; } pool[0] = at + r.d0; log(`dmp alloc ${h(r.d0)} -> ${h(at)}`); ret(r, at); },
    dmpMem4: (r) => ret(r, 0),
    // nativeWindow: d1 width, a1 height (256 x 256 for CC, 720 x 480 for ART)
    nativeInit: (r) => ret(r, 0), nativeDisplay: (r) => ret(r, 0x10), nativeWindow: (r) => { st.w = r.d1 >>> 0; st.h = r.a1 >>> 0; st.surf = null; log(`window ${st.w} x ${st.h}`); ret(r, 0x20); }, nativeDisplayFree: (r) => ret(r, 0), nativeWindowFree: (r) => ret(r, 0),
    vgLoadIdentity: (r) => { st.mats[st.mode] = ident(); ret(r); },
    vgTranslate: (r) => { st.mats[st.mode] = mul(st.mats[st.mode], { a: 1, b: 0, c: 0, d: 1, e: fl(r.d0), f: fl(r.d1) }); ret(r); },
    vgScale: (r) => { st.mats[st.mode] = mul(st.mats[st.mode], { a: fl(r.d0), b: 0, c: 0, d: fl(r.d1), e: 0, f: 0 }); ret(r); },
    vgRotate: (r) => { const t = fl(r.d0) * Math.PI / 180, c = Math.cos(t), s = Math.sin(t); st.mats[st.mode] = mul(st.mats[st.mode], { a: c, b: s, c: -s, d: c, e: 0, f: 0 }); ret(r); },
    vgGetMatrix: (r) => { const m = st.mats[st.mode], v = [m.a, m.b, 0, m.c, m.d, 0, m.e, m.f, 1]; const b = new Uint8Array(36), dv = new DataView(b.buffer); v.forEach((x, i) => dv.setFloat32(4 * i, x, true)); sim.write(r.a0, b); ret(r); },
    vgSeti: (r) => { st.params.set(r.d0, r.d1 | 0); if (r.d0 === 0x1100) { st.mode = r.d1; st.mats[st.mode] ??= ident(); } ret(r); },
    vgSetf: (r) => { st.params.set(r.d0, fl(r.d1)); ret(r); },
    vgSetfv: (r) => { const n = r.d1, v = []; for (let i = 0; i < n; i++) v.push(fl(u32(r.a0 + 4 * i))); st.params.set(r.d0, v); if (r.d0 === 0x1121) st.clear = v.slice(0, 4); ret(r); },
    vgSetParameteri: (r) => { const o = st.objs.get(r.d0); if (o) o[r.d1] = r.a0; ret(r); },
    vgSetParameterfv: (r) => { const o = st.objs.get(r.d0), n = r.a1, v = []; for (let i = 0; i < n; i++) v.push(fl(u32(r.a0 + 4 * i)));   // Olympus ABI: the pointer takes a0, the count a1
      if (o) { o[r.d1] = v; if (r.d1 === 0x1a01) o.color = v.slice(0, 4); } ret(r); },
    vgClear: (r) => { const S = surface(), x0 = r.d0 | 0, y0 = r.d1 | 0, w = r.a0 | 0, hh = r.a1 | 0, c = st.clear;
      for (let y = Math.max(0, y0); y < Math.min(st.h, y0 + hh); y++) for (let x = Math.max(0, x0); x < Math.min(st.w, x0 + w); x++) { const o = (y * st.w + x) * 4;
        S[o] = c[0] * c[3]; S[o + 1] = c[1] * c[3]; S[o + 2] = c[2] * c[3]; S[o + 3] = c[3]; } ret(r); },
    vgCreatePath: (r) => ret(r, handle({ kind: 'path', dt: r.d1 & 3, scale: fl(r.a0), bias: fl(r.a1), segs: [], coords: [] })),
    vgClearPath: (r) => { const p = st.objs.get(r.d0); if (p) { p.segs = []; p.coords = []; } ret(r); },
    vgDestroyPath: (r) => { st.objs.delete(r.d0); ret(r); },
    vgAppendPathData: (r) => { const p = st.objs.get(r.d0); if (p) { const segs = Array.from(rd(r.a0, r.d1)); append(p, segs, readCoords(p, r.a1, countCoords(segs))); } ret(r); },
    vgModifyPathCoords: (r) => { const p = st.objs.get(r.d0); if (p) { let first = 0; for (let i = 0; i < r.d1; i++) first += NCOORD[p.segs[i] & 0x1e] ?? 0;
      const n = countCoords(p.segs.slice(r.d1, r.d1 + r.a1)), v = readCoords(p, r.a0, n); for (let i = 0; i < n; i++) p.coords[first + i] = v[i]; } ret(r); },
    vgTransformPath: (r) => { const d = st.objs.get(r.d0), s = st.objs.get(r.d1); if (d && s) { const m = st.mats[0x1400];
      for (const poly of flatten(s)) { d.segs.push(2); d.coords.push(...apply(m, poly.pts[0], poly.pts[1])); for (let i = 2; i < poly.pts.length; i += 2) { d.segs.push(4); d.coords.push(...apply(m, poly.pts[i], poly.pts[i + 1])); } if (poly.closed) d.segs.push(0); } } ret(r); },
    // vgPointAlongPath(path d0, startSegment d1, x* a0, y* a1, numSegments, distance, tx*, ty* on the stack; the
    // Olympus ABI puts the pointers in a0/a1 first). The whole path is walked (startSegment/numSegments ignored)
    vgPointAlongPath: (r) => { const p = st.objs.get(r.d0), dist = fl(stackArg(r, 1)); let px = 0, py = 0, tx = 1, ty = 0;
      if (p) { let left = dist, done = false; for (const poly of flatten(p)) { const q = poly.pts; if (!done && q.length >= 2) { px = q[0]; py = q[1]; }
        for (let i = 2; i < q.length && !done; i += 2) { const dx = q[i] - q[i - 2], dy = q[i + 1] - q[i - 1], L = Math.hypot(dx, dy); if (!L) continue;
          tx = dx / L; ty = dy / L; if (left <= L) { px = q[i - 2] + dx * left / L; py = q[i - 1] + dy * left / L; done = true; } else { left -= L; px = q[i]; py = q[i + 1]; } } } }
      const put = (a, v) => { if (a) { const b = new Uint8Array(4); new DataView(b.buffer).setFloat32(0, v, true); sim.write(a >>> 0, b); } };
      put(r.a0, px); put(r.a1, py); put(stackArg(r, 2), tx); put(stackArg(r, 3), ty); ret(r); },
    vgDrawPath: (r) => { const p = st.objs.get(r.d0); if (p) { const polys = flatten(p), m = st.mats[0x1400];
      if (opts.verbose) log(`  path segs ${p.segs} coords ${p.coords.map((v) => +v.toFixed(1))} matrix ${JSON.stringify(m)} fill ${JSON.stringify(st.objs.get(st.fill)?.color)}`);
      if (r.d1 & 2) raster(toSurf(polys, m), st.params.get(0x1101) !== 0x1900, paintColor(st.fill));
      if (r.d1 & 1) { const w = st.params.get(0x1110) ?? 1; raster(toSurf(strokePolys(polys, w), m), true, paintColor(st.stroke)); } } ret(r); },
    // VGU (OpenVG utility) shapes, appended as OpenVG segments: path d0, x d1, y a0, width a1, the rest on the stack
    // (floats as bits; register order from PR #34's wrappers, section 11)
    vguRoundRect: (r) => { const p = st.objs.get(r.d0); if (p) { const x = fl(r.d1), y = fl(r.a0), w = fl(r.a1), hh = fl(stackArg(r, 0));
        const aw = Math.min(Math.abs(fl(stackArg(r, 1))), Math.abs(w)) / 2, ah = Math.min(Math.abs(fl(stackArg(r, 2))), Math.abs(hh)) / 2;
        if (w <= 0 || hh <= 0) { ret(r, 0xf001); return; }
        append(p, [2, 4, 18, 4, 18, 4, 18, 4, 18, 0], [x + aw, y, x + w - aw, y, aw, ah, 0, x + w, y + ah, x + w, y + hh - ah, aw, ah, 0, x + w - aw, y + hh,
          x + aw, y + hh, aw, ah, 0, x, y + hh - ah, x, y + ah, aw, ah, 0, x + aw, y]); } ret(r, 0); },
    vguEllipse: (r) => { const p = st.objs.get(r.d0); if (p) { const cx = fl(r.d1), cy = fl(r.a0), w = fl(r.a1), hh = fl(stackArg(r, 0));
        if (w <= 0 || hh <= 0) { ret(r, 0xf001); return; }
        append(p, [2, 18, 18, 0], [cx + w / 2, cy, w / 2, hh / 2, 0, cx - w / 2, cy, w / 2, hh / 2, 0, cx + w / 2, cy]); } ret(r, 0); },
    vguArc: (r) => { const p = st.objs.get(r.d0); if (p) { const x = fl(r.d1), y = fl(r.a0), w = fl(r.a1), hh = fl(stackArg(r, 0)),
        a0 = fl(stackArg(r, 1)), ext = fl(stackArg(r, 2)), type = stackArg(r, 3);
        if (w <= 0 || hh <= 0 || type < 0xf100 || type > 0xf102) { ret(r, 0xf001); return; }
        const n = Math.max(2, Math.ceil(Math.abs(ext) / 5)), segs = [2], co = [];
        for (let i = 0; i <= n; i++) { const t = (a0 + ext * i / n) * Math.PI / 180; co.push(x + w / 2 * Math.cos(t), y + hh / 2 * Math.sin(t)); if (i) segs.push(4); }
        if (type === 0xf102) { segs.push(4); co.push(x, y); } if (type !== 0xf100) segs.push(0);
        append(p, segs, co); } ret(r, 0); },
    vgCreatePaint: (r) => ret(r, handle({ kind: 'paint', color: [0, 0, 0, 1] })),
    vgDestroyPaint: (r) => { st.objs.delete(r.d0); ret(r); },
    vgSetPaint: (r) => { if (r.d1 & 2) st.fill = r.d0; if (r.d1 & 1) st.stroke = r.d0; ret(r); },
    vgDestroyImage: (r) => { st.objs.delete(r.d0); ret(r); },
    vgCreateImageDataDMP: (r) => { const w = r.d1, hh = r.a1; ret(r, handle({ kind: 'image', fmt: r.d0, w, h: hh, ptr: r.a0, stride: 4 * w })); },
    vgDrawSubImageDMP: (r) => { const img = st.objs.get(r.d0); if (img) drawSub(img, r.d1 | 0, r.a0 | 0, r.a1 | 0, stackArg(r, 0) | 0); ret(r); },
  };
  if (opts.native) {   // the real DMP library runs; only log each entry (its arguments as the call left them)
    for (const [pc, name] of Object.entries(ENTRY)) lab.observe(Number(pc) - 0x10021020, (hle, r) => { st.calls++;
      if (name === 'eglSwapBuffers') st.swaps++;
      log(`${name} mdr=${h(r.mdr)} d0=${h(r.d0)} d1=${h(r.d1)} a0=${h(r.a0)} a1=${h(r.a1)}`); }, `obs-c3d-vg ${name}`);
    return st;
  }
  for (const [pc, name] of Object.entries(ENTRY)) {
    const fn = H[name];
    lab.hook_rt(Number(pc), (hle, r) => {
      st.calls++; st.pc = Number(pc);
      if (opts.verbose) log(`${name} mdr=${h(r.mdr)} sp=${h(r.sp)} d0=${h(r.d0)} d1=${h(r.d1)} a0=${h(r.a0)} a1=${h(r.a1)}`);
      fn(r);
    }, `C3D-VG ${name}`);
  }
  return st;
}

// c3drun.mjs EMU_DIR OUT_DIR KEYS... : om-emu (E137, E-M5 III 1.7) with the c3d vector-graphics tasks running and our
// OpenVG stand-in (c3dvg.mjs) in place of the DMP GPU. Writes OUT_DIR/NN_key.png (the composed screen after each key),
// swapNNN.rgba (c3d's 256x256 surface at each eglSwapBuffers, RGBA top-down) and c3d.log.
// Env: BLOCK2 = the unpacked block2 body (block2_43f60000.bin, from tools/olyfw.py) for the sprite sheets (required);
// BACKDROP = a 720x480 raw RGB file (backdrop.py) shown under all planes in place of live view (needs patch 0003);
// VERBOSE=1 logs every OpenVG call. Keys: om-emu key names, or wait:MS. Color Creator:
//   ok right right right ok right right right right right right right info right right
// What it stands in for (each found on the way; notes: docs/hardware/graphics-pipeline.md 6a, docs/hardware/c3d-gpu.md):
//  - c3d_main (task 67) and task 70 started (om-emu leaves them dormant); c3d_main's queue taken out of S-MODACK and
//    the GUI's synchronous sends to it passed to the native kernel
//  - c3d_exe (0x60c25bde, queue 0x100f) and c3d_sub (0x60c28732, queue 0x1002) run on CPU 1 on the camera, which om-emu
//    lacks: each post to them is run here, on CPU 0, as one pass of the task's loop (lab.task_message); c3d_exe's init
//    runs once natively, and the DMP driver task it creates (entry 0x611c6090) is not created
//  - the GPU's frame-done: after a c3d_exe pass that swapped, c3d_sub gets command 3, which makes it post command 48
//    to c3d_main, which then answers the GUI's deferred request
//  - the resource reader 0x60167060 for category 0x8006 (the sheets) from BLOCK2; the GPU registers 0x9c200000 as
//    plain lab-stub memory
const [J, OUT, ...KEYS] = process.argv.slice(2);
process.env.OM_EMU_MODEL = 'E137';
const fs = await import('node:fs'); const zlib = await import('node:zlib');
const E = await import(J + '/checks/lib/env.mjs');
const { Player } = await import(J + '/src/lab/player.mjs');
const { PLAYER_PARSER } = await import(J + '/scenarios/session_replay.mjs');
const { memoryCard } = await import(J + '/src/lab/sdcard.mjs');
const { pngRaw } = await import(J + '/host/server.mjs');
const { OLYQEWR } = await import(J + '/src/lab/display.mjs');
const { where, RETURN } = await import(J + '/src/lab/hle.mjs');
const { packRegs } = await import(J + '/src/lab/sim.mjs');
const { mode_dial_names, MODE_DIAL } = await import(J + '/src/lab/play.mjs');
if (process.env.BACKDROP) (await import('./backdrop.mjs')).loadBackdrop(process.env.BACKDROP);
const { installC3dVg } = await import('./c3dvg.mjs');
fs.mkdirSync(OUT, { recursive: true });
const a = { ...PLAYER_PARSER, no_browser: true, idle: 'off', debug_api: true, out: OUT, no_wait_on_error: true, hdmi: 'off', audio: 'auto', rotate: 'off', take: 'stand-in', cpu2: 'stand-in', creative_dial: null, held: [], a15: 'auto', device: 'tft' };
let frame = null;
const env = { rom: E.loadImage(), resBlock: E.loadBlock(), nand: E.loadNand(), createHash: E.createHash, ...E.scpuEnv(), loaded: 'auto', card: memoryCard({}),
  deflate: (b, l) => new Uint8Array(zlib.deflateSync(b, { level: l })), inflate: (b) => new Uint8Array(zlib.inflateSync(b)),
  wallClock: () => Number(process.hrtime.bigint()) / 1e9, onFrame: (w, h, raw) => { frame = { w, h, raw: raw.slice() }; }, onAudio: () => {} };
const pl = new Player(a, env);
pl.open_session();
const s = pl.session, lab = s.lab;
const logf = fs.openSync(OUT + '/c3d.log', 'w');
const log = (t) => fs.writeSync(logf, t + '\n');
const st = installC3dVg(lab, { native: !!process.env.C3D_NATIVE, RETURN, packRegs, log, verbose: !!process.env.VERBOSE, targets: () => [lab.sim.u32(0xa25c2b00), lab.sim.u32(0xa25c2b04)],   // the two draw buffers c3d_main's START installs
  onSwap: (px, w, h) => { const rgba = new Uint8Array(w * h * 4); for (let i = 0; i < w * h; i++) { rgba[4*i] = px[4*i+3]; rgba[4*i+1] = px[4*i+2]; rgba[4*i+2] = px[4*i+1]; rgba[4*i+3] = px[4*i]; }
    fs.writeFileSync(`${OUT}/swap${String(st.swaps).padStart(3, "0")}_${w}x${h}.rgba`, rgba); log(`SWAP ${st.swaps}`); } });
s.idle_slice(lab.lab_time() + 1500e6);
try { log('MODE DIAL ' + JSON.stringify(mode_dial_names(lab.sim, MODE_DIAL.positions.length).map((m, k) => `${k}:${m.label}`)) + ' at ' + s.mode_index); } catch (e) { log('mode names: ' + e.message); }
const N = (v) => (v - 0x10021020) >>> 0;
for (const [pc, nm] of [[0x60c27a17, 'c3dmain_rx'], [0x602fccc9, 'bridge_in'], [0x602e4a80, 'sendhelper'], [0x602fce56, 'bridge_sent'], [0x60c25bde, 'c3dexe'], [0x60c27f37, 'h45'], [0x60c27f45, 'h45dly'], [0x60c27fe3, 'h45after'], [0x60c28289, 'reply'], [0x60c282b2, 'replied'], [0x60c2841f, 'setup']]) {
  try { let hits = 0; lab.observe(N(pc), (hle, r) => { if (++hits > (nm === 'bridge_in' ? 40 : 6)) return; if (nm === 'sendhelper') { if ((r.d0 & 0xffff) === 158) log(`SENDHELPER cmd ${r.d1} from ${where(r.mdr)}`); hits--; return; } if (nm === 'bridge_in') log(`BRIDGE d0=${r.d0} a0=${(r.a0>>>0).toString(16)} b=${[...lab.sim.read(r.a0>>>0, 8)].map(x=>x.toString(16))} from ${where(r.mdr)}`); if (nm === 'c3dmain_rx') log(`RX cmd ${lab.sim.u32(r.sp + 44)} p ${lab.sim.u32(r.sp + 48).toString(16)} w ${[0,1,2,3].map(k => lab.sim.u32(r.sp + 36 + 4*k).toString(16))} task ${lab.lt?.current?.()}`); log(`OBS ${nm} d0=${r.d0.toString(16)} d1=${r.d1.toString(16)} d3=${r.d3.toString(16)} a0=${r.a0.toString(16)}`); }, "obs-c3d " + nm); } catch (e) { log('hookfail ' + nm + ' ' + e.message); }
}
for (const t of [67, 70]) { const e = lab.nk.tasks().get(t)[0]; lab.lt.allow.add(e); const [rc] = lab.nk.svc('act_tsk', { d0: t }); log(`act ${t} rc ${rc}`); }
s.settle('c3d');
{ const q = lab.sim.read(0x60041054, 2), qid = q[0] | q[1] << 8, q2 = lab.sim.read(0x6004123c, 2), qid2 = q2[0] | q2[1] << 8;
  log(`c3d_main queue ${qid} c3d_exe queue ${qid2} in S-MODACK: ${s.camapp.module_queues.has(qid)} ${s.camapp.module_queues.has(qid2)}`);
  s.camapp.module_queues.delete(qid); s.camapp.module_queues.delete(qid2);
  lab.wrap(OLYQEWR, (prev) => (h, r) => { const q = r.d0 & 0xFFFF;
    if (st.swaps > 0 && !(q & 0xF000)) log(`QEWR q ${q} from ${where(r.mdr)}`);
    if (q & 0xF000) { const p = lab.sim.u32(r.a0 >>> 0), w = [0,1,2,3,4,5].map((k) => lab.sim.u32(p + 4 * k).toString(16)); log(`QEWR q ${q.toString(16)} from ${where(r.mdr)} desc ${w}`); }
    const cpu1 = CPU1_TASKS.get(q);
    if (cpu1) {                                              // c3d's CPU-1 tasks: run the loop body here for this one message
      const saved = { ...r }, msg = lab.sim.read(lab.sim.u32(r.a0 >>> 0), 16);
      exeRuns += 1; log(`EXE run ${exeRuns} ${cpu1[2]} cmd ${lab.sim.u32(lab.sim.u32(r.a0 >>> 0) + 8)} depth ${lab.depth}`);
      const swaps0 = st.swaps;
      try { lab.task_message(N(cpu1[0]), cpu1[1], msg, cpu1[2], 3000000);
        // the GPU's frame-done: on the camera the DMP driver posts command 3 to c3d_sub when a submitted frame ends,
        // and c3d_sub (while c3d_exe's draw flag 0x6253c479 is set) posts command 48 to c3d_main, which then answers
        // the GUI's request. No GPU here: post it once the draw that swapped has returned
        if (cpu1[2] === 'c3d_exe' && st.swaps > swaps0) {
          const word = lab.alloc(new Uint8Array(4), 4);
          log(`EXE frame done -> c3d_sub cmd 3`);
          lab.task_message(N(0x60c28732), 0x60041222, new Uint8Array(new Uint32Array([0, 0, 3, word]).buffer), 'c3d_sub frame done', 3000000);
        } }
      catch (e) { log('EXE error ' + String(e.stack || e).slice(0, 800)); throw e; }
      if (lab.sim.packet('G' + packRegs(saved)) !== 'OK') throw new Error('regs');
      h.finish(saved, { d0: 0 }); return; }
    return prev(h, r); }, 'c3d-qewr');
  const rq = (a) => { const b = lab.sim.read(a, 2); return b[0] | b[1] << 8; };
  const CPU1_TASKS = new Map([[rq(0x6004123c), [0x60c25bde, 0x6004123c, 'c3d_exe']], [rq(0x60041222), [0x60c28732, 0x60041222, 'c3d_sub']]]);
  { // the DMP GPU's registers as plain lab-stub memory (reads give the last write, else 0)
    let i = 0; for (; i < 32 && (lab.sim.u32(0x89900100 + 12 * i + 8) & 1); i++);
    lab.sim.write(0x89900100 + 12 * i, new Uint8Array(new Uint32Array([0x9c200000, 0x10000, 1]).buffer)); log(`GPU stub slot ${i}`); }
  // the DMP driver's task (entry 0x611c6090, created by c3d_exe's init): not created, the OpenVG stand-in replaces it
  lab.hook(N(0x60051d55), (h, r) => { if ((r.a1 >>> 0) === 0x611c6090) { log('DMP driver task not created'); h.finish(r, { d0: 0x7e }); return; } lab.passthrough(r); }, 'c3d dmp task');
  // the resource reader 0x60167060 for c3d's sheets (category 0x8006 = block2 group 5, entry = atlas): served from
  // the unpacked block2 (om-emu runs no resource loader on E137); returns a0 = {pointer, size}
  const B2 = fs.readFileSync(process.env.BLOCK2 ?? (() => { throw new Error('set BLOCK2 to the unpacked block2_43f60000.bin'); })()), B2_BASE = 0x43f60000;
  const b2u32 = (o) => B2.readUInt32LE(o);
  lab.hook(N(0x60167060), (h, r) => {
    if ((r.d0 & 0xFFFF) !== 0x8006) { lab.passthrough(r); return; }
    const call = lab.sim.read(r.mdr - 7, 7), size = call[6], want = lab.sim.u32(r.sp + size + 4);
    // the unpacked file is the block's body: flash address A is file offset A - base - 32 (the 32-byte OE head);
    // group 5's own OE head sits at its flash address, its 16-byte entries {flash address, size} follow
    const fo = (a) => a - B2_BASE - 32, g = fo(b2u32(16 * 5)) + 32, at = fo(b2u32(g + 16 * r.d1)), have = b2u32(g + 16 * r.d1 + 4);
    const n = Math.min(want, have), dest = r.a0 >>> 0;
    lab.sim.write(dest, new Uint8Array(B2.buffer, B2.byteOffset + at, n));
    const desc = lab.alloc(new Uint8Array(new Uint32Array([dest, n]).buffer), 4);
    log(`RES 0x8006 entry ${r.d1} -> ${dest.toString(16)} ${n} bytes (asked ${want})`);
    h.finish(r, { d0: 0, a0: desc });
  }, 'c3d res 0x8006');
  // the cache flush 0x6006f6aa (notation 0x5004e68a) c3d calls at END (0x60c27910): no caches in om-emu
  { const own = lab._k_cflush.bind(lab);
    lab._k_cflush = (h, r) => { if (r.mdr >>> 0 >= 0x60c24000 && r.mdr >>> 0 < 0x60c29000) { h.finish(r); return; } own(h, r); }; }
  // c3d_exe's own init (queue/flags) once on CPU 0, then skipped at each run's entry
  let exeRuns = 0, exeInit = false;
  lab.hook(N(0x60c25b35), (h, r) => { if (!exeInit) { exeInit = true; log('EXE init native'); lab.passthrough(r); return; } h.finish(r); }, 'c3d_exe init');
  const own = lab._sync_send.bind(lab);
  lab._sync_send = (h, r) => { const q = r.d0 & 0xFFFF; if (st.swaps > 0) log(`SYNC q ${q} cmd ${r.d1} from ${where(r.mdr)}`); if (q === qid || q === qid2) { log(`SYNC native q ${q} cmd ${r.d1}`); return lab.passthrough(r); } return own(h, r); }; }
// TG_OBJ=renderer.o: load an own renderer (an unlinked mn10300 object, e.g. tools/c3d_vg/example_tg_renderer.c) and
// point the free Tough Gear kind's draw stub 0x60c27096 at its tg_render (`mov tg_render,a1; calls (a1); ret [],4`).
// The GUI's Color Creator requests are then turned into TG ones (START kind CC -> TG; each UPDATE carries the float
// TG_ANGLE0 + 30 x n degrees), so opening Color Creator runs the renderer on the TG surface (480 x 480).
if (process.env.TG_OBJ || process.env.C3D_DUMP) {
  if (process.env.TG_OBJ) {
    const { loadObject } = await import('./elfload.mjs');
    const obj = loadObject(lab, process.env.TG_OBJ, log), entry = obj.sym(process.env.TG_ENTRY ?? '_tg_render');
    // The stock submit 0x60c2639f is a `call` entry (no prologue: its callers use `call 0x60c2639f,[],4`); reached by
    // `calls` its `ret [],4` takes the return address from the caller's (4,sp). TG_SUBMIT_FIX=1 points the object's
    // `mov 0x60c2639f,An` at a trampoline (add -4,sp; call 0x60c2639f,[],4; add 4,sp; rets) to see the rest of the frame
    if (process.env.TG_SUBMIT_FIX) { const text = obj.sections.find((x) => x.nm === '.text'), b = text.bytes;
      const tr = new Uint8Array([0xf8, 0xfe, 0xfc, 0xdd, 0, 0, 0, 0, 0x00, 0x04, 0xf8, 0xfe, 0x04, 0xf0, 0xfc]), ta = lab.alloc(tr, 4);
      new DataView(tr.buffer).setInt32(4, 0x60c2639f - (ta + 3), true); lab.sim.write(ta, tr);
      for (let i = 0; i + 4 <= b.length; i++) if (new DataView(b.buffer).getUint32(i, true) === 0x60c2639f) { new DataView(b.buffer).setUint32(i, ta, true); log(`TG submit at .text+${(i - 2).toString(16)} -> trampoline ${ta.toString(16)}`); }
      lab.sim.write(text.addr, b); }
    const stub = new Uint8Array([0xfc, 0xdd, 0, 0, 0, 0, 0xf0, 0xf1, 0xdf, 0x00, 0x04]); new DataView(stub.buffer).setUint32(2, entry, true);
    lab.sim.write(0x60c27096, stub); log(`TG stub 0x60c27096 -> ${entry.toString(16)}`);
  }
  let ups = 0; const a0deg = Number(process.env.TG_ANGLE0 ?? 0);
  lab.observe(N(0x60c27a17), (hle, r) => { const cmd = lab.sim.u32(r.sp + 44), p = lab.sim.u32(r.sp + 48);
    if (cmd !== 45 && cmd !== 46) return;
    const hx = (b) => [...b].map((x) => x.toString(16).padStart(2, '0')).join(' '), q = lab.sim.u32(p);
    log(`C3D cmd ${cmd} msg ${p.toString(16)}: ${hx(lab.sim.read(p, 32))} | *msg ${q.toString(16)}: ${hx(lab.sim.read(q, 32))}`);
    if (!process.env.TG_OBJ) return;
    // the request block (*msg): byte 0 the kind, 0-based (CP 0, CC 1 .. ART 5, TG 6; c3d_main 0x60c27f58), +4 UPDATE's data
    if (lab.sim.read(q, 1)[0] !== 1) return;
    lab.sim.write(q, new Uint8Array([6]));
    if (cmd === 45) { log('C3D START kind CC -> TG'); return; }
    const f = new Uint8Array(4); new DataView(f.buffer).setFloat32(0, a0deg + 30 * ups++, true); lab.sim.write(lab.sim.u32(q + 4), f);
    log(`C3D UPDATE CC -> TG, angle ${a0deg + 30 * (ups - 1)}`);
  }, 'obs-c3d tg');
}
// C3D_NATIVE=1: the real DMP library instead of the stand-in; each command list it posts to DMP_RD_MGR
// (0x611c5fed, count d0, request a0, payload a0+40 = {list0, halfwords0, list1, halfwords1}) goes to OUT/cmdlists.txt
if (process.env.C3D_NATIVE) {
  let nl = 0; const f = `${OUT}/cmdlists.txt`; fs.writeFileSync(f, '');
  lab.hook(N(0x611c5fed), (hle, r) => { const a = (r.a0 >>> 0) + 40, w = [0, 1, 2, 3].map((k) => lab.sim.u32(a + 4 * k));
    // 0x611c5fed(count d0, request array a0); the kind is the word at request +4 (1/8/10 VG kick, 3 PSC fill, 7 wait)
    if (r.d0 !== 1) log(`DMP request count ${r.d0}: only the first is dumped`);
    let t = `# list ${nl++} count ${r.d0} kind ${lab.sim.u32((r.a0 >>> 0) + 4)} req ${(r.a0 >>> 0).toString(16)} from ${where(r.mdr)} after vg call ${st.calls}\n`;
    const hexw = (a, n) => { let o = ''; for (let i = 0; i < n; i += 32) o += '   ' + [...Array(Math.min(8, (n - i) >> 2))].map((_, k) => lab.sim.u32(a + i + 4 * k).toString(16).padStart(8, '0')).join(' ') + '\n'; return o; };
    const refs = new Set();
    if ((r.mdr >>> 0) === 0x611a15a0) t += '  (end-of-frame request, not a list)\n';
    else for (const [addr, n] of [[w[0], 4 * w[1]], [w[2], 4 * w[3]]]) { if (!addr || !n || n > 0x40000) { t += `  ${addr.toString(16)} ${n} bytes (not dumped)\n`; continue; }
      t += `  ${addr.toString(16)} ${n} bytes\n` + hexw(addr, n);   // the sizes count 32-bit words
      for (let i = 0; i + 4 < n; i += 4) { const x = lab.sim.u32(addr + i); if (((x >>> 16) === 2 || (x >>> 16) === 4) && (x & 0xffff) === 0xf004) refs.add(lab.sim.u32(addr + i + 4)); } }
    for (const a of refs) if (a >= 0xa0000000 && a < 0xb0000000) t += `  data at ${a.toString(16)} (256 bytes, from a 0x002/0x004 word)\n` + hexw(a, 256);
    fs.appendFileSync(f, t); log(`DMP list ${nl - 1} count ${r.d0} ${w.map((x) => x.toString(16))}`);
    // no DMP_RD_MGR task here (not created): take the request as accepted, as if the GPU ran it at once
    hle.finish(r, { d0: 0 }); }, 'c3d dmp list');
}
// OBS_OSDLINE=1: log every gpiDrawOsdLine (0x60c951f0: x d0, y d1, w a1, vinfo a0; h, colour, layer on the stack)
if (process.env.OBS_OSDLINE) lab.observe(N(0x60c951f0), (hle, r) => { const ra = r.mdr >>> 0, c = lab.sim.read(ra - 7, 7);
  const size = c[0] === 0xdd ? c[6] : lab.sim.read(ra - 5, 5)[4], sa = (k) => lab.sim.u32(r.sp + size + 4 + 4 * k) | 0;
  log(`OSDLINE x ${r.d0 | 0} y ${r.d1 | 0} w ${r.a1 | 0} h ${sa(0)} colour ${sa(1)} layer ${sa(2)} from ${where(r.mdr)}`); }, 'obs-osdline');
const shot = (name) => { try { pl.publish_frame?.(); const [w, h, raw] = s.frame('boundary', true); fs.writeFileSync(`${OUT}/${name}.png`, pngRaw(w, h, raw)); return `${w}x${h}`; } catch (e) { return 'err ' + String(e).slice(0, 200); } };
let n = 0;
for (const k of KEYS) {
  try {
    if (k.startsWith('wait:')) s.idle_slice(lab.lab_time() + Number(k.slice(5)) * 1e6);
    else if (k.startsWith('mode:')) { s.switch_input('mode_dial', Number(k.slice(5))); s.camapp.pump(); s.idle_slice(lab.lab_time() + 1500e6); }
    else { s.key(k, 'down'); s.camapp.pump(); s.idle_slice(lab.lab_time() + 150e6); s.key(k, 'up'); s.camapp.pump(); s.idle_slice(lab.lab_time() + 800e6); }
  } catch (e) { log(`ERROR at ${k}: ${String(e.stack || e).slice(0, 1500)}`); console.log('ERROR', k, String(e).slice(0, 500)); break; }
  console.log(String(n).padStart(2), k, 'calls', st.calls, 'swaps', st.swaps, 'gui', lab.state_names?.get?.(lab.state()) ?? '', 'busy', '0x' + lab.sim.u32(0x61600ba0).toString(16), 'frame', shot(String(n++).padStart(2, '0') + '_' + k.replace(/[^a-z0-9]/gi, '')));
}
if (process.env.OSD_PROBE) {   // OSD_PROBE=x,y0,y1: each OSD plane's pixel index and palette word down column x
  const [px, y0, y1] = process.env.OSD_PROBE.split(',').map(Number), v = lab.sim.m.devices.vsc;
  for (let c = 0; c < v.ch.length; c++) { const m = v.ch[c].m; if (!v.ch[c].latched) continue;
    const hx = (o) => `${o.toString(16)}=${(m[o / 4] >>> 0).toString(16)}`;
    log(`IMG ch ${c}: ` + [0x30, 0x38, 0x50, 0xa4, 0xa8, 0xac, 0x194, 0x104, 0x108, 0x10c, 0x110, 0x114].map(hx).join(' '));
    for (let q = 0; q < 3; q++) { const base = m[(0x44 + 4 * q) / 4], stride = m[(0x5c + 4 * q) / 4] * 64, w1 = m[(0xc8 + 12 * q) / 4], w2 = m[(0xcc + 12 * q) / 4];
      const xs = (w1 >>> 16) - (m[0xf8 / 4] >>> 16), ys = (w2 >>> 16) - (m[0xfc / 4] >>> 16), rows = [];
      for (let y = y0; y <= y1; y += 4) { const idx = lab.sim.read(base + (y - ys) * stride + (px - xs), 1)[0]; rows.push(`${y}:${idx}`); }
      log(`OSD ch ${c} plane ${q} base ${base.toString(16)} stride ${stride} at (${xs},${ys}) ${(w1 & 0xffff)}x${m[(0xd0 + 12 * q) / 4] & 0xffff} col ${px}: ${rows.join(' ')}`); } } }
console.log('tasks', lab.nk.state(67), lab.nk.state(70), 'unknown', [...st.unknown]);
process.exit(0);

"""Small driver: turns drawing ops into an om-emu session script (E-M5 III 1.7 addresses) and runs it."""
import json, os, subprocess, sys
EMU = os.environ.get('OM_EMU', os.path.expanduser('~/emu/om-emu'))          # om-emu clone (ccfe2e0) with om-emu-shot-fresh.patch
NODE = os.environ.get('NODE_BIN', os.path.expanduser('~/emu/node-v26.13.1-linux-x64/bin'))   # node >= 26
VRAM = 0x621d9674          # 16-byte VRAM info records: entries 0-3 GUI layer A (pool 0x0c00), 4-7 layer B (0x0d00)
L2_VRAM = 0x621d9634       # layer 2 (pool 0x0b00) records sit before layer 0's, not after layer 1's
def vinfo(layer, buf): return L2_VRAM + 16 * buf if layer == 2 else VRAM + 16 * (layer * 4 + buf)
class Script:
    def __init__(self, out, model='E137'):
        self.out = os.path.expanduser(out); os.makedirs(self.out, exist_ok=True); self.toks = []; self.n = 0; self.model = model
    def call(self, fn, regs=None, stack=None, **kw):
        self.n += 1; f = f'c{self.n}.json'; d = {'fn': hex(fn)}
        if regs: d['regs'] = {k: (hex(v) if isinstance(v, int) and v > 0xffff else v) for k, v in regs.items()}
        if stack: d['stack'] = stack
        d.update(kw); json.dump(d, open(os.path.join(self.out, f), 'w')); self.toks.append('call:@' + f); return self
    def tok(self, *t): self.toks += list(t); return self
    def start(self): return self.call(0x607f6de0)          # OSDControl drawOsdStart (cw_drawOsdStart)
    def end(self): return self.call(0x607f6e55)            # drawOsdEnd: builds the command list, runs the engine
    def update(self, flip=0): return self.call(0x60c9588b, {'d0': flip})   # gpiUpdateDisplay
    def rect(self, x, y, w, h, c, layer=0, buf=0):      # gpiDrawOsdRectangle 0x60c952fb
        return self.call(0x60c952fb, {'d0': x, 'd1': y, 'a1': w, 'a0': vinfo(layer, buf)}, [h, c, layer])
    def line(self, x, y, w, h, c, layer=0, buf=0):      # gpiDrawOsdLine 0x60c951f0 (same argument order)
        return self.call(0x60c951f0, {'d0': x, 'd1': y, 'a1': w, 'a0': vinfo(layer, buf)}, [h, c, layer])
    def run(self, extra=()):
        open(os.path.join(self.out, 'script.txt'), 'w').write(' '.join(self.toks) + '\n')
        env = dict(os.environ, PATH=NODE + ':' + os.environ['PATH'], OM_SHOT_FRESH='1')
        p = subprocess.run(['node', 'emu/bin/session.mjs', '--model', self.model, '--out', self.out, '--script',
                            os.path.join(self.out, 'script.txt'), *extra], cwd=EMU, env=env, capture_output=True, text=True, timeout=900)
        recs = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
        bad = [r for r in recs if not r.get('ok', True)]
        open(os.path.join(self.out, 'run.jsonl'), 'w').write(p.stdout + p.stderr)
        return recs, bad, p.stderr[-2000:]

def dot(self, x, y, c, layer=0, buf=0):               # gpiDrawOsdDot 0x60c95123
    return self.call(0x60c95123, {'d0': x, 'd1': y, 'a1': c, 'a0': vinfo(layer, buf)}, [layer])
def blockcopy(self, sx, sy, dx, dy, w, h, layer=0, sbuf=0, dbuf=0):   # gpiDrawOsdBlockCopy 0x60c9540a
    return self.call(0x60c9540a, {'d0': sx, 'd1': sy, 'a0': vinfo(layer, sbuf), 'a1': vinfo(layer, dbuf)}, [w, h, dx, dy, layer])
Script.dot = dot; Script.blockcopy = blockcopy

# Pictures and text (E-M5 III 1.7; see the notes page hardware/osd-drawing.md sections 3b and 3c)
def bitmap(self, x, y, stream, layer=1, buf=0, remap8=None):   # gpiDrawBitmap 0x60c95576; stream = picture header + 24
    kw = {}
    if remap8 is not None: kw = dict(scratch=256, mem=[['scratch', bytes(remap8).hex()]])
    return self.call(0x60c95576, {'d0': x, 'd1': y, 'a0': vinfo(layer, buf), 'a1': stream},
                     [0, 0, 0, 'scratch' if remap8 is not None else 0, layer], **kw)
TEXT_GC = 0x621fd480        # the GUI's menu text context: draws into layer 2 buffer 0 (record 0x621d9634)
def text(self, x0, y0, x1, y1, s, colour=5, edge=0, ha=0, va=0, gc=TEXT_GC):   # DrawText 0x60c89f5b
    import struct
    style = bytearray(struct.pack('<IIIBB', colour, 0x10, 0x10, ha, va) + bytes(10)); style[22] = edge
    return self.call(0x60c89f5b, {'d0': 'scratch', 'd1': 'scratch+64', 'a0': gc, 'a1': 'scratch+32'}, None,
                     scratch=64 + 2 * len(s) + 2, frame=[0xf0, 252],
                     mem=[['scratch', style.hex()], ['scratch+32', struct.pack('<4h', x0, y0, x1, y1).hex()],
                          ['scratch+64', (s + '\0').encode('utf-16-le').hex()]])
Script.bitmap = bitmap; Script.text = text
def touch(self, kind, x, y):   # sendEvent 0x60d539e0 with the GUI's touch message (index 107 = 0x9100 on E137)
    import struct              # kind: 1 TOUCH, 2 LONG TOUCH, 3 RELEASE, 4 TAP, 5 DOUBLE TAP, 6 SLIDE, 7 FLICK
    return self.call(0x60d539e0, {'a0': 0, 'a1': 'scratch'}, None, scratch=32, frame=[0, 0],
                     mem=[['scratch', struct.pack('<8I', 107, 0, kind, x, y, 0, 0, 0).hex()]])
Script.touch = touch

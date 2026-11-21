// elfload.mjs: load an unlinked mn10300 ELF object (.o) into emulator memory, without a linker.
// Places every allocatable section (text, data, rodata, bss) with lab.alloc, applies R_MN10300_32 (type 1) relocations
// (S + A, absolute) and the PC-relative branch relocations PCREL32/16/8 (types 4-6, S + A - P), and returns { sym(name) -> address, sections }. Other relocation types are refused, so code must
// reach firmware by absolute address (`mov imm,An; calls (An)`), as c3d_vg.h's wrappers do.
import fs from 'node:fs';

export function loadObject(lab, path, log = () => {}) {
  const d = fs.readFileSync(path), u16 = (o) => d.readUInt16LE(o), u32 = (o) => d.readUInt32LE(o);
  if (u32(0) !== 0x464c457f || d[4] !== 1 || u16(18) !== 89) throw new Error(`${path}: not a 32-bit mn10300 ELF object`);
  const shoff = u32(0x20), n = u16(0x30), strx = u16(0x32);
  const sh = [...Array(n)].map((_, i) => { const o = shoff + 40 * i; return { name: u32(o), type: u32(o + 4), flags: u32(o + 8), off: u32(o + 16), size: u32(o + 20), link: u32(o + 24), info: u32(o + 28), align: u32(o + 32) }; });
  const str = (sec, o) => { const a = sh[sec].off + o; return d.toString('latin1', a, d.indexOf(0, a)); };
  for (const s of sh) s.nm = str(strx, s.name);
  for (const s of sh) if ((s.flags & 2) && s.size) {               // SHF_ALLOC
    const bytes = s.type === 8 ? new Uint8Array(s.size) : new Uint8Array(d.buffer, d.byteOffset + s.off, s.size).slice();
    s.addr = lab.alloc(bytes, Math.max(4, s.align)); s.bytes = bytes; log(`elf ${s.nm} ${s.size} B at ${s.addr.toString(16)}`); }
  const symtab = sh.find((s) => s.type === 2);
  const syms = [...Array(symtab.size / 16)].map((_, i) => { const o = symtab.off + 16 * i;
    return { name: str(symtab.link, u32(o)), value: u32(o + 4), shndx: u16(o + 14) }; });
  const symAddr = (s) => (s.shndx && s.shndx < 0xff00 ? (sh[s.shndx].addr ?? 0) : 0) + s.value;
  for (const r of sh.filter((s) => s.type === 4)) {                 // SHT_RELA
    const tgt = sh[r.info]; if (tgt.addr === undefined) continue;
    for (let o = r.off; o < r.off + r.size; o += 12) {
      const off = u32(o), info = u32(o + 4), add = d.readInt32LE(o + 8), type = info & 0xff, sym = syms[info >>> 8];
      if (type === 34) continue;                                      // R_MN10300_ALIGN: a relaxation marker, nothing to patch
      const dv = new DataView(tgt.bytes.buffer);
      if (type >= 4 && type <= 6) {                                   // R_MN10300_PCREL32/16/8: S + A - P (branches gas keeps for relaxation)
        const v = symAddr(sym) + add - (tgt.addr + off), bits = [32, 16, 8][type - 4];
        if (bits < 32 && (v < -(2 ** (bits - 1)) || v >= 2 ** (bits - 1))) throw new Error(`${path}: PC-relative ${bits}-bit reloc out of range at ${tgt.nm}+${off.toString(16)}`);
        if (bits === 32) dv.setInt32(off, v, true); else if (bits === 16) dv.setInt16(off, v, true); else dv.setInt8(off, v);
        continue; }
      if (type !== 1) throw new Error(`${path}: relocation type ${type} at ${tgt.nm}+${off.toString(16)} not supported`);
      const v = (symAddr(sym) + add) >>> 0; dv.setUint32(off, v, true);
      log(`elf reloc ${tgt.nm}+${off.toString(16)} = ${sym.name || sh[sym.shndx]?.nm}+${add} = ${v.toString(16)}`); }
    lab.sim.write(tgt.addr, tgt.bytes); }
  const table = new Map(syms.filter((s) => s.name).map((s) => [s.name, symAddr(s)]));
  return { sym: (name) => { const a = table.get(name); if (a === undefined) throw new Error(`${path}: no symbol ${name}`); return a; }, sections: sh };
}

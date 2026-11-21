import fs from 'node:fs';
const fd = 1;
globalThis.__vsclog = (c, off, v) => fs.writeSync(fd, `VSC ch${c} +0x${off.toString(16)} = 0x${(v>>>0).toString(16)}\n`);

# Memory and storage controllers: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Memory and storage controllers](memory-and-storage.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the E-M5 III's DRAM controller and its physical interface (PHY), and the NAND flash controller and its
driver. The driver part covers error correction (ECC), bad-block remapping, the read, write and erase paths and the
write guard. The page also covers how the flash stores sit on top of the driver.

This is desk research. There were no camera runs and no flash writes.[^fw1] One existing flash backup file (`FLF.BIN`,
made on our camera) was read for the bad-block table.[^cam1]

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. Function addresses are in the
[address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Summary

- **Flash.** 128 MB raw NAND, 1024 blocks of 128 KB, 64 pages of 2 KB, 128 spare bytes per page. The controller at
  `0x98d01000` does ECC in 1 KB sectors and moves data by DMA.[^fw1]
- **Flash addresses are names, not memory.** `0x40000000` to `0x47ffffff` (and `0x80000000` to `0x87ffffff`) are only
  passed to the driver. The CPU never reads them, and the access monitor guards that range after start-up.[^fw1]
- **Bad blocks** are remapped by a 1024-entry table. Blocks 992 to 1013 are the spare pool. The table is kept three
  times, in blocks 1014 to 1016. A block is moved to a spare when a read needs more than 13 corrected bits or a program
  or erase times out.[^fw1]
- **The write guard does not protect the spare pool or the table.** Its last window runs to `0x48000000`.[^fw1]
- **DRAM.** 1 GB, two 16-bit channels (a 32-bit bus with four byte lanes), burst of 8. The controller "EMC" sits at
  `0x98b00000` and the PHY "DFI" at `0x99e00000`. The memory PLL has 16 fixed settings from 840 to 1536 MHz. The
  controller clock is a quarter of it.[^fw1] The DRAM type is DDR3-class, not LPDDR4.[^inf1]
- **DRAM setup and training live in the boot area**, not in block0. Block0 only re-runs PHY calibration after
  standby.[^fw1]
- **The OM-5 II 1.1 program has the same NAND driver, bad-block table and spare pool.** Its write guard allows
  `0x46c40000` to `0x50000000`.[^fw1]

## Address views

| view | range | what | notes |
|---|---|---|---|
| flash name | `0x40000000`–`0x47ffffff`, alias `0x80000000`–`0x87ffffff` | logical flash offset + `0x40000000`, passed to the driver | the driver strips `0x40000000` or `0x80000000` and checks page alignment[^fw1] |
| DRAM cached | `0x60000000`–`0x9fffffff` | 1 GB | [memory map](memory-map.md)[^cam2] |
| DRAM uncached | `0xa0000000`–`0xdfffffff` | same bytes | [^fw1] |
| DRAM bus | `0x20000000` + offset | what the NAND DMA is given | an address at or above `0x80000000` has bit 31 cleared, so `0xa0000000` becomes `0x20000000`[^fw1] |
| on-chip RAM | `0x47000000`–`0x47001fff` (8 KB per core) | boot stack, copied 6 KB library, standby code | the access-monitor guard starts at `0x47002000`[^fw1] |

*The address views of flash and DRAM.*

The permanent access-monitor table guards `0x28b81000` to `0x46ffffff` and `0x47002000` to `0x5fffffff`. Addresses
are folded from `0x80xxxxxx` to `0x40xxxxxx` first. So a direct load from a flash name trips the monitor. Read flash
only through the driver's read function.[^fw1]

See also: [Caches and the access monitor](caches-technical.md).

## NAND controller

Registers as the driver uses them. The names are ours. The accesses are read in the firmware.[^fw1] The meanings are
inferred.[^inf1]

| register | written / read | meaning |
|---|---|---|
| `0x98d01018` | 1 at init | enable |
| `0x98d01038` | 1 | |
| `0x98d0103c` | 1 at init, then wait for `0x98d01104` bit 13 | controller reset |
| `0x98d0104c`, `1054`, `106c`, `107c`, `1080`, `1084`, `1088`, `108c`, `1094` | 6, 64, 16, 4, 4, 5, 3, 2, 1 | `0x1054` = 64 pages per block. The small values look like NAND timing counts. |
| `0x98d01058` | 0 | |
| `0x98d0105c` / `0x98d01060` | 2048 / 128 | page size / spare bytes per page (also used as column / length for spare access) |
| `0x98d01064` | 0 or 1 from a board-revision byte (`0x8ff0019c` >= 1 gives 1) | The OM-5 II program always writes 1. |
| `0x98d010a8` | `0x001b0010` | timing |
| `0x98d01104` | wait mask, write 1 to clear | interrupt status. Read `0x9004`, program `0x9004`, erase `0x1100`, spare program `0x9080`, reset done `0x2000`. |
| `0x98d01108` | 0 | interrupt enable (polling only) |
| `0x98d01194` | read, low 4 bits | corrected-bit count of the last read |
| `0x98d011ac` / `0x98d011b0` / `0x98d011b4` | 1024 / 1024 / 2 | ECC sector size, two sectors per page |
| `0x98d011c0` | 1 before a DMA op, 0 after | DMA enable |
| `0x98d01800` | `0x08000000` + page for DMA ops. `0x0c000000` / `0x0c000002` for direct command / data. `0x04000000` + page for spare access. | target / mode |
| `0x98d01804` | op word, DRAM bus address, 0 | command queue, or the data port in direct mode |

*NAND controller registers as the driver uses them.*

**Op words** go to `0x98d01804`.

- `0x01402001` reads one page.
- `0x01402040` reads 64 pages (one block).
- `0x01402101` programs one page.
- `0x00000001` erases the block.

Bit 8 means program, and the low byte is the page count. The values are read in the firmware.[^fw1] The bit meanings
are inferred.[^inf1]

**Direct mode** reads the chip status. The driver writes `0x0c000000`, the command `0x70` (the standard NAND READ
STATUS) and `0x0c000002`, then reads one byte.[^fw1]

**Around every DMA op** the driver sets bit 25 of `0x9880014c` and clears it after.[^fw1] That bit is a clock or bus
enable.[^inf1] Its clock gate is CLKNAND, block 8 of the `per clk` list.[^fw1]

**Init.** The spare-area writer calls the init function again after it is done.[^fw1] The first init is in the boot
area, because block0 never calls it at start-up.[^inf1]

## NAND driver

The whole driver sits in the head of block0 (`0x60021000` to `0x60022800`), which the boot area copies first. So the
section loader can use it.[^fw1]

The driver has three public entries, for read, write and erase.

- **Read** takes a flash name, a RAM address and a length. Any alignment works. Partial pages go through a bounce
  buffer, and aligned runs over 256 KB use block ops.
- **Write** takes a flash name, a RAM address and a length. It pads partial pages with `0xff`. There is no
  read-modify-write.
- **Erase** takes a flash name and a length.

Every store save uses an erase-then-write helper. Two more helpers write the other bank of store 63 or store 50, then
read it back to RAM. The full function list is in the [address reference](#address-reference).[^fw1]

Every public entry takes a lock, but only once the OS runs. Each call is logged in a 100-entry ring of 20-byte records
(type string, addresses, length, time). `flash trace` sets a flag so each call is printed.[^fw1]

### Read path and ECC

1. Remap the page, then start a DMA read into uncached, 16-byte aligned RAM. Otherwise the driver prints "RAM CACHE
   Address error" or "RAM 16Byte Align error".[^fw1]
2. Wait for `0x9004`. A status other than 0 or 1 logs error `0x310f` and prints the address.[^fw1]
3. Read the corrected-bit count (`0x98d01194 & 15`). If it is **over 13**, the block is copied to a spare. The data
   just read is still returned.[^fw1]
4. Poll READ STATUS for ready. A time-out prints "Read Disturb Hassei" and retries the page.[^fw1]

So ECC corrects at least 14 bits per 1 KB sector.[^inf1] The exact strength is not in block0.

The spare-area writer gives the best estimate. It puts its mark at column 2104 = 2048 + 56, after 2 marker bytes at
column 2048. 56 bytes per page is 28 bytes per 1 KB sector. That is exactly the parity of a 16-bit BCH code over
GF(2^14), 16 × 14 = 224 bits. So the most likely strength is **16 bits per 1 KB**, with the move at 14 or more.[^inf2]

### Write and erase path

1. **Guard.** One guard function checks raw writes and another checks store writes (see [Write guard](#write-guard)).
2. **Write protect.** A device-control call with id 58 is made with 1 before and 0 after.[^fw1] Id 58 has type nibble
   0, which dispatches to the GPIO pin-write routine. That routine maps the id to a pin through the board table at
   `0x61a02680`, then finds the pin register in the table at `0x600242c8`. So the driver raises GPIO 58 for the length
   of every write or erase and drops it after.[^fw1] That is the usual NAND write-protect line (WP#, low =
   protected).[^inf1] Which pad it is was not traced.
3. **Program or erase.** Program each page (op `0x01402101`) or erase each block (op 1). Wait for the interrupt bits,
   then READ STATUS with mask `0xe1`. Reads use `0xe0`.[^fw1]
4. **Errors.** A wait time-out prints "write error" and stops (error `0x3110`). A READ STATUS time-out prints "Bad
   Block Hassei WRITE/ERASE", moves the block to a spare and redoes it.[^fw1]

**As read, the status check cannot see a reported failure.** The poll ends as soon as any bit of the mask is set, and
a finished operation always sets the ready bits. So a page the chip reports as failed (bit 0) passes. Only a chip that
never reports ready triggers the remap. This is as read in the firmware, not seen on a camera.[^fw1] Firmware updates
read every component back and compare, which catches it there. Store saves rely on the store checksum at the next
load.

**The flashdev layer** is used by the property stores and `res.c`. It also sets the watchdog field around each write or
erase, to 0 before and to 10 after. That writes the low 6 bits of the always-on register `0x98e0008c` and commits
with `0x20041001` at `0x98e000a4`.[^fw1] So the watchdog is held off while flash is busy.[^inf1]

See also: [Power and watchdog block](power-block-technical.md).

### Bad-block table

| item | value | evidence |
|---|---|---|
| RAM copy | `0xa001ef80`, 1024 × 8 bytes (boot-area RAM, below block0) | [^fw1] |
| entry | `{u32 physical block, u32 state}` | [^fw1] |
| normal block | `{n, n}` | [^cam1] |
| free spare | `{n, 0xffffffff}` | [^cam1] |
| spare in use | `{n, n}` | the move function copies +0 into +4[^fw1] |
| remapped block | `{spare, 0xffffffff}` | [^cam1] |
| spare pool | blocks 992–1013 (flash `0x47c00000`–`0x47ebffff`, 22 blocks, 2.75 MB) | [^fw1] |
| flash copies | `0x47ec0000`, `0x47ee0000`, `0x47f00000` (blocks 1014–1016), 8 KB each, all three rewritten after each move | [^fw1] |
| unused | blocks 1017–1023 (`0x47f20000`–`0x47ffffff`), erased on our camera | [^cam1] |

*Layout of the bad-block table and the spare pool.*

**Moving a block** takes these steps.[^fw1]

1. Take the first free spare.
2. Read the failing block raw into `0xa299e000`.
3. Erase the spare and program it.
4. Write a 36-byte mark (three 12-byte copies of `0xf0` bytes) at spare-area column 2104 of the failing block.
5. Erase blocks 1014 to 1016 and program the table three times.

It prints "BBM Tbable FULL" when no spare is left.[^fw1]

Nothing in block0 reads the table from flash. The boot area does, before block0 starts.[^inf1]

### Write guard

The two guard functions read a mode that a setter stores.[^fw1]

- **Mode 0** means no write is expected. It resets the camera at once by setting the watchdog field to `0x81`,
  committing and spinning.
- **Mode `0x1xx`** is the updater's. Every address is allowed. `flash running` uses `0x400`.
- **Any other mode** allows the write only inside one window. Otherwise it prints "[FLSH]Flash Access Guard Error!!!"
  and resets the camera.

| window (E-M5 III) | holds |
|---|---|
| `0x40060000`–`0x40780000` | maintenance and settings stores ([maintenance](../firmware/maintenance-technical.md)) |
| `0x41f60000`–`0x42160000` | gap after block0 |
| `0x47a80000`–`0x47b80000` | `res.c` store, 1 MB |
| `0x47b80000`–`0x48000000` | **includes the spare pool and the table copies** |

*Write-guard windows on the E-M5 III 1.7.[^fw1]*

Each window is checked under both names, `0x4…` and `0x8…`.[^fw1]

| window (OM-5 II 1.1) |
|---|
| `0x40060000`–`0x40780000` |
| `0x41f40000`–`0x42140000` |
| `0x46620000`–`0x46c40000` |
| `0x46c40000`–`0x50000000` |

*Write-guard windows in the OM-5 II 1.1 program.[^fw1]*

The OM-5 II program's numbered store slots at `0x46e60000` + n × `0x80000` (n < 27) end below `0x47c00000`. So the
OM-5 II program does not write into the spare pool.[^fw3]

### Flash stores on top

| store | flash | how it is written | notes |
|---|---|---|---|
| 17 adjust | `0x40060000` | RAM cache `0xa276e000`, erase and write | flashmem table `0x60078b04`[^fw1] |
| fd1 / fd2 | `0x40080000` / `0x400e0000` | erase and write, every adjust save | [maintenance](../firmware/maintenance-technical.md) |
| 50 user settings | `0x40240000` / `0x40280000` | two banks, alternate on each save, RAM cache `0xa294e000` | type 2[^fw1] |
| 63 counters | `0x402c0000` / `0x402e0000` | two banks, alternate, RAM cache `0xa298e000` | type 1[^fw1] |
| settings bulk | `0x406a0000`, `0x40700000`, `0x40740000` | erase and write | [memory map](memory-map.md) |
| `res.c` | `0x47a80000` | erase (flashdev `0x200`) and write | [^fw1] |

*Flash stores and how each is written.*

The flashmem layer accepts a RAM-cache address in place of a flash name. It swaps it through the 3-entry table at
`0x60078b04`, and prints "can't exchange sdram --> flashrom address" when that fails. Write mode 1, used by the
updater, writes, then reads back and compares.[^fw1]

### Debug commands

The `flash` shell command has the subcommands `addr`, `log`, `trace`, `speed`, `showbbm`, `erase`, `write` and
`running`. `running` is the PureNAND stress test. It erases and rewrites every block from `0x40060000` to `0x47b80000`
with `0x5a`/`0xa5` patterns, forever, in guard mode `0x400`. It destroys the factory calibration and all stores.[^fw1]

> [!WARNING]
> Never run any `flash` subcommand. `flash running` wipes the factory calibration and every settings store.

See also: [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md).

## DRAM controller (EMC)

The controller sits at `0x98b00000`.[^fw1]

| register | use |
|---|---|
| `0x98b00004` / `08` / `0c` | DRAM command. Data in +4, write 2 to +8, wait for bit 1 of +`0xc`. |
| `0x98b00014` / `18` | 1 = enter self-refresh, wait until +`0x18` reads 1. 0 = leave. |
| `0x98b00118` | saved to on-chip RAM `0x47001900` before standby, restored after |
| `0x98b00850` | 1 during standby |
| `0x98b00810` / `14` / `18` | arbiter setup, written with 73 agent entries copied to `0x98b01000` |
| `0x98b01000` | 73 × 8-byte per-agent arbiter table, from `0x60074560` (and mode sets at `0x60073d58`) |
| `0x98b00c00`–`0x98b00cff` | four bus-monitor slots (agent select, access count, max latency, total latency, underflow, traffic), table `0x60075ba4` |
| `0x98b00d00` / `0x98b00d40` | start bits of the channel 0 / channel 1 counters |
| `0x98b00d04`–`0x98b00d24`, `0x98b00d44`–`0x98b00d64` | per channel: reads, writes, refreshes, total loss, bank loss, read-to-write and write-to-read turnaround losses, same-bank turnarounds. Strings "Bus Measure Infomation CH0/CH1". |

*DRAM controller registers.[^fw1] The functions that use them are in the [address reference](#address-reference).*

**Two channels, 16 bits each.** The measurement help says "SDRAM Access (R/W's 1Count = 16bit x 8Burst = 16 byte)",
and every counter exists twice.[^fw1] With four PHY byte lanes that is a 32-bit bus.[^inf1]

**Bus agents.** The name list has 78 names of 10 bytes each.[^fw1] Each is a block that reads or writes DRAM itself.

SYSTEM0-4, FSC, SSG1/2, CWD11-17, CWD21, VSC1-4, CP, CODER0/1, CODEW, CACH0-3, ARM0/1, FMI0/1, USB, SD0/1, EMS1/2,
PFC, CCA2YC2, CCA1YC1, HDRR/W, CCI, TS, FLC, TCPL, MOB, RW2, JRA, RW3, ISP0/1, FNR1/2, R1, R4, NR1/2, ICM1/2, W11,
W12, MCR, MCW, SEQ12, OSDGEN, CIC, JPMC, JPMY, BACDR/W, FD, PD, SRR, SRW, GPU1-3.

CACH0-3 are most likely the cores' cache ports, and ARM0/1 the Cortex-A9 side.[^inf1] The list is also a census of
the chip's bus masters. There is no shared DMA controller.

See also: [Interrupts, timers and DMA](interrupts-timers-dma-technical.md).

## DRAM PHY (DFI)

The PHY sits at `0x99e00000`. In block0 only the standby exit touches it, and that code runs from on-chip RAM.[^fw1]

**Standby exit** takes these steps.

1. Turn the memory PLL back on (`0x98800268` bits 0 and 4, `0x9880026c` bit 0), wait, and ungate the clocks
   (`0x98800154 = 0x1fff`).
2. Set `0x99e0000c` bit 26 and clear 20 lane registers: `0x99e0029c`–`0x99e002ac`, `0x99e0031c`–`032c`,
   `0x99e0039c`–`03ac` and `0x99e0041c`–`042c`. That is five per lane with a lane stride of `0x80`, so **four byte
   lanes**. Clear bit 26.
3. Write `0x99e00004 = 0x30`, then `0x31`, and wait for `0x99e00018` bit 1. This is the PHY init.[^inf1]
4. Leave self-refresh (`0x98b00014 = 0`) and send DRAM command 2 through `0x98b00004`.
5. Write `0x99e00004 = 0xf400`, then `0xf401`. Wait for bit 1, then check bits 20-29 of `0x99e00018`. Those are the
   training errors.[^inf1]
6. Restore `0x98b00118` and clear `0x98b00850`.

Another path sets bits in `0x99e0000c`, `0x99e00068`, `0x99e00080` and `0x99e00084`.[^fw1]

**Standby entry** runs when the power manager's "pwr standby enter" asks.[^fw1]

1. Touch DRAM.
2. Set `0x98b00850` and save `0x98b00118`.
3. Request self-refresh and wait.
4. Gate the clocks (`0x988001d0 = 0x1fff`).
5. Power the PLLs down.

The state is kept at `0x8ff000b8`. The code sits in the 6 KB library that each core copies to on-chip RAM (from
`0xa1483000` to `0x47000800`). DRAM is not usable while it self-refreshes, which is why the code runs from there.[^fw1]

## Clocks

`per clk blkclk` reads each block clock through one shared reader.[^fw1]

- **Memory PLL.** `0x9880026c` bits 12-15 select one of 16 fixed rates: 0 = 1536 MHz, then 1488, 1464, 1416, 1368,
  1272, 1224, 1200, 1176, 1128, 1104, 1080, 1032, 936, 888 and 840 MHz.[^fw1]
- **CLKDFI** is that rate. **CLKSYS** and **CLKEMC** are a quarter of it.[^fw1]
- **Other PLLs** (A to F at `0x98800250` to `0x98800264`) are read the same way, in 2.4 MHz steps.[^fw1]

## DRAM type

Block0 names no DRAM type. What it shows is a burst of 8, 16-bit channels, refresh counters, bank-loss counters,
self-refresh and a PHY with per-lane training.[^fw1]

**The boot area settles it as DDR3.** Stage 1 writes four mode-register values twice, to the controller
(`0x98b00040`–`4c`) and to the PHY (`0x99e0009c`–`a8`). They decode cleanly in the DDR3 mode-register layout, and not
in LPDDR3's. The values are read in the firmware.[^fw2] The decode is ours.[^inf1]

| register | value | DDR3 meaning |
|---|---|---|
| MR0 | `0x1c70` | burst 8, CAS latency 11, write recovery 12, fast power-down exit |
| MR1 | `0x0010` | additive latency CL-2, 40 ohm drive, no nominal termination |
| MR2 | `0x0418` | CAS write latency 8, dynamic write termination RZQ/2 |
| MR3 | 0 | normal |

*DDR3 mode registers written by boot-area stage 1.*

CL 11 with CWL 8 is the DDR3-1600 speed grade, run at 1536 MT/s. Two 16-bit channels with 1 GB in total fits two
4-Gbit x16 dies. Whether they are 1.35 V DDR3L is not visible in the code.[^inf1] It is not LPDDR4, which uses burst 16
as on the OM-1.

See also: [SoC overview](soc-overview-technical.md#memory).

## Serial NOR

CLKSNOR is in the clock list, but block0 has no serial NOR driver and no string for one. The "EEROM" store of
`prmdbg` is a property device, not a chip found here.[^fw1]

## OM-5 II 1.1

- NAND init is identical except that `0x98d01064` is always 1. The op words, ECC settings, bad-block table address,
  spare pool and table copies are the same.[^fw1]
- The guard windows differ, as in the [Write guard](#write-guard) tables.[^fw1]
- Standby entry and exit, the memory PLL table and the bus counters are byte-identical, at moved addresses.[^fw1]

## Open questions

- The exact ECC strength. 16 bits per 1 KB is the best fit from the spare layout, not confirmed.[^inf2]
- GPIO 58 as write protect. The GPIO path is read in the firmware, the WP# role is inferred.[^inf1]
- The NAND part number. A board photo would settle it.
- An optional read-only check. `per clk pllinfo` and `per clk blkclk` over the Wi-Fi shell print the live clocks.
  Other `per clk` subcommands change clocks (`chgdispclk`, `chgimggclk`, `pllboff`). Not run.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| flash name check (strips `0x40000000` or `0x80000000`, checks page alignment) | `0x60021f99` |
| DRAM bus address (clears bit 31 of an address at or above `0x80000000`) | `0x60021f6c` |
| permanent access-monitor table | `0x600c07f0` |
| NAND init | `0x6002209e` |
| logical page to physical page through the bad-block table (follows chains, "Check BBM Table NG" past 1024) | `0x600217a9` |
| read pages (one DMA op per page), remap, ECC check | `0x600218c1` |
| read pages without remapping (used to copy a failing block) | `0x600219f8` |
| read whole blocks (64-page op), remap, ECC check | `0x60021ada` |
| program pages, remap, status check | `0x60021c18` |
| write a 36-byte record into the spare area of a page (bad-block mark) | `0x60021d49` |
| erase blocks, remap, status check | `0x60021e55` |
| READ STATUS poll, up to 16,383 tries ("status0 BIT OFF" on time-out) | `0x60021ede` |
| wait for interrupt-status bits, 65,535 tries | `0x60021f26` |
| move a block to a spare and rewrite the table | `0x600216b0` |
| print the table (`flash showbbm`) | `0x600217ea` |
| **read**(a0 = flash name, a1 = RAM, d0 = length) | `0x60022180` |
| read bounce buffer for partial pages | `0xa25cf3b0` |
| **write**(a0 = flash, a1 = RAM, d0 = length) | `0x6002246d` |
| **erase**(a0 = flash, d0 = length) | `0x600225dd` |
| erase then write (every store save) | `0x60022353` |
| write the other bank of store 63 / store 50, then read it back | `0x600223a1` / `0x6002242f` |
| driver lock, take / give | `0x60022691` / `0x600226ba` |
| lock semaphore id | `0x60040cdc` |
| call log ring (100 × 20 bytes) | `0xa2624f3c` |
| `flash trace` flag | `0x61a02388` |

*NAND controller and driver functions.*

| item | address |
|---|---|
| raw write guard / store write guard | `0x600c481e` / `0x600c463a` |
| guard mode, setter | `0x600c4631`, `0x600c4628` |
| device-control call (id 58, write protect) | `0x6006791e` |
| GPIO pin-write routine | `0x6006821a` |
| GPIO board table / pin register table | `0x61a02680` / `0x600242c8` |
| flashdev layer | `0x6005a177` |
| watchdog field set (0 before, 10 after a write) | `0x600226e1` |
| move-block buffer | `0xa299e000` |
| bad-block table RAM copy | `0xa001ef80` |
| `res.c` store load / save | `0x60166a64` / `0x601678b0` |
| store 50 / 63 handler (type 2 / type 1) | `0x60059b32` |
| flashmem read / write / erase | `0x600c4922` / `0x600c49d3` / `0x600c497e` |
| flashmem RAM-cache table (3 entries) | `0x60078b04` |
| updater, write mode 1 | `0x60c3b6eb` |
| `flash` command | `0x6005a245` |
| PureNAND stress test (`flash running`) | `0x60059a44` |
| OM-5 II numbered store slots | `0x6005b914` (OM-5 II) |

*Write path, guard and flash stores.*

| item | address |
|---|---|
| DRAM command | `0x6148351a` |
| self-refresh enter / leave | `0x614834af` / `0x6148354a` |
| arbiter setup | `0x60051f88` |
| per-agent arbiter table source / mode sets | `0x60074560` / `0x60073d58` |
| bus-monitor slot table | `0x60075ba4` |
| bus measurement | `0x600524bd` |
| bus agent name list (78 × 10 bytes) | `0x60075678` |
| standby exit (runs from on-chip RAM) | `0x6148354a` |
| other PHY path | `0x614836ab` |
| standby entry, called from | `0x614834af`, from `0x614830ae` |
| standby entry as run from on-chip RAM | `0x47000caf` |
| 6 KB library, staged and copied | `0xa1483000` to `0x47000800` |
| standby state | `0x8ff000b8` |
| block clock reader (`per clk blkclk`) | `0x6007270b` |
| memory PLL rate table | `0x60071d0c` |
| OM-5 II standby entry and exit, PLL table, bus counters | `0x616a34d3`, `0x60075d96`, `0x60052699` (OM-5 II) |

*DRAM controller, PHY and clocks.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. E-M5 III 1.7 block0, compared with the OM-5 II 1.1 program.
[^fw2]: Read in the boot area of a flash backup made on our E-M5 III, 2026-11-25.
[^fw3]: Read in the OM-5 II 1.1 program, 2026-11-25, from a scan of immediate values, not a full trace.
[^inf1]: Inferred, 2026-11-25.
[^inf2]: Inferred from the spare-area writer's layout, 2026-11-25.
[^cam1]: Read from a flash backup made on our E-M5 III, 2026-11-25.
[^cam2]: Seen on our E-M5 III. See [memory map](memory-map.md).


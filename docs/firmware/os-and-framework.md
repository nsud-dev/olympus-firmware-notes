# OS and software framework (MN103 side)

## RTOS: μITRON
- The MN103 runs **μITRON**, the Japanese embedded RTOS standard: standard calls (`cre_tsk`, `acre_tsk`,
  `twai_sem`), a "uITRON Error Code" table, an `itronos.cpp` layer. [code] (2026-11-05)
- Olympus wraps it in its own API (`OlySemaphoreWait`, `OlyQueueWrite`, ...), which most code calls. [code]
- The ARM also has a small μITRON image ("load arm itron") besides Linux. [code]

## Rhapsody OXF
- On top sits **IBM Rhapsody's OXF** framework (`rhapsody/oxf/itronos.h`): a UML tool that generates C++ state
  machines. That explains the very regular shooting-state and component code. [code]
- Component naming: `Cmp*` (CmpPli/CmpPls playback, CmpSqp sequence parts, CmpShc, CmpCCom), GUI classes
  `*_Viewer`, `*_Actuator`, `Menu_*`, `SubApp*`; `userGui*`. [code]
- `OlyApiShooting` (OM-5 II 0x608f0a26, vtable 0x60bb6cc4): shooting API object; GND methods there are stubs on OM-5 II. [code]

## Tasks (examples)
STB_SEQ (standby sequencer), TAKE_EXPOSE, DSP0/DSP1, MVR_* (movie), ZOOM_MAIN, UI_OUT, FCS (focus), TSK_FACE_FD/MAIN,
REC_*, PC3/PC4 (USB), ISEQ_* (image sequencer), LENS_FLASH, FILECLBK, FIRMUP_CLI (SD updater), TSK_CA9PWR_MNGR,
TPC_CAMC_MAIN/FADD (USB camera control). Boot creates them in stages ([boot](boot-and-sections.md)). [code]

## Source-file and module names
Trace/error calls pass Olympus source file names (`iseq_nd_main.c`, `iseq_ndlv.c`, `stb_seq_flash.c`,
`take_lv_comp_mem.c`, `api_firmup.c`, `mvr_if_buff.c`, `CapThr_ThroughImage.cpp`, `sd_asic.c`). The symbols tool
groups functions into modules from these. [code]
- iseq function-id table ~0x6078d608 (E-M1 III): pairs are **{u32 id, char *name}** (reading {name,id} shifts
  everything by one). E-M5 {name,id} table at 0x6073dbd0 holds `iseq_nd_*` names. [code]

## Messages, events, locks
- Shooting events are (event, handler) pairs in a table from 0x6044e8a4 (e.g. ev63 0x602b4f16, ev65 0x602b5062,
  ev85 0x602b50e4). Details in [shooting sequencer](shooting-sequencer.md). [code]
- Properties: get 0x6005ce6b, address 0x6005ce41; drive mode = property 3265 via 0x602c5159. [code]
- Some completions run in **interrupt context** (StlUhs frame completion): no file I/O or locks there. [camera]

## Debug console
The MN103 has a debug console (commands `usb tpc ...` at 0x60c30320, `arm ...`, `fcs seq set2 6` = handheld HR
debug flag, `help dbg` in block 3). How to reach it on a retail body is unknown. [code]
- 2026-11-05: there are **two shells**, both in the static task tables. **System shell `S_SHELL`** (task 0x600570bd, always
  ready) reads the UART; line executor **0x60056e5f(a0 = line)** splits up to 4 words and calls dispatcher **0x60055d99(d0 = argc,
  a0 = argv)** (mdump, mem_get/put, od, ps, arm, isc, ...). **User shell `Tsk_USHL`** (0x6019c924, section 1) reads lines from a
  message buffer (id u16 at 0x600410cc); line executor **0x6019c8d8(a0 = line)** uses the 58-command table at **0x601fbe38**
  (lens, take, fcs, iseq, file, prm, usb, ...; many handlers in sections 4-10). [code]
- 2026-11-05: console text (`puts` 0x60023042) can be teed into a 16 KB buffer (open 0x6010189a, read 0x601018c6, close 0x60101932)
  and into an 8 KB log 0xa264deb0 when property 63873 is non-zero; stock's `dbgterm` writer 0x6010194d saves that log as
  `C:\dbgterm\<time>.txt`. No stock code reads console commands from the card. [code]
- 2026-11-05: the `tpc` PTP responder has ops **0x94B5** (run a console line) and **0x94B6** (read its output), gated on that
  responder's session flag 0x62358c58. Which USB mode exposes it is unchecked (USB parked). [code]
- 2026-11-11: **stock card-file switch for a Wi-Fi shell.** The parameter importer reads `PARAMDT/CP??????.CSV` (strings
  0x6073e6c8) as RAM overrides; a line `Wifi shell,0xF971,1,1` sets property 63857 (0xF971). 0x6005bafb reads it via 0x6005ce6b
  and, if non-zero, waits for readiness 7 (0x60045d92) and calls 0x6122e9b6 / 0x6122e9f6 (Wi-Fi request); it then reads 63873
  (the 8 KB log switch above) and 0x7B64 bit 31. [code] External report (fishcu/oly_fw_analysis, enduity on forum, 2026-11-01):
  on E-M5 III 1.7 this brings up an **open** Wi-Fi network with the user shell on port 23; a battery pull was sometimes needed.
  Not tried by us. Their PEN-F audit says the shell's `flash` dump can remap flash blocks, so it is not read-only. [inferred]

The external caduceus-ep7 project (E-P7) documents a 0x99700000 NMI monitor and bootloop behaviour; not checked on the
E-M5 III. [inferred]


### Shell commands are not safe to capture via the console log (CON3 audit, 2026-11-06) [code]
- `ps` rows are printed by 0x60055947 → 0x60056f8f, which calls the tee writer 0x60022f61 and then sends characters [code]
  straight to the UART (0x60056f5e → putc 0x60021436). The 8 KB console log (only fed by `puts` 0x60023042) never sees them.
- `puts` advances the log write index before copying the bytes, so a reader can't tell when a line is complete.
- `od` variants write a shared init byte 0x61f26468 (at 0x6005627e); `heaplist`'s listing is a "NotSupport" stub; [code]
  `oserr` prints a fixed uITRON error legend, not a log. All of them busy-wait the UART with no timeout (0x6002144a-0x60021459).
- Task table route (2026-11-06) [code]: `ps` 0x6005991e walks the u16 task-id list at **0x60038b5c** (0-terminated) and
  calls the task query **0x60034bab**(d0 = id, a0 = out). The query takes the per-CPU kernel object from
  **0x8ff00004 + 4 × (0x8050)** (CPU number at 0x8050); id = cpu<<12 | index; record = *(*(kobj+204) + 4×(index−1));
  record +12 u16 state, +20 byte, +8 u16 copied out. 0x8ff00000-0x8ff000bc is a block shared by all CPUs (lock word
  0x8ff00000, UART state 0x8ff0005c used by putc); native code reads 0x8ff00004 at 330 sites. CON2's admitted ranges
  exclude it, so a CON2 dump can't reach the task records yet.

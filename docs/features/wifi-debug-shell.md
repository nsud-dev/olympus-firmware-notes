# Stock Wi-Fi debug shell (card file, no flashing)

The stock firmware can start a debug Wi-Fi network and a command shell from a settings file on the card. No firmware
change is needed. We learned about it from fishcu/oly_fw_analysis (2026-11-11). A forum user reports it working on an
E-M5 III 1.7, and it passed on our test camera on 2026-11-12 (see "First camera test" below) [camera].

## How it works (E-M5 III 1.7)
- **Card file.** At startup the parameter importer looks for `PARAMDT\CP??????.CSV` on the card (pattern + folder strings
  0x6073e6c8 / 0x6073e6d4, used by the DCF search 0x60615f6d in `dcfnum.c`, called from 0x60615b1b). Each line is
  `label,ID,count,value`; the label is ignored. [code] 2026-11-11
- **After the import.** sub_6005add3 (called from a message handler at 0x6005d65d) runs the import step 0x6005bddf; when it
  returns 0 it queues callback **0x6005bafb** through 0x600691c8. [code] 2026-11-11
- **The callback.** 0x6005bafb reads property **63857 (0xF971)** via 0x6005ce6b. Non-zero: wait until readiness 7 is set
  (0x60045d92, polling with 0x60051a24), then call 0x6122e9b6 and **0x6122e9f6**, which fills the Wi-Fi request block
  0xa25c3c2c (216 bytes) and starts the debug network. It then reads **63873 (0xF981)**, the 8 KB console log switch
  (0x60022f9f; see [OS and framework](../firmware/os-and-framework.md#debug-consoles)), and property 0x7B64 bit 31. [code] 2026-11-11
- The same Wi-Fi starter is reachable from a shell command with sub-commands `init` / `start` / `info` / `auto`
  (handler 0x6122ec89; `auto` = 0x6122e9f6). [code]
- **The shell is the user shell (Tsk_USHL)**, with the 58-command table at 0x601fbe38: echo help lens aud cam bas pwr bc take stbd
  per res app usb prm flash rec file sc exp dbg ui mec fcs dbgall sdet osd mdet face play mddyna disp tpc sdk efct buff api c3d
  sync usr damage spc mcon wifi qr olis mvr pos avm iseq img movp md_sve digizoom zoom move albm syscall. [code] The PEN-F
  analysis traces the port-23 listener into the same shell. [inferred for E-M5 III]
- **Lasts until power-off.** On PEN-F the import is a RAM override and no flash write was found on that path. The E-M5 III uses the
  same import → callback pattern. [inferred] Removing the file and power-cycling should undo it; the test plan checks this.
- Reported on the E-M5 III 1.7 (enduity, forum, 2026-11-01): an **open** Wi-Fi network, debug console on port 23, OI.Share
  still connects, sometimes needs a brief battery pull before boot. [external report]

## Risks
- The network has **no password**. Run the test only where nobody else is in Wi-Fi range, keep the session short, and switch the camera off after.
- Some shell commands write flash or settings. Never run `flash` (on PEN-F its dump can remap/rewrite blocks), `prm` writes
  (`prm clear` includes a flash target), `file` rm/format, `usr`, `damage`, `sdk` (macro writes files), `syscall`, `usb`/`tpc`,
  or anything not on the list below.
- The shell runs inside the normal firmware, so it is no help if the camera won't boot.

## How to try it (stock 1.7, nothing flashed)
1. Card: a spare card, formatted in the camera. On a computer, create the folder `PARAMDT` at the card root and the file
   `PARAMDT\CP000001.CSV` with one line (plain text, Windows or Unix line ending):
   `Wifi shell,0xF971,1,1`
2. Location: home, nobody else in range. Laptop Wi-Fi only (no Ethernet bridging). Camera on stock 1.7 (or any of our
   builds: none of them touch this path).
3. Power on with the card in. If no new network shows within ~1 min, power off, pull the battery for ~10 s, try again.
4. Join the camera's open network. Note the network name and the laptop's IP and gateway. The camera is probably the gateway
   (192.168.0.10 on OI.Share networks). [inferred] Connect: `nc 192.168.0.10 23` (or `telnet`).
5. First commands, read-only only: `help`, then `echo hello`, then `help` for these groups only: `fcs`, `iseq`, `take`, `dbg`, `wifi`.
   Save the session text (copy the terminal) for the readout.
6. Undo: power off, delete `PARAMDT\CP000001.CSV` (or the whole folder), power on, and check that the open network does **not**
   appear and that OI.Share pairing behaves as before.
7. Report: network name, IP, whether a battery pull was needed, the `help` output, and step 6's result.

Possible follow-ups, each its own item: add `dbg log,0xF981,1,1` to the same file to tee console text into the 8 KB log
(on PEN-F 1 = fill once, 2 = circular; the E-M5 III values aren't checked), then save it with the stock `dbgterm` writer; read-only reads of our Live ND/HHHR state while the camera
runs; `sdk macro` record/replay for repeatable UI tests (read-only design first).

## First camera test (2026-11-12): shell works
- With the card file, the laptop joined the camera's network by DHCP: laptop 192.168.0.3, router 192.168.0.10, mask /24. [camera]
- `nc 192.168.0.10 23` connected (no refusal), but `help` and `echo hello` sent with nc's default LF line ending printed
  nothing. [camera] Next try: CR or CRLF line endings (`nc -c`). Cause open.
- **CRLF fixes it:** `nc -c 192.168.0.10 23` gives the prompt `USR>`; `echo hello` returns `hello`; `help` lists the 58 user
  commands, exactly the table at 0x601fbe38. The shell needs CR (LF alone is ignored). [camera] 2026-11-12
- `help <command>` just reprints the command list; per-command help has another form (not traced yet). [camera]
- Undo check (file deleted, network gone) not reported yet.

## Simulated button presses
Traced 2026-11-17 [code]. The user shell's `ui` command (handler 0x61408cf3, sub-command table 0x601b7bd0: `key jog out led sound help`) can press and
release the camera's buttons through the same path the real buttons use. Read in block0; not tried on the camera yet.
- **How the real buttons arrive.** The key-matrix module (UI_IN, around 0x6011f000-0x60122000) keeps one bit image per key group:
  table 0x601b8320, 12-byte records `{u32 entry lists, u32 image, u8 bytes, u8 bits, u8 count}`, five groups: power (image
  0xa2652f38), gio (0xa2652f34, 3 bytes), adc (0xa2652f2c), dial (0xa2652f2d) and ext (0xa2652f30). When the image changes, the
  module decodes it into app events `0x2000000 | code` (press), `0x2010000 | code` (release), `0x2020000 | code` (change), in the
  dispatcher 0x60120ad3, which also sends a half press first when the full press arrives alone, and posts them with 0x60046008. [code]
- **`ui key skey <code> <state>`** (sub-command 0x61408f79) calls **0x60120327(code, state)**: it finds the key's group and bit
  (0x60120dea), copies the group image, sets or clears the bit (state 1 = pressed; the entry's polarity byte is applied), writes the
  image back under an interrupt lock (0x60120cef) and sets UI_IN's event flag (word 0x60040dd4, set_flg 0x60051078). UI_IN's own
  task then handles it exactly like a real press. So `skey` simulates the key matrix, not a GUI event. Numbers take `0x` for hex
  (parser 0x60102915). The mode dial is the special code `0x2021901` with the dial position as state. [code]
- Other sub-commands: `gkey <code>` = current state of a key (0x60120227); `gtbl` = print the key table; `debug <n>` = set the key log
  level (byte 0xa2652cd8), which prints every app event as it is sent (good for checking which code a real button makes); `pwr_fact` =
  power-on factor; `spkey`, `multi1`, `multi2` = special shutter callbacks (don't use). [code]
- **Key codes** (name table 0x60251248, 4-letter names): Trg1 0x100 (half press), Trg2 0x101 (full press), MdDi 0x1901 (mode dial),
  Cut1 0xb, Cut2 0x1209, Cut3 0x120a, Cut4 0x120b, Cut5 0x1224, Cut8 0x1227 (the Fn/REC style buttons), Levr 0x1223 (lever),
  Play 0x87, Menu 0x89, Eras 0x84, Info 0x1205, Ok 0x4, Up 0x5, Down 0x6, Left 0x7, Rigt 0x8. Which physical button each Cut code is
  needs `ui key debug` on the camera. [code]
- **Never inject** Powr 0xc, LpSw 0x121c, UsbC 0x400, Hdmi 0x501, MdaC 0x1506, LnsC 0x2202 and the other cable/card/lens codes in
  the table: they fake power, cable, card or lens events. Always send the release (state 0) after a press; a press with no release
  stays held until a power cycle or until a real key in the same group changes. [inferred]
- **Dials are not keys.** The front and rear dials go through the jog driver (JOG_SendEvent 0x6011fe86 posts
  `0x2030000 | 0x1902/0x1903` with 0x60046008); `ui jog` only has start/stop/count/debug, so there is no stock way to turn a dial
  from the shell. In menus the arrow keys do the same job; a dial turn would need a small helper in one of our builds. [code]
- The touch panel is a separate driver (`[TP]` strings, 0x601fa531); not traced. [code]
- **From the key line to the app (2026-11-19)** [code] unless marked. Source: block0 disassembly.
  - Key-line interrupts: block **0x9bd00000** (two pairs of channels at +0x00 and +0x80; status +0x08/+0x88, written back to
    clear). The handler 0x601231e0 calls the callback registered per channel in table 0x620b2860 (registration
    0x601230ab, which also zeroes +0x00/+0x04 or +0x80/+0x84 and calls 0x60071fa6(0, 3, 1) once). UI_IN registers
    0x60120011 for its gio lines (at 0x6011faf1). That 0x9bd00000 is a GPIO edge-interrupt block is [inferred].
  - Other key sources register their own callbacks: two per-channel callbacks 0x60121305 / 0x601213bd in records at
    0x620b27a8 + 56 × n (likely the adc keys, [inferred]) and the power key 0x60121f0d through 0x60063d13 (which takes
    cross-core lock 8), whose reader 0x60063d81 fills the power image 0xa2652f38.
  - [code] Each callback updates the group's bit image and sets bit 0 of UI_IN's event flag (u16 0x60040dd4).
  - **UI_IN task loop 0x6011f9d8** [code]: wait on that flag (bit 0, no timeout), clear it, run the key decoder 0x6012092f (→
    dispatcher 0x60120ad3, see above), then the jog handler 0x6011fb2d; a progress word 0x620b2784 goes 1 → 2 → 3 each pass.
  - **App events** [code] go out through 0x60046008 → 0x602e39b9, which allocates a 12-byte message {u16, u32 event, u32
    argument} and writes it to queue u16 (0x60040f24) with `OlyQeWrCpu`. The HLS_EVENT task reads that queue in
    `appevent::Wait_Event` 0x602e2f49 (also `Wait_ExecuteEvent` 0x602e32f6); the api_*.c modules (api_rec, api_play,
    api_disp, ...) use the same queue id. 0x60046008 drops two event codes (0x40d00b5/0x40d00b6) while byte 0xa25b897e
    is 119 and 0x602e69f9(3008) is set (meaning open).
  - How a half-press app event reaches the shooting sequencer is open (see research gaps).

## Commands useful for Live ND / HHHR (traced 2026-11-12) [code]
Read from the C decompile (`seg_6140.bundle.c`) and block0 strings.
- **`take`** (handler 0x602a158b) with no argument prints its own help (0x602a168b, text 0x6044fceb): `func ...`, `dbgmode`,
  `dbginfo`, `exec COM`, `ev_qname NAME`. Also accepts `cont_dbgmode`, `ps`, `pe`. [code]
- **`take dbginfo`** (0x602a169b) is print-only: shooting-sequencer state (u16 0x62107744), event mask (0x62107750), the pending
  imdfunc queue/command, then the status printers 0x60227bb0, 0x602a747d, 0x602c4e43, 0x602bbe53, 0x602a2085, 0x602a19a5,
  0x602aee91 (job, flag manager, capture counters). No writes found two call levels down. [code]
- **`take dbgmode`** with no value prints the current value; `take dbgmode 1` sets u32 0x62107754 (RAM) = "TAKE_MAIN sequence dbg
  log" (the `.post(%d)` / `.exec(%d)` / `.ipost(%d)` event trace, strings 0x6044fc8d..). All four readers (0x602a0ff9, 0x602a1125, 0x602a1256, 0x602a13ba, in the state dispatcher) only test bit 0 and print the state name (state table entry +4) plus `.exec(n)` / `.ipost(n)` / `.post(n)`, and `old -> new` on a state change; no other effect, apart from the time the prints take. Written only by the `take` command and init 0x602a0f48. [code]
- **Do not run** `take exec`, `take ps`, `take pe`, `take func exec`: they post commands to the sequencer.
- `dbg` (0x61401a03): `dbg put put|off` sets the DBG_PUT output state (0xa2566018); `dbg info ...` block information;
  `dbg test`/`dmyp`/`dmyw`/`nmip`/`nmiw` raise dummy warnings and **NMIs on purpose: never run them**. [code]
- A line that is only `:` switches the session to the **system shell** dispatcher (toggle byte 0xa25b8800), which has
  `mdump4/2/1` and `mem_get4/2/1` (read memory) but also `mem_put*`, `nmiset`, `arm load*`, `shelloff`. Not tried; whether
  system-shell output reaches the Wi-Fi session is unknown (its `ps` writes straight to the UART). [inferred]
- Use for a Live ND run: connect, `take dbgmode 1`, run the armed capture; the event trace arrives on the laptop, so it survives a reset
  or battery pull. During a hang, `take dbginfo` shows the state and event mask if the shell task still runs. [inferred]

## Live sequencer trace over Wi-Fi works (2026-11-12) [camera]
- `take dbgmode 1` streams the native shooting-sequencer trace to the port-23 session as it happens: state names,
  `.exec(n)` / `.ipost(n)` / `.post(n)` per event and ` -> NewState` on every change. A normal single shot reads
  Idle → RdyStart → RdyFcsRdy1-3 → RdyTrig2Wait → RdyFcsTake → Standby → StlRdy1 → StlRdy2 → StlTakeCave → StlEnd1 → StlEnd2 →
  RdyTrig2Wait → RdyAbort → RdyEnd → Idle. [camera]
- `take dbginfo` prints the sequencer status, including a `history` line of recent events and the burst fields
  (continue_mode, uhs_cont_speed, capture_count, stop#req, uhs_cam_packet_queue). [camera]
- Body shutter works normally while the debug network and session are up. [camera]
- Consequence: a Live ND / HHHR test run can be traced on the laptop with no logging code in the build, and the trace
  survives a reset or battery pull. [inferred] Since 2026-11-12 it has been used on every armed Live ND test run (a fault at capture start was found this way), so it works on armed builds. [camera] 2026-11-19
- `take dbgmode N` stores N unmasked (0x602a1898: `*0x62107754 = parsed number`); the four stock readers test bit 0 only, so the upper bits are free as console switches for our builds (our Live ND builds use bit 1 as the LV Simulation switch). Trace print path: sprintf 0x600e054f (`[],12`), puts 0x60022fbf (`[a2,a3],28`), copied from 0x602a101d. System-shell `mem_get4 <addr>` / `mdump4 <addr> (<size>)` print through 0x60055947 -> 0x60056f8f (UART), so they are not expected to reach the Wi-Fi session. [code] 2026-11-12




- One connection per power-on: after the first `nc` session is closed, a new connection gets no answer until a power cycle; the prompt appears only after the first Enter. Scripts must be the first and only connection. [camera] 2026-11-12

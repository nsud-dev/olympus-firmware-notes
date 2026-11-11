# Stock Wi-Fi debug shell (card file, no flashing)

The stock firmware can start a debug Wi-Fi network and a command shell from a settings file on the card. No firmware
change is needed. We learned about it from fishcu/oly_fw_analysis (2026-11-11). A forum user reports it working on an
E-M5 III 1.7; the maintainer hasn't tried it yet. Comparison page: oly_fw_analysis.

## How it works (E-M5 III 1.7)
- **Card file.** At startup the parameter importer looks for `PARAMDT\CP??????.CSV` on the card (pattern + folder strings
  0x6073e6c8 / 0x6073e6d4, used by the DCF search 0x60615f6d in `dcfnum.c`, called from 0x60615b1b). Each line is
  `label,ID,count,value`; the label is ignored. [code] 2026-11-11
- **After the import.** sub_6005add3 (called from a message handler at 0x6005d65d) runs the import step 0x6005bddf; when it
  returns 0 it queues callback **0x6005bafb** through 0x600691c8. [code] 2026-11-11
- **The callback.** 0x6005bafb reads property **63857 (0xF971)** via 0x6005ce6b. Non-zero: wait until readiness 7 is set
  (0x60045d92, polling with 0x60051a24), then call 0x6122e9b6 and **0x6122e9f6**, which fills the Wi-Fi request block
  0xa25c3c2c (216 bytes) and starts the debug network. It then reads **63873 (0xF981)**, the 8 KB console log switch
  (0x60022f9f; see [OS and framework](../firmware/os-and-framework.md#debug-console)), and property 0x7B64 bit 31. [code] 2026-11-11
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

## Test plan W1 (stock 1.7, nothing flashed) [planned]
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

Follow-ups if W1 works, each its own item: add `dbg log,0xF981,1,1` to the same file to tee console text into the 8 KB log
(on PEN-F 1 = fill once, 2 = circular; the E-M5 III values aren't checked), then save it with the stock `dbgterm` writer; read-only reads of our Live ND/HHHR state while the camera
runs; `sdk macro` record/replay for repeatable UI tests (read-only design first).

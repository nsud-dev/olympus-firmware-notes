# Wi-Fi debug shell

<!-- human page -->
<!-- house style -->

## Key points

- A small text file on the SD card makes the camera start a debug Wi-Fi network with a command shell.
- Nothing has to be flashed, and taking the file off the card turns it off again.
- The shell runs alongside normal shooting and has become our main test tool.
- Some of its commands write to flash memory, so only reading commands are safe to use.

The E-M5 III has a hidden debug console, most likely left over from development. A small text file on the SD card
makes the camera start its own Wi-Fi network, and a laptop on that network can then type commands into the camera.

Nothing has to be flashed. It works on the stock firmware, and taking the file off the card turns it off again. With
our [card mod loader](card-mods.md) installed there is an easier way. A Wi-Fi shell row on the "K. Mods" menu page
starts the same network at the next power-on, with no file on the card.

## How it starts

At power-on the camera looks for settings files in a folder called `PARAMDT` on the card. Each line in such a file sets
one of the camera's internal properties. One of those properties tells the camera to start a debug Wi-Fi network.

Once the camera is ready, it brings up an open network and listens for a connection on port 23. That is the usual port
for a plain text console. Whatever you type there goes to the camera's built-in command shell.

The setting is not saved. It lasts until the camera is switched off, so the file has to be on the card at every
power-on.

## Trying it

With the card mod loader, set the Wi-Fi shell row in K. Mods to On, switch the camera off and on again, then go
straight to step 5. On a stock camera, use the settings file as below.

You need a spare card, a laptop and a place where nobody else is in Wi-Fi range.

1. Format the card in the camera.
2. On a computer, make a folder called `PARAMDT` at the top of the card.
3. In it, make a plain text file called `CP000001.CSV` containing this one line.

   ```
   Wifi shell,0xF971,1,1
   ```

4. Put the card in the camera and switch it on. A new open network should appear within about a minute. If it does
   not, switch off, take the battery out for ten seconds and try again.
5. Join that network from the laptop. The camera is at `192.168.0.10`.
6. Connect with `nc -c 192.168.0.10 23`. The `-c` matters, because the shell ignores a line unless it ends with a
   carriage return.
7. Press Enter. You should see `USR>`. Type `help` to see the commands.

To undo it, switch off, delete the file and switch on again.

Two quirks are worth knowing. The camera accepts only one connection per power-on, so a second `nc` gets no answer.
The shell also cuts every line at 31 characters, so long commands lose their end without any warning.

## Risks

The network has no password. Anyone in range could join it while the camera is on, so keep sessions short and switch
the camera off afterwards.

> [!WARNING]
> Some commands write to the camera's flash memory or settings. A wrong one could damage the firmware.

Stick to reading commands such as `help`, `echo` and `take dbginfo`. Never run `flash`, `prm`, `res`, `bas`, `usr`,
`damage`, `sdk`, `syscall` or the `dbg` test commands, which raise faults on purpose. The technical notes have
[the full never-run list](wifi-debug-shell-technical.md#risks).

The shell is part of the normal firmware. It is no help if the camera will not start.

## What it is good for

**Watching the camera take a picture.** `take dbgmode 1` makes the shooting sequencer print every step as it
happens. A single shot reads as a chain of states, from Idle through focus, exposure and the end of the capture, and
back to Idle. The text arrives on the laptop, so it survives even if the camera locks up or resets. This is how we
found a fault at the start of a Live ND capture.

**Saving memory to the card.** `file memdump` writes a block of the camera's memory to a file. We used it to read the
colour tables behind the profile editor.

**Pressing buttons remotely.** `ui key skey` presses and releases any button through the same path the real buttons
use. It has been traced in the firmware but not yet tried on the camera. A remote test rig built on it could step
through menus without anyone touching the camera. Always send the release after a press, and never fake the power,
cable, card or lens signals.

**Starting it from the menu.** With our card mod loader, the "K. Mods" menu page has a Wi-Fi shell row. From the next
power-on, that starts the same network without the settings file.

## Other cameras

| camera | shell | notes |
|---|---|---|
| E-M5 III 1.7 | works | tested on our camera |
| PEN-F | same shell | traced in earlier community work |
| E-M5 II 4.1 | commands present | its Wi-Fi works differently, so the way in still has to be found |
| E-M5 (Mark I) 2.3 | commands present | no Wi-Fi at all |

*The debug shell on other Olympus bodies.*

## Credit

We learned about the shell from fishcu's oly_fw_analysis project. A forum user on forum reported it working on an
E-M5 III before we tried it.

## Status

- **It works on the camera.** It was first confirmed on our E-M5 III with firmware 1.7.
- **The shell answers.** It shows the prompt `USR>` and lists 58 commands.
- **It runs alongside normal shooting.** The camera takes pictures as usual while a laptop is connected.
- **It has become our main test tool.** Every Live ND test run since its first test has been watched through it.

## Further reading

- [Wi-Fi debug shell: technical notes](wifi-debug-shell-technical.md) has the full command details, the button codes
  and the addresses.

- [Buttons](../guides/button-press.md) follows a button press from the key to the app, which is the path
  the remote presses use.
- [Taking a photo](../guides/taking-a-photo.md) explains the shooting sequencer whose trace the shell prints.
- [Modifying the firmware](../firmware/patching-techniques.md), sections 11, 16 and 17, covers watching runs live,
  card files and remote presses.

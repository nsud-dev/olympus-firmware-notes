# USB webcam

<!-- human page -->
> The dense reference for this page is [USB webcam: technical notes](webcam-technical.md).

The OM-5 can act as a USB webcam on its own. Plug it into a computer and it shows up like any other webcam. The
E-M5 III cannot. A webcam mode was the first feature this project tried to bring over.

## Status

Parked. The E-M5 III can now appear to a computer as a webcam and stream a picture of its own. Streaming the real live
view did not work, and fixing that would be a large change.

## On the OM-5

The OM-5 streams 1280 by 720 video at about 30 frames per second as Motion JPEG, with stereo sound. It uses the standard
webcam protocol, so computers need no driver. The frames come from the movie recorder, which is why the picture matches
what the camera would record.

## The port

The E-M5 III never had webcam support. Its USB code covers file transfer and remote control only.

The tests went in steps.

| test | result |
|---|---|
| appear to a computer as a webcam | worked |
| stream a small test picture, and survive unplugging | worked |
| pace the stream with the camera's own timer | worked, about 22 frames per second |
| stream the real live view | failed |

The last test failed because the camera switches its shooting pipeline off while USB is connected. The screen shows
"One moment..." and there is no live view to send. Keeping the camera in shooting mode while connected would mean
large changes to how it handles USB and its modes, so the work was parked.

## Lessons

- Most of what went wrong on the computer side, such as a black picture after reopening an app, was the computer
  waiting for the camera to start again. It was not a camera fault.
- Without proper pacing, the camera sent far too many frames and the computer dropped most of them.

## Other cameras

The OM-5, OM-5 II and OM-1 II have a webcam mode. The E-M1 III, OM-1, PEN-F, E-M5 II and E-M5 III do not.

## Without changing the firmware

The camera's Wi-Fi remote live view can be turned into a webcam on the computer with a virtual-camera tool. That needs
no firmware change. It has not been tried.

## Further reading

- [USB](../hardware/usb.md) covers the camera's USB modes.

# Wireless CarPlay on the Audi Virtual Cockpit (AK3918AN)

> **Experimental branch warning — 2026-11-21:** This branch contains a newer, **not device-validated** ARM/AK3918 port and separate combined stream-111 source changes. The author's historical success statement and downloadable installer below describe the **older archive on `main`**, not proof that this WIP revision is safe to flash. The legacy stock and recovery packages are unchanged. Do not package or install WIP firmware without a separate hardware/recovery review. See [Step 129 release and safety status](docs/STEP129_RELEASE_AND_SAFETY_STATUS.md).


I ordered a dongle to try [OMKE’s wireless CarPlay mod](https://github.com/OMKE/wireless-carplay-virtual-cockpit) and ended up with the wrong one. His is a Suding AX1800M. Mine turned out to be an AK3918AN. I already had the LukaDev mod working over USB, so I used OMKE’s code to get the wireless dongle working with my car.

The first builds kept dropping CarPlay. With the build in this repo, the MMI stayed connected and navigation showed up on the Virtual Cockpit. I’ve tested it on my own setup.

## My setup

I tested this on my 2018 Audi A5 with a Harman MHI2Q head unit. The MMI software train is `MHI2Q_US_AUG22_P5087` (`MU1316`). I already had the LukaDev Virtual Cockpit mod working over wired CarPlay before testing the Suding AK3918AN dongle.

## Before you flash

- Plug your iPhone directly into the Audi first. If the map doesn’t show up in the Virtual Cockpit over USB, get that working before trying the dongle.
- Join the dongle’s `SmartBox_XXXX` Wi-Fi and open `http://192.168.200.1/cgi-bin/getversion.cgi`. Look for `platform:AK3918AN` and `custom:suding`. I tested with CarPlay firmware `20261008165915`. The installer checks the model and vendor, so check the firmware version yourself.

## Install

Download [ak3918-ready-to-flash.zip](./ak3918-ready-to-flash.zip) and unzip it. It has the Python installer and both firmware files. With the car parked, keep the dongle powered and your computer on the dongle’s `SmartBox_XXXX` Wi-Fi. If prompted, enter the Wi-Fi password supplied with your dongle. Install Python 3 before switching to the dongle’s Wi-Fi if you don’t already have it. [Python downloads](https://www.python.org/downloads/)

### macOS

Open Terminal. Type `cd ` with a space after it, drag the extracted folder from Finder into Terminal, and press Return. Then run:

```sh
python3 flash_ak.py
```

### Windows

Open the extracted folder in File Explorer. Click the address bar, type `cmd`, and press Enter. Then run:

```bat
py -3 flash_ak.py
```

If Windows doesn’t recognize `py`, try `python flash_ak.py` with Python 3 installed.

Check the device it reports and type `yes`. Let it reboot, reconnect your iPhone, start navigation, and switch the Virtual Cockpit to the map.

## Back to stock

Connect to the dongle’s Wi-Fi and run the command for your computer from the same folder:

- **macOS:** `python3 flash_ak.py --stock`
- **Windows:** `py -3 flash_ak.py --stock` (or `python flash_ak.py --stock` if you used `python` to install)

Type `yes` and leave it powered through the reboot. The installer uses `stock_ak_202610081659.tar`. `SHA256SUMS` lists the checksums for that file and the patched `ak_hook.tar`.

Thanks to [OMKE](https://github.com) for sharing the patch and the research behind it, and to [luka-dev](https://github.com) for the Audi-side mod I used.

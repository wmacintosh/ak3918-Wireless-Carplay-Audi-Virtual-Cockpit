# Wireless CarPlay on the Audi Virtual Cockpit (AK3918AN)

I ordered a dongle to try [OMKE’s wireless CarPlay mod](https://github.com/OMKE/wireless-carplay-virtual-cockpit) and ended up with the wrong one. His is a Suding AX1800M. Mine turned out to be an AK3918AN. I already had the LukaDev mod working over USB, so I used OMKE’s code to get the wireless dongle working with my car.

The first builds kept dropping CarPlay. With the build in this repo, the MMI stayed connected and navigation showed up on the Virtual Cockpit. I’ve tested it on my own setup.

## Before you flash

- Plug your iPhone directly into the Audi first. If the map doesn’t show up in the Virtual Cockpit over USB, get that working before trying the dongle.
- Join the dongle’s `SmartBox_XXXX` Wi-Fi and open `http://192.168.200.1/cgi-bin/getversion.cgi`. Look for `platform:AK3918AN` and `custom:suding`. I tested with CarPlay firmware `20261008165915`. The installer checks the model and vendor, so check the firmware version yourself.

## Install

Download [ak3918-ready-to-flash.zip](./ak3918-ready-to-flash.zip) and unzip it. It has the Python installer and both firmware files. With the car parked, keep the dongle powered and your computer on the dongle’s Wi-Fi. Open Terminal in the extracted folder and run:

```sh
python3 flash_ak.py
```

Check the device it reports and type `yes`. Let it reboot, reconnect your iPhone, start navigation, and switch the Virtual Cockpit to the map.

## Back to stock

Connect to the dongle’s Wi-Fi and run this from the same folder:

```sh
python3 flash_ak.py --stock
```

Type `yes` and leave it powered through the reboot. The installer uses `stock_ak_202610081659.tar`. `SHA256SUMS` lists the checksums for that file and the patched `ak_hook.tar`.

Thanks to OMKE for sharing the patch and the research behind it, and to LukaDev for the Audi-side mod I used.

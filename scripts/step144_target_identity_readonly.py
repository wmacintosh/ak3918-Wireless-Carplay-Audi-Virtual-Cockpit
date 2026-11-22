#!/usr/bin/env python3
"""Step 144: optional strictly read-only AK3918AN device identity collection.

No writes to the dongle, no HTTP POST, no firmware staging, CGI upload,
installer invocation, reboot, filesystem fetch, shell execution or scanning.
Only an EXPLICIT --probe-version permits a single GET to the exact historical
read-only endpoint http://192.168.200.1/cgi-bin/getversion.cgi.

Does not prove installed libc, target dynamic-loader compatibility, board
revision, UART recovery or ability to unbrick the physical unit.
"""
import argparse
import re
import sys
import urllib.error
import urllib.request

VERSION_URL="http://192.168.200.1/cgi-bin/getversion.cgi"
MAX_RESPONSE_BYTES=4096
TIMEOUT_SECONDS=4
PRINT_KEYS=(
    "platform", "custom", "system_version", "protocol_version",
    "product_Model", "firmware_version", "carplay_version",
    "software_version", "hardware_version"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Avoid following a redirect to an unknown LAN, auth portal or
        # internet address. The user's explicit intent is exactly one host.
        return None


def parse_identity(payload):
    # Fail closed if binary/oversized/malformed data comes back.
    if len(payload)>MAX_RESPONSE_BYTES or b"\x00" in payload:
        raise ValueError("unexpected CGI response size or binary content")
    body=payload.decode("utf-8","replace")
    pairs={}
    for line in body.splitlines():
        if ":" not in line:
            continue
        k,v=line.split(":",1)
        k=k.strip()
        v=v.strip()
        if k not in PRINT_KEYS or k in pairs:
            continue
        if not v or len(v)>110 or any(ord(ch)<32 or ord(ch)==127 for ch in v):
            continue
        pairs[k]=v
    if pairs.get("platform")!="AK3918AN" or pairs.get("custom","").casefold()!="suding":
        raise ValueError(
            "response lacks the expected AK3918AN/Suding platform identity; "
            "do not assume this address is the intended dongle"
        )
    return pairs


def probe(opener=None):
    if opener is None:
        opener=urllib.request.build_opener(NoRedirect())
    req=urllib.request.Request(
        VERSION_URL,
        headers={"Accept":"text/plain","User-Agent":"AK3918-Step144-ReadOnly/1.0"},
        method="GET",
    )
    with opener.open(req,timeout=TIMEOUT_SECONDS) as res:
        if res.status!=200:
            raise ValueError(f"expected HTTP 200; returned {res.status}")
        payload=res.read(MAX_RESPONSE_BYTES+1)
    return parse_identity(payload)


def run(argv=None, opener=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-version",action="store_true",
                        help="Opt-in to ONE exact-host GET (only getversion.cgi)")
    args=parser.parse_args(argv)
    print("STEP 144 — EXACT-DEVICE IDENTITY CHECK")
    print("NO CGI upload, POST, installer, reboot or firmware change")
    if not args.probe_version:
        print("NO NETWORK REQUEST MADE: --probe-version was not given")
        print("OPTION: connect Mac to the dongle's SmartBox Wi-Fi, then "
              "run with --probe-version")
        print("BLOCKED FOR FLASH: target libc/loader and independent recovery unknown")
        return 0
    print("PROBE: one GET to /cgi-bin/getversion.cgi at 192.168.200.1")
    try:
        info=probe(opener)
    except (OSError,ValueError,urllib.error.URLError) as exc:
        print("FAIL CLOSED: device identity request failed:", str(exc)[:280])
        print("NO OTHER HOST/ENDPOINT/HTTP METHOD WAS ATTEMPTED")
        return 2
    for k in PRINT_KEYS:
        if k in info:
            print(f"DEVICE {k}={info[k]}")
    print("PASS: STEP144 READ-ONLY HTTP DEVICE IDENTITY")
    print("UNKNOWN: exact on-device /lib/libc.so.0 and ld-uClibc.so.0 hashes")
    print("UNKNOWN: physical board variant, serial console, bootloader recovery")
    print("BLOCKED FOR FLASH: CGI identity is not target loader or recovery proof")
    return 0


if __name__=="__main__":
    sys.exit(run())

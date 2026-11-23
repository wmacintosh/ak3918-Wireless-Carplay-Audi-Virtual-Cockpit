#!/usr/bin/env python3
"""Deliberate AK3918AN stream-111 experimental firmware installer.

--probe only validates local package and GETs device identity.
--install uploads AND installs a modified application ELF. The dongle might not
boot afterward; known --stock recovery requires functioning Wi-Fi/CGI.
No proven out-of-band recovery exists for this RM-KPL083-2 board.
This installer NEVER selects/replaces legacy ak_hook.tar.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from step144_target_identity_readonly import (
    VERSION_URL, NoRedirect, parse_identity, MAX_RESPONSE_BYTES
)
from step147_validate_experimental_package import (
    validate, PACKAGE_NAME,MANIFEST_NAME,EXPECTED_SYSTEM_VERSION,
    EXPECTED_PROTOCOL_VERSION
)

HOST = "192.168.200.1"
CHUNK = 10240
RNAME = "ak_hook"  # Historical CGI receiver name, NOT on-disk archive name.
BOUNDARY = "----ak3918boundary"
BUNDLE = Path.home()/"Desktop"/"AK3918_Stream111_Test"
MAX_REPLY = 4096


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def opener():
    # Bypass user HTTP proxy and reject redirects off exact local target.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect()
    )


def get_text(client,url,timeout=8):
    req=urllib.request.Request(
        url,method="GET",
        headers={"User-Agent":"AK3918-Step147-ExplicitExperimental/1.0"}
    )
    with client.open(req,timeout=timeout) as resp:
        require(resp.status==200, f"unexpected status {resp.status} for exact host")
        data=resp.read(MAX_REPLY+1)
    require(len(data)<=MAX_REPLY,"unexpected oversized CGI response")
    return data.decode("utf-8","replace").strip()


def verify_device(client):
    req=urllib.request.Request(
        VERSION_URL,method="GET",headers={"Accept":"text/plain"}
    )
    with client.open(req,timeout=5) as resp:
        require(resp.status==200,"device version endpoint not HTTP 200")
        payload=resp.read(MAX_RESPONSE_BYTES+1)
    values=parse_identity(payload)
    require(values.get("system_version")==EXPECTED_SYSTEM_VERSION,
            "dongle system_version differs from inspected device; DO NOT install")
    require(values.get("protocol_version")==EXPECTED_PROTOCOL_VERSION,
            "dongle protocol_version differs from verified target; DO NOT install")
    print("PASS: EXACT AK3918AN/Suding live system/protocol versions")
    print("SYSTEM_VERSION",values["system_version"])
    print("PROTOCOL_VERSION",values["protocol_version"])
    return values


def post_chunk(client,part,name):
    prefix=(f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="chunk"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    suffix=(f"\r\n--{BOUNDARY}--\r\n").encode()
    request=urllib.request.Request(
        f"http://{HOST}/cgi-bin/downfile.cgi",
        data=prefix+part+suffix,
        headers={"Content-Type":f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST"
    )
    with client.open(request,timeout=30) as resp:
        require(resp.status==200,"chunk receiver returned non-200")
        body=resp.read(MAX_REPLY+1)
    require(len(body)<=MAX_REPLY,"chunk reply larger than expected")
    return body.decode("utf-8","replace").strip()


def install(client,blob):
    md5=hashlib.md5(blob).hexdigest()  # Vendor CGI wire protocol uses MD5.
    n=(len(blob)+CHUNK-1)//CHUNK
    require(n>=2,"test tar unexpectedly too short for CGI chunk protocol")
    print("UPLOAD: historical CGI ak_hook framing; separate experimental tar")
    last=""
    for i in range(n):
        # This deliberately matches the historical flash_ak.py CGI wire names.
        name=(f"{RNAME}.0" if i==0 else
              (f"{RNAME}:{md5}.2" if i==n-1 else f"{RNAME}.1"))
        last=post_chunk(client,blob[i*CHUNK:(i+1)*CHUNK],name)
        require("success" in last.lower(),
                f"upload chunk {i+1}/{n} was not accepted: {last[:160]}")
        print(f"\rUploaded {i+1}/{n}",end="",flush=True)
    print()
    require("file check success" in last.lower(),
            "dongle did not confirm final archive integrity; refusing install")
    print("PASS: dongle reported file check success")
    # WARNING: this request is the actual firmware installation action.
    result=get_text(client,f"http://{HOST}/cgi-bin/submition.cgi?filename={RNAME}&",
                    timeout=45)
    print("INSTALL CGI RESPONSE:",result[:300])
    lower=result.lower()
    require(bool(result) and "success" in lower and "error" not in lower and "fail" not in lower,
            f"install CGI did not confirm success; refusing reboot: {result[:160]}")
    print("INSTALL REQUEST CONFIRMED: a valid response is not proof firmware can boot")
    try:
        result=get_text(client,f"http://{HOST}/cgi-bin/reboot.cgi",timeout=5)
        print("REBOOT CGI RESPONSE:",result[:120])
    except (OSError,ValueError,urllib.error.URLError) as exc:
        print("REBOOT REQUEST MAY HAVE BEEN ACCEPTED (connection dropped):",str(exc)[:180])
    print("POWER: keep the dongle powered through reboot; do not disconnect early")
    print("AFTER BOOT: connect iPhone, then test cluster output and capture logs")
    print("IF CGI DISAPPEARS: the historical stock restorer cannot be assumed to work")


def main(argv=None,input_func=input,client=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--probe",action="store_true",
                        help="verify local tar and do one device identity GET; no writes")
    action.add_argument("--install",action="store_true",
                        help="after explicit typed risk acceptance, UPLOAD AND FLASH")
    parser.add_argument("--bundle",type=Path,default=BUNDLE,
                        help="directory containing exact dedicated test tar and manifest")
    args=parser.parse_args(argv)
    print("STEP 147: EXPERIMENTAL STREAM-111 FIRMWARE")
    print("Warning: no verified offline recovery. Failure can brick this dongle.")
    try:
        blob,record=validate(
            args.bundle/PACKAGE_NAME,args.bundle/MANIFEST_NAME
        )
        print("PASS: exact six-file experimental firmware and manifest")
        print("BUNDLE_SHA256",record["sha256"])
        print("SOURCE_COMMIT",record["commit"])
        client=client or opener()
        verify_device(client)
        if args.probe:
            print("PASS: STEP147 PROBE ONLY — no firmware uploaded or flashed")
            return 0

        # Verify the user's explicit understanding BEFORE ANY archive upload.
        print()
        print("FINAL RISK GATE: --install uploads and replaces dongle application files.")
        print("If it no longer boots or serves Wi-Fi/CGI, software stock restore")
        print("may be impossible. There is no verified physical unbrick method.")
        print("Park the car and provide continuous stable USB power.")
        phrase="FLASH STREAM111 AT MY RISK"
        typed=input_func(f"Type '{phrase}' to install: ").strip()
        require(typed==phrase,"exact flash-risk confirmation not provided")
        print("CONFIRMED: starting the user-requested experimental install")
        install(client,blob)
        return 0
    except (OSError,ValueError,EOFError,KeyboardInterrupt,
            urllib.error.URLError) as exc:
        print("\nSTOPPED: STEP147:",str(exc)[:400])
        print("Do not blindly retry after any partial upload or install.")
        return 2


if __name__=="__main__":
    sys.exit(main())

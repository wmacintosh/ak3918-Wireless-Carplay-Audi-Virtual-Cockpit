#!/usr/bin/env python3
"""Step 143: offline inspection of archive and recovery script limitations.

NO DEVICE ACCESS. Never invokes flash_ak.py (even with --check-only),
imports executable firmware, or uploads archive chunks. Does NOT claim an
out-of-band recovery method exists on the hardware.
"""
import ast
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from step141_readonly_firmware_preflight import (
    RECOVERY_NAME, RECOVERY_SHA256, STOCK_SHA256,
    audit_recovery_archive, need as require
)

def recovery_policy(source):
    """Check exact historic upload flow, not a general static program proof."""
    tree=ast.parse(source)
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
    upload_sites=[n for n in calls if isinstance(n.func,ast.Name) and
                  n.func.id=="post_chunk" and n.args and
                  isinstance(n.args[0],ast.Subscript)]
    require(len(upload_sites)==1,"expected exactly one upload loop call")
    line=upload_sites[0].lineno
    required=["/cgi-bin/getversion.cgi","/cgi-bin/downfile.cgi",
              "/cgi-bin/submition.cgi","/cgi-bin/reboot.cgi",
              '"--check-only"', '"--stock"']
    for token in required:
        require(token in source,"missing expected historical CGI/option "+token)
    # The check-only option *does not guard the post_chunk call*. The control
    # structure guarding submission and reboot comes after chunk upload.
    upload_loops=[
        n for n in ast.walk(tree) if isinstance(n,ast.For) and
        n.lineno <= line <= n.end_lineno
    ]
    require(len(upload_loops)==1,"upload is not in expected for loop")
    enclosing_check_only=[
        n for n in ast.walk(tree) if isinstance(n,ast.If) and
        n.lineno <= line <= n.end_lineno and
        "check_only" in ast.unparse(n.test)
    ]
    require(not enclosing_check_only,
            "historical upload flow changed: post_chunk now check_only guarded")
    return line


def check(root):
    script=(root/"flash_ak.py").read_text()
    upload_line=recovery_policy(script)
    source=root/RECOVERY_NAME
    digests=audit_recovery_archive(source)
    require(digests["sdDongle"]==STOCK_SHA256,
            "recovery tar contains wrong original executable")
    print("PASS: pinned historical stock recovery SHA256 and original ELF member")
    print("PASS: archive contains exactly five original vendor files")
    print("INFO: flash_ak.py performs upload via /cgi-bin/downfile.cgi "
          f"even for --check-only (call at line {upload_line})")
    print("INFO: --stock restore also calls /cgi-bin/submition.cgi and reboot.cgi")
    print("RECOVERY_CLASSIFICATION: CGI-dependent software restore only")
    print("NOT VERIFIED: UART, serial console, bootloader, alternate boot source, "
          "full flash image or hardware-independent unbrick")
    print("BLOCKED FOR FLASH: no verified recovery route if Wi-Fi/CGI cannot start")
    print("PASS: STEP143 OFFLINE RECOVERY LIMITATION AUDIT")
    return 0


if __name__=="__main__":
    try:
        sys.exit(check(ROOT))
    except (OSError,ValueError,tarfile.TarError,SyntaxError) as e:
        print("FAIL CLOSED: STEP143 RECOVERY READINESS:",e)
        sys.exit(2)

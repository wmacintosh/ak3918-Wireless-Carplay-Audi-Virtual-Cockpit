#!/usr/bin/env python3
"""Host-only Step143 symbol-provider parser and recovery safety regressions."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    instance=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


sym=load("step143_symbols","step143_audit_loader_symbols.py")
rec=load("step143_recovery","step143_recovery_readiness.py")

DYNSYM_SAMPLE="""Symbol table '.dynsym' contains 8 entries:
   Num:    Value  Size Type    Bind   Vis      Ndx Name
     0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND
     1: 00000000     0 FUNC    GLOBAL DEFAULT  UND pthread_create
     2: 00000000     0 FUNC    GLOBAL DEFAULT  UND connect
     3: 00000000     0 FUNC    WEAK   DEFAULT  UND __cxa_finalize
     4: 00001144    44 FUNC    GLOBAL DEFAULT    9 shim_screen_http_send
     5: 00001000    56 FUNC    GLOBAL HIDDEN     9 hidden_function
     6: 00000000     0 FUNC    GLOBAL DEFAULT  UND libc_function@VERSION
     7: 00000000     0 FUNC    GLOBAL DEFAULT  UND _ITM_registerTMCloneTable
"""

class Step143Host(unittest.TestCase):
    def test_exact_readelf_dynsym_export_and_undefined_parsing(self):
        req, weak, exported=sym.parse_symbols(DYNSYM_SAMPLE)
        self.assertEqual(req,{"pthread_create","connect","libc_function",
                              "_ITM_registerTMCloneTable"})
        self.assertEqual(weak,{"__cxa_finalize"})
        self.assertEqual(exported,{"shim_screen_http_send"})

    def test_resolver_separates_stock_vs_toolchain_provenance(self):
        strong={"pthread_create","connect","libc_function"}
        providers={
            "stock:sdDongle":{"native"},
            "stock:libSdCommon.so":{"connect"},
            "toolchain:libc.so.0":{"libc_function"},
            "toolchain:libpthread.so.0":{"pthread_create"},
        }
        covered,missing=sym.evaluate(providers,strong)
        self.assertEqual(missing,[])
        self.assertEqual(covered["connect"],["stock:libSdCommon.so"])
        self.assertEqual(covered["pthread_create"],
                         ["toolchain:libpthread.so.0"])
        del providers["toolchain:libpthread.so.0"]
        covered,missing=sym.evaluate(providers,strong)
        self.assertEqual(missing,["pthread_create"])
        self.assertNotIn("pthread_create",covered)

    def test_needed_soname_and_startup_bind_now_parsing(self):
        dynamic="""Dynamic section:
 0x00000001 (NEEDED) Shared library: [libc.so.0]
 0x0000000e (SONAME) Library soname: [libSdH.so]
 0x00000018 (BIND_NOW)
 0x6ffffffb (FLAGS_1) Flags: NOW
"""
        self.assertEqual(sym.parse_needed(dynamic),["libc.so.0"])
        self.assertEqual(sym.parse_soname(dynamic),"libSdH.so")
        self.assertIn("BIND_NOW",dynamic)
        self.assertIn("Flags: NOW",dynamic)

    def test_historical_installer_check_only_still_uploads(self):
        text=(ROOT/"flash_ak.py").read_text()
        line=rec.recovery_policy(text)
        self.assertGreater(line,20)
        self.assertIn('check_only, stock = "--check-only" in args',text)
        self.assertIn('resp = post_chunk(data[i*CHUNK:(i+1)*CHUNK], fn)',text)
        # A genuinely check-only-guarded post_chunk must be classified
        # differently, not implicitly called safe.
        changed=text.replace(
            '    resp = post_chunk(data[i*CHUNK:(i+1)*CHUNK], fn)',
            '    if not check_only:\n        resp = post_chunk(data[i*CHUNK:(i+1)*CHUNK], fn)',
        )
        with self.assertRaisesRegex(ValueError,"check_only guarded"):
            rec.recovery_policy(changed)

    def test_script_only_checks_pinned_offline_recovery(self):
        text=(ROOT/"scripts/step143_recovery_readiness.py").read_text()
        self.assertIn("audit_recovery_archive(source)",text)
        self.assertIn('"/cgi-bin/downfile.cgi"',text)
        self.assertIn("RECOVERY_CLASSIFICATION: CGI-dependent",text)
        self.assertIn("BLOCKED FOR FLASH",text)
        self.assertNotIn("urllib.request",text)

    def test_shell_never_mounts_writable_repo_or_uses_device_network(self):
        script=ROOT/"scripts/step143_isolated_loader_audit.sh"
        subprocess.run(["bash","-n",str(script)],check=True)
        text=script.read_text()
        self.assertIn("--network none",text)
        self.assertIn("--pull never",text)
        self.assertIn('-v "$HERE:/repo:ro"',text)
        self.assertIn('ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro',text)
        self.assertIn('export AK_STEP128_ALLOW_TEST_PACKAGE=0',text)
        self.assertIn('if build_hook.package_plan() is not None:',text)
        self.assertIn('build_hook.build_shim("libSdH.so")',text)
        self.assertNotIn("build_hook.patch_sddongle",text)
        self.assertNotIn("make_tar(",text)
        self.assertNotIn("post_chunk(",text)
        self.assertNotIn("flash_ak.py",text)
        self.assertNotIn("cgi-bin/",text)
        self.assertNotIn("docker cp ",text)
        self.assertIn('cp "$OUT" "$REPORT"',text)

    def test_source_audit_requires_exact_original_and_sysroot_separation(self):
        text=(ROOT/"scripts/step143_audit_loader_symbols.py").read_text()
        self.assertIn("digest(args.stock)==STOCK_SHA",text)
        self.assertIn('hook_needed==["libc.so.0"]',text)
        self.assertIn("actual target",text)
        self.assertIn("toolchain:libc.so.0",text)
        self.assertIn("stock:"+ '"',text)
        self.assertIn("BLOCKED FOR FLASH",text)
        self.assertNotIn("subprocess.run([str(args.hook)",text)

if __name__=="__main__":
    unittest.main(verbosity=2)

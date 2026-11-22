#!/usr/bin/env python3
"""Hermetic Step147 build policy, package validation and install-action tests.

No device network. Uses mocks and synthetic ELF byte strings; never creates or
executes real modified firmware, never calls any CGI endpoints on hardware.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts"
sys.path.insert(0,str(SCRIPTS))
import step147_validate_experimental_package as pkg
import step147_flash_experimental as flash
import step144_target_identity_readonly as identity

class FakeResp:
    def __init__(self,body,status=200):
        self.status=status
        self.body=io.BytesIO(body)
    def read(self,n): return self.body.read(n)
    def __enter__(self): return self
    def __exit__(self,*x): return False

class Client:
    def __init__(self,version=None,receipts=None):
        if version is None:
            version=(b"platform:AK3918AN\ncustom:suding\n"
                     b"system_version:20260411104900CA\n"
                     b"protocol_version:20261008165915\n")
        self.version=version
        self.receipts=receipts or []
        self.requests=[]
    def open(self,req,timeout=None):
        self.requests.append((req.get_method(),req.full_url,req.data))
        if req.full_url==identity.VERSION_URL:
            return FakeResp(self.version)
        if req.full_url.endswith("downfile.cgi"):
            response=self.receipts.pop(0) if self.receipts else b"success"
            return FakeResp(response)
        if "submition.cgi" in req.full_url:
            return FakeResp(b"install success")
        if req.full_url.endswith("reboot.cgi"):
            return FakeResp(b"success")
        raise AssertionError("unexpected URL "+req.full_url)

def synthesize_bundle(folder):
    folder=Path(folder)
    fixture={name:b"\x7fELF"+"fake-fixture-"+name.encode()
             for name in pkg.EXPECTED_ORDER}
    sha={name:hashlib.sha256(blob).hexdigest()
         for name,blob in fixture.items()}
    tar=folder/pkg.PACKAGE_NAME
    with tarfile.open(tar,"w") as tf:
        for name,blob in fixture.items():
            info=tarfile.TarInfo(name)
            info.size=len(blob)
            tf.addfile(info,io.BytesIO(blob))
    manifest=folder/pkg.MANIFEST_NAME
    data={
        "format":"ak3918-step147-stream111-test-v1",
        "package":pkg.PACKAGE_NAME,
        "sha256":hashlib.sha256(tar.read_bytes()).hexdigest(),
        "branch":pkg.EXPECTED_BRANCH,
        "commit":"a"*40,
        "features":{"AK_ENABLE_COMBINED_CLUSTER":1,"AK_ENABLE_PHONE_CMDS":1},
        "system_version":pkg.EXPECTED_SYSTEM_VERSION,
        "protocol_version":pkg.EXPECTED_PROTOCOL_VERSION,
        "members":sha,
    }
    manifest.write_text(json.dumps(data))
    return tar,manifest,sha,data


class TestPackage(unittest.TestCase):
    def test_pinned_real_firmware_hashes_are_from_step142_143(self):
        self.assertEqual(pkg.EXPECTED["sdDongle"],
          "0e63050bdd63bebb0d14f8f751b1e920f2679da375b0498a1ace06a2ba376039")
        self.assertEqual(pkg.EXPECTED["libSdH.so"],
          "6e70f606501354267567873ec75d291914a5f946a04be3730dc4f085575d1bd9")
        self.assertEqual(pkg.EXPECTED_ORDER,[
          "libSdAuto.so","libSdCommon.so","libSdSampleRate.so",
          "libSdUtils.so","sdDongle","libSdH.so"])
        self.assertEqual(pkg.PACKAGE_NAME,"ak_hook_step128_test.tar")

    def test_synthetic_tar_only_passes_with_matching_explicit_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            tar,manifest,sha,_=synthesize_bundle(d)
            with mock.patch.object(pkg,"EXPECTED",sha):
                blob,meta=pkg.validate(tar,manifest)
            self.assertEqual(blob,tar.read_bytes())
            self.assertEqual(meta["features"]["AK_ENABLE_PHONE_CMDS"],1)
            with self.assertRaisesRegex(ValueError,"independently inspected"):
                pkg.validate(tar,manifest)

    def test_wrong_feature_flag_and_manifest_digest_refused(self):
        with tempfile.TemporaryDirectory() as d:
            tar,manifest,sha,data=synthesize_bundle(d)
            with mock.patch.object(pkg,"EXPECTED",sha):
                data["features"]["AK_ENABLE_PHONE_CMDS"]=0
                manifest.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,"feature flags"):
                    pkg.validate(tar,manifest)
                data["features"]["AK_ENABLE_PHONE_CMDS"]=1
                data["sha256"]="0"*64
                manifest.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,"SHA-256 differs"):
                    pkg.validate(tar,manifest)

    def test_corrupted_member_or_extra_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tar,manifest,sha,data=synthesize_bundle(d)
            data["sha256"]=hashlib.sha256(tar.read_bytes()).hexdigest()
            with mock.patch.object(pkg,"EXPECTED",sha):
                raw=bytearray(tar.read_bytes())
                raw[512]=ord("X")
                tar.write_bytes(raw)
                data["sha256"]=hashlib.sha256(raw).hexdigest()
                manifest.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,"incorrect original"):
                    pkg.validate(tar,manifest)

    def test_wrong_package_filename_cannot_alias_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            tar,manifest,sha,data=synthesize_bundle(d)
            old=Path(d)/"ak_hook.tar"
            tar.rename(old)
            with self.assertRaisesRegex(ValueError,"archive name"):
                pkg.validate(old,manifest)

    def test_no_real_firmware_packaged_by_ci(self):
        sh=ROOT/"scripts/step147_prepare_test_archive.sh"
        subprocess.run(["bash","-n",str(sh)],check=True)
        s=sh.read_text()
        self.assertIn("--network none",s)
        self.assertIn('-v "$ROOT:/repo:ro"',s)
        self.assertIn('ak3918-buildroot-work:/workspace/buildroot-work/buildroot:ro',s)
        self.assertIn("AK_ENABLE_COMBINED_CLUSTER=1",s)
        self.assertIn("AK_ENABLE_PHONE_CMDS=1",s)
        self.assertIn('build_hook.main()',s)
        self.assertIn("step142_audit_patched_elf.py",s)
        self.assertIn("step147_validate_experimental_package.py",s)
        self.assertIn('[[ -d "$(dirname "$OUT")" && ! -e "$OUT" ]]',s)
        self.assertNotIn("flash_ak.py",s)
        self.assertNotIn("submition.cgi",s)
        self.assertNotIn("downfile.cgi",s)


class TestInstaller(unittest.TestCase):
    def test_probe_no_post_or_install(self):
        client=Client()
        fake_blob=b"synthetic-test"
        record={"sha256":hashlib.sha256(fake_blob).hexdigest(),"commit":"a"*40}
        with mock.patch.object(flash,"validate",return_value=(fake_blob,record)):
            with redirect_stdout(io.StringIO()):
                ret=flash.main(["--probe"],client=client,input_func=lambda _:self.fail("prompt"))
        self.assertEqual(ret,0)
        self.assertEqual([x[0] for x in client.requests],["GET"])
        self.assertEqual(client.requests[0][1],identity.VERSION_URL)
        self.assertIsNone(client.requests[0][2])

    def test_wrong_physical_system_version_aborts_before_prompt(self):
        client=Client(version=b"platform:AK3918AN\ncustom:suding\n"
                              b"system_version:different\n"
                              b"protocol_version:20261008165915\n")
        with mock.patch.object(flash,"validate",return_value=(b"synthetic",{"sha256":"x","commit":"a"*40})):
            with redirect_stdout(io.StringIO()):
                ret=flash.main(["--install"],client=client,
                               input_func=lambda _:self.fail("prompt must not run"))
        self.assertEqual(ret,2)
        self.assertEqual([x[0] for x in client.requests],["GET"])

    def test_install_wrong_confirmation_does_not_upload(self):
        client=Client()
        with mock.patch.object(flash,"validate",return_value=(b"x"*40960,{"sha256":"x","commit":"a"*40})):
            with redirect_stdout(io.StringIO()):
                ret=flash.main(["--install"],client=client,
                               input_func=lambda _:"yes")
        self.assertEqual(ret,2)
        self.assertEqual([x[0] for x in client.requests],["GET"])

    def test_explicit_consent_uploads_with_stock_cgi_wire_name(self):
        client=Client(receipts=[b"success",b"success",b"file check success"])
        image=b"x"*23000
        with mock.patch.object(flash,"validate",return_value=(image,{"sha256":"x","commit":"a"*40})):
            with redirect_stdout(io.StringIO()):
                ret=flash.main(["--install"],client=client,
                               input_func=lambda _:"FLASH STREAM111 AT MY RISK")
        self.assertEqual(ret,0)
        methods=[x[0] for x in client.requests]
        self.assertEqual(methods,["GET","POST","POST","POST","GET","GET"])
        paths=[x[1] for x in client.requests]
        self.assertTrue(all(x.endswith("downfile.cgi") for x in paths[1:4]))
        self.assertEqual(paths[4],"http://192.168.200.1/cgi-bin/submition.cgi?filename=ak_hook&")
        self.assertEqual(paths[5],"http://192.168.200.1/cgi-bin/reboot.cgi")
        for method,url,data in client.requests[1:4]:
            self.assertTrue(b'filename="ak_hook' in data)

    def test_missing_final_integrity_never_installs(self):
        client=Client(receipts=[b"success",b"success",b"success"])
        with redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,"archive integrity"):
                flash.install(client,b"x"*24000)
        self.assertEqual([x[0] for x in client.requests],["POST","POST","POST"])
        self.assertTrue(all("submition.cgi" not in x[1] for x in client.requests))

    def test_wrong_final_response_aborts_without_cgi_install(self):
        client=Client(receipts=[b"success",b"success",b"error"])
        with redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,"not accepted"):
                flash.install(client,b"x"*24000)
        self.assertEqual(len(client.requests),3)

    def test_no_legacy_archive_selected(self):
        code=(ROOT/"scripts/step147_flash_experimental.py").read_text()
        self.assertNotIn("ak_hook.tar", "\n".join(
            line for line in code.splitlines() if not line.lstrip().startswith("#") and
            not line.lstrip().startswith('"""') and "installer NEVER" not in line
        ))
        self.assertIn("validate(",code)
        self.assertIn("FLASH STREAM111 AT MY RISK",code)
        self.assertIn('group(required=True)',code)

if __name__=="__main__":
    unittest.main(verbosity=2)

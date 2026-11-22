#!/usr/bin/env python3
"""Hermetic Step144 read-only device fingerprint tests. NO NETWORK REQUESTS."""
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import urllib.error
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"scripts/step144_target_identity_readonly.py"
spec=importlib.util.spec_from_file_location("step144_identity",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeResponse:
    def __init__(self,payload,status=200):
        self.status=status
        self.buffer=io.BytesIO(payload)
        self.limit=None
    def read(self,size):
        self.limit=size
        return self.buffer.read(size)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


class FakeOpener:
    def __init__(self,payload=None,status=200,error=None):
        self.response=FakeResponse(payload or b"",status)
        self.error=error
        self.calls=[]
    def open(self,request,timeout=None):
        self.calls.append((request,timeout))
        if self.error:
            raise self.error
        return self.response


IDENTITY=(
    b"system_version:20261008165915\n"
    b"protocol_version:20260901\n"
    b"product_Model:something\n"
    b"custom:suding\n"
    b"platform:AK3918AN\n"
)


class ExactTargetIdentity(unittest.TestCase):
    def test_default_no_network_even_when_opener_passed(self):
        op=FakeOpener(IDENTITY)
        out=io.StringIO()
        with redirect_stdout(out):
            status=mod.run([],op)
        self.assertEqual(status,0)
        self.assertEqual(op.calls,[])
        self.assertIn("NO NETWORK REQUEST MADE",out.getvalue())

    def test_single_opt_in_get_uses_exact_known_host_and_url(self):
        op=FakeOpener(IDENTITY)
        out=io.StringIO()
        with redirect_stdout(out):
            code=mod.run(["--probe-version"],op)
        self.assertEqual(code,0)
        self.assertEqual(len(op.calls),1)
        req,timeout=op.calls[0]
        self.assertEqual(req.full_url,"http://192.168.200.1/cgi-bin/getversion.cgi")
        self.assertEqual(req.get_method(),"GET")
        self.assertIsNone(req.data)
        self.assertEqual(timeout,4)
        self.assertEqual(op.response.limit,4097)
        self.assertIn("PASS: STEP144 READ-ONLY HTTP DEVICE IDENTITY",out.getvalue())
        self.assertIn("DEVICE platform=AK3918AN",out.getvalue())
        self.assertIn("DEVICE custom=suding",out.getvalue())

    def test_no_redirect_even_if_another_host_is_supplied(self):
        handler=mod.NoRedirect()
        self.assertIsNone(handler.redirect_request(
            None,None,302,"Found",{},"http://example.com/fake"
        ))

    def test_wrong_platform_or_vendor_rejected(self):
        for bad in (
            IDENTITY.replace(b"AK3918AN",b"AX1800M"),
            IDENTITY.replace(b"custom:suding",b"custom:another"),
            b"hello there",
            b"platform:AK3918AN\n",
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError,"expected AK3918AN/Suding"):
                    mod.parse_identity(bad)

    def test_oversized_binary_or_non_200_rejected(self):
        for bad in (b"x"*4097,b"platform:AK3918AN\x00\ncustom:suding\n"):
            with self.assertRaisesRegex(ValueError,"unexpected CGI"):
                mod.parse_identity(bad)
        op=FakeOpener(IDENTITY,status=301)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(mod.run(["--probe-version"],op),2)
        self.assertEqual(len(op.calls),1)

    def test_unexpected_cgi_error_remains_fail_closed(self):
        op=FakeOpener(error=urllib.error.URLError("unreachable"))
        out=io.StringIO()
        with redirect_stdout(out):
            code=mod.run(["--probe-version"],op)
        self.assertEqual(code,2)
        self.assertEqual(len(op.calls),1)
        self.assertIn("FAIL CLOSED",out.getvalue())

    def test_only_identity_fields_appear_not_serial_or_secrets(self):
        payload=(IDENTITY+
                 b"serial_number:secret-12345\n"
                 b"mac:12:34:56:78\n"
                 b"device_key:should-not-display\n")
        op=FakeOpener(payload)
        out=io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(mod.run(["--probe-version"],op),0)
        result=out.getvalue()
        self.assertNotIn("secret-12345",result)
        self.assertNotIn("12:34:56:78",result)
        self.assertNotIn("should-not-display",result)

    def test_duplicate_metadata_fails_closed_to_first_value(self):
        self.assertEqual(
            mod.parse_identity(IDENTITY+b"platform:AX1800M\n")["platform"],
            "AK3918AN"
        )
        with self.assertRaisesRegex(ValueError,"expected AK3918AN/Suding"):
            mod.parse_identity(b"platform:AX1800M\ncustom:suding\n"+IDENTITY)

    def test_no_execution_or_mutation_apis(self):
        script=PATH.read_text()
        self.assertNotIn("urllib.request.urlopen(",script)
        self.assertNotIn('method="POST"',script)
        self.assertNotIn("subprocess",script)
        self.assertNotIn("os.system",script)
        self.assertNotIn("write_bytes(",script)
        self.assertNotIn("write_text(",script)
        self.assertNotIn("cgi-bin/downfile.cgi",script)
        self.assertNotIn("cgi-bin/submition.cgi",script)
        self.assertNotIn("cgi-bin/reboot.cgi",script)
        self.assertNotIn("flush",script)

if __name__=="__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Step145 vendor archive provenance and safe-string inventory negative controls."""
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
PATH=ROOT/"scripts/step145_stock_recovery_inventory.py"
spec=importlib.util.spec_from_file_location("step145",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def create_fake(path, body=None, extra=False):
    original=b"synthetic-not-a-firmware-ELF AK3918AN U-Boot secret=superprivate"
    if body is None: body=original
    contents={name:(body if name=="sdDongle" else b"fake "+name.encode())
              for name in mod.REQUIRED_MEMBERS}
    if extra:
        contents["root.sqsh4"]=b"NOT A VERIFIED ROOTFS"
    with tarfile.open(path,"w") as tar:
        for name,data in contents.items():
            m=tarfile.TarInfo(name)
            m.size=len(data)
            tar.addfile(m,io.BytesIO(data))
    return (hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(body).hexdigest())


class Step145RecoveryArchive(unittest.TestCase):
    def test_pinned_real_stock_archive_exact_five_members(self):
        path=ROOT/mod.RECOVERY_NAME
        self.assertTrue(path.exists())
        counts,sizes,hashes=mod.audit_archive(path)
        self.assertEqual(set(counts),set(mod.REQUIRED_MEMBERS))
        self.assertEqual(set(sizes),set(mod.REQUIRED_MEMBERS))
        self.assertEqual(hashes["sdDongle"],mod.STOCK_SHA256)
        self.assertTrue(all(n>0 for n in sizes.values()))
        self.assertTrue(all(type(n) is int and n>=0
                            for sub in counts.values() for n in sub.values()))

    def test_synthetic_dongle_marker_no_secret_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.tar"
            t_sha,stock_sha=create_fake(path)
            counts,sizes,hashes=mod.audit_archive(
                path,archive_sha=t_sha,stock_sha=stock_sha)
            self.assertEqual(counts["sdDongle"]["AK3918AN"],1)
            self.assertEqual(counts["sdDongle"]["U-Boot label"],1)
            self.assertNotIn("superprivate",str(counts))
            self.assertNotIn("superprivate",str(sizes))
            self.assertEqual(sorted(Path(temp).iterdir()),[path])
            self.assertEqual(hashes["sdDongle"],stock_sha)

    def test_wrong_tar_digest_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.tar"
            _tar_sha,stock_sha=create_fake(path)
            with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
                mod.audit_archive(path,archive_sha="0"*64,stock_sha=stock_sha)

    def test_wrong_stock_digest_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.tar"
            tar_sha,_=create_fake(path)
            with self.assertRaisesRegex(ValueError,"original sdDongle differs"):
                mod.audit_archive(path,archive_sha=tar_sha,stock_sha="0"*64)

    def test_extra_embedded_fullflash_name_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.tar"
            tar_sha,stock_sha=create_fake(path,extra=True)
            with self.assertRaisesRegex(ValueError,"additional members"):
                mod.audit_archive(path,archive_sha=tar_sha,stock_sha=stock_sha)

    def test_no_network_mutation_or_raw_string_dumps(self):
        s=PATH.read_text()
        for forbidden in ("urllib", "requests", "socket.connect", "subprocess",
                          ".write_bytes(", ".write_text(", "extractall(",
                          "tar.extract(", "os.system(", "flash_ak.py", "post_chunk(",
                          "reboot.cgi", "downfile.cgi", "submition.cgi"):
            self.assertNotIn(forbidden,s)
        self.assertIn('blob.count(needle)',s)
        self.assertIn("MARKERS = OrderedDict",s)
        self.assertIn("PACKAGE_SCOPE=five application/vendor ELF files only",s)
        self.assertIn("BLOCKED FOR FLASH",s)
        self.assertNotIn("print(blob",s)

if __name__=="__main__":
    unittest.main(verbosity=2)

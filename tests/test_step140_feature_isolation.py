#!/usr/bin/env python3
"""Step 140 source-only stock/combined hook isolation checks.

Preprocessing and AST inspection only. Never executes patch_sddongle(),
build_hook.main(), packages, modifies stock ELF, or contacts dongle.
"""
import ast
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"altscreen.c"
BUILDER=ROOT/"build_hook.py"

def name(node):
    return node.id if isinstance(node,ast.Name) else None

class HookIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=C.read_text()
        cls.builder=BUILDER.read_text()
        cls.py=ast.parse(cls.builder)
        cls.patch=next(
            x for x in cls.py.body if isinstance(x,ast.FunctionDef)
            and x.name=="patch_sddongle"
        )

    @staticmethod
    def calls(node,callee):
        return [x for x in ast.walk(node)
                if isinstance(x,ast.Call) and name(x.func)==callee]

    def test_stock_hook_instruction_words_and_callback_identity(self):
        for m in [
            r"STREAM_HOOK_BL_VA = 0x0002FADC",
            r"STREAM_HOOK_OLD_BL = 0xEB018DE6",
            r"SEND_HOOK_BL_VA = 0x0002FBB0",
            r"SEND_HOOK_OLD_BL = 0xEB01DB6F",
            r"STREAM_HOOK_PTR_VA = 0x0013C644",
            r"SEND_HOOK_PTR_VA = 0x0013C648",
        ]:
            self.assertRegex(self.builder,m)
        self.assertIn("#define STOCK_SCREEN_RESPONSE_VA 0x0002ec7cu",self.c)
        self.assertIn("#define CLUSTER_STREAM_TYPE     0x6f",self.c)
        self.assertIn("#define CLUSTER_W               1440",self.c)
        self.assertIn("#define CLUSTER_H               542",self.c)

    def test_both_screen_hooks_only_inside_opt_in_branch(self):
        guarded=[x for x in ast.walk(self.patch)
                 if isinstance(x,ast.If) and name(x.test)=="ENABLE_COMBINED_CLUSTER"]
        self.assertEqual(len(guarded),1)
        body=guarded[0]
        calls=self.calls(self.patch,"install_screen_hook")
        self.assertEqual(len(calls),2)
        self.assertEqual(len(self.calls(body,"install_screen_hook")),2)
        arguments=[tuple(name(y) for y in x.args[:3])
                   for x in self.calls(body,"install_screen_hook")]
        self.assertEqual(set(arguments),{
            ("STREAM_HOOK_BL_VA","STREAM_HOOK_OLD_BL","STREAM_HOOK_PTR_VA"),
            ("SEND_HOOK_BL_VA","SEND_HOOK_OLD_BL","SEND_HOOK_PTR_VA"),
        })
        self.assertEqual(len(body.orelse),0)

    def test_combined_feature_false_does_not_install_both_screen_entries(self):
        def preprocess(combined):
            return subprocess.check_output(
                ["cc","-E","-P",f"-DAK_ENABLE_COMBINED_CLUSTER={combined}",
                 "-DAK_ENABLE_PHONE_CMDS=0",str(C)],text=True,timeout=20)
        off=preprocess(0)
        on=preprocess(1)
        for text in ("void shim_screen_ensure_stream(void **streams, void *stock_video)",
                     "int shim_screen_http_send(void *client, void *msg)",
                     "*stream_slot = (void *)&shim_screen_ensure_stream",
                     "*send_slot = (void *)&shim_screen_http_send"):
            self.assertNotIn(text,off)
            self.assertIn(text,on)
        # The normal setup and session-finalizer hooks remain present in both
        # modes; this is *screen-111 isolation*, not a bitwise-stock ELF claim.
        self.assertIn("void shim_session_finalize(void *session)",off)
        self.assertIn("void shim_session_finalize(void *session)",on)

    def test_no_combined_transport_from_unpaired_stock_request(self):
        # The source-derived C integration test is the executable check;
        # this check ensures the feature-off path cannot even define it.
        on=self.c.split("void shim_screen_ensure_stream(",1)[1]
        self.assertIn("cf_arr_ensure(streams, stock_video);",on)
        self.assertIn("if (!streams || !*streams || *GPAIRVERIFY_HK != 0) return;",on)
        self.assertIn("if (!gen) return;",on)
        self.assertIn("g_combo_build[build_slot].message = native_msg;",on)
        self.assertIn("g_combo_request[i].canceled = 1;",self.c)

if __name__=="__main__":
    unittest.main(verbosity=2)

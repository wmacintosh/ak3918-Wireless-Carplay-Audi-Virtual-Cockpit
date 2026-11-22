#!/usr/bin/env python3
"""Step 130: source-derived session switch / phone-command lifetime regression.

Compile the actual leading lock/state transition from shim_session_setup for
both feature modes. Simulates a phone command already admitted against the
old session, then verifies the old session remains published until the command
releases its lifetime gate. This is not a target-device runtime test.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "altscreen.c").read_text()
start_marker = "int shim_session_setup(void *session, void *req, void **resp_out) {"
end_marker = "    if (session_changed) {"
if src.count(start_marker) != 1:
    raise RuntimeError("Expected exactly one native session setup wrapper")
start = src.index(start_marker)
end = src.index(end_marker, start)
prologue = src[start:end]
# Preserve the actual function prologue, including its lock/state writes and
# cond_wait, without compiling unrelated CoreFoundation/vendor function calls.
prologue = prologue.replace(
    start_marker,
    "static unsigned shim_session_transition_under_test(void *session) {\n"
)
prologue += "    (void)session_changed;\n    return generation;\n}\n"
for required in (
    "g_session_valid = 0;",
    "while (g_session_cmd_inflight > 0)",
    "pthread_cond_wait(&g_session_cv, &g_state_lock)",
    "g_session = session;",
    "g_session_generation++;",
    "combo_wait_sends_drained_locked();",
):
    if required not in prologue:
        raise RuntimeError("Missing transition safeguard: " + required)
if prologue.index("g_session = session;") < prologue.index("while (g_session_cmd_inflight > 0)"):
    raise RuntimeError("Session pointer must remain old during command drain")

test = r'''
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#define CHECK(cond) do { if (!(cond)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #cond); exit(1); \
} } while (0)

static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_session_cv = PTHREAD_COND_INITIALIZER;
static void *g_session = (void *)(uintptr_t)0x1000;
static int g_session_valid = 1;
static int g_session_cmd_inflight = 1;
static unsigned g_session_generation = 80;
static unsigned g_combo_inflight_generation = 80;
static int g_cancel_builds = 0, g_cancel_requests = 0;
static void combo_cancel_all_builds_locked(void) { ++g_cancel_builds; }
static void combo_cancel_all_requests_locked(void) { ++g_cancel_requests; }
static void combo_wait_sends_drained_locked(void) {}

/* Only the exact source-code leading block is inserted here. */
{{PROLOGUE}}

static void *switch_thread(void *ctx) {
    unsigned actual = shim_session_transition_under_test(ctx);
    CHECK(actual == 81);
    return NULL;
}

int main(void) {
    pthread_t t;
    CHECK(pthread_create(&t, NULL, switch_thread,
                         (void *)(uintptr_t)0x2000) == 0);
    int saw_invalidation = 0;
    for (int i = 0; i < 2000; ++i) {
        pthread_mutex_lock(&g_state_lock);
        saw_invalidation = !g_session_valid;
        if (saw_invalidation) {
            /* Crucial: an old-session finalizer sees the active pointer and
               can wait on the outstanding phone command before freeing it. */
            CHECK(g_session == (void *)(uintptr_t)0x1000);
            CHECK(g_session_cmd_inflight == 1);
        }
        pthread_mutex_unlock(&g_state_lock);
        if (saw_invalidation) break;
        usleep(1000);
    }
    CHECK(saw_invalidation);

    pthread_mutex_lock(&g_state_lock);
    CHECK(g_session == (void *)(uintptr_t)0x1000);
    g_session_cmd_inflight = 0;
    pthread_cond_broadcast(&g_session_cv);
    pthread_mutex_unlock(&g_state_lock);
    CHECK(pthread_join(t, NULL) == 0);

    pthread_mutex_lock(&g_state_lock);
    CHECK(g_session == (void *)(uintptr_t)0x2000);
    CHECK(g_session_generation == 81);
    CHECK(g_session_valid == 0); /* No SETUP success yet. */
#if AK_ENABLE_COMBINED_CLUSTER
    CHECK(g_cancel_builds == 1 && g_cancel_requests == 1);
    CHECK(g_combo_inflight_generation == 0);
#else
    CHECK(g_cancel_builds == 0 && g_cancel_requests == 0);
#endif
    pthread_mutex_unlock(&g_state_lock);

    puts("PASS Step 130: old session retained during in-flight phone command");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="ak3918-step130-") as tmp:
    cpath = Path(tmp) / "step130.c"
    for combined in (0, 1):
        code = (test.replace("{{PROLOGUE}}", prologue))
        cpath.write_text(code)
        executable = Path(tmp) / f"step130_{combined}"
        cmd = [
            "cc", "-std=gnu11", "-O1", "-g", "-pthread", "-Wall", "-Wextra",
            "-Werror", "-Wno-unused-function", "-DAK_ENABLE_COMBINED_CLUSTER=" +
            str(combined), str(cpath), "-o", str(executable),
        ]
        subprocess.run(cmd, check=True)
        subprocess.run([str(executable)], check=True, timeout=10,
                       env=dict(os.environ))
print("PASS: native source-derived session switch guarded for combined=0/1")

#!/usr/bin/env python3
"""Step 132 source-derived canceled callback / reconnect saturation stress.

The stock HTTP request metadata helpers are compiled from the actual shim
source, not copied into the harness. This tests conservative callback ownership,
NOT the timing, dispatch, or error behavior of native hardware.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "altscreen.c").read_text()
start = source.index("struct combo_build {")
stop_marker = "/* END STEP115 REQUEST HELPERS */"
stop = source.index(stop_marker, start) + len(stop_marker)
helpers = source[start:stop]

response = source.split("static void shim_screen_response(void *msg) {", 1)[1]
response = response.split("static ", 1)[0]
if not (response.index("combo_consume_response_locked(msg, &gen, &connid)") <
        response.index("STOCK_SCREEN_RESPONSE_VA)(msg)")):
    raise RuntimeError("Original stock callback no longer follows shim response claim")
if "combo_cancel_all_requests_locked();" not in source:
    raise RuntimeError("Session invalidation no longer cancels combined records")
if "return 0; /* Fail closed if callbacks never arrive and slots fill. */" not in helpers:
    raise RuntimeError("Request capacity limit is no longer fail-closed")

test = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#define COMBINED_REQUEST_LIMIT 8

static unsigned g_session_generation;
static int g_session_valid;
static void *g_session;
{{HELPERS}}
#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr, "Step132 FAIL line %d: %s\n", __LINE__, #expr); \
    exit(1); } } while (0)

static void activate(unsigned generation) {
    g_session_generation = generation;
    g_session_valid = 1;
    g_session = (void *)(uintptr_t)0x5000;
}
static void invalidate(void) {
    g_session_valid = 0;
    g_session = NULL;
    ++g_session_generation;
    combo_cancel_all_requests_locked();
}
static int used(void) {
    int n=0;
    for (int i=0; i<COMBINED_REQUEST_LIMIT; ++i)
        n+=g_combo_request[i].in_use != 0;
    return n;
}
static void callback(void *msg, unsigned expected_gen, uint64_t expected_conn) {
    unsigned gen = 123456;
    uint64_t conn = 123456;
    combo_consume_response_locked(msg, &gen, &conn);
    CHECK(gen==expected_gen);
    CHECK(conn==expected_conn);
}
int main(void) {
    uint64_t tickets[COMBINED_REQUEST_LIMIT] = {0};
    void *msg[COMBINED_REQUEST_LIMIT];
    void *ninth = (void *)(uintptr_t)0x7000;
    activate(500);
    for (int i=0; i<COMBINED_REQUEST_LIMIT; ++i) {
        msg[i]=(void *)(uintptr_t)(0x10000 + i*0x100);
        CHECK(combo_claim_request_locked(msg[i], 500, 3000+i, &tickets[i]));
    }
    CHECK(used()==COMBINED_REQUEST_LIMIT);
    CHECK(!combo_claim_request_locked(ninth,500,999,&tickets[0]));
    CHECK(!combo_claim_request_locked(msg[0],500,999,&tickets[0]));

    /* Teardown is not permission to discard callbacks: queue may still hold
     * retained message refs and a later callback may use those same pointers. */
    invalidate();
    CHECK(used()==COMBINED_REQUEST_LIMIT);
    activate(502);
    CHECK(!combo_claim_request_locked(ninth,502,999,&tickets[0]));
    CHECK(!combo_claim_request_locked(msg[0],502,999,&tickets[0]));

    /* Native callbacks in reverse order free slots; old generations must
     * never start a new transport, even though the new session is valid. */
    for (int i=COMBINED_REQUEST_LIMIT-1; i>=0; --i) {
        callback(msg[i],0,0);
        CHECK(used()==i);
    }
    CHECK(combo_claim_request_locked(msg[0],502,9876,&tickets[0]));
    callback(msg[0],502,9876);
    CHECK(used()==0);

    /* Repeated reconnects are safe when callbacks are eventually delivered.
     * Validate pointer reuse only AFTER the old message's callback. */
    for (unsigned cycle=0; cycle<128; ++cycle) {
        unsigned old_gen=600+cycle*2;
        activate(old_gen);
        for (int i=0; i<COMBINED_REQUEST_LIMIT; ++i)
            CHECK(combo_claim_request_locked(msg[i],old_gen,4000+i,
                                             &tickets[i]));
        invalidate();
        activate(old_gen+2);
        CHECK(!combo_claim_request_locked(ninth,old_gen+2,1,&tickets[0]));
        for (int i=0; i<COMBINED_REQUEST_LIMIT; ++i) {
            callback(msg[i],0,0);
            CHECK(combo_claim_request_locked(msg[i],old_gen+2,8000+i,
                                             &tickets[i]));
            callback(msg[i],old_gen+2,8000+i);
        }
        CHECK(used()==0);
    }

    /* Do not invent a timeout. No callback = the 8-slot table remains full
     * after any number of new session attempts, a safe availability failure. */
    activate(9000);
    for (int i=0; i<COMBINED_REQUEST_LIMIT; ++i)
        CHECK(combo_claim_request_locked(msg[i],9000,999+i,&tickets[i]));
    for (int generation=9001; generation<9100; ++generation) {
        invalidate();
        activate(generation);
        CHECK(used()==COMBINED_REQUEST_LIMIT);
        CHECK(!combo_claim_request_locked(ninth,generation,25,&tickets[0]));
    }
    /* Callback observed -> tombstone can be released even after saturation. */
    for (int i=0; i<COMBINED_REQUEST_LIMIT; ++i)
        callback(msg[i],0,0);
    CHECK(used()==0);
    CHECK(combo_claim_request_locked(ninth,9100,555,&tickets[0]));
    callback(ninth,0,0); /* generation deliberately not 9100 -> rejected */
    CHECK(used()==0);

    puts("PASS Step 132: 128 reconnects, cancel+late callbacks, no unproven timeout reclamation");
    return 0;
}
'''
code = test.replace("{{HELPERS}}",helpers)
with tempfile.TemporaryDirectory(prefix="ak3918-step132-") as tmp:
    cpath = Path(tmp)/"callback_reconnect.c"
    cpath.write_text(code)
    for name,extra in (
        ("ubsan",["-fsanitize=undefined"]),
        ("normal",[]),
    ):
        exe = Path(tmp)/("run_"+name)
        cmd=["cc","-std=gnu11","-O1","-g","-Wall","-Wextra","-Werror",
             "-Wno-unused-function","-pthread"] + extra + [str(cpath),"-o",str(exe)]
        subprocess.run(cmd,check=True)
        subprocess.run([str(exe)],check=True,timeout=12,
                       env=dict(os.environ,UBSAN_OPTIONS="halt_on_error=1"))
print("PASS: Step 132 host stress compiles actual request-tracking source helpers.")

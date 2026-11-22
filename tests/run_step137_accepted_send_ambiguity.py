#!/usr/bin/env python3
"""Step 137 source-derived host negative control for indistinguishable rc==0.

The *real* C tracking helpers are compiled from altscreen.c. Native queue
execution is only MODELED from pinned stock ARM evidence, not emulated.
Two native possibilities (work node inserted vs calloc dropped) expose the
same wrapper return and metadata until an actual callback is observed.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "altscreen.c").read_text()
start = source.index("struct combo_build {")
end_marker = "/* END STEP115 REQUEST HELPERS */"
stop = source.index(end_marker, start) + len(end_marker)
helpers = source[start:stop]
start = source.index("static int g_combo_send_inflight = 0;")
end_marker = "/* END STEP128 SEND ADMISSION GATE */"
stop = source.index(end_marker, start) + len(end_marker)
sends = source[start:stop]
send_wrapper = source.split("int shim_screen_http_send(void *client, void *msg) {", 1)[1]
send_wrapper = send_wrapper.split("static int combined_response_port(", 1)[0]

assert "if (rc != 0)" in sends
assert "combo_forget_never_submitted_locked(ticket)" in sends
assert "int rc = http_send(client, msg)" in send_wrapper
assert "combo_send_leave_locked(rc, gen, ticket)" in send_wrapper
assert "return rc;" in send_wrapper
assert "return 0; /* Fail closed if callbacks never arrive" in helpers
assert "combo_cancel_all_requests_locked();" in source

harness = r'''
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define COMBINED_REQUEST_LIMIT 8

static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_session_cv = PTHREAD_COND_INITIALIZER;
static unsigned g_session_generation;
static int g_session_valid;
static void *g_session;

{{REAL_REQUEST_HELPERS}}
{{REAL_SEND_HELPERS}}

#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr,"Step137 FAIL %s:%d: %s\n",__FILE__,__LINE__,#expr); \
    exit(1); } } while (0)

static void begin_independent_test(unsigned gen) {
    /* This reset is a TEST FIXTURE ONLY, never an allowed production cleanup. */
    memset(g_combo_request,0,sizeof g_combo_request);
    memset(g_combo_build,0,sizeof g_combo_build);
    g_combo_next_ticket=0;
    g_combo_inflight_generation=gen;
    g_combo_send_inflight=0;
    g_session_generation=gen;
    g_session_valid=1;
    g_session=(void *)(uintptr_t)0x4000;
}

static int used(void) {
    int count=0;
    for(int i=0;i<COMBINED_REQUEST_LIMIT;++i)
        count+=g_combo_request[i].in_use!=0;
    return count;
}

static uint64_t accepted_send(void *msg,unsigned gen,uint64_t conn,int rc) {
    uint64_t ticket=0;
    CHECK(combo_claim_request_locked(msg,gen,conn,&ticket)==1);
    CHECK(ticket!=0);
    combo_send_enter_locked();
    combo_send_leave_locked(rc,gen,ticket);
    CHECK(g_combo_send_inflight==0);
    return ticket;
}

static void stop_session(void) {
    g_session_valid=0;
    g_session=NULL;
    ++g_session_generation;
    combo_cancel_all_requests_locked();
}

static void start_new_session(unsigned gen) {
    g_session_generation=gen;
    g_session_valid=1;
    g_session=(void *)(uintptr_t)0x5000;
}

static void response(void *msg,unsigned wanted_gen,uint64_t wanted_conn) {
    unsigned gen=99999;
    uint64_t conn=99999;
    combo_consume_response_locked(msg,&gen,&conn);
    CHECK(gen==wanted_gen);
    CHECK(conn==wanted_conn);
}

static void test_same_visible_acceptance_for_two_native_paths(void) {
    struct combo_request late_queued[COMBINED_REQUEST_LIMIT];
    struct combo_request failed_alloc[COMBINED_REQUEST_LIMIT];
    const void *msg=(void *)(uintptr_t)0x10000;
    /* Scenario A: native calloc succeeds, callback is still delayed.
       Actual source sees only http_send(rc=0). */
    begin_independent_test(11);
    accepted_send((void *)msg,11,111,0);
    memcpy(late_queued,g_combo_request,sizeof late_queued);

    /* Scenario B: native calloc fails; dispatcher drops the request.
       Actual source still sees exactly the same http_send(rc=0). */
    begin_independent_test(11);
    accepted_send((void *)msg,11,111,0);
    memcpy(failed_alloc,g_combo_request,sizeof failed_alloc);
    CHECK(memcmp(late_queued,failed_alloc,sizeof late_queued)==0);
    CHECK(used()==1);
    puts("PASS: delayed enqueue and failed calloc yield identical shim records");
}

static void test_eight_missing_callbacks_remain_fail_closed(void) {
    begin_independent_test(21);
    for(int i=0;i<COMBINED_REQUEST_LIMIT;i++){
        void *msg=(void *)(uintptr_t)(0x10000u+i*0x100u);
        accepted_send(msg,21,(uint64_t)(1000+i),0);
    }
    CHECK(used()==COMBINED_REQUEST_LIMIT);
    stop_session();
    start_new_session(23);
    uint64_t tmp=0;
    CHECK(combo_claim_request_locked((void *)(uintptr_t)0x70000,23,2222,&tmp)==0);
    CHECK(combo_claim_request_locked((void *)(uintptr_t)0x10000,23,2222,&tmp)==0);
    for(int i=0;i<COMBINED_REQUEST_LIMIT;i++) {
        CHECK(g_combo_request[i].in_use);
        CHECK(g_combo_request[i].canceled);
    }
    puts("PASS: eight missing callbacks exhaust only optional combined capacity");
}

static void test_delayed_old_callback_reclaims_only_its_own_ticket(void) {
    const void *msg=(void *)(uintptr_t)0x20000;
    begin_independent_test(31);
    accepted_send((void *)msg,31,333,0);
    stop_session();
    start_new_session(33);
    uint64_t next=0;
    CHECK(!combo_claim_request_locked((void *)msg,33,444,&next));
    CHECK(used()==1);
    response((void *)msg,0,0); /* Old, canceled; no new-session transport. */
    CHECK(used()==0);
    CHECK(combo_claim_request_locked((void *)msg,33,444,&next));
    CHECK(used()==1);
    response((void *)msg,33,444);
    CHECK(used()==0);
    puts("PASS: late canceled callback cannot mutate new session");
}

static void test_premature_reclaim_is_a_deliberately_unsafe_negative_control(void) {
    const void *msg=(void *)(uintptr_t)0x30000;
    begin_independent_test(41);
    uint64_t old_ticket=accepted_send((void *)msg,41,555,0);
    stop_session();
    start_new_session(43);
    /* UNSAFE EXPERIMENT: pretending rc==0 proves no queued work.
       Actual shim NEVER does this; old callback could arrive after reuse. */
    combo_forget_never_submitted_locked(old_ticket);
    uint64_t new_ticket=0;
    CHECK(combo_claim_request_locked((void *)msg,43,777,&new_ticket));
    CHECK(new_ticket!=old_ticket);
    unsigned wrong_gen=0;
    uint64_t wrong_conn=0;
    /* A late callback for the OLD request consumes the NEW record. */
    combo_consume_response_locked((void *)msg,&wrong_gen,&wrong_conn);
    CHECK(wrong_gen==43 && wrong_conn==777);
    CHECK(used()==0);
    puts("EXPECTED UNSAFE: premature cleanup lets stale callback steal new ticket");
}

static void test_nonzero_native_prep_error_is_safely_reclaimable(void) {
    begin_independent_test(51);
    accepted_send((void *)(uintptr_t)0x40000,51,888,-123);
    CHECK(used()==0);
    puts("PASS: native nonzero pre-dispatch error reclaims exact ticket");
}

int main(void) {
    test_same_visible_acceptance_for_two_native_paths();
    test_eight_missing_callbacks_remain_fail_closed();
    test_delayed_old_callback_reclaims_only_its_own_ticket();
    test_premature_reclaim_is_a_deliberately_unsafe_negative_control();
    test_nonzero_native_prep_error_is_safely_reclaimable();
    return 0;
}
'''
code = harness.replace("{{REAL_REQUEST_HELPERS}}", helpers).replace(
    "{{REAL_SEND_HELPERS}}", sends
)
with tempfile.TemporaryDirectory(prefix="ak3918-step137-") as tmp:
    cpath = Path(tmp) / "accepted_send_ambiguity.c"
    cpath.write_text(code)
    for mode, flags in (("normal", []), ("ubsan", ["-fsanitize=undefined"])):
        exe = Path(tmp) / ("run_" + mode)
        command = [
            "cc","-std=gnu11","-O1","-g","-Wall","-Wextra","-Werror",
            "-Wno-unused-function","-pthread",
        ] + flags + [str(cpath),"-o",str(exe)]
        subprocess.run(command,check=True,timeout=20)
        subprocess.run(
            [str(exe)],check=True,timeout=15,
            env=dict(os.environ, UBSAN_OPTIONS="halt_on_error=1"),
        )
print("PASS: Step137 real source helper negative controls (normal + UBSan)")

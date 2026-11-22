#!/usr/bin/env python3
"""Exercise actual compiled send AND teardown entrypoints from altscreen.c.

Uses stock transport stubs and host pthreads; no hardware or binary patching.
Unlike Step 128's helper-only test, both public shim entrypoint bodies are
compiled from source, not reimplemented by the test harness.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "altscreen.c").read_text()

def section(start, end):
    if source.count(start) != 1:
        raise RuntimeError("Unexpected shim source layout: " + start)
    remainder = source.split(start, 1)[1]
    if end not in remainder:
        raise RuntimeError("Missing end delimiter after " + start)
    return remainder.split(end, 1)[0]

helpers = "struct combo_build {" + section(
    "struct combo_build {", "/* END STEP128 SEND ADMISSION GATE */"
) + "/* END STEP128 SEND ADMISSION GATE */"
teardown = "void shim_session_teardown(void *session) {" + section(
    "void shim_session_teardown(void *session) {", "#if AK_ENABLE_PHONE_CMDS"
)
send = "int shim_screen_http_send(void *client, void *msg) {" + section(
    "int shim_screen_http_send(void *client, void *msg) {",
    "static int combined_response_port(void *msg)"
)

required_send = ("combo_forget_never_submitted_locked", "combo_send_enter_locked",
                 "combo_send_leave_locked", "http_send(client, msg)")
required_teardown = ("g_session_valid = 0;", "combo_cancel_all_requests_locked()",
                     "g_combo_send_inflight > 0")
for s in required_send:
    if s not in send:
        raise RuntimeError("Send wrapper missing safety gate: " + s)
for s in required_teardown:
    if s not in teardown:
        raise RuntimeError("Teardown missing safety gate: " + s)

test = r'''
#define AK_ENABLE_COMBINED_CLUSTER 1
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/socket.h>

#define COMBINED_REQUEST_LIMIT 8
#define STOCK_SCREEN_RESPONSE_VA 0x0002ec7cu
static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_session_cv = PTHREAD_COND_INITIALIZER;
static unsigned g_session_generation = 501;
static unsigned g_alt_seen_generation = 501;
static int g_session_valid = 1;
static int g_session_cmd_inflight = 0;
static void *g_session = (void *)(uintptr_t)0x5000;

struct cluster_ctx {
    int fd;
    int retired;
    unsigned generation;
};
static struct cluster_ctx *g_cluster_ctx = NULL;
static unsigned g_cluster_ctx_generation = 0;
static void cluster_ctx_release(struct cluster_ctx *ctx) { (void)ctx; }
static void dbg(const char *s, int x) { (void)s; (void)x; }

{{HELPERS}}
static void shim_screen_response(void *msg);

static pthread_mutex_t g_test_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_test_cv = PTHREAD_COND_INITIALIZER;
static int g_test_http_calls = 0, g_test_entered = 0;
static int g_test_should_block = 1, g_test_release_send = 0;
static int g_test_result = 0, g_test_teardown_done = 0;
static int g_test_response_calls = 0;
#define CHECK(c) do { if (!(c)) { \
    fprintf(stderr, "FAIL at line %d: %s\n", __LINE__, #c); exit(1); \
} } while (0)

/* Deliberately simulate a callback while stock send is outstanding. Real
 * stock is enqueue-only but our shim must never depend on stub internals. */
static void shim_screen_response(void *msg) {
    unsigned gen = 999;
    uint64_t conn = 999;
    pthread_mutex_lock(&g_state_lock);
    combo_consume_response_locked(msg, &gen, &conn);
    pthread_mutex_unlock(&g_state_lock);
    CHECK(gen == 0 && conn == 0);
    pthread_mutex_lock(&g_test_lock);
    ++g_test_response_calls;
    pthread_cond_broadcast(&g_test_cv);
    pthread_mutex_unlock(&g_test_lock);
}

static int http_send(void *client, void *msg) {
    CHECK(client != NULL && msg != NULL);
    pthread_mutex_lock(&g_test_lock);
    ++g_test_http_calls;
    g_test_entered = 1;
    pthread_cond_broadcast(&g_test_cv);
    while (g_test_should_block && !g_test_release_send)
        pthread_cond_wait(&g_test_cv, &g_test_lock);
    int result = g_test_result;
    pthread_mutex_unlock(&g_test_lock);
    return result;
}
{{SEND}}
{{TEARDOWN}}

struct send_params { void *msg; int rc; };
static void *run_send(void *arg) {
    struct send_params *p = arg;
    pthread_mutex_lock(&g_state_lock);
    g_combo_build[0].in_use = 1;
    g_combo_build[0].owner = pthread_self();
    g_combo_build[0].message = p->msg;
    g_combo_build[0].generation = 501;
    g_combo_build[0].connid = 7777;
    g_combo_inflight_generation = 501;
    pthread_mutex_unlock(&g_state_lock);
    p->rc = shim_screen_http_send((void *)(uintptr_t)0x9000, p->msg);
    return NULL;
}
static void *run_teardown(void *unused) {
    (void)unused;
    shim_session_teardown((void *)(uintptr_t)0x5000);
    pthread_mutex_lock(&g_test_lock);
    g_test_teardown_done = 1;
    pthread_cond_broadcast(&g_test_cv);
    pthread_mutex_unlock(&g_test_lock);
    return NULL;
}
static void install_stock_callback(void *msg) {
    void *stock = (void *)(uintptr_t)STOCK_SCREEN_RESPONSE_VA;
    memcpy((char *)msg + 0x904, &stock, sizeof stock);
}
static void set_build(void *msg, unsigned gen, uint64_t conn) {
    pthread_mutex_lock(&g_state_lock);
    g_combo_build[0].in_use = 1;
    g_combo_build[0].canceled = 0;
    g_combo_build[0].owner = pthread_self();
    g_combo_build[0].message = msg;
    g_combo_build[0].generation = gen;
    g_combo_build[0].connid = conn;
    g_combo_inflight_generation = gen;
    pthread_mutex_unlock(&g_state_lock);
}
int main(void) {
    char *msg1 = calloc(1, 0x920), *msg2 = calloc(1, 0x920);
    char *msg3 = calloc(1, 0x920), *msg4 = calloc(1, 0x920);
    CHECK(msg1 && msg2 && msg3 && msg4);
    install_stock_callback(msg1);
    install_stock_callback(msg2);
    install_stock_callback(msg3);
    install_stock_callback(msg4);

    struct send_params params = {.msg = msg1, .rc = 999};
    pthread_t sender, teardown_thread;
    CHECK(pthread_create(&sender, NULL, run_send, &params) == 0);
    pthread_mutex_lock(&g_test_lock);
    while (!g_test_entered)
        pthread_cond_wait(&g_test_cv, &g_test_lock);
    pthread_mutex_unlock(&g_test_lock);
    CHECK(pthread_create(&teardown_thread, NULL, run_teardown, NULL) == 0);

    int invalidated = 0;
    for (int i = 0; i < 1000; ++i) {
        pthread_mutex_lock(&g_state_lock);
        invalidated = !g_session_valid && g_session == NULL;
        pthread_mutex_unlock(&g_state_lock);
        if (invalidated) break;
        usleep(1000);
    }
    CHECK(invalidated);
    pthread_mutex_lock(&g_test_lock);
    CHECK(!g_test_teardown_done);
    pthread_mutex_unlock(&g_test_lock);

    /* A canceled message callback executes while teardown is waiting.
     * It must not deadlock and must not start an outdated cluster connection. */
    shim_screen_response(msg1);
    CHECK(g_test_response_calls == 1);

    pthread_mutex_lock(&g_test_lock);
    g_test_release_send = 1;
    pthread_cond_broadcast(&g_test_cv);
    pthread_mutex_unlock(&g_test_lock);
    CHECK(pthread_join(sender, NULL) == 0);
    CHECK(pthread_join(teardown_thread, NULL) == 0);
    CHECK(params.rc == 0);
    CHECK(g_test_teardown_done);
    CHECK(g_combo_send_inflight == 0);

    pthread_mutex_lock(&g_state_lock);
    g_session = (void *)(uintptr_t)0x6000;
    g_session_valid = 1;
    g_session_generation = 600;
    g_alt_seen_generation = 600;
    pthread_mutex_unlock(&g_state_lock);

    /* Proof of non-submission: NULL HTTP client is rejected by the wrapper
     * before calling native send, so the request record can be reclaimed. */
    set_build(msg2, 600, 8888);
    int before = g_test_http_calls;
    CHECK(shim_screen_http_send(NULL, msg2) == -1);
    CHECK(g_test_http_calls == before);
    CHECK(g_combo_send_inflight == 0);
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i)
        CHECK(!g_combo_request[i].in_use);

    /* An ambiguous native transport failure MUST keep a canceled tombstone.
     * It may have enqueued a late callback despite returning an error. */
    pthread_mutex_lock(&g_test_lock);
    g_test_should_block = 0;
    g_test_result = -19;
    pthread_mutex_unlock(&g_test_lock);
    set_build(msg3, 600, 9999);
    CHECK(shim_screen_http_send((void *)(uintptr_t)0x9000, msg3) == -19);
    CHECK(g_combo_send_inflight == 0);
    int found = 0;
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i)
        if (g_combo_request[i].in_use && g_combo_request[i].message == msg3 &&
            g_combo_request[i].canceled) ++found;
    CHECK(found == 1);

    unsigned gen = 999;
    uint64_t conn = 999;
    pthread_mutex_lock(&g_state_lock);
    combo_consume_response_locked(msg3, &gen, &conn);
    pthread_mutex_unlock(&g_state_lock);
    CHECK(gen == 0 && conn == 0);
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i)
        CHECK(!g_combo_request[i].in_use);

    /* Stock-only messages with no injected build must keep their callback. */
    pthread_mutex_lock(&g_test_lock);
    g_test_result = 0;
    pthread_mutex_unlock(&g_test_lock);
    void *callback_before = NULL, *callback_after = NULL;
    memcpy(&callback_before, msg4 + 0x904, sizeof callback_before);
    before = g_test_http_calls;
    CHECK(shim_screen_http_send((void *)(uintptr_t)0x9000, msg4) == 0);
    CHECK(g_test_http_calls == before + 1);
    memcpy(&callback_after, msg4 + 0x904, sizeof callback_after);
    CHECK(callback_before == callback_after);
    CHECK(g_combo_send_inflight == 0);

    free(msg1); free(msg2); free(msg3); free(msg4);
    puts("PASS Step 129 integrated real wrapper+teardown; no-client reclaim,"
         " late callback, uncertain-error tombstone and stock isolation");
    return 0;
}
'''

code = (test.replace("{{HELPERS}}", helpers)
            .replace("{{SEND}}", send)
            .replace("{{TEARDOWN}}", teardown))
with tempfile.TemporaryDirectory(prefix="ak3918-step129-integrated-") as tmp:
    cfile = Path(tmp) / "integrated.c"
    cfile.write_text(code)
    for sanitizer in ("undefined", "none"):
        exe = Path(tmp) / ("test_" + sanitizer)
        cmd = ["cc", "-std=gnu11", "-O1", "-g", "-pthread", "-Wall", "-Wextra",
               "-Werror", "-Wno-unused-function"]
        if sanitizer != "none":
            cmd.append("-fsanitize=undefined")
        cmd += [str(cfile), "-o", str(exe)]
        subprocess.run(cmd, check=True)
        env = dict(os.environ, UBSAN_OPTIONS="halt_on_error=1")
        subprocess.run([str(exe)], check=True, timeout=15, env=env)
print("Step 129 test compiles actual shim_screen_http_send and shim_session_teardown source bodies.")

#!/usr/bin/env python3
"""Verify Step 128 send-admission gate extracted directly from altscreen.c.

Exercises:
1. Teardown blocks in combo_wait_sends_drained_locked while an admitted
   http_send is executing without g_state_lock held.
2. A concurrent send arriving after teardown invalidates the session is
   rejected (-1) and never calls http_send.
3. A concurrent response callback running while teardown is waiting does not
   deadlock, consumes its canceled tombstone, and returns gen=0.
4. A failing http_send (rc != 0) cancels its ticket, clears inflight
   generation, and wakes waiting teardown cleanly.
"""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
src = (root / 'altscreen.c').read_text()
build_def = src[src.index('struct combo_build {'):src.index('/* An installed callback can outlive the session.')]
start = src.index('/* An installed callback can outlive the session.')
end = src.index('/* END STEP128 SEND ADMISSION GATE */', start) + len('/* END STEP128 SEND ADMISSION GATE */')
helpers = src[start:end]

test = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <pthread.h>
#include <unistd.h>

#define COMBINED_REQUEST_LIMIT 8
static unsigned g_session_generation = 501;
static unsigned g_alt_seen_generation = 501;
static int g_session_valid = 1;
static void *g_session = (void *)(uintptr_t)0x5000;
static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_session_cv = PTHREAD_COND_INITIALIZER;

static pthread_mutex_t g_sync_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_sync_cv = PTHREAD_COND_INITIALIZER;
static int g_in_http_send = 0;
static int g_allow_http_send_return = 0;
static int g_teardown_waiting = 0;
static int g_teardown_finished = 0;
static int g_response_done = 0;

{{BUILD_DEF}}
{{HELPERS}}

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL %d: %s\n", __LINE__, #x); exit(1); } } while (0)

static void *admitted_send_thread(void *arg) {
    void *msg = arg;
    pthread_t me = pthread_self();
    unsigned gen = 0;
    uint64_t ticket = 0;

    pthread_mutex_lock(&g_state_lock);
    g_combo_build[0].in_use = 1;
    g_combo_build[0].canceled = 0;
    g_combo_build[0].owner = me;
    g_combo_build[0].message = msg;
    g_combo_build[0].generation = 501;
    g_combo_build[0].connid = 7777;
    g_combo_inflight_generation = 501;

    int decision = combo_prepare_send_locked(me, msg, 1, &gen, &ticket);
    CHECK(decision == 1 && gen == 501 && ticket != 0);
    combo_send_enter_locked();
    pthread_mutex_unlock(&g_state_lock);

    /* Simulate executing stock http_send with no shim lock held. */
    pthread_mutex_lock(&g_sync_mu);
    g_in_http_send = 1;
    pthread_cond_broadcast(&g_sync_cv);
    while (!g_allow_http_send_return)
        pthread_cond_wait(&g_sync_cv, &g_sync_mu);
    /* Teardown must NOT have completed while http_send is still active. */
    CHECK(!g_teardown_finished);
    pthread_mutex_unlock(&g_sync_mu);

    pthread_mutex_lock(&g_state_lock);
    combo_send_leave_locked(0, gen, ticket);
    pthread_mutex_unlock(&g_state_lock);
    return NULL;
}

static void *teardown_thread(void *unused) {
    (void)unused;
    pthread_mutex_lock(&g_sync_mu);
    while (!g_in_http_send)
        pthread_cond_wait(&g_sync_cv, &g_sync_mu);
    pthread_mutex_unlock(&g_sync_mu);

    pthread_mutex_lock(&g_state_lock);
    g_session_valid = 0;
    g_session = NULL;
    g_session_generation++;
    g_combo_inflight_generation = 0;
    combo_cancel_all_builds_locked();
    combo_cancel_all_requests_locked();

    pthread_mutex_lock(&g_sync_mu);
    g_teardown_waiting = 1;
    pthread_cond_broadcast(&g_sync_cv);
    pthread_mutex_unlock(&g_sync_mu);

    combo_wait_sends_drained_locked();
    pthread_mutex_unlock(&g_state_lock);

    pthread_mutex_lock(&g_sync_mu);
    g_teardown_finished = 1;
    pthread_cond_broadcast(&g_sync_cv);
    pthread_mutex_unlock(&g_sync_mu);
    return NULL;
}

static void *late_response_thread(void *arg) {
    void *msg = arg;
    unsigned gen = 999;
    uint64_t connid = 999;

    /* Must not deadlock even while teardown is parked in pthread_cond_wait. */
    pthread_mutex_lock(&g_state_lock);
    combo_consume_response_locked(msg, &gen, &connid);
    pthread_mutex_unlock(&g_state_lock);
    CHECK(gen == 0 && connid == 0);

    pthread_mutex_lock(&g_sync_mu);
    g_response_done = 1;
    pthread_cond_broadcast(&g_sync_cv);
    pthread_mutex_unlock(&g_sync_mu);
    return NULL;
}

int main(void) {
    void *msg1 = (void *)(uintptr_t)0x8000;
    void *msg2 = (void *)(uintptr_t)0x8100;
    pthread_t t_send, t_td, t_resp;

    CHECK(pthread_create(&t_send, NULL, admitted_send_thread, msg1) == 0);
    CHECK(pthread_create(&t_td, NULL, teardown_thread, NULL) == 0);

    pthread_mutex_lock(&g_sync_mu);
    while (!g_teardown_waiting)
        pthread_cond_wait(&g_sync_cv, &g_sync_mu);
    pthread_mutex_unlock(&g_sync_mu);

    /* Give teardown a brief moment to enter pthread_cond_wait and confirm it stays blocked. */
    usleep(20000);
    pthread_mutex_lock(&g_sync_mu);
    CHECK(!g_teardown_finished);
    pthread_mutex_unlock(&g_sync_mu);

    /* A second send arriving after teardown invalidated the session must fail closed. */
    pthread_mutex_lock(&g_state_lock);
    g_combo_build[1].in_use = 1;
    g_combo_build[1].canceled = 0;
    g_combo_build[1].owner = pthread_self();
    g_combo_build[1].message = msg2;
    g_combo_build[1].generation = 501;
    g_combo_build[1].connid = 8888;
    unsigned gen2 = 0;
    uint64_t ticket2 = 0;
    int dec2 = combo_prepare_send_locked(pthread_self(), msg2, 1, &gen2, &ticket2);
    CHECK(dec2 == -1 && gen2 == 0 && ticket2 == 0);
    pthread_mutex_unlock(&g_state_lock);

    /* A concurrent response callback must run without deadlocking against waiting teardown. */
    CHECK(pthread_create(&t_resp, NULL, late_response_thread, msg1) == 0);
    CHECK(pthread_join(t_resp, NULL) == 0);
    CHECK(g_response_done == 1);

    /* Now let http_send finish; teardown must wake and complete. */
    pthread_mutex_lock(&g_sync_mu);
    g_allow_http_send_return = 1;
    pthread_cond_broadcast(&g_sync_cv);
    pthread_mutex_unlock(&g_sync_mu);

    CHECK(pthread_join(t_send, NULL) == 0);
    CHECK(pthread_join(t_td, NULL) == 0);
    CHECK(g_teardown_finished == 1);
    CHECK(g_combo_send_inflight == 0);

    /* Step 131 verified stock: rc != 0 means no queue submission.
     * Reclaim the record and clear in-flight state without a callback. */
    pthread_mutex_lock(&g_state_lock);
    g_session_generation = 600;
    g_alt_seen_generation = 600;
    g_session_valid = 1;
    g_session = (void *)(uintptr_t)0x6000;
    g_combo_inflight_generation = 600;
    g_combo_build[0].in_use = 1;
    g_combo_build[0].canceled = 0;
    g_combo_build[0].owner = pthread_self();
    g_combo_build[0].message = msg2;
    g_combo_build[0].generation = 600;
    g_combo_build[0].connid = 9999;
    unsigned gen3 = 0;
    uint64_t ticket3 = 0;
    CHECK(combo_prepare_send_locked(pthread_self(), msg2, 1, &gen3, &ticket3) == 1);
    combo_send_enter_locked();
    CHECK(g_combo_send_inflight == 1);
    combo_send_leave_locked(-1, gen3, ticket3);
    CHECK(g_combo_send_inflight == 0);
    CHECK(g_combo_inflight_generation == 0);
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i)
        CHECK(!g_combo_request[i].in_use);
    unsigned out_gen = 1;
    uint64_t out_conn = 1;
    combo_consume_response_locked(msg2, &out_gen, &out_conn);
    CHECK(out_gen == 0 && out_conn == 0);
    pthread_mutex_unlock(&g_state_lock);

    puts("PASS Step 128: send-admission gate serializes teardown, rejects post-teardown sends, no callback deadlock");
    return 0;
}
'''

code = test.replace('{{BUILD_DEF}}', build_def).replace('{{HELPERS}}', helpers)
with tempfile.TemporaryDirectory(prefix='ak3918-step128-') as temp:
    cfile = Path(temp) / 'step128.c'
    cfile.write_text(code)
    for sanitizer in ('address,undefined', 'undefined', 'none'):
        exe = Path(temp) / ('step128_' + sanitizer.replace(',', '_'))
        cmd = [
            'cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
            '-pthread', '-Wno-unused-function', '-fno-omit-frame-pointer',
        ]
        if sanitizer != 'none':
            cmd.append('-fsanitize=' + sanitizer)
        cmd += [str(cfile), '-o', str(exe)]
        subprocess.run(cmd, check=True)
        env = os.environ.copy()
        leak_detection = '0' if sys.platform == 'darwin' else '1'
        env['ASAN_OPTIONS'] = 'detect_leaks=' + leak_detection + ':halt_on_error=1'
        env['UBSAN_OPTIONS'] = 'halt_on_error=1'
        print('RUN:', sanitizer, flush=True)
        subprocess.run([str(exe)], check=True, env=env, timeout=10)
print('source sha256', hashlib.sha256(src.encode()).hexdigest())

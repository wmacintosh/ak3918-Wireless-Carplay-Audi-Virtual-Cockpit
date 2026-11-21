#!/usr/bin/env python3
"""Deterministically expose admission-to-send gap using source-derived C helpers.

NEGATIVE TEST: passing confirms the current combined shim can enter stock
http_send after concurrent teardown. Not a safety fix or device test.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
src = (root / 'altscreen.c').read_text()
start = src.index('/* An installed callback can outlive the session.')
end = src.index('/* END STEP120 SEND GATE */', start) + len('/* END STEP120 SEND GATE */')
helpers = src[start:end]
build_def = src[src.index('struct combo_build {'):start]

test = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <pthread.h>

#define COMBINED_REQUEST_LIMIT 8
static unsigned g_session_generation = 401;
static unsigned g_alt_seen_generation = 401;
static int g_session_valid = 1;
static void *g_session = (void *)(uintptr_t)0x5000;
static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t g_test_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_test_cv = PTHREAD_COND_INITIALIZER;
static int claimed, teardown_done, sending_after_teardown;
{{BUILD_DEF}}
{{HELPERS}}
#define CHECK(x) do { if(!(x)) {fprintf(stderr, "FAIL %d: %s\n", __LINE__,#x);exit(1);} } while (0)

static void *send_thread(void *unused) {
    (void)unused;
    pthread_t me = pthread_self();
    void *msg = (void *)(uintptr_t)0x7000;
    unsigned gen = 0;
    uint64_t ticket = 0;
    pthread_mutex_lock(&g_state_lock);
    CHECK(!combo_owner_has_build_locked(me));
    g_combo_build[0].in_use = 1;
    g_combo_build[0].owner = me;
    g_combo_build[0].message = msg;
    g_combo_build[0].generation = 401;
    g_combo_build[0].connid = 1515;
    g_combo_inflight_generation = 401;
    int decision = combo_prepare_send_locked(me, msg, 1, &gen, &ticket);
    CHECK(decision == 1 && gen == 401 && ticket != 0);
    pthread_mutex_unlock(&g_state_lock);

    pthread_mutex_lock(&g_test_mu);
    claimed = 1;
    pthread_cond_broadcast(&g_test_cv);
    while (!teardown_done)
        pthread_cond_wait(&g_test_cv, &g_test_mu);
    pthread_mutex_unlock(&g_test_mu);

    /* This reproduces shim_screen_http_send calling http_send unconditionally
       after releasing g_state_lock, with no post-teardown transport barrier. */
    pthread_mutex_lock(&g_state_lock);
    sending_after_teardown = !g_session_valid && !g_session &&
                             g_session_generation == 402;
    pthread_mutex_unlock(&g_state_lock);
    return NULL;
}

int main(void) {
    pthread_t thread;
    CHECK(pthread_create(&thread, NULL, send_thread, NULL) == 0);
    pthread_mutex_lock(&g_test_mu);
    while (!claimed)
        pthread_cond_wait(&g_test_cv, &g_test_mu);
    pthread_mutex_unlock(&g_test_mu);

    pthread_mutex_lock(&g_state_lock);
    g_session_valid = 0;
    g_session = NULL;
    ++g_session_generation;
    g_combo_inflight_generation = 0;
    combo_cancel_all_builds_locked();
    combo_cancel_all_requests_locked();
    pthread_mutex_unlock(&g_state_lock);

    pthread_mutex_lock(&g_test_mu);
    teardown_done = 1;
    pthread_cond_broadcast(&g_test_cv);
    pthread_mutex_unlock(&g_test_mu);
    CHECK(pthread_join(thread, NULL) == 0);

    CHECK(sending_after_teardown);
    CHECK(g_combo_request[0].in_use && g_combo_request[0].canceled);
    puts("EXPECTED BLOCKER: combined HTTP send can execute after teardown.");
    puts("PASS negative Step 125 race reproduction (not deployment-safe)");
    return 0;
}
'''

code = (test.replace('{{BUILD_DEF}}', build_def)
            .replace('{{HELPERS}}', helpers))
with tempfile.TemporaryDirectory(prefix='ak3918-step125-') as temp:
    cfile = Path(temp) / 'race.c'
    cfile.write_text(code)
    exe = Path(temp) / 'race'
    subprocess.run([
        'cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-pthread', str(cfile), '-o', str(exe)
    ], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)

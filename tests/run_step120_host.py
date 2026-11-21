#!/usr/bin/env python3
"""Compile and exercise the actual Step 115 + Step 120 helper functions."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
src = (root / 'altscreen.c').read_text()
start = src.index('/* An installed callback can outlive the session.')
end = src.index('/* END STEP120 SEND GATE */', start) + len('/* END STEP120 SEND GATE */')
impl = src[start:end]
build_def = src[src.index('struct combo_build {'):start]

test = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <pthread.h>
#define COMBINED_REQUEST_LIMIT 8
static unsigned g_session_generation;
static unsigned g_alt_seen_generation;
static int g_session_valid;
static void *g_session;
{{BUILD_DEF}}
{{IMPL}}
#define CHECK(x) do { if(!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
static void reset_state(unsigned gen) {
    memset(g_combo_build,0,sizeof g_combo_build);
    memset(g_combo_request,0,sizeof g_combo_request);
    g_combo_inflight_generation=gen;
    g_session_generation=gen;
    g_alt_seen_generation=gen;
    g_session_valid=1;
    g_session=(void *)(uintptr_t)0x1000;
}
static void build(pthread_t who, unsigned gen, uint64_t connid, void *msg) {
    CHECK(!combo_owner_has_build_locked(who));
    int slot=-1;
    for(int i=0;i<COMBINED_REQUEST_LIMIT;i++)
        if(!g_combo_build[i].in_use) {slot=i;break;}
    CHECK(slot>=0);
    g_combo_build[slot].in_use=1;
    g_combo_build[slot].canceled=0;
    g_combo_build[slot].owner=who;
    g_combo_build[slot].message=msg;
    g_combo_build[slot].generation=gen;
    g_combo_build[slot].connid=connid;
}
int main(void) {
    pthread_t me=pthread_self();
    void *m=(void *)(uintptr_t)0x5670;
    unsigned gen=999;
    uint64_t ticket=999;

    // Uninstrumented request: unchanged stock path.
    reset_state(100);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==0);
    CHECK(gen==0 && ticket==0);

    // Valid 111 request: hook is registered and retained until callback.
    build(me,100,1111,m);
    CHECK(combo_owner_has_build_locked(me));
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==1);
    CHECK(gen==100 && ticket!=0);
    CHECK(!combo_owner_has_build_locked(me));
    CHECK(g_combo_request[0].in_use && g_combo_request[0].connid==1111);
    unsigned gotgen;uint64_t gotid;
    combo_consume_response_locked(m,&gotgen,&gotid);
    CHECK(gotgen==100 && gotid==1111);

    combo_cancel_all_requests_locked();

    // Teardown after array publication but before send must reject the send.
    reset_state(101);
    build(me,101,2222,m);
    combo_cancel_all_builds_locked();
    g_session_valid=0;
    g_session=NULL;
    g_session_generation++;
    g_combo_inflight_generation=0;
    CHECK(combo_owner_has_build_locked(me));
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);
    CHECK(!combo_owner_has_build_locked(me));
    CHECK(!g_combo_request[0].in_use);

    // If we lose a generation without explicit cancellation, reject anyway.
    reset_state(200);
    build(me,200,3333,m);
    g_session_generation++;
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);

    // No verified stock response callback: reject rather than send untracked 111.
    reset_state(300);
    build(me,300,4444,m);
    CHECK(combo_prepare_send_locked(me,m,0,&gen,&ticket)==-1);

    // A tracking-table collision must reject the entire injected request.
    reset_state(400);
    CHECK(combo_claim_request_locked(m,400,9999,&ticket));
    build(me,400,5555,m);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);
    CHECK(g_combo_request[0].in_use && g_combo_request[0].connid==9999);

    // All slots are occupied: reject injected 111, but preserve existing records.
    reset_state(500);
    for(int i=0;i<COMBINED_REQUEST_LIMIT;i++)
        CHECK(combo_claim_request_locked((void*)(uintptr_t)(0x20000+i*16),500,9999,&ticket));
    build(me,500,6666,m);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);
    for(int i=0;i<COMBINED_REQUEST_LIMIT;i++) CHECK(g_combo_request[i].in_use);

    // Canceled build stays owned; the next ensure must not overwrite it.
    reset_state(600);
    build(me,600,7777,m);
    combo_cancel_all_builds_locked();
    CHECK(combo_owner_has_build_locked(me));
    CHECK(g_combo_build[0].canceled);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);

    // Error return from HTTP send cancels only its request ticket.
    reset_state(700);
    build(me,700,8888,m);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==1);
    combo_cancel_ticket_locked(ticket);
    CHECK(g_combo_request[0].canceled);
    combo_consume_response_locked(m,&gotgen,&gotid);
    CHECK(gotgen==0 && gotid==0);

    // Different native message on the same thread must preserve stock send.
    // An orphaned 111 build cannot claim an unrelated HTTP message.
    reset_state(800);
    build(me,800,9999,m);
    void *unrelated_stock_msg=(void *)(uintptr_t)0x6780;
    CHECK(combo_owner_has_build_locked(me));
    CHECK(combo_prepare_send_locked(me,unrelated_stock_msg,1,&gen,&ticket)==0);
    CHECK(gen==0 && ticket==0);
    CHECK(combo_owner_has_build_locked(me));
    CHECK(!g_combo_request[0].in_use);

    // A fresh native ensure call cancels old orphan metadata; an older
    // request reaching the send hook later is rejected rather than untracked.
    combo_cancel_owner_builds_locked(me);
    CHECK(g_combo_build[0].canceled);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);
    CHECK(!combo_owner_has_build_locked(me));
    CHECK(!g_combo_request[0].in_use);

    // Allocator pointer reuse for a new native request is not accepted when
    // the fresh ensure hook has already canceled the prior build.
    reset_state(801);
    build(me,801,1234,m);
    combo_cancel_owner_builds_locked(me);
    CHECK(combo_prepare_send_locked(me,m,1,&gen,&ticket)==-1);
    CHECK(!g_combo_request[0].in_use);

    puts("PASS Step 120/123: stock, valid, teardown, mismatch, alias, orphan cancellation");
    return 0;
}
'''
code = test.replace('{{BUILD_DEF}}', build_def).replace('{{IMPL}}', impl)
with tempfile.TemporaryDirectory(prefix='ak3918-step120-') as tmp:
    file=Path(tmp)/'send_gate.c'
    file.write_text(code)
    for mode in ('address,undefined','undefined','none'):
        exe=Path(tmp)/('test_'+mode.replace(',','_'))
        cmd=['cc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-fno-omit-frame-pointer','-pthread']
        if mode != 'none':
            cmd += ['-fsanitize='+mode]
        subprocess.run(cmd + [str(file),'-o',str(exe)],check=True)
        env=os.environ.copy()
        env['ASAN_OPTIONS']='detect_leaks='+('0' if sys.platform=='darwin' else '1')+':halt_on_error=1'
        env['UBSAN_OPTIONS']='halt_on_error=1'
        print('RUN',mode,flush=True)
        subprocess.run([str(exe)],check=True,env=env)
print('source sha256',hashlib.sha256(src.encode()).hexdigest())

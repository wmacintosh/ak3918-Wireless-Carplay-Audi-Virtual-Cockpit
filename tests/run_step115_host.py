#!/usr/bin/env python3
from pathlib import Path
import subprocess, hashlib, tempfile, os, sys
root=Path(__file__).resolve().parents[1]
src=(root/'altscreen.c').read_text()
start=src.index('/* An installed callback can outlive the session.')
end=src.index('/* END STEP115 REQUEST HELPERS */',start)+len('/* END STEP115 REQUEST HELPERS */')
impl=src[start:end].replace("static struct combo_build g_combo_build[COMBINED_REQUEST_LIMIT];\n", "")
test=r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#define COMBINED_REQUEST_LIMIT 8
static unsigned g_session_generation = 0;
static int g_session_valid = 0;
static void *g_session = NULL;
{{IMPL}}
static void fail(const char *what) { fprintf(stderr,"FAIL %s\n",what); exit(1); }
#define CHECK(x) do {if(!(x)) fail(#x);} while(0)
static void set_session(unsigned gen) {
    g_session_generation=gen;
    g_session_valid=1;
    g_session=(void *)(uintptr_t)0x1234;
}
int main(void) {
    unsigned gen; uint64_t connid, ticket_a, ticket_b;
    void *a=(void *)(uintptr_t)0x1020;
    void *b=(void *)(uintptr_t)0x2040;
    set_session(11);
    CHECK(combo_claim_request_locked(a,11,111,&ticket_a));
    CHECK(g_combo_request[0].ticket==ticket_a);
    CHECK(!combo_claim_request_locked(a,11,111,&ticket_b)); // no silent overwrite
    combo_cancel_all_requests_locked();
    CHECK(g_combo_request[0].in_use && g_combo_request[0].canceled);
    CHECK(!combo_claim_request_locked(a,12,222,&ticket_b)); // tombstone blocks alias
    set_session(12);
    CHECK(combo_claim_request_locked(b,12,222,&ticket_b));
    CHECK(ticket_a!=ticket_b);
    combo_consume_response_locked(a,&gen,&connid); // late response on old session
    CHECK(gen==0 && connid==0);
    CHECK(!g_combo_request[0].in_use);
    CHECK(g_combo_request[1].in_use);
    combo_consume_response_locked(b,&gen,&connid);
    CHECK(gen==12 && connid==222);
    CHECK(!g_combo_request[1].in_use);

    // Synchronous callback followed by error return: old ticket must not cancel
    // an unrelated new record, even when memory address is reused.
    set_session(13);
    CHECK(combo_claim_request_locked(a,13,333,&ticket_a));
    combo_consume_response_locked(a,&gen,&connid);
    CHECK(gen==13 && connid==333);
    CHECK(combo_claim_request_locked(a,13,444,&ticket_b));
    combo_cancel_ticket_locked(ticket_a);
    CHECK(g_combo_request[0].in_use && !g_combo_request[0].canceled);
    combo_consume_response_locked(a,&gen,&connid);
    CHECK(gen==13 && connid==444);

    // Failed HTTP send: keep tombstone until callback delivered, fail closed.
    CHECK(combo_claim_request_locked(a,13,555,&ticket_a));
    combo_cancel_ticket_locked(ticket_a);
    CHECK(!combo_claim_request_locked(a,13,666,&ticket_b));
    combo_consume_response_locked(a,&gen,&connid);
    CHECK(gen==0 && connid==0);
    CHECK(combo_claim_request_locked(a,13,666,&ticket_b));
    combo_consume_response_locked(a,&gen,&connid);
    CHECK(gen==13 && connid==666);

    // An old-generation record cannot start a new session transport even if a
    // session switch occurs without its cancellation helper.
    set_session(14);
    CHECK(combo_claim_request_locked(a,14,777,&ticket_a));
    set_session(15);
    combo_consume_response_locked(a,&gen,&connid);
    CHECK(gen==0 && connid==0);

    // Null, overflow, and no free slots reject registration.
    CHECK(!combo_claim_request_locked(NULL,15,888,&ticket_a));
    CHECK(!combo_claim_request_locked(a,0,888,&ticket_a));
    CHECK(!combo_claim_request_locked(a,15,0,&ticket_a));
    for (int i=0;i<COMBINED_REQUEST_LIMIT;i++)
        CHECK(combo_claim_request_locked((void *)(uintptr_t)(0x10000+i*16),15,999,&ticket_a));
    CHECK(!combo_claim_request_locked((void *)(uintptr_t)0x20000,15,1000,&ticket_b));
    combo_cancel_all_requests_locked();
    for (int i=0;i<COMBINED_REQUEST_LIMIT;i++) {
        void *m=(void *)(uintptr_t)(0x10000+i*16);
        CHECK(!combo_claim_request_locked(m,16,1000,&ticket_b));
        combo_consume_response_locked(m,&gen,&connid);
        CHECK(gen==0 && connid==0);
    }
    CHECK(combo_claim_request_locked(a,15,1001,&ticket_a));
    combo_consume_response_locked(a,&gen,&connid);
    CHECK(gen==15 && connid==1001);
    g_combo_next_ticket=UINT64_MAX;
    CHECK(!combo_claim_request_locked(a,15,1002,&ticket_a));
    puts("PASS: Step 115 tombstone, pointer collision, ticket, generation, capacity tests");
    return 0;
}
'''
code=test.replace('{{IMPL}}',impl)
with tempfile.TemporaryDirectory(prefix="ak3918-step115-") as d:
    out=Path(d)
    name=out/'test_step115_extracted.c'
    name.write_text(code)
    for sanitizer in ('address,undefined','undefined','none'):
        cmd=['cc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-fno-omit-frame-pointer']
        if sanitizer!='none':cmd+=['-fsanitize='+sanitizer]
        cmd+=[str(name),'-o',str(out/('step115_'+sanitizer.replace(',','_')))]
        subprocess.run(cmd,check=True)
        env=os.environ.copy()
        # Apple's ASan runtime rejects detect_leaks=1; Linux ASan supports it.
        leak_detection='0' if sys.platform=='darwin' else '1'
        env['ASAN_OPTIONS']='detect_leaks='+leak_detection+':halt_on_error=1'
        env['UBSAN_OPTIONS']='halt_on_error=1'
        print('RUN:',sanitizer,'(leak detection',leak_detection+')',flush=True)
        subprocess.run([cmd[-1]],check=True,env=env)
print('source sha256',hashlib.sha256(src.encode()).hexdigest())

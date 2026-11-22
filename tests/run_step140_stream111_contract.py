#!/usr/bin/env python3
"""Step 140 stock-110/experimental-111 path: compile actual shim bodies on host.

The actual ensure/send/response functions and lifecycle metadata helpers are
extracted from altscreen.c (not reimplemented). CF APIs and HTTP transport are
deterministic test doubles; no real plist serializer, ARM ABI or device invoked.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "altscreen.c").read_text()

def extract(start, end):
    if source.count(start) != 1:
        raise RuntimeError("Expected exactly one source marker: " + start)
    part = source.split(start, 1)[1]
    if end not in part:
        raise RuntimeError("Missing section terminator: " + end)
    return start + part.split(end, 1)[0]

helpers = extract("struct combo_build {", "/* END STEP128 SEND ADMISSION GATE */")
ctx_type = extract("struct cluster_ctx {", "struct sink_args {")
worker_type = extract("struct cluster_worker_args {", "static void *cluster_setup_to_car(")
ensure = extract("void shim_screen_ensure_stream(void **streams, void *stock_video) {",
                 "/* Invoked instead of stock BL")
send = extract("int shim_screen_http_send(void *client, void *msg) {",
               "static int combined_response_port(")
response = extract("static int combined_response_port(void *msg) {",
                   "#endif /* AK_ENABLE_COMBINED_CLUSTER */")
required = (
    "cf_arr_ensure(streams, stock_video)", "cf_array_append(copy, sd)",
    "*streams = replacement", "g_combo_build[build_slot].message = native_msg",
    "combo_prepare_send_locked", "http_send(client, msg)",
    "combo_send_leave_locked", "combo_consume_response_locked",
    "combined_response_port(msg)", "STOCK_SCREEN_RESPONSE_VA)(msg)",
    "cluster_setup_to_car", "cf_dict_get_int64(sd, K_TYPE, 0)",
)
joined = ensure + send + response
for marker in required:
    if marker not in joined:
        raise RuntimeError("Lost source hook invariant: " + marker)

harness = r'''
#define _GNU_SOURCE
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <limits.h>

#define AK_ENABLE_COMBINED_CLUSTER 1
#define COMBINED_REQUEST_LIMIT 8
#define CLUSTER_STREAM_TYPE 0x6f
#define ALT_SCREEN_TYPE 111
#define K_STREAMS ((void *)(uintptr_t)0x11)
#define K_TYPE ((void *)(uintptr_t)0x12)
#define K_DATAPORT ((void *)(uintptr_t)0x13)
#define K_CONNID ((void *)(uintptr_t)0x14)
#define K_UUID ((void *)(uintptr_t)0x15)
#define K_LATENCYMS ((void *)(uintptr_t)0x16)
#define CLUSTER_UUID "b7e6c5a0-2222-4000-8000-000000000002"
#define STOCK_SCREEN_RESPONSE_VA ((uintptr_t)&stock_response_stub)

static int pair_verify;
#define GPAIRVERIFY_HK (&pair_verify)

static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_session_cv = PTHREAD_COND_INITIALIZER;
static unsigned g_session_generation, g_alt_seen_generation;
static int g_session_valid, g_session_cmd_inflight;
static void *g_session;
static unsigned g_cluster_connecting_gen, g_cluster_ctx_generation;
{{CTX_TYPE}}
static struct cluster_ctx *g_cluster_ctx;
{{WORKER_TYPE}}
{{HELPERS}}

#define CHECK(expr) do { if (!(expr)) { \
    fprintf(stderr, "Step140 FAIL line %d: %s\n", __LINE__, #expr); exit(1); \
} } while (0)

enum { DICT=1, ARRAY=2 };
struct Obj {
    int kind, refs;
    int count;
    struct Obj *entries[72];
    struct Obj *streams;
    int64_t type, connid, port, latency;
};
typedef struct Obj Obj;
static int live_objects, uuid_zero, send_result, send_calls, stock_calls;
static int worker_calls, last_worker_port;
static uint64_t last_worker_conn;
static unsigned last_worker_gen;
static Obj *response_dictionary;
static char *last_http_msg;
static char *last_native_callback_field;
static int array_ensure_calls, lock_violation;

static void expect_unlocked(void) {
    if (pthread_mutex_trylock(&g_state_lock) != 0) { ++lock_violation; return; }
    pthread_mutex_unlock(&g_state_lock);
}
static Obj *obj(int kind) {
    expect_unlocked();
    Obj *v = calloc(1, sizeof *v);
    CHECK(v);
    v->kind = kind; v->refs = 1;
    ++live_objects;
    return v;
}
static void retain(Obj *v) { if(v) ++v->refs; }
static void cf_release(void *p) {
    expect_unlocked();
    Obj *v=p;
    if (!v) return;
    CHECK(v->refs > 0);
    if (--v->refs > 0) return;
    if (v->kind == ARRAY) {
        for(int i=0;i<v->count;i++) cf_release(v->entries[i]);
    } else if(v->kind == DICT && v->streams) {
        cf_release(v->streams);
    }
    --live_objects;
    free(v);
}
static void *cf_dict_create_mutable(int a,int b,void *k,void *v) {
    (void)a; (void)b; (void)k; (void)v;
    return obj(DICT);
}
static void *cf_array_create_mutable(int a,int b,void *cb) {
    (void)a;(void)b;(void)cb;
    return obj(ARRAY);
}
static void *arr_cb, *dict_key_cb, *dict_val_cb;
static long cf_array_count(void *p) {
    expect_unlocked();
    Obj *v=p;
    CHECK(v && v->kind==ARRAY);
    return v->count;
}
static void *cf_array_at(void *p,long i) {
    expect_unlocked();
    Obj *v=p;
    CHECK(v && v->kind==ARRAY);
    if(i<0 || i>=v->count) return NULL;
    return v->entries[i];
}
static void cf_array_append(void *p,void *entry) {
    expect_unlocked();
    Obj *v=p; Obj *e=entry;
    CHECK(v && v->kind==ARRAY && v->count<72 && e);
    retain(e);
    v->entries[v->count++]=e;
}
static void cf_arr_ensure(void **p,void *video) {
    expect_unlocked();
    ++array_ensure_calls;
    if(!*p) *p=cf_array_create_mutable(0,0,NULL);
    Obj *a=*p;
    if (a->count==0) cf_array_append(a,video);
}
static int cf_uuidget(void *target) {
    expect_unlocked();
    unsigned char *b=target;
    memset(b,0,16);
    if(!uuid_zero) {
        b[0]=0x11; b[1]=0x22; b[2]=0x33; b[3]=0x44;
        b[4]=0x55; b[5]=0x66; b[6]=0x77; b[7]=0x88;
    }
    return 0;
}
static void cf_dict_set_int64(void *p,void *key,int64_t v) {
    expect_unlocked();
    Obj *d=p;
    CHECK(d && d->kind==DICT);
    if(key==K_TYPE) d->type=v;
    if(key==K_CONNID) d->connid=v;
    if(key==K_DATAPORT) d->port=v;
    if(key==K_LATENCYMS) d->latency=v;
}
static int64_t cf_dict_get_int64(void *p,void *key,int *err) {
    expect_unlocked();
    Obj *d=p;
    if(err) *err=0;
    CHECK(d && d->kind==DICT);
    if(key==K_TYPE) return d->type;
    if(key==K_DATAPORT) return d->port;
    if(key==K_CONNID) return d->connid;
    return 0;
}
static void cf_dict_set_cstr(void *p,void *key,void *value,unsigned size) {
    expect_unlocked();
    (void)p;(void)key;(void)value;(void)size;
}
static unsigned long cf_array_type_id(void) {return ARRAY;}
static unsigned long cf_dict_type_id(void) {return DICT;}
static unsigned long cf_get_type_id(void *p) { return (unsigned long)((Obj *)p)->kind; }
static void *cf_dict_get_typed(void *p,void *key,unsigned long type,int *err) {
    expect_unlocked();
    Obj *d=p;
    if(err) *err=0;
    CHECK(d && d->kind==DICT && key==K_STREAMS && type==ARRAY);
    return d->streams;
}
static void *cf_plist_read(void *data,int len,int *err) {
    expect_unlocked();
    if(err) *err=0;
    if(!data || len!=1 || !response_dictionary) {
        if(err) *err=-1;
        return NULL;
    }
    retain(response_dictionary);
    return response_dictionary;
}
static int http_send(void *client,void *msg) {
    expect_unlocked();
    CHECK(client && msg);
    ++send_calls;
    last_http_msg=msg;
    /* Test double reads opaque ARM callback bytes without requiring its
     * alignment to match a 64-bit host's pointer representation. */
    memcpy(&last_native_callback_field,(char*)msg+0x904,
           sizeof last_native_callback_field);
    return send_result;
}
static void dbg(const char *s,int n) {(void)s;(void)n;}
static void stock_response_stub(void *msg) {
    ++stock_calls;
    CHECK(msg==last_http_msg);
}
static void *cluster_setup_to_car(void *p) {
    struct cluster_worker_args *a=p;
    ++worker_calls;
    last_worker_port=a->data_port;
    last_worker_conn=a->connid;
    last_worker_gen=a->generation;
    free(a);
    return NULL;
}
static void cluster_clear_connecting(unsigned generation) {
    if(g_cluster_connecting_gen==generation) g_cluster_connecting_gen=0;
}
/* Do not execute a real asynchronous worker: only C hook branch behavior is
 * under test; actual native work scheduling cannot be reproduced here. */
static int fake_pthread_create(pthread_t *thread,const pthread_attr_t *attrs,
                               void *(*start)(void*),void *argument) {
    (void)attrs;
    *thread=pthread_self();
    start(argument);
    return 0;
}
static int fake_pthread_detach(pthread_t thread) {(void)thread;return 0;}
#define pthread_create fake_pthread_create
#define pthread_detach fake_pthread_detach

/* Production has this forward declaration before the send wrapper. */
static void shim_screen_response(void *msg);

{{ENSURE}}
{{SEND}}
{{RESPONSE}}

static char *make_msg(char **raw) {
    *raw=calloc(1,0x940);
    CHECK(*raw);
    /* ARM 0x904 is 4-byte-aligned; host pointer at +0x904 needs +4. */
    char *msg=*raw+4;
    CHECK(((uintptr_t)(msg+0x904)%sizeof(void*))==0);
    void *callback=(void *)STOCK_SCREEN_RESPONSE_VA;
    memcpy(msg+0x904,&callback,sizeof callback);
    /* Stock ARM has a 4-byte pointer at 0x49c and 4-byte len at 0x4a0.
     * On a 64-bit host, a pointer read at 0x49c overlaps the next word.
     * The CF stub below intentionally NEVER dereferences body; use an opaque
     * nonnull pointer token whose high 32 bits encode native length=1.
     * This is a strict host ABI test limit, not a real data buffer. */
    CHECK(sizeof(void*)==8);
    char **body=(char **)(msg+0x49c);
    *body=(char *)(uintptr_t)UINT64_C(0x0000000100000001);
    CHECK(*(int *)(msg+0x4a0)==1);
    return msg;
}
static void set_callback(char *msg) {
    void *callback=(void *)STOCK_SCREEN_RESPONSE_VA;
    memcpy(msg+0x904,&callback,sizeof callback);
}
static int tracked(void) {
    int n=0;
    for(int i=0;i<COMBINED_REQUEST_LIMIT;i++) n+=!!g_combo_request[i].in_use;
    return n;
}
static void fresh_session(unsigned gen) {
    /* Independent test fixture reset only when all native callbacks have
     * already completed: NEVER a production session-reset operation. */
    CHECK(tracked()==0);
    g_session_valid=1;
    g_session=(void *)(uintptr_t)0x5000;
    g_session_generation=gen;
    g_alt_seen_generation=gen;
    g_combo_inflight_generation=0;
    g_cluster_connecting_gen=0;
    g_cluster_ctx=NULL; g_cluster_ctx_generation=0;
    pair_verify=0; uuid_zero=0; send_result=0;
    send_calls=0; stock_calls=0; worker_calls=0;
    array_ensure_calls=0; lock_violation=0;
    response_dictionary=NULL;
}
static void install_response(int include_111,int port) {
    Obj *dictionary=obj(DICT);
    Obj *arr=obj(ARRAY);
    Obj *stock=obj(DICT); stock->type=110;
    cf_array_append(arr,stock);
    cf_release(stock);
    if(include_111) {
        Obj *extra=obj(DICT);
        extra->type=CLUSTER_STREAM_TYPE;
        extra->port=port;
        cf_array_append(arr,extra);
        cf_release(extra);
    }
    dictionary->streams=arr;
    response_dictionary=dictionary;
}
static void uninstall_response(void) {
    cf_release(response_dictionary);
    response_dictionary=NULL;
}
struct NativeLocals {
    void *message;
    void *streams;
};
static void run_ensure(struct NativeLocals *call,Obj *video) {
    CHECK(offsetof(struct NativeLocals,streams)-
          offsetof(struct NativeLocals,message)==8);
    shim_screen_ensure_stream(&call->streams, video);
}
static Obj *stock_video(void) {
    Obj *v=obj(DICT);v->type=110;return v;
}
static void cleanup(struct NativeLocals *loc,Obj *video,char *raw) {
    cf_release(loc->streams);
    cf_release(video);
    free(raw);
    CHECK(live_objects==0);
    CHECK(!lock_violation);
}

static void test_valid_combined_setup_to_stock_response(void) {
    fresh_session(101);
    char *raw=NULL; char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(array_ensure_calls==1);
    Obj *arr=n.streams;
    CHECK(arr && arr->count==2);
    CHECK(arr->entries[0]==video && video->type==110);
    Obj *sd=arr->entries[1];
    CHECK(sd->type==CLUSTER_STREAM_TYPE);
    CHECK(sd->connid==UINT64_C(0x1122334455667788));
    CHECK(sd->latency==25);
    CHECK(g_combo_inflight_generation==101);
    CHECK(g_combo_build[0].message==msg);
    CHECK(shim_screen_http_send((void *)(uintptr_t)0x9000,msg)==0);
    CHECK(send_calls==1 && last_http_msg==msg);
    CHECK(last_native_callback_field==(char*)&shim_screen_response);
    CHECK(tracked()==1);
    CHECK(g_combo_send_inflight==0);
    install_response(1,5566);
    shim_screen_response(msg);
    CHECK(stock_calls==1 && worker_calls==1);
    CHECK(last_worker_port==5566 && last_worker_gen==101);
    CHECK(last_worker_conn==UINT64_C(0x1122334455667788));
    CHECK(tracked()==0);
    uninstall_response();
    cleanup(&n,video,raw);
    puts("PASS: actual 110/111 array construction, paired send, callback and port-validated worker");
}
static void test_stock_only_without_current_session(void) {
    fresh_session(102);
    g_session_valid=0;g_session=NULL;
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(((Obj*)n.streams)->count==1);
    CHECK(((Obj*)n.streams)->entries[0]==video);
    CHECK(g_combo_inflight_generation==0 && tracked()==0);
    CHECK(shim_screen_http_send((void*)(uintptr_t)0x9000,msg)==0);
    CHECK(send_calls==1 && tracked()==0);
    CHECK(last_native_callback_field==(char*)STOCK_SCREEN_RESPONSE_VA);
    cleanup(&n,video,raw);
    puts("PASS: stock 110 request remains unchanged when combined session absent");
}
static void test_pair_verification_disables_only_111(void) {
    fresh_session(103);
    pair_verify=1;
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(((Obj*)n.streams)->count==1 && tracked()==0);
    CHECK(g_combo_inflight_generation==0);
    CHECK(shim_screen_http_send((void*)(uintptr_t)0x9000,msg)==0);
    CHECK(last_native_callback_field==(char*)STOCK_SCREEN_RESPONSE_VA);
    cleanup(&n,video,raw);
    puts("PASS: peer verification disables injected 111 without suppressing stock send");
}
static void test_uuid_failure_preserves_stock_110(void) {
    fresh_session(104);
    uuid_zero=1;
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(((Obj*)n.streams)->count==1 && tracked()==0);
    CHECK(g_combo_inflight_generation==0);
    cleanup(&n,video,raw);
    puts("PASS: invalid connid aborts optional 111 construction");
}
static void test_null_client_rejects_known_111_before_native_send(void) {
    fresh_session(105);
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(((Obj*)n.streams)->count==2);
    CHECK(shim_screen_http_send(NULL,msg)!=0);
    CHECK(send_calls==0 && tracked()==0);
    CHECK(g_combo_send_inflight==0);
    cleanup(&n,video,raw);
    puts("PASS: accepted 111 without HTTP client fails closed before stock enqueue");
}
static void test_native_prep_error_reclaims_never_submitted_ticket(void) {
    fresh_session(106);
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    send_result=-19;
    CHECK(shim_screen_http_send((void*)(uintptr_t)0x9000,msg)==-19);
    CHECK(send_calls==1 && tracked()==0);
    cleanup(&n,video,raw);
    puts("PASS: nonzero native preparation error reclaims only known non-enqueued ticket");
}
static void test_stale_response_always_calls_stock_but_never_starts_111(void) {
    fresh_session(107);
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(shim_screen_http_send((void*)(uintptr_t)0x9000,msg)==0);
    CHECK(tracked()==1);
    /* Emulate teardown cancellation only: this is the real source helper. */
    pthread_mutex_lock(&g_state_lock);
    g_session_valid=0;g_session=NULL;++g_session_generation;
    combo_cancel_all_requests_locked();
    pthread_mutex_unlock(&g_state_lock);
    CHECK(tracked()==1);
    install_response(1,5666);
    shim_screen_response(msg);
    CHECK(stock_calls==1 && worker_calls==0 && tracked()==0);
    uninstall_response();
    cleanup(&n,video,raw);
    puts("PASS: canceled late 111 response delegates to stock without new-session transport");
}
static void test_invalid_111_port_does_not_spawn_worker(void) {
    fresh_session(108);
    char *raw=NULL;char *msg=make_msg(&raw);
    Obj *video=stock_video();
    struct NativeLocals n={msg,NULL};
    run_ensure(&n,video);
    CHECK(shim_screen_http_send((void*)(uintptr_t)0x9000,msg)==0);
    install_response(1,65536);
    shim_screen_response(msg);
    CHECK(stock_calls==1 && worker_calls==0 && tracked()==0);
    uninstall_response();
    cleanup(&n,video,raw);
    puts("PASS: out-of-range stream-111 dataPort rejected while stock callback still runs");
}
int main(void) {
    test_valid_combined_setup_to_stock_response();
    test_stock_only_without_current_session();
    test_pair_verification_disables_only_111();
    test_uuid_failure_preserves_stock_110();
    test_null_client_rejects_known_111_before_native_send();
    test_native_prep_error_reclaims_never_submitted_ticket();
    test_stale_response_always_calls_stock_but_never_starts_111();
    test_invalid_111_port_does_not_spawn_worker();
    CHECK(tracked()==0);
    return 0;
}
'''

# Include the actual code under test, with only host-compatible type/function
# bindings supplied around it. Never transform the hook bodies themselves.
code = harness.replace("{{CTX_TYPE}}",ctx_type).replace(
    "{{WORKER_TYPE}}",worker_type).replace("{{HELPERS}}",helpers).replace(
    "{{ENSURE}}",ensure).replace("{{SEND}}",send).replace(
    "{{RESPONSE}}",response
)
with tempfile.TemporaryDirectory(prefix="ak3918-step140-") as directory:
    path = Path(directory) / "step140_source_hooks.c"
    path.write_text(code)
    for mode, flags in (("normal",[]),("ubsan",["-fsanitize=undefined"])):
        output = Path(directory) / ("step140_"+mode)
        cmd = ["cc","-std=gnu11","-O1","-g","-Wall","-Wextra","-Werror",
               "-Wno-unused-function","-Wno-unused-variable","-pthread",
               *flags,str(path),"-o",str(output)]
        subprocess.run(cmd,check=True,timeout=30)
        subprocess.run([str(output)],check=True,timeout=25,
                       env=dict(os.environ,UBSAN_OPTIONS="halt_on_error=1"))
print("PASS: Step140 source-derived 110/111 handshake contract (normal + UBSan)")

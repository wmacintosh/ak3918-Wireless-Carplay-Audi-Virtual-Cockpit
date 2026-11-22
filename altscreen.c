#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

/* ARM AK3918AN (ak_202610081659) verified addresses */
#define SETUP_VA                0x0006a60cu
#define SETUP_HOOK_PTR_VA       0x001369fcu
#define FINALIZE_HOOK_PTR_VA    0x0013c640u
#define ADD_RESPONSE_STREAM_VA  0x000652d4u
#define SERVER_SOCKET_OPEN_VA   0x000b709cu

/* Receiver-side CFLString keys */
#define KEY_STREAMS             ((void *)0x000ffce1u)
#define KEY_TYPE                ((void *)0x000ffef3u)
#define KEY_DATAPORT            ((void *)0x00100219u)
#define K_CMD_PARAMS            ((void *)0x001002fau)
#define K_CMD_URL               ((void *)0x00100452u)

/* CFL callbacks (.dynsym) */
#define CB_ARRAY_VA             ((void *)0x00134200u)
#define CB_DICT_KEY_VA          ((void *)0x001341e8u)
#define CB_DICT_VAL_VA          ((void *)0x001341d4u)
#define ALT_SCREEN_TYPE         111

#define CLUSTER_STREAM_TYPE     0x6f
#define CLUSTER_UUID            "b7e6c5a0-2222-4000-8000-000000000002"
#define CLUSTER_MAP_URL         "maps:/car/instrumentcluster/map"
/* luka-dev/mib2q-carplay-rgi uses 1440x542 (MIBSI uses 1440x540) */
#define CLUSTER_W               1440
#define CLUSTER_H               542
#define CLUSTER_W_F32_BITS      0x44b40000u /* 1440.0f */
#define CLUSTER_H_F32_BITS      ((CLUSTER_H == 542) ? 0x44078000u : 0x44070000u)

/* Client-side CFLString keys */
#define K_STREAMS               ((void *)0x000f63f9u)
#define K_TYPE                  ((void *)0x000f6409u)
#define K_DATAPORT              ((void *)0x000f6416u)
#define K_CONNID                ((void *)0x000f6475u)
#define K_UUID                  ((void *)0x000f6490u)
#define K_LATENCYMS             ((void *)0x000f649du)

/* Globals in sdDongle */
#define GPEERADDR               ((void *)0x0013bca0u)
#define GPAIRVERIFY_HK          ((int *)0x0013a7e4u)
#define GSESSION_AESKEY         ((void *)0x0013a800u)

/* Build-time controls & lifecycle limits */
#ifndef AK_ENABLE_PHONE_CMDS
#define AK_ENABLE_PHONE_CMDS    0
#endif
#ifndef ALTSCREEN_LOG_PATH
#define ALTSCREEN_LOG_PATH      "/usr/data/log/altscreen.log"
#endif
#define ALTSCREEN_LOG_MAX_BYTES (64u * 1024u)
#define POLL_SLICE_MS           500
#define SINK_ACCEPT_TIMEOUT_MS  30000
#define CLUSTER_KEY_WAIT_MS     5000
#define CAR_SEND_TIMEOUT_SEC    3
/* Experimental combined car SETUP, disabled unless paired ARM hooks are installed. */
#ifndef AK_ENABLE_COMBINED_CLUSTER
#define AK_ENABLE_COMBINED_CLUSTER 0
#endif
#define STOCK_SCREEN_RESPONSE_VA 0x0002ec7cu
#define SCREEN_STREAM_PTR_SLOT_VA 0x0013c644u
#define SCREEN_SEND_PTR_SLOT_VA   0x0013c648u
#define COMBINED_REQUEST_LIMIT   8

typedef int (*setup_fn)(void *, void *, void **);
typedef int (*add_stream_fn)(void *, void *);
typedef int (*server_socket_open_fn)(int, int, int, int, int *, unsigned, int *);
typedef unsigned long (*type_id_fn)(void);
typedef unsigned long (*gettypeid_fn)(void *);
typedef void *(*dget_typed_fn)(void *, void *, unsigned long, int *);
typedef int64_t (*dget_i64_fn)(void *, void *, int *);
typedef void (*dset_i64_fn)(void *, void *, int64_t);
typedef void (*dset_val_fn)(void *, void *, void *);
typedef void (*dsetcstr_fn)(void *, void *, void *, unsigned);
typedef void *(*dmk_fn)(void *, long, void *, void *);
typedef void *(*amk_fn)(void *, long, void *);
typedef long (*acount_fn)(void *);
typedef void *(*aat_fn)(void *, long);
typedef void (*aappend_fn)(void *, void *);
typedef void (*aensure_fn)(void **, void *);
typedef void (*release_fn)(void *);

typedef int (*uuidget_fn)(void *);
typedef int (*httpsend_fn)(void *, void *);
typedef void *(*plistrd_fn)(void *, int, int *);
typedef void (*sockcopy_fn)(void *, void *);
typedef void (*sockport_fn)(void *, int);
typedef int (*socksize_fn)(void *);
typedef void (*qos_fn)(int, int);

typedef int (*derive_fn)(void *, int, void *, int, void *, int, void *, void *);
typedef void (*aesinit_fn)(void *, void *, void *);
typedef void (*aesupd_fn)(void *, void *, int, void *);
/* ARM EABI 64-bit connID passed in r2:r3 */
typedef void (*derive_screen_fn)(void *, int, uint64_t, void *, void *);
typedef int (*streamkeys_fn)(void *, int, uint64_t, int, void *, void *);
typedef void (*ccinit_fn)(void *, void *, void *);
typedef void (*ccaad_fn)(void *, void *, int);
typedef int (*ccdec_fn)(void *, void *, int, void *);
typedef int (*ccver_fn)(void *, void *, void *, int *);
typedef int (*sendcmd_fn)(void *, void *, void *, void *);

static setup_fn orig_setup = (setup_fn)SETUP_VA;
static add_stream_fn add_response_stream = (add_stream_fn)ADD_RESPONSE_STREAM_VA;
static server_socket_open_fn server_socket_open = (server_socket_open_fn)SERVER_SOCKET_OPEN_VA;

static type_id_fn cf_array_type_id = (type_id_fn)0x00082ca8u;
#if AK_ENABLE_COMBINED_CLUSTER
static type_id_fn cf_dict_type_id = (type_id_fn)0x00083564u;
static gettypeid_fn cf_get_type_id = (gettypeid_fn)0x00082c34u;
#endif
static dget_typed_fn cf_dict_get_typed = (dget_typed_fn)0x000945c8u;
static dget_i64_fn cf_dict_get_int64 = (dget_i64_fn)0x000943ccu;
static dset_i64_fn cf_dict_set_int64 = (dset_i64_fn)0x00096b00u;
static dset_val_fn cf_dict_set_value = (dset_val_fn)0x000836dcu;
#if AK_ENABLE_COMBINED_CLUSTER || AK_ENABLE_PHONE_CMDS
static dsetcstr_fn cf_dict_set_cstr = (dsetcstr_fn)0x0009397cu;
#endif
static dmk_fn cf_dict_create_mutable = (dmk_fn)0x00083568u;
static amk_fn cf_array_create_mutable = (amk_fn)0x00082e10u;
static acount_fn cf_array_count = (acount_fn)0x00082e58u;
static aat_fn cf_array_at = (aat_fn)0x00082e90u;
static aappend_fn cf_array_append = (aappend_fn)0x00082fc0u;
#if AK_ENABLE_COMBINED_CLUSTER
static aensure_fn cf_arr_ensure = (aensure_fn)0x0009327cu;
#endif
static release_fn cf_release = (release_fn)0x00082c78u;

#if AK_ENABLE_COMBINED_CLUSTER
static uuidget_fn cf_uuidget = (uuidget_fn)0x000d03a4u;
static httpsend_fn http_send = (httpsend_fn)0x000a6974u;
static plistrd_fn cf_plist_read = (plistrd_fn)0x0008e414u;
#endif
#if AK_ENABLE_COMBINED_CLUSTER
static sockcopy_fn sock_copy = (sockcopy_fn)0x000b82dcu;
static sockport_fn sock_setport = (sockport_fn)0x000b7858u;
static socksize_fn sock_getsize = (socksize_fn)0x000b6ce8u;
#endif
#if AK_ENABLE_COMBINED_CLUSTER
static qos_fn sock_qos = (qos_fn)0x000b6128u;
#endif

#if AK_ENABLE_COMBINED_CLUSTER
static derive_fn aes_derive = (derive_fn)0x0002b884u;
#endif
static aesinit_fn aesctr_init = (aesinit_fn)0x0007ca74u;
static aesupd_fn aesctr_update = (aesupd_fn)0x0007cab4u;
static derive_screen_fn derive_screen = (derive_screen_fn)0x00073e84u;
static streamkeys_fn get_stream_keys = (streamkeys_fn)0x000654c0u;
static ccinit_fn cc_init = (ccinit_fn)0x000999e0u;
static ccaad_fn cc_aad = (ccaad_fn)0x00099e54u;
static ccdec_fn cc_dec = (ccdec_fn)0x00099f64u;
static ccver_fn cc_ver = (ccver_fn)0x0009a10cu;
#if AK_ENABLE_PHONE_CMDS
static sendcmd_fn session_send_command = (sendcmd_fn)0x000673e0u;
#endif

static void *arr_cb = CB_ARRAY_VA;
static void *dict_key_cb = CB_DICT_KEY_VA;
static void *dict_val_cb = CB_DICT_VAL_VA;

struct cluster_ctx {
    int fd;
    int retired;          /* Protected by g_state_lock */
    int refcnt;           /* Protected by g_state_lock */
    unsigned generation;
    pthread_mutex_t io_mu;
    unsigned char key[16];
    unsigned char iv[16];
    unsigned char aes_ctx[0x120] __attribute__((aligned(8)));
};

struct sink_args {
    int srv;
    uint64_t connid;
    int have_connid;
    unsigned generation;
    int crypto_mode; /* 0 = unavailable, 1 = ChaCha, 2 = AES */
    unsigned char key[32];
    unsigned char iv[16];
};

/* Lock hierarchy (strict): g_cluster_setup_lock > ctx->io_mu > g_state_lock */
#if AK_ENABLE_COMBINED_CLUSTER
static pthread_mutex_t g_cluster_setup_lock = PTHREAD_MUTEX_INITIALIZER;
#endif
static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_session_cv = PTHREAD_COND_INITIALIZER;

static struct cluster_ctx *g_cluster_ctx = NULL;
static unsigned g_cluster_ctx_generation = 0;
#if AK_ENABLE_COMBINED_CLUSTER
static unsigned g_cluster_connecting_gen = 0;
#endif

static void *g_session = NULL;
static int g_session_valid = 0;
static int g_session_cmd_inflight = 0;
static unsigned g_session_generation = 0;
static unsigned g_alt_seen_generation = 0;

#if AK_ENABLE_COMBINED_CLUSTER
struct cluster_worker_args {
    unsigned generation;
    uint64_t connid;
    int data_port;
};
static void *cluster_setup_to_car(void *arg);

/* All these tables are protected by g_state_lock. Never retain stock messages. */
struct combo_build {
    int in_use;
    int canceled;
    pthread_t owner;
    void *message; /* [sp+0x2c] of native frame, identity only; never owned. */
    unsigned generation;
    uint64_t connid;
};
/* An installed callback can outlive the session. Do not re-use its tracking
 * slot until the callback is observed. Pointers are only identities while a
 * record is held; ticket IDs distinguish simultaneous send/return paths. */
struct combo_request {
    int in_use;
    int canceled;
    void *message;
    unsigned generation;
    uint64_t connid;
    uint64_t ticket;
};
static struct combo_build g_combo_build[COMBINED_REQUEST_LIMIT];
static struct combo_request g_combo_request[COMBINED_REQUEST_LIMIT];
static unsigned g_combo_inflight_generation = 0;
static uint64_t g_combo_next_ticket = 0;

/* BEGIN STEP115 REQUEST HELPERS — caller must hold g_state_lock. */
static void combo_cancel_all_requests_locked(void) {
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        if (g_combo_request[i].in_use) {
            g_combo_request[i].canceled = 1;
            g_combo_request[i].generation = 0;
            g_combo_request[i].connid = 0;
        }
    }
}

static int combo_claim_request_locked(void *msg, unsigned gen, uint64_t connid,
                                      uint64_t *ticket_out) {
    if (!msg || !gen || !connid || !ticket_out ||
        g_combo_next_ticket == UINT64_MAX) return 0;

    /* Never overwrite even a canceled record for the same address. */
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        if (g_combo_request[i].in_use && g_combo_request[i].message == msg)
            return 0;
    }
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        if (g_combo_request[i].in_use) continue;
        struct combo_request *r = &g_combo_request[i];
        r->in_use = 1;
        r->canceled = 0;
        r->message = msg;
        r->generation = gen;
        r->connid = connid;
        r->ticket = ++g_combo_next_ticket;
        *ticket_out = r->ticket;
        return 1;
    }
    return 0; /* Fail closed if callbacks never arrive and slots fill. */
}

static void combo_cancel_ticket_locked(uint64_t ticket) {
    if (!ticket) return;
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        struct combo_request *r = &g_combo_request[i];
        if (r->in_use && r->ticket == ticket) {
            r->canceled = 1;
            r->generation = 0;
            r->connid = 0;
            return;
        }
    }
}

/* Only reclaim records when this wrapper is certain native http_send was
 * NEVER invoked. A nonzero native return alone cannot guarantee there will
 * be no future callback; retain a canceled tombstone in that case. */
static void combo_forget_never_submitted_locked(uint64_t ticket) {
    if (!ticket) return;
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        struct combo_request *r = &g_combo_request[i];
        if (r->in_use && r->ticket == ticket) {
            memset(r, 0, sizeof *r);
            return;
        }
    }
}

static void combo_consume_response_locked(void *msg,
                                          unsigned *gen_out,
                                          uint64_t *connid_out) {
    *gen_out = 0;
    *connid_out = 0;
    if (!msg) return;
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        struct combo_request *r = &g_combo_request[i];
        if (!r->in_use || r->message != msg) continue;
        unsigned tracked_gen = r->generation;
        if (!r->canceled && tracked_gen != 0 &&
            tracked_gen == g_session_generation &&
            g_session_valid && g_session != NULL) {
            *gen_out = tracked_gen;
            *connid_out = r->connid;
        }
        memset(r, 0, sizeof *r);
        if (tracked_gen != 0 && g_combo_inflight_generation == tracked_gen)
            g_combo_inflight_generation = 0;
        return;
    }
}
/* END STEP115 REQUEST HELPERS */

/* BEGIN STEP120 SEND GATE — all helpers require g_state_lock.
 * A published stream-111 array must not be sent without a valid response hook.
 * Teardown cancels build entries but leaves them until their native send hook.
 * Early native failure may strand a slot; deliberate fail-closed behaviour. */
static void combo_cancel_all_builds_locked(void) {
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        if (g_combo_build[i].in_use) g_combo_build[i].canceled = 1;
    }
}

static int combo_owner_has_build_locked(pthread_t owner) {
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        if (g_combo_build[i].in_use &&
            pthread_equal(g_combo_build[i].owner, owner)) return 1;
    }
    return 0;
}

/* A fresh invocation of the native ensure hook invalidates older builds on
 * this thread. This prevents a stale build from claiming an allocator-reused
 * message address on a later stock request. Keep the tombstone so an older
 * in-flight call cannot transmit its stream-111 message without tracking. */
static void combo_cancel_owner_builds_locked(pthread_t owner) {
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        if (g_combo_build[i].in_use &&
            pthread_equal(g_combo_build[i].owner, owner))
            g_combo_build[i].canceled = 1;
    }
}

/*  0: no injected stream (stock send unchanged)
 *  1: injected stream with callback successfully claimed
 * -1: stream 111 was injected but must NOT be sent (stale/untrackable)
 * Caller installs shim_screen_response on status 1, and returns -1 to
 * native code without calling http_send on status -1. */
static int combo_prepare_send_locked(pthread_t owner, void *msg,
                                     int callback_is_stock,
                                     unsigned *gen_out, uint64_t *ticket_out) {
    *gen_out = 0;
    *ticket_out = 0;
    for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
        struct combo_build *b = &g_combo_build[i];
        if (!b->in_use || !pthread_equal(b->owner, owner)) continue;
        /* An orphan from an earlier native call is not the current message.
         * Leave it reserved rather than corrupt stock-only response tracking. */
        if (b->message != msg) continue;
        unsigned gen = b->generation;
        uint64_t connid = b->connid;
        int valid = !b->canceled && gen != 0 &&
                    gen == g_session_generation && g_session_valid &&
                    g_session != NULL && g_alt_seen_generation == gen &&
                    g_combo_inflight_generation == gen;
        memset(b, 0, sizeof *b); /* Native request reached its send hook. */
        if (!valid || !callback_is_stock ||
            !combo_claim_request_locked(msg, gen, connid, ticket_out)) {
            if (g_combo_inflight_generation == gen)
                g_combo_inflight_generation = 0;
            return -1;
        }
        *gen_out = gen;
        return 1;
    }
    return 0;
}
/* END STEP120 SEND GATE */

/* BEGIN STEP128 SEND ADMISSION GATE — all helpers require g_state_lock.
 * Stock HTTPClientSendMessage (0xa6974) is verified non-blocking enqueue-only
 * (CFRetain x2 + dispatch_async_f at 0xa1900; never invokes 0xa6040 or
 * msg+0x904 synchronously). Tracking in-flight admitted sends lets teardown and
 * session switches drain active enqueue calls without holding g_state_lock
 * across stock transport or deadlocking against shim_screen_response. */
static int g_combo_send_inflight = 0;

static void combo_send_enter_locked(void) {
    g_combo_send_inflight++;
}

static void combo_send_leave_locked(int rc, unsigned gen, uint64_t ticket) {
    if (rc != 0) {
        /* Do NOT clear this slot merely because native http_send failed:
         * until all native failure paths are proven non-enqueueing, a late
         * response may still run the shim callback for this message. */
        combo_cancel_ticket_locked(ticket);
        if (g_combo_inflight_generation == gen)
            g_combo_inflight_generation = 0;
    }
    if (--g_combo_send_inflight == 0) {
        pthread_cond_broadcast(&g_session_cv);
    }
}

static void combo_wait_sends_drained_locked(void) {
    while (g_combo_send_inflight > 0) {
        pthread_cond_wait(&g_session_cv, &g_state_lock);
    }
}
/* END STEP128 SEND ADMISSION GATE */

static void shim_screen_response(void *msg);
#endif

static void secure_wipe(void *ptr, size_t len) {
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    while (len--) *p++ = 0;
}

static int buf_nonzero(const unsigned char *p, size_t len) {
    unsigned char acc = 0;
    for (size_t i = 0; i < len; i++) acc |= p[i];
    return acc != 0;
}

static uint32_t load_u32_le(const unsigned char *p) {
    uint32_t v;
    memcpy(&v, p, sizeof v);
    return v;
}

static void store_u32_le(unsigned char *p, uint32_t v) {
    memcpy(p, &v, sizeof v);
}

/* Preserve errno, keep lines atomic, and cap log size to protect flash. */
static void dbg(const char *msg, int n) {
    int saved_errno = errno;
    char line[128];
    int len = snprintf(line, sizeof line, "AKDIAG %s %d\n", msg, n);
    if (len > 0 && len < (int)sizeof line) {
        int fd = open(ALTSCREEN_LOG_PATH, O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (fd >= 0) {
            struct stat st;
            if (fstat(fd, &st) == 0 && (size_t)st.st_size < ALTSCREEN_LOG_MAX_BYTES) {
                ssize_t ignored = write(fd, line, (size_t)len);
                (void)ignored;
            }
            close(fd);
        }
    }
    errno = saved_errno;
}

static int has_idr(const unsigned char *b, unsigned len) {
    unsigned pos = 0;
    while (pos + 5u <= len) {
        unsigned nlen = ((unsigned)b[pos] << 24) |
                        ((unsigned)b[pos + 1] << 16) |
                        ((unsigned)b[pos + 2] << 8) |
                        (unsigned)b[pos + 3];
        if ((b[pos + 4] & 0x1fu) == 5u) return 1;
        if (nlen == 0u || nlen > len - pos - 4u) break;
        pos += 4u + nlen;
    }
    return 0;
}

static int sink_generation_current(unsigned generation) {
    int current;
    pthread_mutex_lock(&g_state_lock);
    current = (generation != 0 &&
               generation == g_session_generation &&
               g_session_valid &&
               g_session != NULL);
    pthread_mutex_unlock(&g_state_lock);
    return current;
}

static void cluster_ctx_destroy(struct cluster_ctx *ctx) {
    if (!ctx) return;
    if (ctx->fd >= 0) close(ctx->fd);
    pthread_mutex_destroy(&ctx->io_mu);
    secure_wipe(ctx->key, sizeof ctx->key);
    secure_wipe(ctx->iv, sizeof ctx->iv);
    secure_wipe(ctx->aes_ctx, sizeof ctx->aes_ctx);
    free(ctx);
}

static struct cluster_ctx *cluster_ctx_acquire(unsigned generation) {
    struct cluster_ctx *ctx = NULL;
    pthread_mutex_lock(&g_state_lock);
    if (g_cluster_ctx && !g_cluster_ctx->retired &&
        generation != 0 &&
        generation == g_session_generation &&
        generation == g_cluster_ctx_generation) {
        ctx = g_cluster_ctx;
        ctx->refcnt++;
    }
    pthread_mutex_unlock(&g_state_lock);
    return ctx;
}

static void cluster_ctx_release(struct cluster_ctx *ctx) {
    int destroy = 0;
    if (!ctx) return;
    pthread_mutex_lock(&g_state_lock);
    if (--ctx->refcnt == 0) destroy = 1;
    pthread_mutex_unlock(&g_state_lock);
    if (destroy) cluster_ctx_destroy(ctx);
}

static void cluster_retire(struct cluster_ctx *target) {
    struct cluster_ctx *old = NULL;
    int fd_to_shutdown = -1;

    pthread_mutex_lock(&g_state_lock);
    if (g_cluster_ctx && (!target || g_cluster_ctx == target)) {
        old = g_cluster_ctx;
        old->retired = 1;
        fd_to_shutdown = old->fd;
        g_cluster_ctx = NULL;
        g_cluster_ctx_generation = 0;
    } else if (target) {
        target->retired = 1;
    }
    pthread_mutex_unlock(&g_state_lock);

    if (old) {
        /* Safe: we still hold the global ref until cluster_ctx_release(old). */
        if (fd_to_shutdown >= 0) shutdown(fd_to_shutdown, SHUT_RDWR);
        dbg("cluster retired generation", (int)old->generation);
        cluster_ctx_release(old);
    }
}

/* Ready to wire to sdDongle's session finalize/teardown hook once located. */
void shim_session_teardown(void *session) {
    struct cluster_ctx *retired = NULL;
    int retired_fd = -1;

    pthread_mutex_lock(&g_state_lock);

    if (session != NULL && g_session == session) {
        g_session_valid = 0;
        g_session = NULL;
        g_session_generation++;
#if AK_ENABLE_COMBINED_CLUSTER
        g_combo_inflight_generation = 0;
        combo_cancel_all_builds_locked();
        /* Keep canceled tombstones until the wrapper callback arrives. */
        combo_cancel_all_requests_locked();
        /* A late callback still runs stock, but is forbidden to start transport. */
#endif

        /* Detach only this session's cluster while holding the lock. */
        if (g_cluster_ctx) {
            retired = g_cluster_ctx;
            retired->retired = 1;
            retired_fd = retired->fd;
            g_cluster_ctx = NULL;
            g_cluster_ctx_generation = 0;
        }

        while (g_session_cmd_inflight > 0
#if AK_ENABLE_COMBINED_CLUSTER
               || g_combo_send_inflight > 0
#endif
        ) {
            pthread_cond_wait(&g_session_cv, &g_state_lock);
        }
    }

    pthread_mutex_unlock(&g_state_lock);

    if (retired) {
        if (retired_fd >= 0)
            shutdown(retired_fd, SHUT_RDWR);
        dbg("cluster retired generation", (int)retired->generation);
        cluster_ctx_release(retired);
    }
}

#if AK_ENABLE_PHONE_CMDS
static int tcp_socket_alive(int fd) {
    if (fd < 0) return 0;
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = 0;
    pfd.revents = 0;
    int pr = poll(&pfd, 1, 0);
    if (pr < 0) return errno == EINTR;
    if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) return 0;
    return 1;
}

static int send_phone_cmd_safe(unsigned generation, int phone_fd,
                               const char *type, int with_url) {
    if (!tcp_socket_alive(phone_fd)) return -1;

    void *session = NULL;
    pthread_mutex_lock(&g_state_lock);
    if (generation != 0 && generation == g_session_generation &&
        g_session != NULL && g_session_valid) {
        session = g_session;
        g_session_cmd_inflight++;
    }
    pthread_mutex_unlock(&g_state_lock);
    if (!session) return -1;

    int rc = -1;
    void *req = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    void *params = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    if (req && params) {
        cf_dict_set_cstr(req, KEY_TYPE, (void *)type, 0xffffffffu);
        cf_dict_set_cstr(params, K_UUID, (void *)CLUSTER_UUID, 0xffffffffu);
        if (with_url) cf_dict_set_cstr(params, K_CMD_URL, (void *)CLUSTER_MAP_URL, 0xffffffffu);
        cf_dict_set_value(req, K_CMD_PARAMS, params);
        cf_release(params);
        params = NULL;
        if (tcp_socket_alive(phone_fd) && sink_generation_current(generation)) {
            rc = session_send_command(session, req, 0, 0);
        }
    }
    if (params) cf_release(params);
    if (req) cf_release(req);

    pthread_mutex_lock(&g_state_lock);
    if (--g_session_cmd_inflight == 0) {
        pthread_cond_broadcast(&g_session_cv);
    }
    pthread_mutex_unlock(&g_state_lock);
    return rc;
}
#endif

/* Cluster negotiation is piggybacked only on native outgoing screen SETUP.
 * Retries must wait for another native SETUP, never use *GAIRPLAYCLIENT.
 * This intentionally trades automatic reconnection for fail-closed safety. */
#if AK_ENABLE_COMBINED_CLUSTER
static void cluster_clear_connecting(unsigned generation) {
    pthread_mutex_lock(&g_state_lock);
    if (g_cluster_connecting_gen == generation) g_cluster_connecting_gen = 0;
    pthread_mutex_unlock(&g_state_lock);
}
#endif

static void cluster_maybe_start(unsigned generation, int force) {
    (void)generation;
    (void)force;
    /* No worker can be spawned until a validated stock response supplies
       dataPort and the connection ID for its specific request. */
}

#if AK_ENABLE_COMBINED_CLUSTER
/* The stock code calls cf_arr_ensure(&streams, video110) at 0x2FADC.
 * This wrapper appends 111 to the *same* array prior to serialization.
 * Fail closed if no phone SETUP generation exists yet. */
void shim_screen_ensure_stream(void **streams, void *stock_video) {
    pthread_t self = pthread_self();
    pthread_mutex_lock(&g_state_lock);
    combo_cancel_owner_builds_locked(self); /* New native invocation. */
    pthread_mutex_unlock(&g_state_lock);

    cf_arr_ensure(streams, stock_video);  /* Always preserve original behaviour. */
    if (!streams || !*streams || *GPAIRVERIFY_HK != 0) return;

    /* Exact verified stock callsite: 0x2fad8 passes &sp[0x34], while the
     * already-created HTTP message occupies sp[0x2c] (0x2f784/0x2fb88).
     * 32-bit ARM stack layout, NOT a portable API. Never retain this pointer. */
    void *native_msg = *(void **)((uintptr_t)streams - 8u);
    if (!native_msg) return;

    unsigned gen = 0;
    int build_slot = -1;
    pthread_mutex_lock(&g_state_lock);
    if (g_session_valid && g_session && g_session_generation != 0 &&
        g_alt_seen_generation == g_session_generation &&
        g_combo_inflight_generation == 0 &&
        g_cluster_connecting_gen != g_session_generation &&
        !(g_cluster_ctx && !g_cluster_ctx->retired &&
          g_cluster_ctx_generation == g_session_generation)) {
        /* Never overwrite an unfinished or canceled build from this thread.
         * It may still own an already-serialized stream-111 request. */
        if (!combo_owner_has_build_locked(self)) {
            for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
                if (!g_combo_build[i].in_use) { build_slot = i; break; }
            }
        }
        int have_req_slot = 0;
        for (int i = 0; i < COMBINED_REQUEST_LIMIT; ++i) {
            if (!g_combo_request[i].in_use) { have_req_slot = 1; break; }
        }
        if (build_slot >= 0 && have_req_slot) {
            gen = g_session_generation;
            g_combo_inflight_generation = gen; /* Reserve before CF calls. */
        }
    }
    pthread_mutex_unlock(&g_state_lock);
    if (!gen) return;

    uint64_t connid = 0;
    void *sd = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    if (sd) {
        unsigned char uuid[16] = {0};
        /* Stock already uses this generator; its return convention is unknown.
         * Treat a zero connection ID as failure without assuming an rc value. */
        (void)cf_uuidget(uuid);
        unsigned hi = ((unsigned)uuid[0] << 24) | ((unsigned)uuid[1] << 16) |
                      ((unsigned)uuid[2] << 8) | (unsigned)uuid[3];
        unsigned lo = ((unsigned)uuid[4] << 24) | ((unsigned)uuid[5] << 16) |
                      ((unsigned)uuid[6] << 8) | (unsigned)uuid[7];
        connid = ((uint64_t)hi << 32) | lo;
        if (connid != 0) {
            cf_dict_set_int64(sd, K_CONNID, (int64_t)connid);
            cf_dict_set_int64(sd, K_TYPE, CLUSTER_STREAM_TYPE);
            cf_dict_set_cstr(sd, K_UUID, (void *)CLUSTER_UUID, 0xffffffffu);
            cf_dict_set_int64(sd, K_LATENCYMS, 25);
        }
    }

    /* Build a replacement array without holding the session lock.  CoreFoundation
     * may allocate, retain, release or invoke callbacks; none of those operations
     * may run while g_state_lock is held.  The original native stream array is
     * left untouched unless the replacement and generation both validate. */
    void *old_streams = streams ? *streams : NULL;
    void *replacement = NULL;
    if (sd && connid && old_streams) {
        long n = cf_array_count(old_streams);
        if (n > 0 && n <= 64) {
            void *copy = cf_array_create_mutable(0, 0, arr_cb);
            if (copy) {
                int valid = 1;
                for (long i = 0; i < n; ++i) {
                    void *item = cf_array_at(old_streams, i);
                    if (!item) { valid = 0; break; }
                    cf_array_append(copy, item);
                }
                if (valid && cf_array_count(copy) == n) {
                    cf_array_append(copy, sd);
                    if (cf_array_count(copy) == n + 1)
                        replacement = copy;
                }
                if (copy != replacement) cf_release(copy);
            }
        }
    }

    /* Publish the fully built array and its metadata as a single state
     * transition.  If teardown happened during construction, discard the
     * candidate and retain the unmodified stock stream array (type 110).
     * A later teardown may still cancel transport before native HTTP send;
     * callbacks must validate generation again and always delegate to stock. */
    void *replaced_streams = NULL;
    pthread_mutex_lock(&g_state_lock);
    if (replacement && streams && *streams == old_streams &&
        g_combo_inflight_generation == gen &&
        gen == g_session_generation && g_session_valid &&
        g_alt_seen_generation == gen &&
        g_cluster_connecting_gen != gen &&
        !(g_cluster_ctx && !g_cluster_ctx->retired &&
          g_cluster_ctx_generation == gen)) {
        replaced_streams = *streams;
        *streams = replacement;
        replacement = NULL;  /* Native SETUP now owns this CFArray reference. */
        g_combo_build[build_slot].in_use = 1;
        g_combo_build[build_slot].canceled = 0;
        g_combo_build[build_slot].owner = self;
        g_combo_build[build_slot].message = native_msg;
        g_combo_build[build_slot].generation = gen;
        g_combo_build[build_slot].connid = connid;
    } else {
        connid = 0;
        if (g_combo_inflight_generation == gen)
            g_combo_inflight_generation = 0;
    }
    pthread_mutex_unlock(&g_state_lock);
    if (replaced_streams) cf_release(replaced_streams);
    if (replacement) cf_release(replacement);
    if (sd) cf_release(sd);
    dbg(connid ? "combined stream 111 added" :
                 "combined stream 111 disabled", (int)gen);
}

/* Invoked instead of stock BL at 0x2FBB0, with original AAPCS (r0,r1).
 * Do not touch the original message context at +0x8fc: stock needs it.
 * The only temporary ownership here is our metadata, not a client reference. */
int shim_screen_http_send(void *client, void *msg) {
    int decision = 0;
    unsigned gen = 0;
    uint64_t ticket = 0;
    if (msg) {
        pthread_mutex_lock(&g_state_lock);
        int stock_cb = 0;
        if (combo_owner_has_build_locked(pthread_self())) {
            stock_cb = *(void **)((char *)msg + 0x904) ==
                       (void *)STOCK_SCREEN_RESPONSE_VA;
        }
        /* Require both native message-pointer and thread correlation. A fresh
         * array-ensure invocation cancels older records before allocator reuse.
         * This still cannot prove safety against teardown/send races. */
        decision = combo_prepare_send_locked(pthread_self(), msg, stock_cb,
                                             &gen, &ticket);
        if (decision == 1) {
            if (!client) {
                /* Known preflight failure: NO native send, NO callback.
                 * Reclaim just this ticket instead of leaking one of 8 slots. */
                combo_forget_never_submitted_locked(ticket);
                if (g_combo_inflight_generation == gen)
                    g_combo_inflight_generation = 0;
                ticket = 0;
                decision = -1;
            } else {
                *(void **)((char *)msg + 0x904) = (void *)&shim_screen_response;
                combo_send_enter_locked();
            }
        }
        pthread_mutex_unlock(&g_state_lock);
    }

    if (decision < 0) {
        /* No HTTP submission of a known stream-111 message if its session
         * expired or response tracking is unavailable. The stock caller's
         * nonzero-error path releases its message and continues cleanup. */
        dbg("combined stale 111 send rejected", (int)gen);
        return -1;
    }

    int rc = http_send(client, msg); /* Non-blocking enqueue; no shim lock held. */
    if (decision == 1) {
        pthread_mutex_lock(&g_state_lock);
        combo_send_leave_locked(rc, gen, ticket);
        pthread_mutex_unlock(&g_state_lock);
    }
    return rc;
}

static int combined_response_port(void *msg) {
    if (!msg) return 0;
    int len = *(int *)((char *)msg + 0x4a0);
    void *bytes = *(void **)((char *)msg + 0x49c);
    if (!bytes || len <= 0 || len > 4000000) return 0;
    int err = 0, port = 0;
    void *plist = cf_plist_read(bytes, len, &err);
    if (err == 0 && plist) {
        if (cf_get_type_id(plist) == cf_dict_type_id()) {
            void *streams = cf_dict_get_typed(plist, K_STREAMS, cf_array_type_id(), 0);
            if (streams) {
                long n = cf_array_count(streams);
                for (long i = 0; i < n; ++i) {
                    void *sd = cf_array_at(streams, i);
                    if (sd && cf_dict_get_int64(sd, K_TYPE, 0) == CLUSTER_STREAM_TYPE) {
                        int64_t v = cf_dict_get_int64(sd, K_DATAPORT, 0);
                        if (v > 0 && v <= 65535) port = (int)v;
                        break;
                    }
                }
            }
        }
    }
    if (plist) cf_release(plist);
    return port;
}

static void shim_screen_response(void *msg) {
    /* First claim the matching record, rejecting canceled or stale sessions.
     * Parse only a validated request while the HTTP response is still live.
     * The stock callback must always run, including for unmatched responses. */
    unsigned gen = 0;
    uint64_t connid = 0;
    pthread_mutex_lock(&g_state_lock);
    combo_consume_response_locked(msg, &gen, &connid);
    pthread_mutex_unlock(&g_state_lock);
    int port = (gen && connid) ? combined_response_port(msg) : 0;

    ((void (*)(void *))STOCK_SCREEN_RESPONSE_VA)(msg);

    if (!gen || !connid || port <= 0) {
        dbg("combined response no 111 port", port);
        return;
    }
    struct cluster_worker_args *arg = (struct cluster_worker_args *)malloc(sizeof *arg);
    if (!arg) return;
    arg->generation = gen;
    arg->connid = connid;
    arg->data_port = port;

    int start = 0;
    pthread_mutex_lock(&g_state_lock);
    if (gen == g_session_generation && g_session_valid && g_session &&
        g_cluster_connecting_gen != gen) {
        g_cluster_connecting_gen = gen;
        start = 1;
    }
    pthread_mutex_unlock(&g_state_lock);
    if (!start) { free(arg); return; }

    pthread_t worker;
    int rc = pthread_create(&worker, NULL, cluster_setup_to_car, arg);
    if (rc == 0) {
        pthread_detach(worker);
    } else {
        free(arg);
        cluster_clear_connecting(gen);
    }
}
#endif /* AK_ENABLE_COMBINED_CLUSTER */

static int writeall(int fd, const void *buf, int n) {
    const char *p = (const char *)buf;
    while (n > 0) {
        ssize_t w = send(fd, p, (size_t)n, MSG_NOSIGNAL);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (w == 0) {
            errno = EPIPE;
            return -1;
        }
        p += w;
        n -= (int)w;
    }
    return 0;
}

static int send_to_car(struct cluster_ctx *ctx, int type, unsigned char *body,
                       unsigned len, const char **failed_stage) {
    if (!ctx || !failed_stage) {
        errno = EINVAL;
        return -1;
    }
    unsigned char hdr[128] __attribute__((aligned(8)));
    memset(hdr, 0, sizeof hdr);
    store_u32_le(hdr, len);
    hdr[4] = (unsigned char)type;
    if (type == 1) {
        /* IEEE-754 float bits to avoid soft-float helper calls */
        store_u32_le(hdr + 0x10, CLUSTER_W_F32_BITS);
        store_u32_le(hdr + 0x14, CLUSTER_H_F32_BITS);
        store_u32_le(hdr + 0x28, CLUSTER_W_F32_BITS);
        store_u32_le(hdr + 0x2c, CLUSTER_H_F32_BITS);
    }

    pthread_mutex_lock(&ctx->io_mu);

    int retired;
    pthread_mutex_lock(&g_state_lock);
    retired = ctx->retired || (ctx->generation != g_session_generation);
    pthread_mutex_unlock(&g_state_lock);

    if (retired || ctx->fd < 0) {
        pthread_mutex_unlock(&ctx->io_mu);
        *failed_stage = "cluster socket retired";
        errno = EPIPE;
        return -1;
    }
    if (type == 0) aesctr_update(ctx->aes_ctx, body, (int)len, body);

    int rc = writeall(ctx->fd, hdr, 128);
    const char *failure = "cluster header send errno";
    if (rc == 0 && len > 0) {
        rc = writeall(ctx->fd, body, (int)len);
        failure = "cluster payload send errno";
    }
    int send_error = (rc == 0) ? 0 : errno;
    pthread_mutex_unlock(&ctx->io_mu);

    if (rc != 0) {
        *failed_stage = failure;
        cluster_retire(ctx);
        errno = send_error;
    }
    return rc;
}

static int accept_interruptible(int srv, unsigned generation) {
    int waited_ms = 0;
    while (waited_ms < SINK_ACCEPT_TIMEOUT_MS) {
        if (!sink_generation_current(generation)) {
            dbg("sink stale during accept", (int)generation);
            return -1;
        }
        struct pollfd pfd;
        pfd.fd = srv;
        pfd.events = POLLIN;
        pfd.revents = 0;
        int pr = poll(&pfd, 1, POLL_SLICE_MS);
        if (pr < 0) {
            if (errno == EINTR) continue;
            dbg("sink accept poll errno", errno);
            return -1;
        }
        if (pr == 0) {
            waited_ms += POLL_SLICE_MS;
            continue;
        }
        if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
            dbg("sink accept poll error", pfd.revents);
            return -1;
        }
        int c = accept(srv, NULL, NULL);
        if (c < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) continue;
            dbg("alt accept errno", errno);
            return -1;
        }
        return c;
    }
    dbg("sink accept timeout", (int)generation);
    return -1;
}

static int readn_interruptible(int fd, void *buf, int n, unsigned generation) {
    char *p = (char *)buf;
    int got = 0;
    while (got < n) {
        if (!sink_generation_current(generation)) {
            dbg("sink stale during read", (int)generation);
            return -1;
        }
        struct pollfd pfd;
        pfd.fd = fd;
        pfd.events = POLLIN;
        pfd.revents = 0;
        int pr = poll(&pfd, 1, POLL_SLICE_MS);
        if (pr < 0) {
            if (errno == EINTR) continue;
            dbg("sink read poll errno", errno);
            return -1;
        }
        if (pr == 0) continue;
        if (pfd.revents & POLLNVAL) return -1;

        ssize_t r = read(fd, p + got, (size_t)(n - got));
        if (r < 0) {
            if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) continue;
            dbg("sink phone read errno", errno);
            return -1;
        }
        if (r == 0) {
            dbg("sink phone EOF after bytes", got);
            return -1;
        }
        got += (int)r;
    }
    return 0;
}

static void *sink_thread(void *arg) {
    struct sink_args snapshot = *(struct sink_args *)arg;
    secure_wipe(arg, sizeof(struct sink_args));
    free(arg);

    int srv = snapshot.srv;
    int have_connid = snapshot.have_connid;
    dbg("alt sink thread up", (int)snapshot.generation);

    int c = accept_interruptible(srv, snapshot.generation);
    close(srv);
    if (c < 0) {
        secure_wipe(&snapshot, sizeof snapshot);
        return NULL;
    }

    int cfl = fcntl(c, F_GETFL, 0);
    if (cfl != -1) fcntl(c, F_SETFL, cfl & ~O_NONBLOCK);
    dbg("alt connected", (int)snapshot.generation);

    if (!sink_generation_current(snapshot.generation)) {
        dbg("sink stale after accept", (int)snapshot.generation);
        close(c);
        secure_wipe(&snapshot, sizeof snapshot);
        return NULL;
    }

#if AK_ENABLE_PHONE_CMDS
    {
        int sr = send_phone_cmd_safe(snapshot.generation, c, "showUI", 1);
        dbg("alt showUI err", sr);
    }
#else
    dbg("sink showUI disabled", 0);
#endif

    unsigned char dctx[0x120] __attribute__((aligned(8)));
    unsigned char cctx[0x200] __attribute__((aligned(8)));
    unsigned char cckey[32] = {0}, ccnonce[8] = {0};
    int dec_ready = 0, chacha = 0;

    if (snapshot.crypto_mode == 1) {
        memcpy(cckey, snapshot.key, sizeof cckey);
        dec_ready = 1;
        chacha = 1;
        dbg("sink copied chacha key ready", 1);
    } else if (snapshot.crypto_mode == 2) {
        aesctr_init(dctx, snapshot.key, snapshot.iv);
        dec_ready = 1;
        dbg("sink copied AES key ready", 1);
    } else {
        dbg("sink crypto unavailable", have_connid);
    }

    secure_wipe(snapshot.key, sizeof snapshot.key);
    secure_wipe(snapshot.iv, sizeof snapshot.iv);

    unsigned char hdr[128] __attribute__((aligned(8)));
    unsigned char *body = NULL;
    unsigned bodycap = 0;
    long frames = 0, pushed = 0;
    unsigned char *cfg_body = NULL;
    unsigned cfg_len = 0;
    const char *failed_stage = NULL;
    int cfg_sent = 0, got_idr = 0, wait_idr = 0, send_failed = 0;

    for (;;) {
        if (!sink_generation_current(snapshot.generation)) {
            dbg("sink stale session exit", (int)snapshot.generation);
            break;
        }
        if (readn_interruptible(c, hdr, 128, snapshot.generation) != 0) {
            dbg("sink header read ended", (int)frames);
            break;
        }
        unsigned bodylen = load_u32_le(hdr);
        int ftype = hdr[4];
        if (bodylen > 4000000u) {
            dbg("alt bad bodylen", (int)bodylen);
            break;
        }
        frames++;
        if (frames == 1) dbg("alt first frame type", ftype);
        if (bodylen == 0) continue;

        if (bodylen > bodycap) {
            unsigned char *nb = (unsigned char *)malloc(bodylen + 16u);
            if (!nb) {
                dbg("alt body malloc fail", (int)bodylen);
                break;
            }
            free(body);
            body = nb;
            bodycap = bodylen;
        }
        if (readn_interruptible(c, body, (int)bodylen, snapshot.generation) != 0) {
            dbg("sink payload read ended frame", (int)frames);
            break;
        }

        if (ftype == 0) {
            if (chacha) {
                if (bodylen < 16u) continue;
                int err = 0;
                cc_init(cctx, cckey, ccnonce);
                cc_aad(cctx, hdr, 128);
                int n = cc_dec(cctx, body, (int)(bodylen - 16u), body);
                if (n < 0 || (unsigned)n > bodylen - 16u) {
                    dbg("sink cipher invalid decrypt length", n);
                    break;
                }
                n += cc_ver(cctx, body + n, body + bodylen - 16u, &err);
                for (int k = 0; k < 8 && ++ccnonce[k] == 0; k++) {}
                if (err != 0 || n != (int)(bodylen - 16u)) {
                    dbg("alt chacha fail", err ? err : n);
                    continue;
                }
                bodylen -= 16u;
            } else if (dec_ready) {
                aesctr_update(dctx, body, (int)bodylen, body);
            }

            if (dec_ready && cfg_body) {
                struct cluster_ctx *ctx = cluster_ctx_acquire(snapshot.generation);
                if (!ctx) {
                    cfg_sent = 0;
                    got_idr = 0;
                    wait_idr = 0;
                    cluster_maybe_start(snapshot.generation, 0);
                    continue;
                }
                if (!cfg_sent) {
                    if (send_to_car(ctx, 1, cfg_body, cfg_len, &failed_stage) == 0) {
                        dbg("alt config sent late", (int)cfg_len);
                        cfg_sent = 1;
                        got_idr = 0;
                        wait_idr = 0;
                        send_failed = 0;
                    } else {
                        if (!send_failed) {
                            send_failed = 1;
                            dbg(failed_stage, errno);
                        }
                        cluster_ctx_release(ctx);
                        cluster_maybe_start(snapshot.generation, 0);
                        continue;
                    }
                }
                if (!got_idr && has_idr(body, bodylen)) {
                    got_idr = 1;
                    dbg("alt idr after frames", wait_idr);
                }
                if (!got_idr) {
                    if ((wait_idr++ % 120) == 0) {
#if AK_ENABLE_PHONE_CMDS
                        int kr = send_phone_cmd_safe(snapshot.generation, c, "forceKeyFrame", 0);
                        dbg("alt force keyframe err", kr < 0 ? -kr : kr);
#else
                        dbg("sink keyframe request disabled", wait_idr);
#endif
                    }
                    cluster_ctx_release(ctx);
                    continue;
                }
                if (send_to_car(ctx, 0, body, bodylen, &failed_stage) == 0) {
                    pushed++;
                    send_failed = 0;
                } else {
                    cfg_sent = 0;
                    got_idr = 0;
                    wait_idr = 0;
                    if (!send_failed) {
                        send_failed = 1;
                        dbg(failed_stage, errno);
                        dbg("alt send to car fail", (int)pushed);
                    }
                    cluster_maybe_start(snapshot.generation, 0);
                }
                cluster_ctx_release(ctx);
            }
        } else if (ftype == 1) {
            unsigned char *ncfg = (unsigned char *)malloc(bodylen);
            if (ncfg) {
                free(cfg_body);
                cfg_body = ncfg;
                memcpy(cfg_body, body, bodylen);
                cfg_len = bodylen;
                cfg_sent = 0;
            }
            if (cfg_body) {
                struct cluster_ctx *ctx = cluster_ctx_acquire(snapshot.generation);
                if (ctx) {
                    if (send_to_car(ctx, 1, cfg_body, cfg_len, &failed_stage) == 0) {
                        pushed++;
                        cfg_sent = 1;
                        got_idr = 0;
                        wait_idr = 0;
                        send_failed = 0;
                        dbg("alt config sent", (int)cfg_len);
                    } else {
                        if (!send_failed) {
                            send_failed = 1;
                            dbg(failed_stage, errno);
                        }
                        cluster_maybe_start(snapshot.generation, 0);
                    }
                    cluster_ctx_release(ctx);
                } else {
                    cluster_maybe_start(snapshot.generation, 0);
                }
            }
        }

        if ((frames % 300) == 0) dbg("alt frames pushed", (int)pushed);
    }

    dbg("alt stream end frames", (int)frames);
    free(body);
    free(cfg_body);
    close(c);

    secure_wipe(cckey, sizeof cckey);
    secure_wipe(ccnonce, sizeof ccnonce);
    secure_wipe(cctx, sizeof cctx);
    secure_wipe(dctx, sizeof dctx);
    secure_wipe(&snapshot, sizeof snapshot);
    return NULL;
}

static int open_alt_sink(void *session, unsigned generation,
                         uint64_t connid, int have_connid) {
    uint16_t family_u16;
    memcpy(&family_u16, (char *)session + 0x8c, sizeof family_u16);
    int family = (int)family_u16;

    int port = 0, fd = -1;
    int rc = server_socket_open(family, SOCK_STREAM, IPPROTO_TCP, 0, &port, 0xfffd4000u, &fd);
    if (rc != 0 || fd < 0) {
        dbg("alt ServerSocketOpen rc", rc);
        return 0;
    }
    int fl = fcntl(fd, F_GETFL, 0);
    if (fl != -1) fcntl(fd, F_SETFL, fl | O_NONBLOCK);

    struct sink_args *args = (struct sink_args *)malloc(sizeof *args);
    if (!args) {
        close(fd);
        dbg("sink args malloc fail", -1);
        return 0;
    }
    memset(args, 0, sizeof *args);
    args->srv = fd;
    args->connid = connid;
    args->have_connid = have_connid;
    args->generation = generation;

    /* Derive synchronously inside SETUP and log readiness for verification. */
    if (have_connid && connid != 0) {
        void *pvs = *(void **)((char *)session + 0x3ec);
        dbg("setup pvs present", pvs != NULL);
        if (pvs) {
            int key_rc = get_stream_keys((char *)session + 0x3ec, 0, connid, 0, 0, args->key);
            dbg("setup chacha key rc", key_rc);
            if (key_rc == 0) {
                args->crypto_mode = 1;
                dbg("setup key nonzero", buf_nonzero(args->key, 32));
            }
        } else {
            derive_screen((char *)session + 0x200, 0x10, connid, args->key, args->iv);
            args->crypto_mode = 2;
            dbg("setup legacy key nonzero", buf_nonzero(args->key, 16));
        }
    } else {
        dbg("setup crypto connID unavailable", 0);
    }

    dbg("setup sink crypto mode", args->crypto_mode);
    pthread_t t;
    int thread_rc = pthread_create(&t, NULL, sink_thread, args);
    dbg("sink thread create rc", thread_rc);
    if (thread_rc != 0) {
        secure_wipe(args, sizeof *args);
        free(args);
        close(fd);
        return 0;
    }
    pthread_detach(t);
    return port;
}

static int filter_streams_in_place(void *req, uint64_t *conn111_out, int *have_conn111_out) {
    int had_alt = 0;
    uint64_t conn111 = 0;
    *conn111_out = 0;
    *have_conn111_out = 0;

    if (!req) return 0;
    unsigned long array_type = cf_array_type_id();
    void *orig = cf_dict_get_typed(req, KEY_STREAMS, array_type, 0);
    if (!orig) return 0;

    long n = cf_array_count(orig);
    dbg("req streams", (int)n);
    void *keep = cf_array_create_mutable(0, 0, arr_cb);
    if (!keep) return 0;

    for (long i = 0; i < n; i++) {
        void *sd = cf_array_at(orig, i);
        if (!sd) {
            dbg("req null element index", (int)i);
            cf_release(keep);
            return 0;
        }
        int64_t ty = cf_dict_get_int64(sd, KEY_TYPE, 0);
        if (ty == ALT_SCREEN_TYPE) {
            had_alt = 1;
            conn111 = (uint64_t)cf_dict_get_int64(sd, K_CONNID, 0);
            dbg("req alt connection ID nonzero", conn111 != 0);
            continue;
        }
        cf_array_append(keep, sd);
    }
    if (had_alt) {
        cf_dict_set_value(req, KEY_STREAMS, keep);
        *conn111_out = conn111;
        *have_conn111_out = (conn111 != 0);
    }
    cf_release(keep);
    return had_alt;
}

int shim_session_setup(void *session, void *req, void **resp_out) {
    int session_changed = 0;
    pthread_mutex_lock(&g_state_lock);
    if (session != NULL && g_session != session) {
        /* Step 130: prevent a session switch from dropping ownership of an
         * old session while send_phone_cmd_safe still uses its unowned pointer.
         * Block new commands first, keep the old session identity published,
         * and release the mutex while existing commands finish. The old
         * session finalizer must still recognize its pointer during this
         * drain. Do not hold g_state_lock across vendor command dispatch. */
        g_session_valid = 0; /* Valid only after successful SETUP. */
        while (g_session_cmd_inflight > 0)
            pthread_cond_wait(&g_session_cv, &g_state_lock);
        g_session = session;
        g_session_generation++;
#if AK_ENABLE_COMBINED_CLUSTER
        g_combo_inflight_generation = 0;
        combo_cancel_all_builds_locked();
        /* Keep canceled tombstones until the wrapper callback arrives. */
        combo_cancel_all_requests_locked();
        combo_wait_sends_drained_locked();
#endif
        session_changed = 1;
    }
    unsigned generation = g_session_generation;
    pthread_mutex_unlock(&g_state_lock);

    if (session_changed) {
        dbg("setup new session generation", (int)generation);
        cluster_retire(NULL);
    }

    uint64_t conn111 = 0;
    int have_conn111 = 0;
    int had_alt = filter_streams_in_place(req, &conn111, &have_conn111);
    int rc = orig_setup(session, req, resp_out);
    dbg("setup original rc", rc);

    /* Do not publish a stale or unsuccessful session. */
    int still_current = 0;

    pthread_mutex_lock(&g_state_lock);
    if (session != NULL &&
        g_session == session &&
        g_session_generation == generation) {
        still_current = 1;

        if (rc == 0) {
            g_session_valid = 1;
        } else if (session_changed) {
            g_session_valid = 0;
            g_session = NULL;
            g_session_generation++;
        }
    }
    pthread_mutex_unlock(&g_state_lock);

    if (rc != 0 || !still_current || !had_alt ||
        !resp_out || !*resp_out) return rc;

    /* Handle allocator pointer reuse or altscreen re-SETUP on the same session. */
    int need_retire = 0;
    pthread_mutex_lock(&g_state_lock);
    if (g_session_generation == 0 || g_alt_seen_generation == g_session_generation) {
        g_session_generation++;
#if AK_ENABLE_COMBINED_CLUSTER
        g_combo_inflight_generation = 0;
        combo_cancel_all_builds_locked();
        /* Keep canceled tombstones until the wrapper callback arrives. */
        combo_cancel_all_requests_locked();
        combo_wait_sends_drained_locked();
#endif
        need_retire = 1;
    }
    generation = g_session_generation;
    g_alt_seen_generation = generation;
    pthread_mutex_unlock(&g_state_lock);

    if (need_retire) {
        dbg("setup altscreen generation bump", (int)generation);
        cluster_retire(NULL);
    }

    void *entry = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    if (!entry) return rc;

    int port = open_alt_sink(session, generation, conn111, have_conn111);
    if (port <= 0) {
        dbg("alt sink fail", -1);
        cf_release(entry);
        return rc;
    }

    cf_dict_set_int64(entry, KEY_TYPE, ALT_SCREEN_TYPE);
    cf_dict_set_int64(entry, KEY_DATAPORT, port);
    int append_rc = add_response_stream(*resp_out, entry);
    cf_release(entry);
    dbg("alt dataPort", port);
    if (append_rc != 0) {
        dbg("setup response append rc", append_rc);
        return rc;
    }

    cluster_maybe_start(generation, 1);
    return rc;
}

#if AK_ENABLE_COMBINED_CLUSTER
static int connect_car_interruptible(int family, const unsigned char *sa,
                                     int slen, unsigned generation) {
    for (int attempt = 0; attempt < 21; attempt++) {
        if (!sink_generation_current(generation)) {
            dbg("cluster stale during connect", (int)generation);
            return -1;
        }
        int fd = socket(family, SOCK_STREAM, 0);
        if (fd < 0) {
            dbg("cluster socket errno", errno);
            return -1;
        }
        int one = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
        if (family == AF_INET6) {
#ifdef IPV6_V6ONLY
            setsockopt(fd, IPPROTO_IPV6, IPV6_V6ONLY, &one, sizeof one);
#else
            setsockopt(fd, IPPROTO_IPV6, 26, &one, sizeof one);
#endif
        }
        sock_qos(fd, 0xc);

        int fl = fcntl(fd, F_GETFL, 0);
        if (fl != -1) fcntl(fd, F_SETFL, fl | O_NONBLOCK);

        int rc = connect(fd, (const struct sockaddr *)sa, (socklen_t)slen);
        int ok = (rc == 0);
        if (rc < 0 && errno == EINPROGRESS) {
            int waited_ms = 0;
            while (waited_ms < 2000) {
                if (!sink_generation_current(generation)) {
                    close(fd);
                    return -1;
                }
                struct pollfd pfd;
                pfd.fd = fd;
                pfd.events = POLLOUT;
                pfd.revents = 0;
                int pr = poll(&pfd, 1, POLL_SLICE_MS);
                if (pr < 0) {
                    if (errno == EINTR) continue;
                    break;
                }
                if (pr == 0) {
                    waited_ms += POLL_SLICE_MS;
                    continue;
                }
                int so_err = 0;
                socklen_t so_len = sizeof so_err;
                if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &so_err, &so_len) == 0 && so_err == 0) {
                    ok = 1;
                }
                break;
            }
        }
        if (ok) {
            if (fl != -1) fcntl(fd, F_SETFL, fl & ~O_NONBLOCK);
            struct timeval snd_tv;
            snd_tv.tv_sec = CAR_SEND_TIMEOUT_SEC;
            snd_tv.tv_usec = 0;
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &snd_tv, sizeof snd_tv);
            return fd;
        }
        close(fd);
        usleep(100000);
    }
    dbg("cluster connect failed", (int)generation);
    return -1;
}

/* Transport-only worker: no RTSP creation, no global-client reads, no
 * detached HTTP submission. Its arguments come from a validated stock reply. */
static void *cluster_setup_to_car(void *arg) {
    struct cluster_worker_args args = *(struct cluster_worker_args *)arg;
    free(arg);
    unsigned worker_generation = args.generation;
    uint64_t connid = args.connid;
    int dp = args.data_port;
    int fd = -1;

    pthread_mutex_lock(&g_cluster_setup_lock);
    if (!sink_generation_current(worker_generation) || connid == 0 ||
        dp <= 0 || dp > 65535) {
        dbg("cluster invalid response or generation", (int)worker_generation);
        goto out;
    }
    if (*GPAIRVERIFY_HK != 0) {
        dbg("cluster homekit mode unsupported", -1);
        goto out;
    }

    unsigned char sa[160] __attribute__((aligned(8)));
    memset(sa, 0, sizeof sa);
    sock_copy(GPEERADDR, sa);
    uint16_t family_u16;
    memcpy(&family_u16, sa, sizeof family_u16);
    int family = (int)family_u16;
    sock_setport(sa, dp);
    int slen = sock_getsize(sa);

    fd = connect_car_interruptible(family, sa, slen, worker_generation);
    if (fd < 0) goto out;
    dbg("cluster connected to car", dp);

    /* Wait briefly if car-side pair-verify has not yet populated GSESSION_AESKEY. */
    unsigned char session_key[16];
    int key_ready = 0;
    for (int waited = 0; waited < CLUSTER_KEY_WAIT_MS; waited += 100) {
        if (!sink_generation_current(worker_generation)) goto out;
        memcpy(session_key, GSESSION_AESKEY, sizeof session_key);
        if (buf_nonzero(session_key, sizeof session_key)) {
            key_ready = 1;
            break;
        }
        usleep(100000);
    }
    if (!key_ready) {
        dbg("cluster zero session aes key abort", (int)worker_generation);
        goto out;
    }

    struct cluster_ctx *ctx = (struct cluster_ctx *)malloc(sizeof *ctx);
    if (!ctx) {
        secure_wipe(session_key, sizeof session_key);
        dbg("cluster ctx malloc fail", -1);
        goto out;
    }
    memset(ctx, 0, sizeof *ctx);
    ctx->fd = fd;
    fd = -1;
    ctx->refcnt = 1;
    ctx->generation = worker_generation;
    pthread_mutex_init(&ctx->io_mu, NULL);

    char ks[48], is[48];
    snprintf(ks, sizeof ks, "%s%llu", "AirPlayStreamKey", (unsigned long long)connid);
    snprintf(is, sizeof is, "%s%llu", "AirPlayStreamIV", (unsigned long long)connid);
    aes_derive(session_key, 0x10, ks, (int)strlen(ks), is, (int)strlen(is),
               ctx->key, ctx->iv);
    secure_wipe(session_key, sizeof session_key);
    aesctr_init(ctx->aes_ctx, ctx->key, ctx->iv);

    int published = 0;
    struct cluster_ctx *replaced = NULL;
    int replaced_fd = -1;

    pthread_mutex_lock(&g_state_lock);
    if (worker_generation == g_session_generation &&
        g_session_valid && g_session != NULL) {
        if (g_cluster_ctx) {
            replaced = g_cluster_ctx;
            replaced->retired = 1;
            replaced_fd = replaced->fd;
        }
        g_cluster_ctx = ctx;
        g_cluster_ctx_generation = worker_generation;
        published = 1;
    }
    if (g_cluster_connecting_gen == worker_generation) {
        g_cluster_connecting_gen = 0;
    }
    pthread_mutex_unlock(&g_state_lock);

    if (replaced) {
        if (replaced_fd >= 0) shutdown(replaced_fd, SHUT_RDWR);
        cluster_ctx_release(replaced);
    }

    if (!published) {
        dbg("cluster stale before publish", (int)worker_generation);
        shutdown(ctx->fd, SHUT_RDWR);
        cluster_ctx_release(ctx);
        pthread_mutex_unlock(&g_cluster_setup_lock);
        return NULL;
    }

    dbg("cluster ctx ready", dp);
    pthread_mutex_unlock(&g_cluster_setup_lock);
    return NULL;

out:
    if (fd >= 0) close(fd);
    cluster_clear_connecting(worker_generation);
    pthread_mutex_unlock(&g_cluster_setup_lock);
    return NULL;
}
#endif /* AK_ENABLE_COMBINED_CLUSTER */

/* AirPlayReceiverSession CoreFoundation finalizer.
 * Original callback: 0x66A40.
 * Export only: the ELF finalizer hook is not installed yet.
 */
typedef void (*session_finalize_fn)(void *);

void shim_session_finalize(void *session) {
    if (session)
        shim_session_teardown(session);

    ((session_finalize_fn)0x00066a40u)(session);
}

__attribute__((constructor)) static void init(void) {
    /* This word is zero-initialized by the extended RW PT_LOAD/.bss. */
    void **finalize_slot = (void **)FINALIZE_HOOK_PTR_VA;
    if (*finalize_slot == NULL) {
        *finalize_slot = (void *)&shim_session_finalize;
        dbg("altscreen finalizer shim installed", -1);
    } else {
        dbg("altscreen finalizer slot mismatch", -1);
    }

#if AK_ENABLE_COMBINED_CLUSTER
    void **stream_slot = (void **)SCREEN_STREAM_PTR_SLOT_VA;
    void **send_slot = (void **)SCREEN_SEND_PTR_SLOT_VA;
    if (*stream_slot == NULL && *send_slot == NULL) {
        *stream_slot = (void *)&shim_screen_ensure_stream;
        *send_slot = (void *)&shim_screen_http_send;
        dbg("combined screen hooks installed", 1);
    } else {
        dbg("combined hook slot mismatch", -1);
    }
#endif
    void **hook_slot = (void **)SETUP_HOOK_PTR_VA;
    if (*hook_slot == (void *)SETUP_VA) {
        *hook_slot = (void *)&shim_session_setup;
        dbg("altscreen ARM shim installed", -1);
    } else {
        dbg("altscreen ARM hook slot mismatch", -1);
    }
}

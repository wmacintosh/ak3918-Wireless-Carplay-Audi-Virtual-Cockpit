
void __aeabi_unwind_cpp_pr0(void) {}
void __aeabi_unwind_cpp_pr1(void) {}
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

/* ARM AK3918AN (ak_202610081659) verified addresses */
#define SETUP_VA                0x0006a60cu
#define SETUP_HOOK_PTR_VA       0x001369fcu
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

typedef int (*setup_fn)(void *, void *, void **);
typedef int (*add_stream_fn)(void *, void *);
typedef int (*server_socket_open_fn)(int, int, int, int, int *, unsigned, int *);
typedef unsigned long (*type_id_fn)(void);
typedef void *(*dget_typed_fn)(void *, void *, unsigned long, int *);
typedef int64_t (*dget_i64_fn)(void *, void *, int *);
typedef void (*dset_i64_fn)(void *, void *, int64_t);
typedef void (*dset_val_fn)(void *, void *, void *);
typedef void *(*dmk_fn)(void *, long, void *, void *);
typedef void *(*amk_fn)(void *, long, void *);
typedef long (*acount_fn)(void *);
typedef void *(*aat_fn)(void *, long);
typedef void (*aappend_fn)(void *, void *);
typedef void (*release_fn)(void *);

static setup_fn orig_setup = (setup_fn)SETUP_VA;
static add_stream_fn add_response_stream = (add_stream_fn)ADD_RESPONSE_STREAM_VA;
static server_socket_open_fn server_socket_open = (server_socket_open_fn)SERVER_SOCKET_OPEN_VA;
static type_id_fn cf_array_type_id = (type_id_fn)0x00082ca8u;
static dget_typed_fn cf_dict_get_typed = (dget_typed_fn)0x000945c8u;
static dget_i64_fn cf_dict_get_int64 = (dget_i64_fn)0x000943ccu;
static dset_i64_fn cf_dict_set_int64 = (dset_i64_fn)0x00096b00u;
static dset_val_fn cf_dict_set_value = (dset_val_fn)0x000836dcu;
static dmk_fn cf_dict_create_mutable = (dmk_fn)0x00083568u;
static amk_fn cf_array_create_mutable = (amk_fn)0x00082e10u;
static acount_fn cf_array_count = (acount_fn)0x00082e58u;
static aat_fn cf_array_at = (aat_fn)0x00082e90u;
static aappend_fn cf_array_append = (aappend_fn)0x00082fc0u;
static release_fn cf_release = (release_fn)0x00082c78u;
static void *arr_cb = CB_ARRAY_VA, *dict_key_cb = CB_DICT_KEY_VA, *dict_val_cb = CB_DICT_VAL_VA;

#define CLUSTER_STREAM_TYPE     0x6f
#define CLUSTER_UUID            "b7e6c5a0-2222-4000-8000-000000000002"
/* luka-dev/mib2q-carplay-rgi uses 1440x542 (MIBSI uses 1440x540) */
#define CLUSTER_W               1440
#define CLUSTER_H               542

/* Client-side CFLString keys & HTTP strings */
#define K_STREAMS               ((void *)0x000f63f9u)
#define K_TYPE                  ((void *)0x000f6409u)
#define K_DATAPORT              ((void *)0x000f6416u)
#define K_CONNID                ((void *)0x000f6475u)
#define K_UUID                  ((void *)0x000f6490u)
#define K_LATENCYMS             ((void *)0x000f649du)
#define S_SETUP                 ((void *)0x000f3bc3u)
#define S_URL                   ((void *)0x000f67a9u)
#define S_PROTO                 ((void *)0x000ff624u)
#define S_CSEQ_FMT              ((void *)0x000f3bdf)
#define S_MIME                  ((void *)0x000f3c2fu)

/* Globals */
#define GPEERADDR               ((void *)0x0013bca0u)
#define GAIRPLAYCLIENT          ((void **)0x0013bf28u)
#define GPAIRVERIFY_HK          ((int *)0x0013a7e4u)
#define GSESSION_AESKEY         ((void *)0x0013a800u)
#define GCONNID_LO              ((unsigned *)0x0013acd8u)
#define GCONNID_HI              ((unsigned *)0x0013acdcu)

typedef int (*uuidget_fn)(void *);
typedef int (*httpmk_fn)(void **);
typedef int (*httpinit_fn)(void *, void *, void *, void *);
typedef int (*httpaddf_fn)(void *, void *, void *);
typedef int (*httpsetbody_fn)(void *, void *, void *, int);
typedef int (*httpsend_fn)(void *, void *);
typedef void (*aensure_fn)(void **, void *);
typedef void *(*plistmk_fn)(void *, int *, int);
typedef void *(*plistrd_fn)(void *, int, int *);
typedef void (*dsetcstr_fn)(void *, void *, void *, unsigned);
typedef void *(*semmk_fn)(int);
typedef int (*semwait_fn)(void *, unsigned long long);
typedef void (*semsig_fn)(void *);
typedef void (*sockcopy_fn)(void *, void *);
typedef void (*sockport_fn)(void *, int);
typedef int (*socksize_fn)(void *);
typedef void (*qos_fn)(int, int);
typedef unsigned long (*typeid_fn)(void);
typedef unsigned long (*gettypeid_fn)(void *);
typedef int (*derive_fn)(void *, int, void *, int, void *, int, void *, void *);
typedef void (*aesinit_fn)(void *, void *, void *);
typedef void (*aesupd_fn)(void *, void *, int, void *);
typedef void *(*at_fn)(void *, long);

static uuidget_fn cf_uuidget = (uuidget_fn)0x000d03a4u;
static httpmk_fn http_create = (httpmk_fn)0x000a6d08u;
static httpinit_fn http_init = (httpinit_fn)0x000a9710u;
static httpaddf_fn http_addf = (httpaddf_fn)0x000a9e00u;
static httpsetbody_fn http_setbody = (httpsetbody_fn)0x000a6dc8u;
static httpsend_fn http_send = (httpsend_fn)0x000a6974u;
static aensure_fn cf_arr_ensure = (aensure_fn)0x0009327cu;
static plistmk_fn cf_plist_create = (plistmk_fn)0x0008d0a0u;
static plistrd_fn cf_plist_read = (plistrd_fn)0x0008e414u;
static dsetcstr_fn cf_dict_set_cstr = (dsetcstr_fn)0x0009397cu;
static semmk_fn d_sem_create = (semmk_fn)0x000a11d8u;
static semwait_fn d_sem_wait = (semwait_fn)0x000a15b8u;
static semsig_fn d_sem_signal = (semsig_fn)0x000a1338u;
static sockcopy_fn sock_copy = (sockcopy_fn)0x000b82dcu;
static sockport_fn sock_setport = (sockport_fn)0x000b7858u;
static socksize_fn sock_getsize = (socksize_fn)0x000b6ce8u;
static qos_fn sock_qos = (qos_fn)0x000b6128u;
static typeid_fn cf_dict_type_id = (typeid_fn)0x00083564u;
static gettypeid_fn cf_get_type_id = (gettypeid_fn)0x00082c34u;
static derive_fn aes_derive = (derive_fn)0x0002b884u;
static aesinit_fn aes_ctr_init = (aesinit_fn)0x0007ca74u;
static aesinit_fn aesctr_init = (aesinit_fn)0x0007ca74u;
static aesupd_fn aesctr_update = (aesupd_fn)0x0007cab4u;
static at_fn cf_array_at2 = (at_fn)0x00082e90u;

/* ARM EABI 64-bit connID passed in r2:r3 */
typedef void (*derive_screen_fn)(void *, int, uint64_t, void *, void *);
typedef int (*streamkeys_fn)(void *, int, uint64_t, int, void *, void *);
typedef void (*ccinit_fn)(void *, void *, void *);
typedef void (*ccaad_fn)(void *, void *, int);
typedef int (*ccdec_fn)(void *, void *, int, void *);
typedef int (*ccver_fn)(void *, void *, void *, int *);
typedef int (*sendcmd_fn)(void *, void *, void *, void *);

static derive_screen_fn derive_screen = (derive_screen_fn)0x00073e84u;
static streamkeys_fn get_stream_keys = (streamkeys_fn)0x000654c0u;
static ccinit_fn cc_init = (ccinit_fn)0x000999e0u;
static ccaad_fn cc_aad = (ccaad_fn)0x00099e54u;
static ccdec_fn cc_dec = (ccdec_fn)0x00099f64u;
static ccver_fn cc_ver = (ccver_fn)0x0009a10cu;
static sendcmd_fn session_send_command = (sendcmd_fn)0x000673e0u;

#define CLUSTER_MAP_URL "maps:/car/instrumentcluster/map"

static void dbg(const char *msg, int n);

static int send_phone_cmd(void *session, const char *type, int with_url) {
    dbg("phone command request create begin", 0);
    void *req = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    dbg("phone command request present", req != 0);
    void *params = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    dbg("phone command params present", params != 0);
    if (!req || !params) {
        if (req) cf_release(req);
        if (params) cf_release(params);
        return -1;
    }
    dbg("phone command fields set begin", 0);
    cf_dict_set_cstr(req, KEY_TYPE, (void *)type, 0xffffffffu);
    cf_dict_set_cstr(params, K_UUID, (void *)CLUSTER_UUID, 0xffffffffu);
    if (with_url) cf_dict_set_cstr(params, K_CMD_URL, (void *)CLUSTER_MAP_URL, 0xffffffffu);
    cf_dict_set_value(req, K_CMD_PARAMS, params);
    cf_release(params);
    dbg("phone command dispatch begin", 0);
    int rc = session_send_command(session, req, 0, 0);
    dbg("phone command dispatch rc", rc);
    cf_release(req);
    return rc;
}

static int has_idr(const unsigned char *b, unsigned len) {
    unsigned pos = 0;
    while (pos + 5 <= len) {
        unsigned nlen = (b[pos] << 24) | (b[pos + 1] << 16) | (b[pos + 2] << 8) | b[pos + 3];
        if ((b[pos + 4] & 0x1f) == 5) return 1;
        if (nlen == 0 || nlen > len - pos - 4) break;
        pos += 4 + nlen;
    }
    return 0;
}

static void *g_cluster_ctx;
/* Guards the cluster startup state and publishes the active relay context. */
static pthread_mutex_t g_state_lock = PTHREAD_MUTEX_INITIALIZER;
static int g_cluster_started;
static int g_push_enabled = 1;
static void *g_session;
static unsigned g_session_generation;
static unsigned long long g_conn111;
static int g_have_conn111;
static void *cluster_setup_to_car(void *);

static int session_is_current(void *session, unsigned generation) {
    int current;
    pthread_mutex_lock(&g_state_lock);
    current = session && g_session == session && g_session_generation == generation;
    pthread_mutex_unlock(&g_state_lock);
    return current;
}
static int generation_is_current(unsigned generation) {
    int current;
    pthread_mutex_lock(&g_state_lock);
    current = generation == g_session_generation;
    pthread_mutex_unlock(&g_state_lock);
    return current;
}
static int cluster_claim_start(unsigned generation) {
    int claimed = 0;
    pthread_mutex_lock(&g_state_lock);
    if (generation == g_session_generation && !g_cluster_started) {
        g_cluster_started = 1;
        claimed = 1;
    }
    pthread_mutex_unlock(&g_state_lock);
    return claimed;
}
static void cluster_start_failed(unsigned generation) {
    pthread_mutex_lock(&g_state_lock);
    if (generation == g_session_generation) g_cluster_started = 0;
    pthread_mutex_unlock(&g_state_lock);
}
static void *cluster_context_snapshot(void) {
    void *ctx;
    pthread_mutex_lock(&g_state_lock);
    ctx = g_cluster_ctx;
    pthread_mutex_unlock(&g_state_lock);
    return ctx;
}

/* Preserve errno and keep concurrent checkpoint lines together with one append. */
static void dbg(const char *msg, int n) {
    int saved_errno = errno;
    char line[128];
    int len = snprintf(line, sizeof line, "AKDIAG %s %d\n", msg, n);
    if (len > 0 && len < (int)sizeof line) {
        int fd = open("/usr/data/log/altscreen.log", O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (fd >= 0) {
            write(fd, line, (size_t)len);
            close(fd);
        }
    }
    errno = saved_errno;
}

static int writeall(int fd, const void *buf, int n) {
    const char *p = (const char *)buf;
    while (n > 0) {
        ssize_t w = send(fd, p, n, MSG_NOSIGNAL);
        if (w <= 0) return -1;
        p += w;
        n -= (int)w;
    }
    return 0;
}

static int send_to_car(int type, unsigned char *body, unsigned len,
                       const char **failed_stage) {
    char *ctx = (char *)cluster_context_snapshot();
    if (!ctx || !failed_stage) { errno = EINVAL; return -1; }
    unsigned char hdr[128];
    memset(hdr, 0, sizeof hdr);
    *(unsigned *)hdr = len;
    hdr[4] = (unsigned char)type;
    if (type == 1) {
        /* IEEE-754 float bits to avoid soft-float helper calls */
        *(uint32_t *)(hdr + 0x10) = 0x44b40000u; /* 1440.0f */
        *(uint32_t *)(hdr + 0x14) = (CLUSTER_H == 542) ? 0x44078000u : 0x44070000u;
        *(uint32_t *)(hdr + 0x28) = 0x44b40000u; /* 1440.0f */
        *(uint32_t *)(hdr + 0x2c) = (CLUSTER_H == 542) ? 0x44078000u : 0x44070000u;
    }
    pthread_mutex_t *mu = *(pthread_mutex_t **)(ctx + 0x4c);
    if (!mu) { errno = EINVAL; return -1; }
    pthread_mutex_lock(mu);
    if (type == 0) aesctr_update(ctx + 0x168, body, (int)len, body);
    int fd = *(int *)ctx;
    int rc = writeall(fd, hdr, 128);
    const char *failure = "cluster header send errno";
    if (rc == 0 && len) {
        rc = writeall(fd, body, (int)len);
        failure = "cluster payload send errno";
    }
    int send_error = rc == 0 ? 0 : errno;
    pthread_mutex_unlock(mu);
    /* The sink reports only the first write failure for each connection. */
    if (rc != 0) {
        *failed_stage = failure;
        errno = send_error;
    }
    return rc;
}

static int readn(int fd, void *buf, int n) {
    char *p = (char *)buf;
    int got = 0;
    while (got < n) {
        ssize_t r = read(fd, p + got, n - got);
        if (r < 0) { dbg("sink phone read errno", errno); return -1; }
        if (r == 0) { dbg("sink phone EOF after bytes", got); return -1; }
        got += (int)r;
    }
    return 0;
}

struct sink_args { int srv; void *session; uint64_t connid; int have_connid; unsigned generation; };

static void *sink_thread(void *arg) {
    struct sink_args snapshot = *(struct sink_args *)arg;
    free(arg);
    int srv = snapshot.srv;
    void *session = snapshot.session;
    uint64_t connid = snapshot.connid;
    int have_connid = snapshot.have_connid;
    dbg("alt sink thread up", -1);
    dbg("sink accept begin", 0);
    int c = accept(srv, 0, 0);
    dbg("sink accept success", c >= 0);
    close(srv);
    if (c < 0) { dbg("alt accept fail", -1); return 0; }
    dbg("alt connected", -1);
    if (!session_is_current(session, snapshot.generation)) {
        dbg("sink stale session before showUI", -1);
        close(c);
        return 0;
    }
    {
        dbg("sink showUI begin", 0);
        int sr = send_phone_cmd(session, "showUI", 1);
        dbg("alt showUI err", sr);
    }

    unsigned char dctx[0x120];
    unsigned char cctx[0x200] __attribute__((aligned(8)));
    unsigned char cckey[32], ccnonce[8];
    int dec_ready = 0, chacha = 0;
    dbg("sink pairVerify lookup begin", session != 0);
    void *pvs = session ? *(void **)((char *)session + 0x3ec) : 0;
    dbg("alt pairVerifySession set", pvs ? 1 : 0);
    if (pvs && have_connid && connid != 0) {
        dbg("sink key setup begin", 0);
        int rc = get_stream_keys((char *)session + 0x3ec, 0, connid, 0, 0, cckey);
        dbg("alt chacha keys rc", rc);
        if (rc == 0) {
            memset(ccnonce, 0, sizeof ccnonce);
            dec_ready = 1;
            chacha = 1;
        }
    } else if (have_connid && session && connid != 0) {
        unsigned char key[16], iv[16];
        dbg("sink legacy derive begin", 0);
        derive_screen((char *)session + 0x200, 0x10, connid, key, iv);
        dbg("sink legacy cipher init begin", 0);
        aesctr_init(dctx, key, iv);
        dec_ready = 1;
        dbg("alt decrypt ready", -1);
    } else {
        dbg("alt no connID", have_connid);
    }

    unsigned char hdr[128];
    unsigned char *body = 0;
    int bodycap = 0;
    long frames = 0, pushed = 0;
    int configs_logged = 0, videos_logged = 0;
    unsigned char *cfg_body = 0;
    unsigned cfg_len = 0;
    const char *failed_stage = 0;
    int cfg_sent = 0, got_idr = 0, wait_idr = 0, send_failed = 0;
    dbg("sink first header read begin", 0);
    for (;;) {
        if (!session_is_current(session, snapshot.generation)) {
            dbg("sink session changed", -1);
            break;
        }
        if (readn(c, hdr, 128) != 0) {
            dbg("sink header read ended", (int)frames);
            break;
        }
        unsigned bodylen = *(unsigned *)hdr;
        int ftype = hdr[4];
        if (bodylen > 4000000u) { dbg("alt bad bodylen", (int)bodylen); break; }
        frames++;
        if (frames == 1) dbg("alt first frame type", ftype);
        if (bodylen == 0) continue;
        if ((int)bodylen > bodycap) {
            free(body);
            body = (unsigned char *)malloc(bodylen + 16);
            if (!body) { dbg("alt body malloc fail", -1); break; }
            bodycap = bodylen;
        }
        int trace_frame = frames <= 3;
        if (trace_frame) dbg("sink payload read begin bytes", (int)bodylen);
        if (readn(c, body, bodylen) != 0) {
            dbg("sink payload read ended frame", (int)frames);
            break;
        }
        if (trace_frame) dbg("sink payload read complete type", ftype);
        if (!session_is_current(session, snapshot.generation)) {
            dbg("sink session changed after read", -1);
            break;
        }
        if (ftype == 0) {
            int trace_video = videos_logged < 2;
            if (trace_video) {
                videos_logged++;
                dbg("sink video processing begin bytes", (int)bodylen);
            }
            if (chacha) {
                if (bodylen < 16) continue;
                int err = 0;
                if (trace_video) dbg("sink cipher init begin", 0);
                cc_init(cctx, cckey, ccnonce);
                if (trace_video) dbg("sink cipher header begin", 0);
                cc_aad(cctx, hdr, 128);
                if (trace_video) dbg("sink cipher decrypt begin", 0);
                int n = cc_dec(cctx, body, bodylen - 16, body);
                if (n < 0 || (unsigned)n > bodylen - 16) {
                    dbg("sink cipher invalid decrypt length", n);
                    break;
                }
                if (trace_video) dbg("sink cipher verify begin", n);
                n += cc_ver(cctx, body + n, body + bodylen - 16, &err);
                for (int k = 0; k < 8 && ++ccnonce[k] == 0; k++) {}
                if (trace_video) dbg("alt chacha verify err", err);
                if (err != 0 || n != (int)bodylen - 16) { dbg("alt chacha fail", n); continue; }
                bodylen -= 16;
            } else if (dec_ready) aesctr_update(dctx, body, bodylen, body);
            if (trace_video) dbg("sink video processing complete bytes", (int)bodylen);
            if (dec_ready && cluster_context_snapshot() && g_push_enabled && cfg_body) {
                if (!cfg_sent) {
                    if (send_to_car(1, cfg_body, cfg_len, &failed_stage) == 0) {
                        dbg("alt config sent late", (int)cfg_len);
                        cfg_sent = 1;
                        got_idr = 0;
                        wait_idr = 0;
                    } else {
                        dbg(failed_stage, errno);
                        break;
                    }
                }
                if (!got_idr && has_idr(body, bodylen)) { got_idr = 1; dbg("alt idr after frames", wait_idr); }
                if (!got_idr) {
                    if ((wait_idr++ % 120) == 0) {
                        int kr = send_phone_cmd(session, "forceKeyFrame", 0);
                        dbg("alt force keyframe err", kr < 0 ? -kr : kr);
                    }
                    continue;
                }
                if (send_to_car(0, body, bodylen, &failed_stage) == 0) pushed++;
                else if (!send_failed) { send_failed = 1;
                    dbg(failed_stage, errno);
                    dbg("alt send to car fail", (int)pushed); }
            }
        } else if (ftype == 1) {
            int trace_config = configs_logged < 3;
            if (trace_config) {
                configs_logged++;
                dbg("sink config allocation begin bytes", (int)bodylen);
            }
            free(cfg_body);
            cfg_body = (unsigned char *)malloc(bodylen);
            if (cfg_body) {
                memcpy(cfg_body, body, bodylen);
                cfg_len = bodylen;
                cfg_sent = 0;
            }
            if (trace_config) dbg("sink config buffer ready", cfg_body != 0);
            if (cfg_body && cluster_context_snapshot() && g_push_enabled) {
                if (send_to_car(1, cfg_body, cfg_len, &failed_stage) == 0) {
                    pushed++;
                    dbg("alt config sent", (int)cfg_len);
                    cfg_sent = 1;
                    got_idr = 0;
                    wait_idr = 0;
                } else {
                    dbg(failed_stage, errno);
                    break;
                }
            }
        }
        if ((frames % 300) == 0) dbg("alt frames pushed", (int)pushed);
    }
    dbg("alt stream end frames", (int)frames);
    free(body);
    free(cfg_body);
    close(c);
    return 0;
}

static int open_alt_sink(void *session) {
    dbg("sink socket family lookup begin", 0);
    int family = *(unsigned short *)((char *)session + 0x8c);
    dbg("sink socket open begin family", family);
    int port = 0, fd = -1;
    int rc = server_socket_open(family, SOCK_STREAM, IPPROTO_TCP, 0, &port, 0xfffd4000u, &fd);
    dbg("sink socket open rc", rc);
    if (rc != 0 || fd < 0) { dbg("alt ServerSocketOpen rc", rc); return 0; }
    int fl = fcntl(fd, F_GETFL, 0);
    if (fl != -1) fcntl(fd, F_SETFL, fl & ~O_NONBLOCK);
    struct sink_args *args = (struct sink_args *)malloc(sizeof(*args));
    if (!args) { close(fd); dbg("sink args malloc fail", -1); return 0; }
    pthread_mutex_lock(&g_state_lock);
    args->srv = fd;
    args->session = session;
    args->connid = g_conn111;
    args->have_connid = g_have_conn111;
    args->generation = g_session_generation;
    pthread_mutex_unlock(&g_state_lock);
    pthread_t t;
    dbg("sink thread create begin", 0);
    int thread_rc = pthread_create(&t, 0, sink_thread, args);
    dbg("sink thread create rc", thread_rc);
    if (thread_rc != 0) { free(args); close(fd); return 0; }
    pthread_detach(t);
    return port;
}

static int filter_streams_in_place(void *req) {
    int had_alt = 0;
    unsigned long long conn111 = 0;
    if (!req) return 0;
    dbg("req array type lookup begin", 0);
    unsigned long array_type = cf_array_type_id();
    dbg("req streams lookup begin", 0);
    void *orig = cf_dict_get_typed(req, KEY_STREAMS, array_type, 0);
    dbg("req streams present", orig != 0);
    if (!orig) return 0;
    dbg("req array count begin", 0);
    long n = cf_array_count(orig);
    dbg("req streams", (int)n);
    dbg("req replacement array create begin", 0);
    void *keep = cf_array_create_mutable(0, 0, arr_cb);
    dbg("req replacement array present", keep != 0);
    if (!keep) return 0;
    for (long i = 0; i < n; i++) {
        int trace = i < 16;
        if (trace) dbg("req array get begin index", (int)i);
        void *sd = cf_array_at(orig, i);
        if (trace) dbg("req array get returned element", sd != 0);
        if (!sd) {
            dbg("req null element, filter abandoned index", (int)i);
            cf_release(keep);
            return 0;
        }
        if (trace) dbg("req stream type lookup begin", (int)i);
        int64_t ty = cf_dict_get_int64(sd, KEY_TYPE, 0);
        if (trace) dbg("req stream type", (int)ty);
        if (ty == ALT_SCREEN_TYPE) {
            had_alt = 1;
            dbg("req alt connection ID lookup begin index", (int)i);
            conn111 = (unsigned long long)cf_dict_get_int64(sd, K_CONNID, 0);
            dbg("req alt connection ID nonzero", conn111 != 0);
            continue;
        }
        if (trace) dbg("req append retained stream begin", (int)i);
        cf_array_append(keep, sd);
        if (trace) dbg("req append retained stream complete", (int)i);
    }
    if (had_alt) {
        dbg("req replacement array install begin", 0);
        cf_dict_set_value(req, KEY_STREAMS, keep);
        dbg("req replacement array install complete", 0);
        pthread_mutex_lock(&g_state_lock);
        g_conn111 = conn111;
        g_have_conn111 = conn111 != 0;
        pthread_mutex_unlock(&g_state_lock);
    }
    dbg("req replacement array release begin", 0);
    cf_release(keep);
    dbg("req filter complete had alt", had_alt);
    return had_alt;
}

int shim_session_setup(void *session, void *req, void **resp_out) {
    dbg("setup enter session present", session != 0);
    dbg("setup request present", req != 0);
    unsigned generation;
    pthread_mutex_lock(&g_state_lock);
    if (g_session != session) {
        g_session_generation++;
        g_conn111 = 0;
        g_have_conn111 = 0;
        /* A new session must not inherit the old cluster connection/start flag.
           Context memory is intentionally not freed: old relay threads may hold it. */
        g_cluster_ctx = 0;
        g_cluster_started = 0;
    }
    g_session = session;
    generation = g_session_generation;
    pthread_mutex_unlock(&g_state_lock);
    int had_alt = filter_streams_in_place(req);
    dbg("setup original begin had alt", had_alt);
    int rc = orig_setup(session, req, resp_out);
    dbg("setup original rc", rc);
    if (rc != 0 || !had_alt || !resp_out || !session) return rc;
    dbg("setup response lookup begin", 0);
    if (!*resp_out) {
        dbg("setup response missing", 0);
        return rc;
    }

    int port = open_alt_sink(session);
    if (port <= 0) { dbg("alt sink fail", -1); return rc; }
    dbg("setup response entry create begin", 0);
    void *entry = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    dbg("setup response entry present", entry != 0);
    if (!entry) return rc;
    dbg("setup response type set begin", 0);
    cf_dict_set_int64(entry, KEY_TYPE, ALT_SCREEN_TYPE);
    dbg("setup response port set begin", port);
    cf_dict_set_int64(entry, KEY_DATAPORT, port);
    dbg("setup response append begin", 0);
    int append_rc = add_response_stream(*resp_out, entry);
    dbg("setup response append rc", append_rc);
    dbg("setup response entry release begin", 0);
    cf_release(entry);
    dbg("alt dataPort", port);
    if (cluster_claim_start(generation)) {
        pthread_t ct;
        unsigned *arg = (unsigned *)malloc(sizeof(*arg));
        if (!arg) {
            dbg("cluster generation arg allocation failed", -1);
            cluster_start_failed(generation);
        } else {
            *arg = generation;
            dbg("setup cluster thread create begin", 0);
            int thread_rc = pthread_create(&ct, 0, cluster_setup_to_car, arg);
            dbg("setup cluster thread create rc", thread_rc);
            if (thread_rc == 0) pthread_detach(ct);
            else { free(arg); cluster_start_failed(generation); }
        }
    }
    dbg("setup complete rc", rc);
    return rc;
}

static void cluster_response_cb(void *msg) {
    dbg("cluster response enter", 0);
    if (!msg) { dbg("cluster response null message", -1); return; }
    int len = *(int *)((char *)msg + 0x4a0);
    dbg("cluster response bytes", len);
    void *bodyp = *(void **)((char *)msg + 0x49c);
    if (len <= 0 || len > 4000000 || !bodyp) {
        dbg("cluster response invalid body", len);
        return;
    }
    int err = 0;
    dbg("cluster response plist read begin", 0);
    void *d = cf_plist_read(bodyp, len, &err);
    dbg("cluster response plist read rc", err);
    if (err != 0 || !d) return;
    if (cf_get_type_id(d) == cf_dict_type_id()) {
        dbg("cluster response array lookup begin", 0);
        void *streams = cf_dict_get_typed(d, K_STREAMS, cf_array_type_id(), 0);
        dbg("cluster response array present", streams != 0);
        if (streams) {
            dbg("cluster response count begin", 0);
            long n = cf_array_count(streams);
            dbg("cluster response count", (int)n);
            for (long i = 0; i < n; i++) {
                if (i < 16) dbg("cluster response array get begin index", (int)i);
                void *sd = cf_array_at2(streams, i);
                if (i < 16) dbg("cluster response element present", sd != 0);
                if (!sd) continue;
                if (i < 16) dbg("cluster response stream type lookup begin", (int)i);
                if (cf_dict_get_int64(sd, K_TYPE, 0) == CLUSTER_STREAM_TYPE) {
                    dbg("cluster response port lookup begin", 0);
                    int dp = (int)cf_dict_get_int64(sd, K_DATAPORT, 0);
                    void *ctx = *(void **)((char *)msg + 0x8fc);
                    if (!ctx || dp <= 0 || dp > 65535) {
                        dbg("cluster response invalid context or port", dp);
                        break;
                    }
                    void *sem = *(void **)((char *)ctx + 0x30);
                    if (!sem) { dbg("cluster response null semaphore", -1); break; }
                    *(int *)((char *)ctx + 4) = dp;
                    dbg("cluster car dataPort", dp);
                    dbg("cluster response signal begin", 0);
                    d_sem_signal(sem);
                    dbg("cluster response signal complete", 0);
                    break;
                }
            }
        }
    }
    cf_release(d);
}

static void *cluster_setup_to_car(void *arg) {
    unsigned generation = *(unsigned *)arg;
    free(arg);
    if (!generation_is_current(generation)) {
        dbg("cluster setup stale generation", -1);
        return 0;
    }
    if (*GPAIRVERIFY_HK != 0) {
        dbg("cluster homekit mode unsupported", -1);
        cluster_start_failed(generation);
        return 0;
    }
    char *ctx = (char *)malloc(0x288);
    if (!ctx) { dbg("cluster malloc fail", -1); cluster_start_failed(generation); return 0; }
    memset(ctx, 0, 0x288);
    *(int *)(ctx + 0) = -1;
    pthread_mutex_init((pthread_mutex_t *)(ctx + 0x34), 0);
    *(void **)(ctx + 0x4c) = ctx + 0x34;
    void *sem = d_sem_create(0);
    if (!sem) {
        dbg("cluster semaphore create failed", -1);
        cluster_start_failed(generation);
        return 0;
    }
    *(void **)(ctx + 0x30) = sem;

    void *msg = 0;
    if (http_create(&msg) != 0 || !msg) { dbg("cluster http create fail", -1); cluster_start_failed(generation); return 0; }
    if (http_init((char *)msg + 0x10, "SETUP", "rtsp://localhost/stream", "RTSP/1.0") != 0) {
        dbg("cluster http init fail", -1);
        cluster_start_failed(generation);
        return 0;
    }
    char cseq[16];
    snprintf(cseq, sizeof cseq, "%d", 1);
    http_addf((char *)msg + 0x10, "CSeq", cseq);

    void *req = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    void *sd = cf_dict_create_mutable(0, 0, dict_key_cb, dict_val_cb);
    if (!req || !sd) { dbg("cluster dict fail", -1); cluster_start_failed(generation); return 0; }

    unsigned char u[16];
    cf_uuidget(u);
    unsigned hi = (u[0] << 24) | (u[1] << 16) | (u[2] << 8) | u[3];
    unsigned lo = (u[4] << 24) | (u[5] << 16) | (u[6] << 8) | u[7];
    *GCONNID_LO = lo;
    *GCONNID_HI = hi;
    unsigned long long connid = ((unsigned long long)hi << 32) | lo;
    cf_dict_set_int64(sd, K_CONNID, (int64_t)connid);
    cf_dict_set_int64(sd, K_TYPE, CLUSTER_STREAM_TYPE);
    cf_dict_set_cstr(sd, K_UUID, (void *)CLUSTER_UUID, 0xffffffffu);
    cf_dict_set_int64(sd, K_LATENCYMS, 0x19);

    void *arr = 0;
    dbg("cluster request array ensure begin", 0);
    cf_arr_ensure(&arr, sd);
    dbg("cluster request array present", arr != 0);
    if (!arr) {
        cf_release(sd);
        cf_release(req);
        cluster_start_failed(generation); return 0;
    }
    dbg("cluster request array install begin", 0);
    cf_dict_set_value(req, K_STREAMS, arr);
    dbg("cluster request array install complete", 0);

    int bodylen = 0;
    void *body = cf_plist_create(req, &bodylen, 0);
    if (!body) { dbg("cluster plist fail", -1); cluster_start_failed(generation); return 0; }
    if (http_setbody(msg, "application/x-apple-binary-plist", body, bodylen) != 0) {
        dbg("cluster setbody fail", -1);
        cluster_start_failed(generation); return 0;
    }
    cf_release(arr);
    cf_release(sd);
    cf_release(req);

    *(void **)((char *)msg + 0x904) = (void *)&cluster_response_cb;
    *(int *)((char *)msg + 0x8f4) = 0;
    *(int *)((char *)msg + 0x8f8) = 0;
    *(void **)((char *)msg + 0x8fc) = ctx;

    dbg("cluster SETUP send begin", 0);
    int send_rc = http_send(*GAIRPLAYCLIENT, msg);
    dbg("cluster SETUP send rc", send_rc);
    if (send_rc != 0) { dbg("cluster SETUP dispatch failed", send_rc); cluster_start_failed(generation); return 0; }
    dbg("cluster SETUP wait begin", 0);
    /* The stock semaphore implementation returns an integer result.
       Keep the indefinite wait until the dispatch timebase and asynchronous
       callback ownership are verified; a naïve timed wait can cause UAF. */
    int wait_rc = d_sem_wait(sem, ~0ull);
    dbg("cluster SETUP wait rc", wait_rc);
    if (wait_rc != 0) {
        cluster_start_failed(generation);
        return 0;
    }
    dbg("cluster SETUP replied", -1);
    if (!generation_is_current(generation)) {
        dbg("cluster response from stale generation", -1);
        return 0;
    }

    int dp = *(int *)(ctx + 4);
    if (dp <= 0) { dbg("cluster no dataPort", -1); cluster_start_failed(generation); return 0; }

    char sa[160];
    memset(sa, 0, sizeof sa);
    sock_copy(GPEERADDR, sa);
    int family = *(unsigned short *)sa;
    int fd = socket(family, SOCK_STREAM, 0);
    if (fd < 0) { dbg("cluster socket fail", -1); cluster_start_failed(generation); return 0; }
    int one = 1;
    setsockopt(fd, 0xffff, 4, &one, 4);
    if (family == 10) setsockopt(fd, 0x29, 0x1a, &one, 4);
    sock_qos(fd, 0xc);
    sock_setport(sa, dp);
    int slen = sock_getsize(sa);
    int tries = 21, ok = 0;
    while (tries-- > 0) {
        if (connect(fd, (struct sockaddr *)sa, slen) == 0) { ok = 1; break; }
        usleep(100000);
    }
    if (!ok) { dbg("cluster connect fail", -1); close(fd); cluster_start_failed(generation); return 0; }
    dbg("cluster connected to car", dp);

    char ks[48], is[48];
    snprintf(ks, sizeof ks, "%s%llu", "AirPlayStreamKey", connid);
    snprintf(is, sizeof is, "%s%llu", "AirPlayStreamIV", connid);
    aes_derive(GSESSION_AESKEY, 0x10, ks, (int)strlen(ks), is, (int)strlen(is),
               ctx + 0x10, ctx + 0x20);
    aes_ctr_init(ctx + 0x168, ctx + 0x10, ctx + 0x20);

    *(int *)(ctx + 0xc) = 1;
    *(int *)(ctx + 0) = fd;
    pthread_mutex_lock(&g_state_lock);
    int current = generation == g_session_generation;
    if (current) g_cluster_ctx = ctx;
    pthread_mutex_unlock(&g_state_lock);
    if (!current) {
        dbg("cluster late context rejected", -1);
        close(fd);
        cluster_start_failed(generation); return 0;
    }
    dbg("cluster ctx ready", -1);
    return 0;
}

__attribute__((constructor)) static void init(void) {
    void **hook_slot = (void **)SETUP_HOOK_PTR_VA;
    if (*hook_slot == (void *)SETUP_VA) {
        *hook_slot = (void *)&shim_session_setup;
        dbg("altscreen ARM shim installed", -1);
    } else {
        dbg("altscreen ARM hook slot mismatch", -1);
    }
}

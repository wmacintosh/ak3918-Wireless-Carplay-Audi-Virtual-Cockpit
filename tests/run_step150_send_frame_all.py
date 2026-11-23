#!/usr/bin/env python3
"""Host regression tests for send_frame_all() extracted directly from altscreen.c.

Covers:
1. Full single-call scatter-gather send (128B header + body).
2. Partial writes splitting header, EINTR retry, exact boundary, and body.
3. Partial write crossing the header-to-body boundary.
4. Zero-length body (single iovec only).
5. Peer EOF (sendmsg returning 0 -> -1 with EPIPE).
6. Fatal socket error (ECONNRESET propagated).
"""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
src = (root / "altscreen.c").read_text()
start = src.index("static int send_frame_all(")
end = src.index("\nstatic int send_to_car(", start)
impl = src[start:end]

harness = r'''
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/uio.h>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif

static unsigned char g_sink[4096];
static size_t g_sink_len = 0;
static int g_plan[16];
static int g_plan_errno[16];
static int g_plan_idx = 0;
static int g_plan_len = 0;
static size_t g_last_iovlen = 0;

static void reset_mock(const int *plan, const int *errs, int n) {
    memset(g_sink, 0, sizeof g_sink);
    g_sink_len = 0;
    g_plan_idx = 0;
    g_plan_len = n;
    g_last_iovlen = 0;
    for (int i = 0; i < n; ++i) {
        g_plan[i] = plan[i];
        g_plan_errno[i] = errs ? errs[i] : 0;
    }
}

static ssize_t mock_sendmsg(int fd, const struct msghdr *mh, int flags) {
    (void)fd;
    (void)flags;
    if (g_plan_idx >= g_plan_len) {
        errno = EIO;
        return -1;
    }
    g_last_iovlen = (size_t)mh->msg_iovlen;
    int step = g_plan[g_plan_idx];
    int err = g_plan_errno[g_plan_idx];
    g_plan_idx++;
    if (step < 0) {
        errno = err;
        return -1;
    }
    if (step == 0) return 0;

    size_t want = (size_t)step;
    size_t copied = 0;
    for (size_t i = 0; i < (size_t)mh->msg_iovlen && copied < want; ++i) {
        size_t avail = mh->msg_iov[i].iov_len;
        size_t take = (want - copied < avail) ? (want - copied) : avail;
        if (g_sink_len + take > sizeof g_sink) abort();
        memcpy(g_sink + g_sink_len, mh->msg_iov[i].iov_base, take);
        g_sink_len += take;
        copied += take;
    }
    return (ssize_t)copied;
}

#define sendmsg mock_sendmsg
{{IMPL}}
#undef sendmsg

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL %d: %s\n", __LINE__, #x); exit(1); } } while (0)

int main(void) {
    unsigned char hdr[128], body[64], expect[192];
    for (size_t i = 0; i < sizeof hdr; ++i) hdr[i] = (unsigned char)(i ^ 0x5a);
    for (size_t i = 0; i < sizeof body; ++i) body[i] = (unsigned char)(0xa0 + i);
    memcpy(expect, hdr, sizeof hdr);
    memcpy(expect + sizeof hdr, body, sizeof body);

    /* 1. Full single-call send */
    {
        int plan[] = { 192 };
        reset_mock(plan, NULL, 1);
        CHECK(send_frame_all(3, hdr, sizeof hdr, body, sizeof body) == 0);
        CHECK(g_sink_len == 192 && memcmp(g_sink, expect, 192) == 0);
        CHECK(g_plan_idx == 1);
    }

    /* 2. Split inside header + EINTR + exact boundary + split inside body */
    {
        int plan[] = { 17, -1, 111, 5, 59 };
        int errs[] = { 0, EINTR, 0, 0, 0 };
        reset_mock(plan, errs, 5);
        CHECK(send_frame_all(3, hdr, sizeof hdr, body, sizeof body) == 0);
        CHECK(g_sink_len == 192 && memcmp(g_sink, expect, 192) == 0);
        CHECK(g_plan_idx == 5);
    }

    /* 3. Partial write crossing header->body boundary */
    {
        int plan[] = { 140, 52 };
        reset_mock(plan, NULL, 2);
        CHECK(send_frame_all(3, hdr, sizeof hdr, body, sizeof body) == 0);
        CHECK(g_sink_len == 192 && memcmp(g_sink, expect, 192) == 0);
        CHECK(g_plan_idx == 2);
    }

    /* 4. Zero-length body sends only 1 iovec */
    {
        int plan[] = { 128 };
        reset_mock(plan, NULL, 1);
        CHECK(send_frame_all(3, hdr, sizeof hdr, NULL, 0) == 0);
        CHECK(g_sink_len == 128 && memcmp(g_sink, hdr, 128) == 0);
        CHECK(g_last_iovlen == 1);
    }

    /* 5. Peer EOF returns -1 and sets EPIPE */
    {
        int plan[] = { 64, 0 };
        reset_mock(plan, NULL, 2);
        errno = 0;
        CHECK(send_frame_all(3, hdr, sizeof hdr, body, sizeof body) == -1);
        CHECK(errno == EPIPE);
    }

    /* 6. Fatal ECONNRESET propagated */
    {
        int plan[] = { 10, -1 };
        int errs[] = { 0, ECONNRESET };
        reset_mock(plan, errs, 2);
        errno = 0;
        CHECK(send_frame_all(3, hdr, sizeof hdr, body, sizeof body) == -1);
        CHECK(errno == ECONNRESET);
    }

    puts("PASS Step 150: send_frame_all partial writes, EINTR, boundary, zero-body, EPIPE, ECONNRESET");
    return 0;
}
'''

code = harness.replace("{{IMPL}}", impl)
with tempfile.TemporaryDirectory(prefix="ak3918-step150-") as temp:
    cfile = Path(temp) / "step150.c"
    cfile.write_text(code)
    for sanitizer in ("address,undefined", "undefined", "none"):
        exe = Path(temp) / ("step150_" + sanitizer.replace(",", "_"))
        cmd = [
            "cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-fno-omit-frame-pointer",
        ]
        if sanitizer != "none":
            cmd.append("-fsanitize=" + sanitizer)
        cmd += [str(cfile), "-o", str(exe)]
        subprocess.run(cmd, check=True)
        env = os.environ.copy()
        leak_detection = "0" if sys.platform == "darwin" else "1"
        env["ASAN_OPTIONS"] = "detect_leaks=" + leak_detection + ":halt_on_error=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1"
        print("RUN:", sanitizer, flush=True)
        subprocess.run([str(exe)], check=True, env=env, timeout=10)
print("source sha256", hashlib.sha256(src.encode()).hexdigest())

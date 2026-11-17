import hashlib, os, sys, time, urllib.request
HOST, CHUNK = "192.168.200.1", 10240
ROOT = os.path.dirname(os.path.abspath(__file__))

def get(path, t=15):
    with urllib.request.urlopen(f"http://{HOST}{path}", timeout=t) as r:
        return r.read().decode("utf-8", "replace").strip()

def post_chunk(part, fn):
    b = "----ak3918boundary"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"chunk\"; filename=\"{fn}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + part + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"http://{HOST}/cgi-bin/downfile.cgi", data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace").strip()
args = set(sys.argv[1:])
check_only, stock = "--check-only" in args, "--stock" in args
tar_path = os.path.join(ROOT, "stock_ak_202610081659.tar" if stock else "ak_hook.tar")
rname = "ak_202610081659" if stock else "ak_hook"
data = open(tar_path, "rb").read()
md5 = hashlib.md5(data).hexdigest()

ver = get("/cgi-bin/getversion.cgi", t=5)
print("Version info:\n" + ver)
if "AK3918AN" not in ver or "suding" not in ver:
    sys.exit("Refusing: unexpected platform/custom")

print(f"Image: {os.path.basename(tar_path)} ({len(data)}B) md5={md5} check_only={check_only}")
if not check_only and input("Type 'yes' to flash: ").strip() != "yes":
    sys.exit("Aborted.")

n = (len(data) + CHUNK - 1) // CHUNK
for i in range(n):
    fn = f"{rname}.0" if i == 0 else (f"{rname}:{md5}.2" if i == n - 1 else f"{rname}.1")
    resp = post_chunk(data[i*CHUNK:(i+1)*CHUNK], fn)
    if "success" not in resp: sys.exit(f"\nFailed at {i}: {resp}")
    print(f"\rUploading {i+1}/{n}", end="", flush=True)
print(f"\nFinal chunk response: {resp}")
if "file check success" not in resp:
    sys.exit("MD5 check failed on dongle!")
if not check_only:
    print("Install:", get(f"/cgi-bin/submition.cgi?filename={rname}&", t=30))
    time.sleep(1)
    try: get("/cgi-bin/reboot.cgi", t=5)
    except Exception: pass
    print("Rebooting dongle (~30s).")

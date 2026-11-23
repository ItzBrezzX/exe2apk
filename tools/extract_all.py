#!/usr/bin/env python3
"""Ekstrak arsip bersarang (zip di dalam zip, installer NSIS/Inno/MSI, 7z, dll).
Pemakaian: extract_all.py <input_dir> <out_dir>
Zip diekstrak dengan zipfile (aman dari path traversal), format lain dengan 7z/7zz.
Batas kedalaman dan total ukuran untuk menghindari zip bomb."""
import sys, os, shutil, subprocess, zipfile, pathlib

MAX_DEPTH = 4
MAX_TOTAL = 4 * 1024**3
ARCH_EXT = {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".xz", ".bz2", ".cab", ".msi", ".iso"}
INSTALLER_MARKERS = (b"Nullsoft.NSIS", b"NullsoftInst", b"Inno Setup", b".wixburn", b"7z\xbc\xaf\x27\x1c")

def sevenzip():
    for n in ("7zz", "7z", "7za"):
        if shutil.which(n):
            return n
    return None

def safe_unzip(path, dest):
    dest = pathlib.Path(dest).resolve()
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if dest not in target.parents and target != dest:
                print("  lewati path berbahaya:", m.filename); continue
            z.extract(m, dest)

def is_installer_exe(path):
    try:
        b = path.read_bytes()
    except OSError:
        return False
    return any(m in b for m in INSTALLER_MARKERS)

def extract(path, dest, s7):
    dest.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".zip" and zipfile.is_zipfile(path):
        try:
            safe_unzip(path, dest); return True
        except Exception as e:
            print("  zipfile gagal:", e)
    if not s7:
        print("  7z tidak tersedia, lewati", path.name); return False
    r = subprocess.run([s7, "x", "-y", "-o" + str(dest), str(path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode in (0, 1)  # 1 = warning

def dir_size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

def main(inp, out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    s7 = sevenzip()
    queue = [(f, 0) for f in sorted(pathlib.Path(inp).rglob("*")) if f.is_file()]
    n = 0
    while queue:
        f, depth = queue.pop(0)
        ext = f.suffix.lower()
        wanted = ext in ARCH_EXT or (ext == ".exe" and is_installer_exe(f))
        if not wanted or depth >= MAX_DEPTH:
            continue
        if dir_size(out) > MAX_TOTAL:
            print("Batas ukuran tercapai, berhenti"); break
        n += 1
        dest = out / ("%02d_%s" % (n, f.name))
        print("[%d] ekstrak %s" % (depth, f))
        if extract(f, dest, s7):
            queue += [(g, depth + 1) for g in sorted(dest.rglob("*")) if g.is_file()]
    print("Selesai, %d arsip diekstrak ->" % n, out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

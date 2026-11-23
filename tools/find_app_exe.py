#!/usr/bin/env python3
"""Pilih exe aplikasi Tauri dari hasil ekstrak installer (atau input langsung).
Exit 3 jika tidak ada exe yang terdeteksi sebagai Tauri."""
import sys, pathlib

SKIP = ("uninst", "vc_redist", "vcredist", "webview2", "microsoftedge", "setup.exe")

def tauri_score(path):
    b = path.read_bytes()
    low = b.lower()
    return (low.count(b"tauri") + low.count("tauri".encode("utf-16le"))
            + low.count(b"wry::") + low.count(b"webview2loader"))

def main(roots):
    cands = []
    for r in map(pathlib.Path, roots):
        files = [r] if r.is_file() else list(r.rglob("*.exe"))
        for p in files:
            if p.suffix.lower() != ".exe" or any(s in p.name.lower() for s in SKIP):
                continue
            if p.stat().st_size < 500_000:
                continue
            cands.append(p)
    scored = [(tauri_score(p), p.stat().st_size, p) for p in cands]
    scored = [s for s in scored if s[0] >= 3]
    if not scored:
        sys.stderr.write(
            "Tidak ada exe Tauri terdeteksi. Pipeline ini hanya untuk aplikasi Tauri.\n"
            "Kandidat diperiksa: %s\n" % [str(c) for c in cands])
        sys.exit(3)
    scored.sort(key=lambda s: (s[0] > 0, s[1]), reverse=True)
    print(scored[0][2])

if __name__ == "__main__":
    main(sys.argv[1:])

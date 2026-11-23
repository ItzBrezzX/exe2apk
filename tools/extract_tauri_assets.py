#!/usr/bin/env python3
"""Fallback jika untauri gagal: scan seluruh exe untuk stream brotli yang terlihat seperti
aset web. Lambat dan heuristik; nama file dipulihkan dari referensi index.html.
Pemakaian: extract_tauri_assets.py app.exe outdir"""
import sys, re, hashlib, pathlib
import brotli

def sniff(b):
    h = b[:64].lstrip().lower()
    if h.startswith((b"<!doctype html", b"<html")): return "html"
    if h.startswith(b"<svg"): return "svg"
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    if b[:4] == b"wOF2": return "woff2"
    try:
        t = b[:4000].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(b) > 200 and re.search(r"(import\s|export\s|function\s|const\s|var\s|=>)", t): return "js"
    if re.search(r"[.#]?[\w-]+\s*\{[^}]*:[^}]*\}", t): return "css"
    return None

def main(exe, out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    data = open(exe, "rb").read()
    seen, blobs = set(), []
    for i in range(len(data)):
        try:
            dec = brotli.decompress(data[i:i + 8_000_000])
        except Exception:
            continue
        if len(dec) >= 64:
            k = sniff(dec)
            h = hashlib.sha1(dec).hexdigest()
            if k and h not in seen:
                seen.add(h); blobs.append((k, dec))
    htmls = [d for k, d in blobs if k == "html"]
    if not htmls:
        sys.exit("Tidak ada index.html ditemukan")
    index = max(htmls, key=len)
    (out / "index.html").write_bytes(index)
    pool = {}
    for k, d in blobs:
        if d is not index: pool.setdefault(k, []).append(d)
    for r in re.findall(rb'(?:src|href)="([^"#?]+\.[a-z0-9]+)"', index):
        path = r.decode().lstrip("/")
        if path.startswith("http"): continue
        kind = {"mjs": "js"}.get(path.rsplit(".", 1)[-1].lower(), path.rsplit(".", 1)[-1].lower())
        if pool.get(kind):
            dst = out / path; dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(pool[kind].pop(0))
    print("OK (heuristik) ->", out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

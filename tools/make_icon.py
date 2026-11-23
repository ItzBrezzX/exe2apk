#!/usr/bin/env python3
"""Ambil ikon dari exe (wrestool + Pillow) jadi PNG 1024x1024 RGBA; fallback placeholder.
Pemakaian: make_icon.py [app.exe] out.png"""
import sys, os, struct, zlib, subprocess, tempfile

def placeholder(path, size=1024, rgba=(70, 80, 200, 255)):
    raw = (b"\x00" + bytes(rgba) * size) * size
    def ch(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
                           + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))

def from_exe(exe, out):
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        ico = os.path.join(td, "i.ico")
        with open(ico, "wb") as f:
            r = subprocess.run(["wrestool", "-x", "-t", "14", exe], stdout=f, stderr=subprocess.DEVNULL)
        if r.returncode != 0 or os.path.getsize(ico) < 100:
            raise RuntimeError("no icon resource")
        im = Image.open(ico)
        sizes = im.info.get("sizes") or {im.size}
        im.size = max(sizes)
        im = im.convert("RGBA")
        side = max(im.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
        canvas.resize((1024, 1024), Image.LANCZOS).save(out)

if __name__ == "__main__":
    exe, out = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (None, sys.argv[1])
    try:
        if not exe: raise RuntimeError
        from_exe(exe, out); print("ikon dari exe")
    except Exception as e:
        placeholder(out); print("ikon placeholder", e if exe else "")

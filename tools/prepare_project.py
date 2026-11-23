#!/usr/bin/env python3
"""Buat project Tauri v2 (src-tauri) dari frontend hasil ekstrak (www).
Mendeteksi plugin Tauri dari JS dan memasangnya agar tidak error saat runtime."""
import argparse, json, os, pathlib, re, sys

# plugin -> (ekspresi init Rust). Hanya plugin resmi yang aman di Android.
SUPPORTED = {
    "fs": "tauri_plugin_fs::init()",
    "dialog": "tauri_plugin_dialog::init()",
    "os": "tauri_plugin_os::init()",
    "process": "tauri_plugin_process::init()",
    "http": "tauri_plugin_http::init()",
    "log": "tauri_plugin_log::Builder::new().build()",
    "notification": "tauri_plugin_notification::init()",
    "clipboard-manager": "tauri_plugin_clipboard_manager::init()",
    "opener": "tauri_plugin_opener::init()",
    "store": "tauri_plugin_store::Builder::new().build()",
    "websocket": "tauri_plugin_websocket::init()",
    "upload": "tauri_plugin_upload::init()",
}
BUILTIN = {"window", "webview", "event", "path", "app", "menu", "tray", "resources", "image"}

def exe_meta(exe):
    meta = {}
    if not exe or not os.path.exists(exe):
        return meta
    b = open(exe, "rb").read()
    for key in ("ProductName", "FileVersion", "CompanyName"):
        pat = re.escape(key).encode() if False else key.encode("utf-16le") + b"\x00\x00((?:[^\x00]\x00)+)"
        m = re.search(pat, b)
        if m:
            meta[key] = m.group(1).decode("utf-16le", "ignore").strip()
    return meta

def slug(s):
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    if not s: s = "app"
    return s if s[0].isalpha() else "a" + s

def semver(v):
    nums = re.findall(r"\d+", v or "")[:3]
    while len(nums) < 3: nums.append("0")
    return ".".join(nums) if any(n != "0" for n in nums) else "0.1.0"

def scan_www(www):
    text = ""
    for p in pathlib.Path(www).rglob("*"):
        if p.suffix.lower() in (".js", ".mjs", ".html", ".css", ".json") and p.stat().st_size < 30_000_000:
            text += p.read_text("utf-8", "ignore") + "\n"
    plugins = set(re.findall(r"plugin:([a-z0-9-]+)\|", text))
    return {
        "plugins": plugins,
        "global": bool(re.search(r"__TAURI__(?!_)", text)),
        "v2": "__TAURI_INTERNALS__" in text,
        "v1": "__TAURI_IPC__" in text,
        "files": sum(1 for p in pathlib.Path(www).rglob("*") if p.is_file()),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--www", default="www")
    ap.add_argument("--exe")
    ap.add_argument("--name", default="")
    ap.add_argument("--id", default="")
    ap.add_argument("--web-url", default="")
    a = ap.parse_args()

    www = pathlib.Path(a.www)
    if not (www / "index.html").exists():
        if not a.web_url:
            sys.exit("www/index.html tidak ada dan web_url kosong")
        www.mkdir(parents=True, exist_ok=True)
        (www / "index.html").write_text(
            "<!doctype html><meta charset=utf-8><script>location.replace(%s)</script>" % json.dumps(a.web_url))
    meta = exe_meta(a.exe)
    info = scan_www(www)
    name = a.name.strip() or meta.get("ProductName") or "App"
    app_id = a.id.strip() or "com.exe2apk." + slug(name)
    version = semver(meta.get("FileVersion", ""))

    plugins = sorted(p for p in info["plugins"] if p in SUPPORTED)
    unsupported = sorted(p for p in info["plugins"] if p not in SUPPORTED and p not in BUILTIN)
    warnings = []
    if info["v1"] and not info["v2"]:
        warnings.append("Frontend memakai API Tauri v1 (`__TAURI_IPC__`); tidak kompatibel dengan runtime v2, UI kemungkinan tidak berfungsi.")
    if unsupported:
        warnings.append("Plugin tidak didukung di Android, dilewati: " + ", ".join(unsupported))
    warnings.append("Backend Rust asli tidak ikut ter-port; `invoke()` ke command kustom akan gagal.")

    st = pathlib.Path("src-tauri"); (st / "src").mkdir(parents=True, exist_ok=True)
    (st / "capabilities").mkdir(exist_ok=True)

    deps = "".join('tauri-plugin-%s = "2"\n' % p for p in plugins)
    (st / "Cargo.toml").write_text(
        '[package]\nname = "app"\nversion = "%s"\nedition = "2021"\n\n'
        '[lib]\nname = "app_lib"\ncrate-type = ["staticlib", "cdylib", "rlib"]\n\n'
        '[build-dependencies]\ntauri-build = { version = "2", features = [] }\n\n'
        '[dependencies]\ntauri = { version = "2", features = [] }\n%s' % (version, deps))
    (st / "build.rs").write_text("fn main() {\n    tauri_build::build()\n}\n")
    (st / "src" / "main.rs").write_text(
        '#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]\nfn main() {\n    app_lib::run()\n}\n')
    chain = "".join("        .plugin(%s)\n" % SUPPORTED[p] for p in plugins)
    (st / "src" / "lib.rs").write_text(
        "#[cfg_attr(mobile, tauri::mobile_entry_point)]\npub fn run() {\n    tauri::Builder::default()\n"
        + chain + '        .run(tauri::generate_context!())\n        .expect("error while running tauri application");\n}\n')
    (st / "capabilities" / "default.json").write_text(json.dumps({
        "identifier": "default", "windows": ["main"],
        "permissions": ["core:default"] + ["%s:default" % p for p in plugins]}, indent=2))
    (st / "tauri.conf.json").write_text(json.dumps({
        "$schema": "https://schema.tauri.app/config/2",
        "productName": name, "version": version, "identifier": app_id,
        "build": {"frontendDist": "../www"},
        "app": {"withGlobalTauri": info["global"], "windows": [{"title": name}], "security": {"csp": None}},
        "bundle": {"active": True, "targets": "all",
                   "icon": ["icons/32x32.png", "icons/128x128.png", "icons/128x128@2x.png", "icons/icon.icns", "icons/icon.ico"],
                   "android": {"minSdkVersion": 24}}}, indent=2))

    lines = ["## Hasil persiapan", "- Nama: **%s**, ID: `%s`, versi: `%s`" % (name, app_id, version),
             "- File frontend: %d" % info["files"],
             "- Plugin terpasang: %s" % (", ".join(plugins) or "tidak ada"),
             "- withGlobalTauri: %s" % info["global"], ""] + ["- ⚠️ " + w for w in warnings]
    summary = "\n".join(lines)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(summary + "\n")

if __name__ == "__main__":
    main()

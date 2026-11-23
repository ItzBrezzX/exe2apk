#!/usr/bin/env python3
"""Safely inventory an installer and identify likely desktop frameworks.

This tool does not decompile, patch, or convert proprietary binaries. It extracts
ordinary installer payloads into a temporary workspace and reports file markers
so a developer can decide what Android reimplementation is technically feasible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

MAX_FILES = 4000
MAX_TOTAL = 1024 * 1024 * 1024
MAX_DEPTH = 3

def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", timeout=timeout, check=False)

def safe_zip_extract(src: Path, dest: Path) -> list[Path]:
    extracted = []
    total = 0
    with zipfile.ZipFile(src) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES:
            raise RuntimeError(f"ZIP contains too many entries ({len(infos)}).")
        for info in infos:
            p = Path(info.filename)
            if p.is_absolute() or ".." in p.parts:
                continue
            if info.is_dir():
                continue
            total += info.file_size
            if total > MAX_TOTAL:
                raise RuntimeError("ZIP uncompressed size exceeds 1 GiB safety limit.")
            target = dest.joinpath(*p.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as srcf, target.open("wb") as dstf:
                shutil.copyfileobj(srcf, dstf)
            extracted.append(target)
    return extracted

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def classify(files: list[Path]) -> list[str]:
    names = [p.name.lower() for p in files]
    paths = [p.as_posix().lower() for p in files]
    found = []
    checks = {
        "Tauri": ["tauri.conf.json", "src-tauri", "wry"],
        "Electron": ["resources/app.asar", "electron.asar", "electron.exe"],
        "NW.js": ["nw.dll", "package.nw"],
        ".NET": [".deps.json", ".runtimeconfig.json", "coreclr.dll", "hostfxr.dll"],
        "Qt": ["qt6core.dll", "qt5core.dll", "platforms/qwindows.dll"],
        "Java": [".jar", "jre/bin/java.exe"],
        "Chromium/WebView shell": ["icudtl.dat", "resources.pak", "chrome_100_percent.pak"],
    }
    for label, markers in checks.items():
        if any(any(m in n or m in p for n, p in zip(names, paths)) for m in markers):
            found.append(label)
    return found or ["Unknown / native Windows application (no common framework marker found)"]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    source = Path(args.input)
    out = Path(args.output)
    work = out / "extracted"
    out.mkdir(parents=True, exist_ok=True)

    if not source.is_file():
        raise SystemExit(f"Input not found: {source}")

    report = {
        "input": str(source),
        "size_bytes": source.stat().st_size,
        "sha256": sha256(source),
        "steps": [],
        "framework_candidates": [],
        "files": [],
        "limitations": [
            "This is an inventory report, not an EXE-to-APK converter.",
            "Windows executables cannot be made Android-native by renaming or wrapping them.",
            "A real port requires the original source/SDK or a permitted independent reimplementation."
        ]
    }

    payloads: list[Path] = []
    if source.suffix.lower() == ".zip":
        payloads = safe_zip_extract(source, work / "outer")
        report["steps"].append(f"Extracted outer ZIP: {len(payloads)} files")
    else:
        payloads = [source]

    seven = shutil.which("7z") or shutil.which("7zz")
    nested = []
    for i, p in enumerate(payloads):
        if p.suffix.lower() not in {".exe", ".msi"}:
            continue
        if seven is None:
            report["steps"].append("7z unavailable; installer payload was not expanded")
            break
        target = work / f"installer_{i}"
        target.mkdir(parents=True, exist_ok=True)
        listing = run([seven, "l", str(p)])
        report["steps"].append(f"7z listing {p.name}: exit={listing.returncode}")
        extract = run([seven, "x", "-y", f"-o{target}", str(p)], timeout=240)
        report["steps"].append(f"7z extraction {p.name}: exit={extract.returncode}")
        if extract.returncode == 0:
            nested.extend(x for x in target.rglob("*") if x.is_file())
        else:
            report["steps"].append(f"Installer could not be expanded by 7z: {p.name}")

    all_files = payloads + nested
    unique = []
    seen = set()
    for p in all_files:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp in seen or not p.is_file():
            continue
        seen.add(rp)
        unique.append(p)

    report["files"] = [
        {"path": str(p.relative_to(out)) if out in p.parents else p.name,
         "size_bytes": p.stat().st_size}
        for p in unique[:MAX_FILES]
    ]
    report["framework_candidates"] = classify(unique)
    report["file_count"] = len(unique)
    report["installer_payload_detected"] = bool(nested)
    report["decision"] = (
        "Tauri-like payload found; review the extracted frontend and backend manually."
        if "Tauri" in report["framework_candidates"]
        else "Not identified as Tauri. Do not run the Tauri conversion pipeline for this input."
    )
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Installer inspection",
        "",
        f"- Input: `{source.name}`",
        f"- Size: {report['size_bytes']} bytes",
        f"- SHA-256: `{report['sha256']}`",
        f"- Files inventoried: {report['file_count']}",
        f"- Nested installer payload extracted: {report['installer_payload_detected']}",
        "",
        "## Framework candidates",
        *[f"- {x}" for x in report["framework_candidates"]],
        "",
        "## Decision",
        report["decision"],
        "",
        "## Steps",
        *[f"- {x}" for x in report["steps"]],
        "",
        "## Important",
        *[f"- {x}" for x in report["limitations"]],
        "",
        "Full machine-readable inventory: `report.json`."
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        print("Installer extraction timed out.", file=sys.stderr)
        raise SystemExit(2)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Audit failed: {exc}", file=sys.stderr)
        raise SystemExit(2)

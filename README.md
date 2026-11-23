# exe2apk (khusus aplikasi Tauri)

Mengubah installer/exe **aplikasi Tauri milik Anda** menjadi APK lewat GitHub Actions.
Tidak ada konverter EXE→APK universal; pipeline ini hanya jalan untuk Tauri, dan berhenti dengan pesan jelas jika exe bukan Tauri.

## Pakai
1. Taruh `.exe` / `.msi` / `.zip` di `input/`, commit, push.
2. Actions → **Tauri EXE to APK** → Run workflow (pilih `release`/`debug` dan `abi`; `aarch64` untuk HP modern).
3. Unduh APK dari Artifacts `apk`.

## Alur
1. Ekstrak installer (7z) dan pilih exe yang terdeteksi Tauri (`tools/find_app_exe.py`).
2. Ambil frontend dengan [`untauri`](https://github.com/hbofz/untauri) (membaca tabel aset Tauri, nama asli terjaga); fallback scanner brotli; fallback `web_url`.
3. `tools/prepare_project.py` membuat project Tauri v2, mendeteksi plugin dari JS (fs, dialog, os, http, opener, store, dll.) dan memasangnya.
4. Ikon diambil dari exe (wrestool), lalu `tauri android init` dan `tauri android build`.
5. Release ditandatangani otomatis (keystore sementara). Untuk key tetap (update APK), isi secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEYSTORE_ALIAS`. Jika build release gagal, otomatis fallback ke debug.

## Batasan
- Backend Rust tidak ikut ter-port: `invoke()` ke command kustom gagal sampai Anda menulisnya di `src-tauri/src/lib.rs`.
- Frontend yang memakai API Tauri v1 tidak kompatibel dengan runtime v2.
- Fitur desktop (tray, window kustom, autostart, updater) tidak ada di Android.
- Belum pernah dijalankan di GitHub Actions oleh pembuatnya; log langkah yang gagal akan menunjukkan perbaikan yang perlu.
- Gunakan hanya untuk software milik Anda atau yang Anda berhak analisis.

#!/usr/bin/env bash
# Env: BUILD_TYPE=release|debug, ABI=aarch64|armv7|x86_64|i686|all
set -euo pipefail
mkdir -p out
TARGET=()
[ "${ABI:-aarch64}" != "all" ] && TARGET=(--target "${ABI:-aarch64}")
BUILD_TYPE="${BUILD_TYPE:-release}"

if [ "$BUILD_TYPE" = release ]; then
  if ! tauri android build --apk "${TARGET[@]}" --ci; then
    echo "::warning::Build release gagal, fallback ke debug"
    BUILD_TYPE=debug
  fi
fi
if [ "$BUILD_TYPE" = debug ]; then
  tauri android build --apk --debug "${TARGET[@]}" --ci
  APK=$(find src-tauri/gen/android -path '*debug*' -name '*.apk' | head -1)
  [ -n "$APK" ] || { echo "APK debug tidak ditemukan"; exit 1; }
  cp "$APK" out/app-debug.apk
  exit 0
fi

# Release: apk belum bertanda tangan -> zipalign + apksigner
UNSIGNED=$(find src-tauri/gen/android -name '*.apk' -path '*release*' | head -1)
[ -n "$UNSIGNED" ] || { echo "APK release tidak ditemukan"; exit 1; }
BT="$ANDROID_HOME/build-tools/$(ls "$ANDROID_HOME/build-tools" | sort -V | tail -1)"
if [ -n "${KEYSTORE_BASE64:-}" ]; then
  echo "$KEYSTORE_BASE64" | base64 -d > work/ks.jks
  KS_PASS="${KEYSTORE_PASSWORD:?}"; KS_ALIAS="${KEYSTORE_ALIAS:?}"
else
  KS_PASS="exe2apk-pass"; KS_ALIAS="exe2apk"
  keytool -genkeypair -keystore work/ks.jks -alias "$KS_ALIAS" -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass "$KS_PASS" -keypass "$KS_PASS" -dname "CN=exe2apk" >/dev/null 2>&1
fi
"$BT/zipalign" -f -P 16 4 "$UNSIGNED" work/aligned.apk 2>/dev/null || "$BT/zipalign" -f -p 4 "$UNSIGNED" work/aligned.apk
"$BT/apksigner" sign --ks work/ks.jks --ks-pass "pass:$KS_PASS" --ks-key-alias "$KS_ALIAS" \
  --key-pass "pass:$KS_PASS" --out out/app-release.apk work/aligned.apk
"$BT/apksigner" verify out/app-release.apk

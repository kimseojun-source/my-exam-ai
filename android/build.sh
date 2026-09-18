#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/opt/android-sdk}}"
BT="$(find "$SDK/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
ANDROID_JAR="$(find "$SDK/platforms" -name android.jar | sort -V | tail -1)"
OUT="${FOREST_BUILD_DIR:-$ROOT/build/android}"
mkdir -p "$OUT/classes" "$OUT/dex"
"$BT/aapt2" compile --dir "$ROOT/android/res" -o "$OUT/resources.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$ANDROID_JAR" --manifest "$ROOT/android/AndroidManifest.xml" "$OUT/resources.zip" --min-sdk-version 26 --target-sdk-version 35
javac -source 8 -target 8 -classpath "$ANDROID_JAR" -d "$OUT/classes" "$ROOT/android/src/com/myexamai/app/MainActivity.java"
jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$BT/d8" --lib "$ANDROID_JAR" --min-api 26 --output "$OUT/dex" "$OUT/classes.jar"
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && zip -q "$OUT/unsigned.apk" classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
# Production signing is supplied separately; private keys never enter git.
KEYSTORE=""
if [[ -n "${FOREST_KEYSTORE_PATH:-}" ]]; then
 KEYSTORE="$FOREST_KEYSTORE_PATH"
elif [[ -n "${FOREST_KEYSTORE_B64:-}" ]]; then
 printf '%s' "$FOREST_KEYSTORE_B64" | base64 -d > "$OUT/signing.p12"
 chmod 600 "$OUT/signing.p12"
 KEYSTORE="$OUT/signing.p12"
fi
if [[ -n "$KEYSTORE" ]]; then
 export FOREST_KEYSTORE_PASSWORD="${FOREST_KEYSTORE_PASSWORD:-}"
 "$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass env:FOREST_KEYSTORE_PASSWORD --out "$OUT/FOREST-9.3.0.apk" "$OUT/aligned.apk"
 "$BT/apksigner" verify --verbose --print-certs "$OUT/FOREST-9.3.0.apk"
 [[ "$KEYSTORE" != "$OUT/signing.p12" ]] || rm "$KEYSTORE"
else
 cp "$OUT/aligned.apk" "$OUT/FOREST-9.3.0-unsigned.apk"
fi
"$BT/aapt2" dump badging "$OUT/base.apk"

#!/usr/bin/env bash
set -euo pipefail
SOURCE_REF="${FOREST_SOURCE_COMMIT:-main}"
mkdir -p /tmp/forest-source
curl -fSL --retry 3 "https://github.com/kimseojun-source/my-exam-ai/archive/${SOURCE_REF}.tar.gz" -o /tmp/forest-source.tar.gz
tar xzf /tmp/forest-source.tar.gz -C /tmp/forest-source --strip-components=1
if [[ -z "${FOREST_KEYSTORE_B64:-}" && -z "${FOREST_KEYSTORE_PATH:-}" ]]; then
 KEY_DIR="${FOREST_KEY_DIR:-/data}"
 mkdir -p "$KEY_DIR"
 if [[ ! -s "$KEY_DIR/forest-release.p12" || ! -s "$KEY_DIR/forest-release.password" ]]; then
  PASSWORD="$(head -c 36 /dev/urandom | base64 | tr -d '\n')"
  printf '%s' "$PASSWORD" > "$KEY_DIR/forest-release.password"
  chmod 600 "$KEY_DIR/forest-release.password"
  keytool -genkeypair -noprompt -storetype PKCS12 -keystore "$KEY_DIR/forest-release.p12" -alias forest -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=FOREST App, O=FOREST" -storepass "$PASSWORD" -keypass "$PASSWORD"
  chmod 600 "$KEY_DIR/forest-release.p12"
 fi
 export FOREST_KEYSTORE_PATH="$KEY_DIR/forest-release.p12"
 export FOREST_KEYSTORE_PASSWORD="$(cat "$KEY_DIR/forest-release.password")"
fi
bash /tmp/forest-source/android/build.sh
cd /tmp/forest-source/build/android
# Only the signed APK and minimal landing page are served, not build intermediates or keys.
mkdir -p /tmp/forest-public
cp FOREST-9.3.0.apk /tmp/forest-public/
sha256sum FOREST-9.3.0.apk | awk '{print $1}' > /tmp/forest-public/FOREST-9.3.0.apk.sha256
printf '{"version":"9.3.0","source":"%s"}\n' "$SOURCE_REF" > /tmp/forest-public/build.json
cp /tmp/forest-source/static/icons/icon-192.png /tmp/forest-public/icon.png
cp /tmp/forest-source/android/download.html /tmp/forest-public/index.html
cd /tmp/forest-public
python3 -m http.server "${PORT:-8080}"

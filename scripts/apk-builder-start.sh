#!/usr/bin/env bash
set -euo pipefail
mkdir -p /tmp/forest-source
curl -fSL --retry 3 "https://github.com/kimseojun-source/my-exam-ai/archive/${FOREST_SOURCE_COMMIT:?Set the exact source commit}.tar.gz" -o /tmp/forest-source.tar.gz
tar xzf /tmp/forest-source.tar.gz -C /tmp/forest-source --strip-components=1
bash /tmp/forest-source/android/build.sh
cd /tmp/forest-source/build/android
# Only the signed APK and minimal landing page are served, not build intermediates or keys.
mkdir -p /tmp/forest-public
cp FOREST-9.0.0.apk /tmp/forest-public/
cp /tmp/forest-source/static/icons/icon-192.png /tmp/forest-public/icon.png
cp /tmp/forest-source/android/download.html /tmp/forest-public/index.html
cd /tmp/forest-public
python3 -m http.server "${PORT:-8080}"

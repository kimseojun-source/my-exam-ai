# FOR'EST

A two-profile, course-scoped study app. The existing `exam_ai.db`, `uploads/`, profile IDs, PIN hashes, session cookie and session secret are preserved.

## Run

```sh
pip install -r requirements.txt
DATA_ROOT=./data_store python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

For Railway, retain the existing `/data` volume and `SESSION_SECRET`. Start with `sh -c 'exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}'`. Version 9 creates a consistent SQLite snapshot at `/data/backups/before-9.0.0.sqlite3` before first opening the existing database. Original files are neither moved nor removed.

`static/` is the authoritative web frontend. Root `index.html` is kept in sync for compatibility. The historical ZIP is retained but no longer used by Docker. Runtime environment-variable CSS/JS patches are no longer necessary.

## AI and uploads

Configure `OPENAI_API_KEY` privately on the server. Existing `OPENAI_MODEL` and `OPENAI_VISION_MODEL` settings are retained. With no key, text PDF extraction and basic summaries work; image/scanned originals remain stored as `pending_vision`. They can be reprocessed after connecting AI. API errors are surfaced without exposing credentials.

Uploads support PDF, PNG, JPEG, WEBP, HEIC and HEIF, up to 15 files per request and 40 MiB per file. Each successful file commits independently; invalid files are reported individually. Images are orientation-corrected and converted to JPEG for the vision request. Access to originals, reprocessing, analysis and chat is scoped to the active profile and course. Profile JSON backups include extracted text and exam patterns; original files can be downloaded separately.

## Phones and tablets

The web app/PWA supports Android, iPhone and iPad in portrait and landscape. Wide landscape screens use a sidebar, material panel and study panel. Narrow/split-screen layouts stack without fixed minimum widths. Rotation preserves the existing page and input state. iOS users can add the website to the Home Screen; this repository does not claim to produce a signed iOS IPA.

## Icons and Android

The approved original is `assets/forest-original.png`. `python scripts/export_icons.py` exports launcher, round, adaptive, PWA and iOS assets without substituting artwork. `android/AndroidManifest.xml` references the custom resources and retains package ID `com.myexamai.app`.

Run `bash android/build.sh` inside `mobiledevops/android-sdk-image:36.1.0`. Supply `FOREST_KEYSTORE_B64` (base64 PKCS12/JKS) and `FOREST_KEYSTORE_PASSWORD` privately for a signed APK. With no key, the build produces an unsigned APK. Signing keys must not be committed.

The previously deployed APK signer SHA-256 is `7c73fb139c3a300d4eb836da6906025614c065f56880f88aed704c8af47dc183`. An in-place update requires the matching private signing key. The old builder generated ephemeral signing keys. Do not uninstall an existing app or claim update compatibility until this is resolved. A differently signed candidate can be tested on a device without the previous package.

## Verification

```sh
python -m pytest -q tests
node --check static/app.js
node --check static/detail.js
node --check static/sw.js
```

Tests cover partial and duplicate uploads, original download, profile/course isolation, PDF text extraction, pending image recovery, vision request format, subject-only AI context, SQLite snapshot and backup preservation. AI mocks verify request wiring, not live model quality or billing. Physical iOS/Android devices and matching-key APK upgrade need separate verification.

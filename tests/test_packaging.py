from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_android_release_metadata_and_custom_icon():
    manifest = (ROOT / "android/AndroidManifest.xml").read_text()
    assert 'android:versionCode="901"' in manifest
    assert 'android:versionName="9.1.0"' in manifest
    assert 'android:icon="@mipmap/ic_launcher"' in manifest
    assert 'android:roundIcon="@mipmap/ic_launcher_round"' in manifest


def test_builder_serves_only_signed_release_and_keeps_signer_on_volume():
    start = (ROOT / "scripts/apk-builder-start.sh").read_text()
    build = (ROOT / "android/build.sh").read_text()
    assert 'FOREST_SOURCE_COMMIT:-main' in start
    assert '/data' in start
    assert 'forest-release.p12' in start
    assert 'FOREST-9.1.0.apk' in start
    assert 'FOREST_KEYSTORE_PATH' in build
    assert 'apksigner' in build
    assert 'FOREST-9.1.0.apk' in build


def test_ios_pwa_has_install_guidance_and_apple_metadata():
    html = (ROOT / "static/index.html").read_text()
    script = (ROOT / "static/install.js").read_text()
    manifest = (ROOT / "static/manifest.webmanifest").read_text()
    assert 'apple-mobile-web-app-capable' in html
    assert 'apple-mobile-web-app-status-bar-style' in html
    assert '/install.js?v=1' in html
    assert '홈 화면에 추가' in script
    assert 'navigator.standalone' in script
    assert '"orientation": "any"' in manifest


def test_annotation_close_saves_before_dismissal():
    script = (ROOT / "static/app.js").read_text()
    assert '저장 후 닫기' in script
    assert 'if(a.dirty)await saveAnnotations()' in script
    assert "if(ANNO===a)closeAnnotator()" in script
    assert "addEventListener('beforeunload'" in script


def test_pwa_offline_cache_contains_only_public_shell():
    script = (ROOT / "static/sw.js").read_text()
    assert "forest-shell-v11" in script
    for asset in ["/app.css?v=11", "/app.js?v=10", "/detail.js?v=4", "/install.js?v=1"]:
        assert asset in script
    assert "url.pathname.startsWith('/api/')" in script
    assert "cache.put('/',response.clone())" in script
    assert "caches.match('/')||caches.match('/offline.html')" in script


def test_installed_pwa_has_branded_launch_animation():
    html = (ROOT / "static/index.html").read_text()
    assert "standalone-launch" in html
    assert 'id="launchSplash"' in html
    assert "navigator.standalone===true" in html
    assert "prefers-reduced-motion:reduce" in html
    assert "Math.max(0,900-" in html

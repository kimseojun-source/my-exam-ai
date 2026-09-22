from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_android_release_metadata_and_custom_icon():
    manifest = (ROOT / "android/AndroidManifest.xml").read_text()
    assert 'android:versionCode="930"' in manifest
    assert 'android:versionName="9.3.0"' in manifest
    assert 'android.permission.RECORD_AUDIO' in manifest
    assert 'android:icon="@mipmap/ic_launcher"' in manifest
    assert 'android:roundIcon="@mipmap/ic_launcher_round"' in manifest


def test_builder_serves_only_signed_release_and_keeps_signer_on_volume():
    start = (ROOT / "scripts/apk-builder-start.sh").read_text()
    build = (ROOT / "android/build.sh").read_text()
    assert 'FOREST_SOURCE_COMMIT:-main' in start
    assert '/data' in start
    assert 'forest-release.p12' in start
    assert 'FOREST-9.3.0.apk' in start
    assert 'FOREST_KEYSTORE_PATH' in build
    assert 'apksigner' in build
    assert 'FOREST-9.3.0.apk' in build


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
    assert "forest-shell-v23" in script
    for asset in ["/app.css?v=17", "/app.js?v=19", "/detail.js?v=6", "/install.js?v=1"]:
        assert asset in script
    assert "url.pathname.startsWith('/api/')" in script
    assert "cache.put('/',response.clone())" in script
    assert "caches.match('/')||caches.match('/offline.html')" in script


def test_study_first_workspace_is_cached_and_keeps_management_in_drawer():
    html = (ROOT / "static/index.html").read_text()
    shell = (ROOT / "static/workspace.js").read_text()
    styles = (ROOT / "static/workspace.css").read_text()
    assert '/workspace.js?v=2' in html
    assert '/workspace.css?v=2' in html
    assert "studyDrawer" in shell
    assert "event.target===drawer" in shell
    assert "aria-expanded" in shell
    assert "sourceDocument" in shell
    assert "forest_reading_" in shell
    assert "openAnnotator(doc.id,doc.pages,doc.name,page)" in shell
    assert "@media(max-width:700px)" in styles
    assert "data-view=source" in styles


def test_installed_pwa_has_branded_launch_animation():
    html = (ROOT / "static/index.html").read_text()
    assert 'id="splash"' in html
    assert "For your" in html
    assert "Ever-Smarter" in html
    assert "Tomorrow" in html
    assert "animation:splashOut .38s ease 1.7s forwards" in html
    assert "animation-delay:.22s" in html
    assert "animation-delay:.44s" in html
    assert "animation:brandIn .45s" in html
    assert "prefers-reduced-motion:reduce" in html


def test_recording_ui_and_native_microphone_bridge():
    html = (ROOT / "static/index.html").read_text()
    script = (ROOT / "static/app.js").read_text()
    activity = (ROOT / "android/src/com/myexamai/app/MainActivity.java").read_text()
    assert 'id="startRecording"' in html
    assert 'id="liveTranscript"' in html
    assert "navigator.mediaDevices.getUserMedia" in script
    assert "new MediaRecorder" in script
    assert 'id="cancelRecording"' in html
    assert "cancelLectureRecording" in script
    assert 'id="pauseRecording"' in html
    assert "toggleLectureRecordingPause" in script
    assert "data-delete-lecture" in script
    assert "confirm_saved=true" in script
    assert "data-delete-document" in script
    assert "?confirm=true" in script
    assert "createDataChannel('oai-events')" in script
    assert "/v1/realtime/calls" in script
    assert "RESOURCE_AUDIO_CAPTURE" in activity
    assert "forest-v12-runtime-production.up.railway.app" in activity


def test_market_inspired_today_dashboard_guides_next_action():
    html = (ROOT / "static/index.html").read_text()
    script = (ROOT / "static/app.js").read_text()
    styles = (ROOT / "static/app.css").read_text()
    assert 'id="studyMission"' in html
    assert 'id="studyReadiness"' in html
    assert "function studyDashboardState" in script
    for action in ["upload", "analyze", "review", "quiz", "mock"]:
        assert f"kind:'{action}'" in script
    assert "data-study-action" in script
    assert ".study-mission" in styles


def test_course_resume_and_summary_ui_are_user_scoped():
    script = (ROOT / "static/app.js").read_text()
    styles = (ROOT / "static/app.css").read_text()
    assert "forest_course_${PID}" in script
    assert "course.due_count" in script
    assert "course.document_count" in script
    assert "course.last_score" in script
    assert "data-course-id" in script
    assert ".course-title" in styles


def test_mobile_forms_core_actions_and_timecoded_transcript():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    detail = (ROOT / "static/detail.js").read_text()
    styles = (ROOT / "static/app.css").read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert '<div id="lectureNote"' in html
    assert "data-transcript-lecture" in app
    assert "data-seek-lecture" in app
    assert "data-core-practice" in detail
    assert "data-core-source" in detail
    assert "data-core-ask" in detail
    assert 'id="cancelAnalysisButton"' in html
    assert "cancelCurrentAnalysis" in app
    assert "AbortController" in app
    assert ".core-detail-layout.has-source" in detail
    assert "loadInlineSource" in detail
    assert "@media(max-width:520px){.side{grid-template-columns:minmax(0,1fr)}" in styles
    assert "uvicorn forest_app:app" in dockerfile

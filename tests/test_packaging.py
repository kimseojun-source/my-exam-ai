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
    html = (ROOT / "static/index.html").read_text()
    script = (ROOT / "static/sw.js").read_text()
    assert "forest-shell-v40" in script
    for asset in ["/app.css?v=21", "/app.js?v=33", "/detail.js?v=6", "/install.js?v=1"]:
        assert asset in script
    assert 'src="/app.js?v=33"' in html
    assert "url.pathname.startsWith('/api/')" in script
    assert "cache.put('/',response.clone())" in script
    assert "caches.match('/')||caches.match('/offline.html')" in script


def test_study_first_workspace_is_cached_and_keeps_management_in_drawer():
    html = (ROOT / "static/index.html").read_text()
    shell = (ROOT / "static/workspace.js").read_text()
    styles = (ROOT / "static/workspace.css").read_text()
    assert '/workspace.js?v=3' in html
    assert '/workspace.css?v=3' in html
    assert "studyDrawer" in shell
    assert "event.target===drawer" in shell
    assert "aria-expanded" in shell
    assert "forest_source_width" in shell
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
    assert 'id="retryCaptions"' in html
    assert "retryRealtimeCaptions" in script
    assert "실시간 자막 다시 연결 중" in script
    assert "setCaptionConnectionState('connected')" in script
    assert "자막 연결 시간이 초과됐어" in script
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


def test_document_selection_gives_immediate_mobile_feedback():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert 'id="uploadStatus" role="status" aria-live="polite"' in html
    assert "addEventListener('change',showSelectedDocuments)" in app
    assert "한 번에 15개까지만" in app
    assert "40MB를 넘는 파일" in app
    assert "아래 자료 추가를 누르면 읽기를 시작해" in app
    assert 'onclick="uploadDocs()" disabled' in html
    assert "button.disabled=tooMany||tooLarge" in app
    assert "if(button)button.disabled=true" in app


def test_document_upload_can_be_stopped_without_hiding_partial_results():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert 'id="cancelUploadButton"' in html
    assert "documentUploadController=new AbortController()" in app
    assert "signal:documentUploadController.signal" in app
    assert "documentUploadController?.abort()" in app
    assert "e.name==='AbortError'" in app
    assert "서버 처리가 먼저 끝난 자료가 있으면 목록에 표시돼" in app
    assert "if(!uploadStopped)showSelectedDocuments()" in app
    assert "같은 파일로 다시 시도할 수 있어" in app


def test_audio_selection_explains_size_before_upload():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert 'id="uploadLecture"' in html and 'onclick="uploadLectureAudio()" disabled' in html
    assert 'id="audioSelectionStatus"' in html
    assert "addEventListener('change',showSelectedLectureAudio)" in app
    assert "24MB를 넘어 AI 자막을 만들 수 없어" in app
    assert "파일 분석하기를 누르면 시간 자막을 만들기 시작해" in app
    assert "showSelectedLectureAudio();" in app


def test_audio_upload_can_be_stopped_and_retried():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert 'id="cancelLectureUpload"' in html
    assert "lectureUploadController=new AbortController()" in app
    assert "signal:lectureUploadController.signal" in app
    assert "lectureUploadController?.abort()" in app
    assert "녹음 파일 업로드를 중단했어. 파일 선택은 유지했어." in app


def test_active_recording_or_upload_blocks_accidental_navigation():
    app = (ROOT / "static/app.js").read_text()
    assert "function workspaceNavigationBlocked()" in app
    assert "if(course&&!workspaceNavigationBlocked())openCourse" in app
    assert "switchProfile=async function(){if(workspaceNavigationBlocked())return;" in app
    assert "녹음 중에는 과목이나 사용자를 바꿀 수 없어" in app
    assert "자료 업로드 중에는 과목이나 사용자를 바꿀 수 없어" in app
    assert "녹음 파일 업로드 중에는 과목이나 사용자를 바꿀 수 없어" in app
    assert "자동분석 중에는 과목이나 사용자를 바꿀 수 없어" in app
    assert "!ANNO?.dirty&&!REC?.active&&!documentUploadController&&!lectureUploadController&&!analysisRunning" in app


def test_mobile_touch_targets_remain_at_least_44px():
    styles = (ROOT / "static/app.css").read_text()
    assert ".document-delete{flex:none;min-height:44px" in styles
    assert ".lecture-delete{flex:none;min-height:44px" in styles
    assert ".annotation-toolbar button{min-height:44px}" in styles
    assert ".annotation-sheet footer button{min-height:44px}" in styles


def test_network_loss_and_recovery_are_explained():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert 'id="networkStatus"' in html
    assert "addEventListener('offline'" in app
    assert "addEventListener('online'" in app
    assert "인터넷 연결이 끊겼어" in app
    assert "인터넷 연결이 복구됐어" in app


def test_empty_state_points_to_first_course_action():
    html = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert 'onclick="startFirstCourse()"' in html
    assert "input.scrollIntoView" in app
    assert "e.key==='Enter'" in app


def test_course_creation_validates_and_reports_progress():
    html = (ROOT / "static/index.html").read_text()
    assert 'id="createCourseButton"' in html
    assert 'id="courseCreateStatus"' in html
    assert 'if(!name){status.textContent="과목명을 입력해줘."' in html
    assert 'button.disabled=true;button.textContent="만드는 중…"' in html
    assert 'if(button.disabled)return' in html

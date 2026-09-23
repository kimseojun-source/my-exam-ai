from pathlib import Path

from fastapi.testclient import TestClient

import server


def test_public_homepage_is_readable_without_changing_legacy_login():
    client = TestClient(server.app)
    page = client.get('/start.html')
    assert page.status_code == 200
    assert '내 자료에서' in page.text
    assert '기존 사용자 로그인' in page.text
    assert '새 회원가입과 유료 서비스는 준비 중' in page.text
    assert '아직 결제할 수 없고 요금도 확정되지 않았어' in page.text
    assert client.get('/').status_code == 200


def test_homepage_has_mobile_viewport_and_no_payment_or_user_data_scripts():
    page = (Path(__file__).resolve().parents[1] / 'static/start.html').read_text()
    assert 'name="viewport"' in page
    assert '본문으로 바로가기' in page
    assert 'prefers-reduced-motion' in page
    assert '<script' not in page
    assert 'schema.org/SoftwareApplication' in page
    assert 'itemprop="applicationCategory"' in page
    assert 'property="og:image"' in page
    assert '/api/profiles' not in page
    assert 'checkout' not in page.lower()


def test_search_files_expose_only_the_public_homepage():
    root = Path(__file__).resolve().parents[1] / 'static'
    robots = (root / 'robots.txt').read_text()
    sitemap = (root / 'sitemap.xml').read_text()
    indexnow_files = list(root.glob('[0-9a-f]' * 32 + '.txt'))

    assert 'Disallow: /' in robots
    assert 'Allow: /start.html' in robots
    assert 'Allow: /sitemap.xml' in robots
    assert len(indexnow_files) == 1
    assert f'Allow: /{indexnow_files[0].name}' in robots
    assert '/start.html' in sitemap
    assert '/api/' not in sitemap

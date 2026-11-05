import re


def test_home_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Habari</title>" in response.text
    assert "Are you safe right now?" in response.text
    assert 'id="quick-exit"' in response.text


def test_page_assets_are_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/icon.svg").status_code == 200
    assert client.get("/favicon.ico").status_code == 200


def test_page_has_strict_security_headers(client):
    for path in ("/", "/static/app.js"):
        headers = client.get(path).headers
        assert "default-src 'self'" in headers["content-security-policy"]
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["referrer-policy"] == "no-referrer"
        assert headers["cache-control"] == "no-store"


def test_docs_page_is_not_restricted_by_the_page_policy(client):
    assert "content-security-policy" not in client.get("/docs").headers


def test_page_has_no_inline_script_or_style(client):
    html = client.get("/").text
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "style=" not in html
    assert "onclick=" not in html


def test_page_makes_no_third_party_requests(client):
    for path in ("/", "/static/app.js", "/static/app.css"):
        body = client.get(path).text
        hosts = re.findall(r"https?://([^/\s\"')]+)", body)
        assert set(hosts) <= {"www.w3.org", "www.google.com"}, hosts


def test_script_never_writes_server_text_as_html(client):
    script = client.get("/static/app.js").text
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script
    assert "localStorage" not in script and "sessionStorage" not in script


def test_unknown_static_file_is_404(client):
    assert client.get("/static/missing.js").status_code == 404

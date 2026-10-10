"""
Main test suite for RepurposeKit Lite.
"""
import json
import os
import pytest
from fastapi.testclient import TestClient

# Use an isolated in-memory database for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_repurposekit.db"
os.environ["AI_PROVIDER"] = "mock"
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"

from app.main import app
from app.database import init_db, engine, Base


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean up file
    if os.path.exists("test_repurposekit.db"):
        try:
            os.remove("test_repurposekit.db")
        except Exception:
            pass


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def get_csrf(client: TestClient) -> str:
    """Fetch a CSRF token by loading the homepage."""
    resp = client.get("/")
    assert resp.status_code == 200
    # Extract CSRF from the response HTML
    html = resp.text
    start = html.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    end = html.find('"', start)
    token = html[start:end]
    assert token, "Could not extract CSRF token"
    return token


# ── 1. Homepage ────────────────────────────────────────────────────────────────
def test_homepage_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "RepurposeKit" in resp.text


# ── 2. Health endpoint ─────────────────────────────────────────────────────────
def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "mock_mode" in data


# ── 3. Valid input generates all four outputs ──────────────────────────────────
def test_valid_generate_mock(client):
    csrf = get_csrf(client)
    resp = client.post("/generate", data={
        "source_content": "IBM has announced a major expansion of AI services for enterprise clients.",
        "tone": "professional",
        "csrf_token": csrf,
    })
    assert resp.status_code == 200
    html = resp.text
    assert "LinkedIn" in html
    assert "Twitter" in html or "X /" in html
    assert "Instagram" in html
    assert "Newsletter" in html


# ── 4. Empty input rejected ────────────────────────────────────────────────────
def test_empty_input_rejected(client):
    csrf = get_csrf(client)
    resp = client.post("/generate", data={
        "source_content": "   ",
        "tone": "professional",
        "csrf_token": csrf,
    })
    assert resp.status_code == 422
    assert "empty" in resp.text.lower() or "cannot" in resp.text.lower()


# ── 5. Oversized input rejected ────────────────────────────────────────────────
def test_oversized_input_rejected(client):
    csrf = get_csrf(client)
    huge = "x" * 5001
    resp = client.post("/generate", data={
        "source_content": huge,
        "tone": "professional",
        "csrf_token": csrf,
    })
    assert resp.status_code == 422
    assert "5,000" in resp.text or "5000" in resp.text or "exceed" in resp.text.lower()


# ── 6. X character limit ───────────────────────────────────────────────────────
def test_x_character_limit():
    from app.schemas import GeneratedContent
    from app.validators import validate_content, MAX_X_POST_CHARS

    oversized_post = "A" * 300  # > 280
    content = GeneratedContent(
        title="Test",
        tags=["AI"],
        linkedin="LinkedIn post",
        x_thread=[oversized_post, "Normal post"],
        instagram="Instagram caption",
        newsletter="Newsletter content",
    )
    corrected, issues = validate_content(content)
    assert len(corrected.x_thread[0]) <= MAX_X_POST_CHARS
    statuses = [i.status for i in issues if "x_thread[0]" in i.field]
    assert "WARNING" in statuses


# ── 7. Instagram character limit ───────────────────────────────────────────────
def test_instagram_character_limit():
    from app.schemas import GeneratedContent
    from app.validators import validate_content, MAX_INSTAGRAM_CHARS

    content = GeneratedContent(
        title="Test",
        tags=["AI"],
        linkedin="LinkedIn post",
        x_thread=["Post 1"],
        instagram="I" * 2300,
        newsletter="Newsletter content",
    )
    corrected, issues = validate_content(content)
    assert len(corrected.instagram) <= MAX_INSTAGRAM_CHARS
    statuses = [i.status for i in issues if i.field == "instagram"]
    assert "WARNING" in statuses


# ── 8. More than 5 hashtags rejected/trimmed ───────────────────────────────────
def test_hashtag_limit():
    from app.schemas import GeneratedContent
    from app.validators import validate_content, MAX_HASHTAGS

    content = GeneratedContent(
        title="Test",
        tags=["A", "B", "C", "D", "E", "F", "G"],
        linkedin="LinkedIn post",
        x_thread=["Post 1"],
        instagram="Caption",
        newsletter="Newsletter",
    )
    corrected, issues = validate_content(content)
    assert len(corrected.tags) <= MAX_HASHTAGS
    statuses = [i.status for i in issues if i.field == "tags"]
    assert "WARNING" in statuses


# ── 9. SQL injection payload ───────────────────────────────────────────────────
def test_sql_injection_does_not_bypass(client):
    csrf = get_csrf(client)
    payload = "' OR 1=1 --"
    # This should either work as content or be rejected, never cause a server error
    resp = client.post("/generate", data={
        "source_content": payload,
        "tone": "professional",
        "csrf_token": csrf,
    })
    # Either 200 (generated fine, safely) or 422 (validation rejected short content)
    assert resp.status_code in (200, 422)
    # Must never be a 500
    assert resp.status_code != 500


# ── 10. XSS content escaped in HTML ──────────────────────────────────────────
def test_xss_escaped_in_history(client):
    csrf = get_csrf(client)
    xss = "<script>alert(1)</script>"
    resp = client.post("/generate", data={
        "source_content": f"Test content with XSS attempt: {xss} and more text here.",
        "tone": "professional",
        "csrf_token": csrf,
    })
    # If generation succeeded, check no raw script tag appears
    assert "<script>alert(1)</script>" not in resp.text
    # Check that it's properly escaped if present
    if "script" in resp.text.lower():
        assert "&lt;script&gt;" in resp.text or "alert" not in resp.text


# ── 11. POST without CSRF token returns 403 ───────────────────────────────────
def test_post_without_csrf_returns_403(client):
    resp = client.post("/generate", data={
        "source_content": "Some valid content here for testing purposes.",
        "tone": "professional",
        "csrf_token": "invalid-token-xyz",
    })
    assert resp.status_code == 403


# ── 12. Generated content saved in DB ────────────────────────────────────────
def test_generation_saved_in_db(client):
    from app.database import SessionLocal
    from app.models import Generation

    csrf = get_csrf(client)
    unique_content = "Unique test content for DB persistence check 99887766."
    resp = client.post("/generate", data={
        "source_content": unique_content,
        "tone": "casual",
        "csrf_token": csrf,
    })
    assert resp.status_code == 200

    db = SessionLocal()
    try:
        gen = db.query(Generation).filter(Generation.source_content == unique_content).first()
        assert gen is not None
        assert gen.tone == "casual"
        assert gen.linkedin
        assert gen.newsletter
    finally:
        db.close()


# ── 13. History listing works ─────────────────────────────────────────────────
def test_history_listing(client):
    resp = client.get("/history")
    assert resp.status_code == 200
    assert "History" in resp.text


# ── 14. Unknown history ID returns 404 ────────────────────────────────────────
def test_unknown_history_id_returns_404(client):
    resp = client.get("/history/999999")
    assert resp.status_code == 404


# ── 15. Markdown export data present ─────────────────────────────────────────
def test_markdown_export_data_in_results(client):
    csrf = get_csrf(client)
    resp = client.post("/generate", data={
        "source_content": "Testing markdown export functionality with sufficient content.",
        "tone": "witty",
        "csrf_token": csrf,
    })
    assert resp.status_code == 200
    # EXPORT_DATA JS object should be in the page
    assert "EXPORT_DATA" in resp.text
    assert "linkedin" in resp.text
    assert "x_thread" in resp.text
    assert "instagram" in resp.text
    assert "newsletter" in resp.text

"""
Validators for generated content.
All checks are deterministic and independent of the AI model.
"""
from typing import List
from app.schemas import GeneratedContent, ValidationIssue

MAX_X_POST_CHARS = 280
MAX_INSTAGRAM_CHARS = 2200
MAX_HASHTAGS = 5


def validate_content(content: GeneratedContent) -> tuple[GeneratedContent, List[ValidationIssue]]:
    """
    Validate and, where possible, auto-correct generated content.
    Returns (corrected_content, issues).
    """
    issues: List[ValidationIssue] = []
    data = content.model_copy(deep=True)

    # ── Hashtags ──────────────────────────────────────────────────────────────
    if len(data.tags) > MAX_HASHTAGS:
        original_count = len(data.tags)
        data.tags = data.tags[:MAX_HASHTAGS]
        issues.append(ValidationIssue(
            field="tags",
            status="WARNING",
            message=f"Trimmed hashtags from {original_count} to {MAX_HASHTAGS}.",
        ))
    else:
        issues.append(ValidationIssue(field="tags", status="VALID", message="Hashtags OK."))

    # ── X/Twitter thread ──────────────────────────────────────────────────────
    corrected_thread: List[str] = []
    thread_ok = True
    for i, post in enumerate(data.x_thread):
        if len(post) > MAX_X_POST_CHARS:
            thread_ok = False
            truncated = post[:MAX_X_POST_CHARS - 1] + "…"
            corrected_thread.append(truncated)
            issues.append(ValidationIssue(
                field=f"x_thread[{i}]",
                status="WARNING",
                message=f"Post {i+1} truncated from {len(post)} to {MAX_X_POST_CHARS} chars.",
            ))
        else:
            corrected_thread.append(post)
    if thread_ok:
        issues.append(ValidationIssue(field="x_thread", status="VALID", message="X/Twitter thread OK."))
    data.x_thread = corrected_thread

    # ── Instagram ─────────────────────────────────────────────────────────────
    if len(data.instagram) > MAX_INSTAGRAM_CHARS:
        data.instagram = data.instagram[:MAX_INSTAGRAM_CHARS - 1] + "…"
        issues.append(ValidationIssue(
            field="instagram",
            status="WARNING",
            message=f"Instagram caption truncated to {MAX_INSTAGRAM_CHARS} chars.",
        ))
    else:
        issues.append(ValidationIssue(field="instagram", status="VALID", message="Instagram caption OK."))

    # ── Required fields ───────────────────────────────────────────────────────
    for field in ("title", "linkedin", "newsletter"):
        val = getattr(data, field, "")
        if not isinstance(val, str) or not val.strip():
            issues.append(ValidationIssue(
                field=field,
                status="REJECTED",
                message=f"Field '{field}' is missing or empty.",
            ))
        else:
            issues.append(ValidationIssue(field=field, status="VALID", message=f"{field} OK."))

    if not data.x_thread:
        issues.append(ValidationIssue(
            field="x_thread",
            status="REJECTED",
            message="X/Twitter thread is empty.",
        ))

    return data, issues

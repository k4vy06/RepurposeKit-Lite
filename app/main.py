import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import get_db, init_db
from app.models import Generation, HashtagResult, CarouselResult, ReelResult, ContentIdeasBatch, WeeklyPlan
from app.schemas import GeneratedContent, GenerationResponse, ValidationIssue
from app.ai_service import (
    generate_content, IS_MOCK,
    generate_hashtags, generate_carousel, generate_reel_script,
    generate_content_ideas, generate_weekly_plan, generate_posting_times,
    optimize_hook_caption,
)
from app.validators import validate_content
from app.security import (
    SECRET_KEY,
    SECURITY_HEADERS,
    get_or_create_csrf_token,
    validate_csrf_token,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ── App setup ─────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="RepurposeKit AI", version="2.0.0", docs_url="/docs")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="rk_session",
    https_only=False,   # set True in production behind HTTPS
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.autoescape = True


@app.on_event("startup")
async def startup():
    init_db()


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    return response


# ── Existing Routes (PRESERVED) ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/generate", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def generate(
    request: Request,
    source_content: str = Form(...),
    tone: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(request, csrf_token)

    source_content = source_content.strip()
    errors = []
    if not source_content:
        errors.append("Source content cannot be empty.")
    if len(source_content) > 5000:
        errors.append("Source content exceeds 5,000 characters.")
    if tone not in ("professional", "casual", "witty"):
        errors.append("Invalid tone selected.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "csrf_token": new_csrf,
                "is_mock": IS_MOCK,
                "errors": errors,
                "source_content": source_content,
                "tone": tone,
            },
            status_code=422,
        )

    try:
        content, mock_used = await generate_content(source_content, tone)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "csrf_token": new_csrf,
                "is_mock": IS_MOCK,
                "errors": ["Content generation failed. Please try again."],
                "source_content": source_content,
                "tone": tone,
            },
            status_code=500,
        )

    validated_content, issues = validate_content(content)

    gen = Generation(
        source_content=source_content,
        tone=tone,
        title=validated_content.title,
        hashtags_json=json.dumps(validated_content.tags),
        linkedin=validated_content.linkedin,
        x_thread_json=json.dumps(validated_content.x_thread),
        instagram=validated_content.instagram,
        newsletter=validated_content.newsletter,
        created_at=datetime.utcnow(),
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "csrf_token": new_csrf,
            "gen": gen,
            "is_mock": mock_used,
            "issues": issues,
            "tone": tone,
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def history_list(request: Request, db: Session = Depends(get_db)):
    generations = db.query(Generation).order_by(Generation.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "history.html",
        {"generations": generations, "is_mock": IS_MOCK},
    )


@app.get("/history/{gen_id}", response_class=HTMLResponse)
async def history_detail(gen_id: int, request: Request, db: Session = Depends(get_db)):
    gen = db.query(Generation).filter(Generation.id == gen_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return templates.TemplateResponse(
        request,
        "history_detail.html",
        {"gen": gen, "is_mock": IS_MOCK},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "mock_mode": IS_MOCK}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    recent_gens = db.query(Generation).order_by(Generation.created_at.desc()).limit(5).all()
    total_gens = db.query(Generation).count()
    total_hashtags = db.query(HashtagResult).count()
    total_carousels = db.query(CarouselResult).count()
    total_reels = db.query(ReelResult).count()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "is_mock": IS_MOCK,
            "recent_gens": recent_gens,
            "total_gens": total_gens,
            "total_hashtags": total_hashtags,
            "total_carousels": total_carousels,
            "total_reels": total_reels,
        },
    )


# ── Hashtag Finder ────────────────────────────────────────────────────────────

@app.get("/hashtags", response_class=HTMLResponse)
async def hashtags_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "hashtags.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/hashtags", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def hashtags_post(
    request: Request,
    topic: str = Form(...),
    niche: str = Form(...),
    audience: str = Form(...),
    caption: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    topic = topic.strip()
    niche = niche.strip()
    audience = audience.strip()
    if not topic:
        errors.append("Topic is required.")
    if len(topic) > 500:
        errors.append("Topic exceeds 500 characters.")
    if not niche:
        errors.append("Niche is required.")
    if not audience:
        errors.append("Audience is required.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "hashtags.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "topic": topic, "niche": niche, "audience": audience, "caption": caption},
            status_code=422,
        )

    try:
        result, mock_used = await generate_hashtags(topic, niche, audience, caption)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "hashtags.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Hashtag generation failed. Please try again."],
             "topic": topic, "niche": niche, "audience": audience},
            status_code=500,
        )

    db_record = HashtagResult(
        topic=topic,
        niche=niche,
        audience=audience,
        hashtags_json=json.dumps({
            "caption_suggestion": result.caption_suggestion,
            "groups": [g.model_dump() for g in result.groups],
            "total_count": result.total_count,
        }),
        created_at=datetime.utcnow(),
    )
    db.add(db_record)
    db.commit()

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "hashtags_result.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "result": result,
         "topic": topic, "niche": niche, "audience": audience},
    )


# ── Carousel Studio ───────────────────────────────────────────────────────────

@app.get("/carousel", response_class=HTMLResponse)
async def carousel_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "carousel.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/carousel", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def carousel_post(
    request: Request,
    topic: str = Form(...),
    platform: str = Form(...),
    format_type: str = Form(...),
    slide_count: int = Form(...),
    audience: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    topic = topic.strip()
    audience = audience.strip()
    if not topic:
        errors.append("Topic is required.")
    if len(topic) > 500:
        errors.append("Topic exceeds 500 characters.")
    if platform not in ("Instagram", "LinkedIn", "TikTok", "Pinterest"):
        errors.append("Invalid platform selected.")
    if not 3 <= slide_count <= 15:
        errors.append("Slide count must be between 3 and 15.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "carousel.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "topic": topic, "platform": platform, "slide_count": slide_count, "audience": audience},
            status_code=422,
        )

    try:
        result, mock_used = await generate_carousel(topic, platform, format_type, slide_count, audience)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "carousel.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Carousel generation failed. Please try again."],
             "topic": topic, "platform": platform},
            status_code=500,
        )

    all_slides = [result.hook_slide] + result.content_slides + [result.cta_slide]
    db_record = CarouselResult(
        topic=topic,
        platform=platform,
        format_type=format_type,
        slide_count=len(all_slides),
        slides_json=json.dumps([s.model_dump() for s in all_slides]),
        created_at=datetime.utcnow(),
    )
    db.add(db_record)
    db.commit()

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "carousel_result.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "result": result,
         "all_slides": all_slides, "topic": topic, "platform": platform},
    )


# ── Reel Script Studio ────────────────────────────────────────────────────────

@app.get("/reels", response_class=HTMLResponse)
async def reels_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "reels.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/reels", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def reels_post(
    request: Request,
    topic: str = Form(...),
    platform: str = Form(...),
    duration: str = Form(...),
    style: str = Form(...),
    niche: str = Form(...),
    audience: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    topic = topic.strip()
    niche = niche.strip()
    audience = audience.strip()
    if not topic:
        errors.append("Topic is required.")
    if len(topic) > 500:
        errors.append("Topic exceeds 500 characters.")
    if not niche:
        errors.append("Niche is required.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "reels.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "topic": topic, "platform": platform, "niche": niche, "audience": audience},
            status_code=422,
        )

    try:
        result, mock_used = await generate_reel_script(topic, platform, duration, style, niche, audience)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "reels.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Reel script generation failed. Please try again."],
             "topic": topic, "platform": platform},
            status_code=500,
        )

    db_record = ReelResult(
        topic=topic,
        platform=platform,
        duration=duration,
        style=style,
        script_json=json.dumps({
            "hook": result.hook,
            "scenes": [s.model_dump() for s in result.scenes],
            "caption": result.caption,
            "hashtags": result.hashtags,
            "storyboard_summary": result.storyboard_summary,
        }),
        created_at=datetime.utcnow(),
    )
    db.add(db_record)
    db.commit()

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "reels_result.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "result": result,
         "topic": topic, "platform": platform, "duration": duration},
    )


# ── Content Idea Generator ────────────────────────────────────────────────────

@app.get("/ideas", response_class=HTMLResponse)
async def ideas_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "ideas.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/ideas", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def ideas_post(
    request: Request,
    niche: str = Form(...),
    platform: str = Form(...),
    goal: str = Form(...),
    audience: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    niche = niche.strip()
    audience = audience.strip()
    goal = goal.strip()
    if not niche:
        errors.append("Niche is required.")
    if len(niche) > 200:
        errors.append("Niche exceeds 200 characters.")
    if not audience:
        errors.append("Target audience is required.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "ideas.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "niche": niche, "platform": platform, "goal": goal, "audience": audience},
            status_code=422,
        )

    try:
        ideas, mock_used = await generate_content_ideas(niche, platform, goal, audience)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "ideas.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Idea generation failed. Please try again."],
             "niche": niche, "platform": platform},
            status_code=500,
        )

    db_record = ContentIdeasBatch(
        niche=niche,
        platform=platform,
        ideas_json=json.dumps([i.model_dump() for i in ideas]),
        created_at=datetime.utcnow(),
    )
    db.add(db_record)
    db.commit()

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "ideas_result.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "ideas": ideas,
         "niche": niche, "platform": platform, "goal": goal, "audience": audience},
    )


# ── Weekly Content Planner ────────────────────────────────────────────────────

@app.get("/planner", response_class=HTMLResponse)
async def planner_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "planner.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/planner", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def planner_post(
    request: Request,
    frequency: str = Form(...),
    platforms: List[str] = Form(...),
    objective: str = Form(...),
    niche: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    niche = niche.strip()
    objective = objective.strip()
    if not niche:
        errors.append("Niche is required.")
    if not objective:
        errors.append("Objective is required.")
    if frequency not in ("daily", "5x", "3x", "2x", "1x"):
        errors.append("Invalid frequency selected.")
    if not platforms:
        errors.append("At least one platform is required.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "planner.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "niche": niche, "objective": objective, "frequency": frequency},
            status_code=422,
        )

    try:
        plan_days, mock_used = await generate_weekly_plan(frequency, platforms, objective, niche)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "planner.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Planner generation failed. Please try again."],
             "niche": niche},
            status_code=500,
        )

    db_record = WeeklyPlan(
        frequency=frequency,
        objective=objective,
        platform=", ".join(platforms),
        plan_json=json.dumps([d.model_dump() for d in plan_days]),
        created_at=datetime.utcnow(),
    )
    db.add(db_record)
    db.commit()

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "planner_result.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "plan_days": plan_days,
         "niche": niche, "objective": objective, "frequency": frequency, "platforms": platforms},
    )


# ── Posting Time Advisor ──────────────────────────────────────────────────────

@app.get("/posting-times", response_class=HTMLResponse)
async def posting_times_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "posting_times.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/posting-times", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def posting_times_post(
    request: Request,
    platform: str = Form(...),
    content_type: str = Form(...),
    niche: str = Form(...),
    audience: str = Form(...),
    country: str = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    niche = niche.strip()
    audience = audience.strip()
    country = country.strip()
    if not niche:
        errors.append("Niche is required.")
    if not audience:
        errors.append("Audience is required.")
    if not country:
        errors.append("Country is required.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "posting_times.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "platform": platform, "niche": niche, "audience": audience, "country": country},
            status_code=422,
        )

    try:
        recommendation, mock_used = await generate_posting_times(platform, content_type, niche, audience, country)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "posting_times.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Failed to generate recommendations. Please try again."],
             "platform": platform, "niche": niche},
            status_code=500,
        )

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "posting_times.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "recommendation": recommendation,
         "platform": platform, "content_type": content_type, "niche": niche,
         "audience": audience, "country": country},
    )


# ── Ads Intelligence Lab ──────────────────────────────────────────────────────

@app.get("/ads", response_class=HTMLResponse)
async def ads_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "ads.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


# ── Hook / Caption Optimizer ──────────────────────────────────────────────────

@app.get("/optimizer", response_class=HTMLResponse)
async def optimizer_get(request: Request):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "optimizer.html",
        {"csrf_token": csrf_token, "is_mock": IS_MOCK},
    )


@app.post("/optimizer", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def optimizer_post(
    request: Request,
    text: str = Form(...),
    platform: str = Form(...),
    audience: str = Form(...),
    tone: str = Form(...),
    csrf_token: str = Form(...),
):
    validate_csrf_token(request, csrf_token)

    errors = []
    text = text.strip()
    audience = audience.strip()
    if not text:
        errors.append("Text to optimize is required.")
    if len(text) > 2000:
        errors.append("Text exceeds 2,000 characters.")
    if not audience:
        errors.append("Audience is required.")

    if errors:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "optimizer.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK, "errors": errors,
             "text": text, "platform": platform, "audience": audience, "tone": tone},
            status_code=422,
        )

    try:
        result, mock_used = await optimize_hook_caption(text, platform, audience, tone)
    except Exception:
        new_csrf = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "optimizer.html",
            {"csrf_token": new_csrf, "is_mock": IS_MOCK,
             "errors": ["Optimization failed. Please try again."],
             "text": text, "platform": platform},
            status_code=500,
        )

    new_csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "optimizer.html",
        {"csrf_token": new_csrf, "is_mock": mock_used, "result": result,
         "text": text, "platform": platform, "audience": audience, "tone": tone},
    )


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        request,
        "base.html",
        {
            "error_title": "404 Not Found",
            "error_message": str(exc.detail),
        },
        status_code=404,
    )


@app.exception_handler(403)
async def forbidden(request: Request, exc: HTTPException):
    return JSONResponse({"detail": str(exc.detail)}, status_code=403)

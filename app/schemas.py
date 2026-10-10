from typing import List, Optional
from pydantic import BaseModel, field_validator


class GenerateRequest(BaseModel):
    source_content: str
    tone: str
    csrf_token: str = ""

    @field_validator("source_content")
    @classmethod
    def validate_source(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Source content cannot be empty.")
        if len(v) > 5000:
            raise ValueError("Source content exceeds 5,000 characters.")
        return v

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v: str) -> str:
        allowed = {"professional", "casual", "witty"}
        if v.lower() not in allowed:
            raise ValueError(f"Tone must be one of: {', '.join(allowed)}")
        return v.lower()


class GeneratedContent(BaseModel):
    title: str
    tags: List[str]
    linkedin: str
    x_thread: List[str]
    instagram: str
    newsletter: str


class ValidationIssue(BaseModel):
    field: str
    status: str  # VALID | WARNING | REJECTED
    message: str


class GenerationResponse(BaseModel):
    id: int
    title: str
    tags: List[str]
    linkedin: str
    x_thread: List[str]
    instagram: str
    newsletter: str
    validation_issues: List[ValidationIssue] = []
    mock_mode: bool = False


# ── Hashtag Schemas ───────────────────────────────────────────────────────────

class HashtagGroup(BaseModel):
    label: str           # e.g. "High Volume", "Niche", "Trending"
    hashtags: List[str]
    tip: Optional[str] = None


class HashtagResult(BaseModel):
    topic: str
    caption_suggestion: str
    groups: List[HashtagGroup]
    total_count: int


# ── Carousel Schemas ──────────────────────────────────────────────────────────

class CarouselSlide(BaseModel):
    slide_number: int
    headline: str
    body: str
    cta: Optional[str] = None  # call to action on last slide


class CarouselResult(BaseModel):
    topic: str
    platform: str
    title: str
    hook_slide: CarouselSlide
    content_slides: List[CarouselSlide]
    cta_slide: CarouselSlide
    caption: str
    hashtags: List[str]


# ── Reel Script Schemas ───────────────────────────────────────────────────────

class ReelScene(BaseModel):
    scene_number: int
    timestamp: str           # e.g. "0:00 – 0:03"
    visual: str              # what to film/show
    script_line: str         # what to say
    broll: Optional[str] = None


class ReelScript(BaseModel):
    topic: str
    platform: str
    duration: str
    hook: str                # opening hook line
    scenes: List[ReelScene]
    caption: str
    hashtags: List[str]
    storyboard_summary: str


# ── Content Idea Schemas ──────────────────────────────────────────────────────

class ContentIdea(BaseModel):
    idea_number: int
    title: str
    format: str              # e.g. "Carousel", "Reel", "Thread"
    hook: str
    outline: str
    best_platform: str
    why_it_works: str


# ── Weekly Planner Schemas ────────────────────────────────────────────────────

class WeeklyPlanPost(BaseModel):
    platform: str
    content_type: str        # e.g. "Reel", "Carousel", "Text post"
    topic: str
    hook: str
    best_time: str


class WeeklyPlanDay(BaseModel):
    day: str                 # e.g. "Monday"
    theme: str
    posts: List[WeeklyPlanPost]


# ── Posting Time Schemas ──────────────────────────────────────────────────────

class PostingWindow(BaseModel):
    day: str
    time_range: str
    reason: str


class PostingTimeRecommendation(BaseModel):
    platform: str
    content_type: str
    top_windows: List[PostingWindow]
    frequency_advice: str
    timezone_note: str
    general_tip: str


# ── Hook/Caption Optimizer Schemas ────────────────────────────────────────────

class HookVariant(BaseModel):
    variant_number: int
    text: str
    why: str


class HookOptimization(BaseModel):
    original: str
    platform: str
    score_original: int      # 1–10
    variants: List[HookVariant]
    best_variant: int        # index into variants
    improvement_tips: List[str]


# ── Ads Campaign Schemas ──────────────────────────────────────────────────────

class AdVariant(BaseModel):
    variant: str             # "A", "B", "C"
    headline: str
    primary_text: str
    cta: str
    audience_note: str


class AdsCampaign(BaseModel):
    objective: str
    platform: str
    budget_note: str
    variants: List[AdVariant]
    targeting_tips: List[str]
    creative_notes: str

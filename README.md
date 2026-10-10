# RepurposeKit AI

**AI-powered Social Media Growth and Creator Intelligence Platform**

Built for IBM Bob Hack Day 2025 — IBM User Group Nagpur.

---

## What It Does

RepurposeKit AI turns one piece of content into platform-optimised posts for LinkedIn, X/Twitter, Instagram, and Newsletter — plus a full suite of AI creator tools:

| Tool | What it does |
|---|---|
| **Repurpose** | One input → LinkedIn, X thread, Instagram caption, Newsletter |
| **Hashtag Finder** | Grouped hashtag sets by volume and niche |
| **Carousel Studio** | Slide-by-slide carousel scripts |
| **Reel Script Studio** | Scene-by-scene reel scripts with hooks |
| **Content Ideas** | 8 tailored content ideas for your niche |
| **Hook Optimizer** | Score and rewrite hooks for maximum impact |
| **Weekly Planner** | Full week content calendar |
| **Posting Time Advisor** | Best times to post per platform and audience |
| **Ads Intelligence Lab** | Metrics calculator + platform benchmarks |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env file
copy .env.example .env

# 3. Run
uvicorn app.main:app --reload --port 8000
```

Open: http://localhost:8000

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock` or `openai` |
| `OPENAI_API_KEY` | — | Required for real AI mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `SECRET_KEY` | auto-generated | Session + CSRF secret |
| `DATABASE_URL` | `sqlite:///./repurposekit.db` | SQLite DB path |

---

## Running Tests

```bash
py -3.13 -m pytest tests/ -v
```

---

## Tech Stack

- **FastAPI** — Python web framework
- **Jinja2** — Server-side templates
- **SQLAlchemy + SQLite** — Database
- **OpenAI API** — AI generation (mock mode when no key)
- **slowapi** — Rate limiting
- **Starlette SessionMiddleware** — CSRF protection

---

## Security

- CSRF tokens on all POST endpoints
- Input validation and sanitisation
- Jinja2 autoescaping enabled
- Security headers on all responses
- Rate limiting (10 req/min per IP)
- SQL injection protection via SQLAlchemy ORM

---

*Hackathon prototype — not for production use.*

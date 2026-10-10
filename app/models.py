import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class Generation(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True, index=True)
    source_content = Column(Text, nullable=False)
    tone = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    hashtags_json = Column(Text, nullable=False)  # JSON array
    linkedin = Column(Text, nullable=False)
    x_thread_json = Column(Text, nullable=False)  # JSON array
    instagram = Column(Text, nullable=False)
    newsletter = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def hashtags(self):
        return json.loads(self.hashtags_json)

    @hashtags.setter
    def hashtags(self, value):
        self.hashtags_json = json.dumps(value)

    @property
    def x_thread(self):
        return json.loads(self.x_thread_json)

    @x_thread.setter
    def x_thread(self, value):
        self.x_thread_json = json.dumps(value)


class HashtagResult(Base):
    __tablename__ = "hashtag_results"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False)
    niche = Column(String(200), nullable=False)
    audience = Column(String(200), nullable=False)
    hashtags_json = Column(Text, nullable=False)  # JSON object with groups
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def hashtags_data(self):
        return json.loads(self.hashtags_json)


class CarouselResult(Base):
    __tablename__ = "carousel_results"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False)
    platform = Column(String(100), nullable=False)
    format_type = Column(String(100), nullable=False)
    slide_count = Column(Integer, nullable=False)
    slides_json = Column(Text, nullable=False)  # JSON array of slides
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def slides(self):
        return json.loads(self.slides_json)


class ReelResult(Base):
    __tablename__ = "reel_results"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False)
    platform = Column(String(100), nullable=False)
    duration = Column(String(50), nullable=False)
    style = Column(String(100), nullable=False)
    script_json = Column(Text, nullable=False)  # JSON object
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def script_data(self):
        return json.loads(self.script_json)


class ContentIdeasBatch(Base):
    __tablename__ = "content_ideas_batches"

    id = Column(Integer, primary_key=True, index=True)
    niche = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=False)
    ideas_json = Column(Text, nullable=False)  # JSON array of ideas
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def ideas(self):
        return json.loads(self.ideas_json)


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id = Column(Integer, primary_key=True, index=True)
    frequency = Column(String(50), nullable=False)
    objective = Column(String(500), nullable=False)
    platform = Column(String(200), nullable=False)
    plan_json = Column(Text, nullable=False)  # JSON array of days
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def plan(self):
        return json.loads(self.plan_json)

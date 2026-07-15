"""Database setup — sync SQLAlchemy ORM (compatible with installed packages)."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, ForeignKey,
    DateTime, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    cookies = relationship("Cookie", back_populates="user", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")


class Cookie(Base):
    __tablename__ = "cookies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cookie_json = Column(Text, nullable=False)
    nickname = Column(String(64))
    is_active = Column(Boolean, default=True)
    is_valid = Column(Boolean, default=None)
    validated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="cookies")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    profile_url = Column(String(256), nullable=False)
    xhs_user_id = Column(String(64))
    nickname = Column(String(128))
    follower_count = Column(Integer)
    bio = Column(String(512))
    avatar_url = Column(String(512))
    last_task_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    analysis_results = relationship("AnalysisResult", back_populates="account",
                                    cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    cookie_id = Column(Integer, ForeignKey("cookies.id"))
    task_type = Column(String(32), default="full_analysis")
    status = Column(String(16), default="pending")
    progress = Column(Integer, default=0)
    error_message = Column(Text)
    run_log = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="tasks")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    results_json = Column(Text, nullable=False)
    reports_dir = Column(String(256))
    note_count = Column(Integer)
    likes_total = Column(Integer)
    avg_likes = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="analysis_results")


class CompetitorComparison(Base):
    __tablename__ = "competitor_comparisons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    main_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    comp_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    comparison_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# Sync engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite needs this
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    """Sync DB session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

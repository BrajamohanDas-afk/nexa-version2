from datetime import datetime
import uuid
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from extensions import db


# ============================
# CATEGORIES
# ============================
class Category(db.Model):
    __tablename__ = "blog_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)

    posts = relationship(
        "BlogPost",
        back_populates="category"
    )

    def __repr__(self):
        return f"<Category {self.name}>"


# ============================
# BLOG POSTS (SEO CORE)
# ============================
class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True)

    # ===== CONTENT =====
    title = Column(String(255), nullable=False)
    slug = Column(String(300), unique=True, nullable=False)

    summary = Column(Text, nullable=False)       # Used for SEO + listings
    content = Column(Text, nullable=False)       # Full HTML / Markdown

    featured_image = Column(String(300))

    # ===== AUTHOR (TEXT ONLY) =====
    author_name = Column(String(120), nullable=False)

    # ===== SEO =====
    seo_title = Column(String(255))
    seo_description = Column(String(300))
    seo_keywords = Column(Text)            # comma-separated keyword list
    featured_image_alt = Column(String(255))

    # ===== RELATIONS =====
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("blog_categories.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ===== PUBLISHING =====
    is_published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, index=True)

    view_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    category = relationship("Category", back_populates="posts")

    __table_args__ = (
        Index("idx_blog_slug", "slug"),
        Index("idx_blog_published", "is_published", "published_at"),
    )

    def __repr__(self):
        return f"<BlogPost {self.title}>"

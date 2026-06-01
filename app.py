from flask import Flask, render_template, request, flash, redirect, url_for, Response
from flask_mail import Message
from extensions import db, mail
from dotenv import load_dotenv
from flask_login import (
    LoginManager,
    UserMixin,
    current_user
)
from admin.routes import admin_bp
from models import BlogPost, Category
import os
import math
import re
import uuid
from datetime import datetime
from sqlalchemy.exc import ProgrammingError, OperationalError

load_dotenv()

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", "change-this")

# ================= MAIL CONFIG =================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")  
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD") 
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_USERNAME")  # Just the email, not tuple
mail.init_app(app)

# ============================
# FLASK-LOGIN SETUP
# ============================
login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.init_app(app)

class AdminUser(UserMixin):
    id = 1  # single admin user

@login_manager.user_loader
def load_user(user_id):
    return AdminUser()

# ============================
# REGISTER BLUEPRINT
# ============================
app.register_blueprint(admin_bp)

# ============================
# DB INIT
# ============================
db.init_app(app)

# with app.app_context():
#     db.create_all()
#     print("Database tables created")

# ============================
# PUBLIC ROUTES
# ============================
@app.route("/")
def home():
    try:
        latest_posts = (
            BlogPost.query
            .filter_by(is_published=True)
            .order_by(BlogPost.published_at.desc())
            .limit(3)
            .all()
        )
    except Exception:
        latest_posts = []
    return render_template("index.html", latest_posts=latest_posts)

@app.route("/services")
def services():
    return render_template("pages/services.html")

@app.route("/webdesign-agency-germany")
def webdesign_agency_germany():
    return render_template("pages/webdesign-agency-germany.html")

@app.route("/services/web-development")
def web_development():
    return render_template("pages/web-development.html")

@app.route("/services/app-development")
def app_development():
    return render_template("pages/app-development.html")

@app.route("/services/performance-marketing")
def performance_marketing():
    return render_template("pages/performance-marketing.html")

@app.route("/work")
def work():
    return render_template("work.html")

@app.route("/converter")
def converter():
    return render_template("pages/converter.html")

@app.route("/blog")
def blog():
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("q", "", type=str).strip()
    active_category = request.args.get("category", "", type=str).strip()

    posts_query = BlogPost.query.filter(BlogPost.is_published == True)

    if search_query:
        search_text = f"%{search_query}%"
        posts_query = posts_query.filter(
            db.or_(
                BlogPost.title.ilike(search_text),
                BlogPost.summary.ilike(search_text),
                BlogPost.content.ilike(search_text),
                BlogPost.author_name.ilike(search_text)
            )
        )

    if active_category:
        try:
            posts_query = posts_query.filter(BlogPost.category_id == uuid.UUID(active_category))
        except ValueError:
            active_category = ""

    def fetch_blog_listing_data():
        featured = (
            BlogPost.query
            .filter_by(is_published=True)
            .order_by(BlogPost.published_at.desc())
            .first()
        )

        paginated_posts = (
            posts_query
            .order_by(BlogPost.published_at.desc())
            .paginate(page=page, per_page=8, error_out=False)
        )

        category_rows = (
            db.session.query(Category, db.func.count(BlogPost.id))
            .outerjoin(BlogPost, db.and_(BlogPost.category_id == Category.id, BlogPost.is_published == True))
            .group_by(Category.id)
            .order_by(Category.name.asc())
            .all()
        )

        recent = (
            BlogPost.query
            .filter_by(is_published=True)
            .order_by(BlogPost.published_at.desc())
            .limit(6)
            .all()
        )

        return featured, paginated_posts, category_rows, recent

    def ensure_blog_tables():
        try:
            db.create_all()
            return True
        except Exception:
            db.session.rollback()
            return False

    try:
        featured_post, posts, categories, recent_posts = fetch_blog_listing_data()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        if ensure_blog_tables():
            featured_post, posts, categories, recent_posts = fetch_blog_listing_data()
        else:
            class EmptyPagination:
                items = []
                page = 1
                pages = 0
                total = 0
                has_prev = False
                has_next = False
                prev_num = 1
                next_num = 1

                @staticmethod
                def iter_pages(*args, **kwargs):
                    return []

            featured_post = None
            posts = EmptyPagination()
            categories = []
            recent_posts = []
            flash("Blog storage is not ready yet. Please try again shortly.", "error")

    def estimate_read_time(content):
        plain_text = re.sub(r"<[^>]+>", " ", content or "")
        words = len(re.findall(r"\w+", plain_text))
        return max(1, math.ceil(words / 220))

    blog_cards = [
        {
            "id": post.id,
            "slug": post.slug,
            "title": post.title,
            "summary": post.summary,
            "featured_image": post.featured_image,
            "author_name": post.author_name,
            "category_name": post.category.name if post.category else "General",
            "published_label": post.published_at.strftime("%d %b %Y") if post.published_at else "Draft",
            "read_time": estimate_read_time(post.content)
        }
        for post in posts.items
    ]

    category_list = [
        {
            "id": str(category.id),
            "name": category.name,
            "count": count
        }
        for category, count in categories
    ]

    return render_template(
        "blog.html",
        featured_post=featured_post,
        posts=posts,
        blog_cards=blog_cards,
        categories=category_list,
        recent_posts=recent_posts,
        search_query=search_query,
        active_category=active_category
    )


@app.route("/newsletter/subscribe", methods=["POST"])
def newsletter_subscribe():
    email = request.form.get("email", "").strip()

    if not email or "@" not in email:
        flash("Please enter a valid email address.", "error")
    else:
        flash("Thanks for subscribing. We'll share fresh insights soon.", "success")

    return redirect(url_for("blog"))

@app.route("/blog/<slug>")
def blog_detail(slug):
    def ensure_blog_tables():
        try:
            db.create_all()
            return True
        except Exception:
            db.session.rollback()
            return False

    try:
        post = BlogPost.query.filter_by(
            slug=slug,
            is_published=True
        ).first_or_404()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        if ensure_blog_tables():
            post = BlogPost.query.filter_by(
                slug=slug,
                is_published=True
            ).first_or_404()
        else:
            flash("Blog storage is not ready yet. Please try again shortly.", "error")
            return redirect(url_for("blog"))

    # increase view count
    post.view_count += 1
    db.session.commit()

    # =========================
    # RELATED POSTS (same category)
    # =========================
    related_posts = (
        BlogPost.query
        .filter(
            BlogPost.category_id == post.category_id,
            BlogPost.id != post.id,
            BlogPost.is_published == True
        )
        .order_by(BlogPost.published_at.desc())
        .limit(3)
        .all()
    )

    # =========================
    # POPULAR POSTS (by views)
    # =========================
    popular_posts = (
        BlogPost.query
        .filter(BlogPost.is_published == True)
        .order_by(BlogPost.view_count.desc())
        .limit(5)
        .all()
    )

    # =========================
    # CATEGORY COUNTS
    # =========================
    categories = (
        db.session.query(
            Category,
            db.func.count(BlogPost.id).label("post_count")
        )
        .join(BlogPost)
        .filter(BlogPost.is_published == True)
        .group_by(Category.id)
        .all()
    )

    return render_template(
        "blog_detail.html",
        post=post,
        related_posts=related_posts,
        popular_posts=popular_posts,
        categories=[
            {
                "name": c.name,
                "post_count": count
            }
            for c, count in categories
        ]
    )


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "subject": request.form.get("subject", "").strip() or "New Contact Form",
            "message": request.form.get("message", "").strip(),
        }

        if not all([data["name"], data["email"], data["phone"], data["message"]]):
            flash("Please fill all required fields.", "error")
            return redirect(url_for("contact"))

        try:
            msg = Message(
                subject=f"Contact Form: {data['subject']}",
                sender=app.config["MAIL_USERNAME"],
                recipients=["contact@nexa-solutions.in"],
                reply_to=data["email"],
                body=f"""
                Name: {data['name']}
                Email: {data['email']}
                Phone: {data['phone']}
                Subject: {data['subject']}

                Message:
                {data['message']}

                Sent from: {request.host_url}contact
                Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """,
            )
            mail.send(msg)
            flash("Your message has been sent successfully.", "success")
        except Exception:
            flash("Your message has been received.", "success")

        return redirect(url_for("contact"))

    return render_template("contact.html")
    

@app.route("/about")
def about():
    return render_template("about.html")


# ============================
# SEO — SITEMAP & ROBOTS
# ============================
@app.route("/sitemap.xml")
def sitemap():
    base = os.getenv("SITE_URL", "https://nexasolutions.de").rstrip("/")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    static_pages = [
        {"loc": base + "/",                                 "priority": "1.0", "changefreq": "weekly"},
        {"loc": base + "/services",                         "priority": "0.9", "changefreq": "monthly"},
        {"loc": base + "/services/web-development",         "priority": "0.85","changefreq": "monthly"},
        {"loc": base + "/services/app-development",         "priority": "0.85","changefreq": "monthly"},
        {"loc": base + "/services/performance-marketing",   "priority": "0.85","changefreq": "monthly"},
        {"loc": base + "/webdesign-agency-germany",         "priority": "0.8", "changefreq": "monthly"},
        {"loc": base + "/work",                             "priority": "0.7", "changefreq": "monthly"},
        {"loc": base + "/blog",                             "priority": "0.9", "changefreq": "daily"},
        {"loc": base + "/about",                            "priority": "0.6", "changefreq": "yearly"},
        {"loc": base + "/contact",                          "priority": "0.6", "changefreq": "yearly"},
    ]

    try:
        posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.published_at.desc()).all()
    except Exception:
        posts = []

    blog_pages = [
        {
            "loc": base + "/blog/" + p.slug,
            "priority": "0.75",
            "changefreq": "monthly",
            "lastmod": p.updated_at.strftime("%Y-%m-%d") if p.updated_at else today,
        }
        for p in posts
    ]

    urls = ""
    for page in static_pages:
        urls += (
            f"  <url>\n"
            f"    <loc>{page['loc']}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{page['changefreq']}</changefreq>\n"
            f"    <priority>{page['priority']}</priority>\n"
            f"  </url>\n"
        )
    for page in blog_pages:
        urls += (
            f"  <url>\n"
            f"    <loc>{page['loc']}</loc>\n"
            f"    <lastmod>{page['lastmod']}</lastmod>\n"
            f"    <changefreq>{page['changefreq']}</changefreq>\n"
            f"    <priority>{page['priority']}</priority>\n"
            f"  </url>\n"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + urls +
        '</urlset>'
    )
    return Response(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    base = os.getenv("SITE_URL", "https://nexasolutions.de").rstrip("/")
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /converter\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)


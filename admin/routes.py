from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required
from models import BlogPost, Category, upload_blog_image
from .forms import BlogForm
from .utils import generate_unique_slug
import re
import os
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ============================
# LOGIN
# ============================
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form["username"] == os.getenv("ADMIN_USERNAME")
            and request.form["password"] == os.getenv("ADMIN_PASSWORD")
        ):
            from app import AdminUser
            login_user(AdminUser())
            return redirect(url_for("admin.dashboard"))

        flash("Invalid credentials", "error")

    return render_template("admin/login.html")

# ============================
# LOGOUT
# ============================
@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("blog"))

# ============================
# DASHBOARD
# ============================
@admin_bp.route("/")
@login_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        blog_count=BlogPost.query.count(),
        category_count=Category.query.count()
    )

# ============================
# BLOG LIST
# ============================
@admin_bp.route("/blogs")
@login_required
def blog_list():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template("admin/blog_list.html", blogs=posts)

# ============================
# CREATE BLOG 
# ============================
@admin_bp.route("/blogs/new", methods=["GET", "POST"])
@login_required
def create_blog():
    form = BlogForm()
    # Populate category choices
    form.category_id.choices = [
        (str(c.id), c.name) for c in Category.query.order_by(Category.name).all()
    ]

    if form.validate_on_submit():
        content = request.form.get('content', '').strip()
        # Strip all HTML tags and check there is actual visible text
        if not re.sub(r'<[^>]+>', '', content).strip():
            flash("Blog content cannot be empty.", "error")
            return render_template("admin/blog_form.html", form=form, is_edit=False)

        # Handle Image Upload
        image_url = None
        if form.featured_image.data:
            image_url = upload_blog_image(form.featured_image.data)

        # Create the new record
        post = BlogPost(
            title=form.title.data,
            slug=generate_unique_slug(form.title.data),
            summary=form.summary.data,
            content=content,
            author_name=form.author_name.data,
            category_id=form.category_id.data,
            featured_image=image_url,
            is_published=form.is_published.data,
            published_at=db.func.now() if form.is_published.data else None,
        )

        try:
            db.session.add(post)
            db.session.commit()
            flash("Blog created successfully!", "success")
            return redirect(url_for("admin.blog_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Database Error: {str(e)}", "error")

    else:
        print("VALIDATION FAILED!")
        print(form.errors)

    
    return render_template("admin/blog_form.html", form=form, is_edit=False)

# ============================
# EDIT BLOG
# ============================
@admin_bp.route("/blogs/<int:blog_id>/edit", methods=["GET", "POST"])
@login_required
def edit_blog(blog_id):
    post = BlogPost.query.get_or_404(blog_id)
    form = BlogForm(obj=post)

    form.category_id.choices = [
        (c.id, c.name) for c in Category.query.order_by(Category.name).all()
    ]

    if form.validate_on_submit():
        content = request.form.get('content', '').strip()
        if not re.sub(r'<[^>]+>', '', content).strip():
            flash("Blog content cannot be empty.", "error")
            return render_template("admin/blog_form.html", form=form, is_edit=True)

        post.title = form.title.data
        post.slug = generate_unique_slug(form.slug.data, post_id=post.id)
        post.summary = form.summary.data
        post.content = content
        post.author_name = form.author_name.data
        post.category_id = form.category_id.data
        post.is_published = form.is_published.data

        if form.is_published.data and not post.published_at:
            post.published_at = db.func.now()

        if form.featured_image.data:
            post.featured_image = upload_blog_image(form.featured_image.data)

        db.session.commit()
        flash("Blog updated", "success")
        return redirect(url_for("admin.blog_list"))

    return render_template("admin/blog_form.html", form=form, is_edit=True)

# ============================
# DELETE BLOG
# ============================
@admin_bp.route("/blogs/<int:blog_id>/delete", methods=["POST"])
@login_required
def delete_blog(blog_id):
    blog = BlogPost.query.get_or_404(blog_id)
    db.session.delete(blog)
    db.session.commit()
    flash("Blog deleted", "success")
    return redirect(url_for("admin.blog_list"))

@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
def manage_categories():
    if request.method == "POST":
        name = request.form.get("name")

        if not name:
            flash("Category name required", "error")
            return redirect(url_for("admin.manage_categories"))

        category = Category(name=name)
        db.session.add(category)
        db.session.commit()

        flash("Category added", "success")
        return redirect(url_for("admin.manage_categories"))

    categories = Category.query.all()
    return render_template("admin/categories.html", categories=categories)

@admin_bp.route("/categories/<uuid:id>/delete", methods=["POST"])
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)

    if category.posts:
        flash("Cannot delete category with blogs", "error")
        return redirect(url_for("admin.manage_categories"))

    db.session.delete(category)
    db.session.commit()

    flash("Category deleted", "success")
    return redirect(url_for("admin.manage_categories"))

# ============================
# QUILL IMAGE UPLOAD (AJAX)
# ============================
@admin_bp.route("/upload-image", methods=["POST"])
@login_required
def upload_image():
    """Upload an image from the Quill editor to Cloudinary."""
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No image provided"}), 400

    try:
        url = upload_blog_image(file)
        return jsonify({"url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


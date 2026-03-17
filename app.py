import os
import re
import json
import uuid
import math
import logging
from datetime import datetime, timedelta
from functools import wraps
from collections import Counter, defaultdict

from dotenv import load_dotenv
from openai import OpenAI
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from fpdf import FPDF

# -------------------------------------------------
# Load environment & OpenAI client
# -------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY not set. AI features will not work.")
client = OpenAI(api_key=OPENAI_API_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "eduvoxus-secret-key-2024")

# Database: Use DATABASE_URL env var for production (PostgreSQL), fallback to SQLite for local dev
database_url = os.getenv("DATABASE_URL", "sqlite:///eduvox.db")
# Render/Heroku use "postgres://" but SQLAlchemy 2.x requires "postgresql://"
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,  # Verify connections before use (handles DB restarts)
}
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'notes'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'certificates'), exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# -------------------------------------------------
# APPROVAL CHECK MIDDLEWARE
# -------------------------------------------------
@app.before_request
def check_user_approval():
    """Block pending/rejected users from accessing any protected route."""
    # Allow unauthenticated routes and static files
    open_endpoints = {'login', 'register', 'setup_admin', 'logout', 'static', 'home'}
    if request.endpoint in open_endpoints or request.endpoint is None:
        return None
    if current_user.is_authenticated:
        status = getattr(current_user, 'status', 'approved')
        if status == 'pending':
            logout_user()
            flash("Your approval is pending. Please contact the administrator for more information.", "warning")
            return redirect("/login")
        elif status == 'rejected':
            logout_user()
            flash("Your registration was rejected. Please contact the administrator.", "error")
            return redirect("/login")
    return None


# -------------------------------------------------
# SECURITY HEADERS
# -------------------------------------------------
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
    return response


ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'png', 'jpg', 'jpeg'}
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_topic(topic):
    """Sanitize topic input to prevent prompt injection."""
    if not topic or not isinstance(topic, str):
        return "General"
    topic = topic.strip()[:100]
    topic = re.sub(r'[^\w\s\-\+\#\.\,]', '', topic)
    return topic if topic else "General"


def validate_password(password):
    """Check password meets minimum requirements."""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    return True, ""


def validate_email(email):
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# Simple in-memory rate limiter
_rate_limit_store = {}
_rate_limit_last_cleanup = datetime.utcnow()

def check_rate_limit(key, max_requests=10, window_seconds=60):
    """Returns True if request is allowed, False if rate limited."""
    global _rate_limit_last_cleanup
    now = datetime.utcnow()

    # Periodic cleanup: remove stale keys every 5 minutes to prevent memory leak
    if (now - _rate_limit_last_cleanup).total_seconds() > 300:
        stale_keys = [k for k, v in _rate_limit_store.items() if not v or (now - v[-1]).total_seconds() > window_seconds]
        for k in stale_keys:
            del _rate_limit_store[k]
        _rate_limit_last_cleanup = now

    if key not in _rate_limit_store:
        _rate_limit_store[key] = []
    # Clean old entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if (now - t).total_seconds() < window_seconds]
    if len(_rate_limit_store[key]) >= max_requests:
        return False
    _rate_limit_store[key].append(now)
    return True

# =================================================================
# DATABASE MODELS
# =================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, index=True)
    password = db.Column(db.String(200))
    plain_password = db.Column(db.String(200), nullable=True)  # Plain text for admin reference
    role = db.Column(db.String(20), default='student')  # student, teacher, admin
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    points = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('InterviewResult', backref='user', lazy=True, cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    forum_posts = db.relationship('ForumPost', backref='author', lazy=True, cascade='all, delete-orphan')
    forum_replies = db.relationship('ForumReply', backref='author', lazy=True, cascade='all, delete-orphan')
    badges = db.relationship('Badge', backref='user', lazy=True, cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', backref='user', lazy=True, cascade='all, delete-orphan')
    flashcard_decks = db.relationship('FlashcardDeck', backref='user', lazy=True, cascade='all, delete-orphan')
    study_notes = db.relationship('StudyNote', backref='user', lazy=True, cascade='all, delete-orphan')


class InterviewResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    topic = db.Column(db.String(100), index=True)
    score = db.Column(db.Integer)
    mode = db.Column(db.String(20), default='voice')  # quiz, voice, theory, timed_quiz
    difficulty = db.Column(db.String(20), default='medium')
    date = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    materials = db.relationship('StudyMaterial', backref='course', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', backref='courses_created')


class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), index=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    file_type = db.Column(db.String(10))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.relationship('User', backref='uploaded_materials')


class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    message = db.Column(db.Text)
    response = db.Column(db.Text)
    topic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    topic = db.Column(db.String(100), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replies = db.relationship('ForumReply', backref='post', lazy=True, order_by='ForumReply.created_at', cascade='all, delete-orphan')


class ForumReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id', ondelete='CASCADE'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    content = db.Column(db.Text)
    is_ai = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50))
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    subject = db.Column(db.String(100))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    question = db.Column(db.Text)
    answer = db.Column(db.Text, nullable=True)
    topic = db.Column(db.String(100), index=True)
    source = db.Column(db.String(20))  # quiz, theory, voice, flashcard
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FlashcardDeck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    title = db.Column(db.String(200))
    topic = db.Column(db.String(100), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cards = db.relationship('Flashcard', backref='deck', lazy=True, cascade='all, delete-orphan')


class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.Integer, db.ForeignKey('flashcard_deck.id', ondelete='CASCADE'), index=True)
    front = db.Column(db.Text)
    back = db.Column(db.Text)
    difficulty = db.Column(db.Integer, default=0)  # 0=new, 1=easy, 2=medium, 3=hard
    easiness_factor = db.Column(db.Float, default=2.5)  # SM-2 E-Factor
    interval = db.Column(db.Integer, default=0)  # SM-2 interval in days
    next_review = db.Column(db.DateTime, default=datetime.utcnow)
    review_count = db.Column(db.Integer, default=0)


class StudyNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), index=True)
    topic = db.Column(db.String(200))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------------------------------
# ADMIN DECORATOR
# -------------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function



# -------------------------------------------------
# GAMIFICATION HELPERS
# -------------------------------------------------
def award_points(user, points, reason=""):
    user.points = (user.points or 0) + points
    # NOTE: caller is responsible for db.session.commit()


def check_and_award_badges(user):
    existing = [b.name for b in user.badges]
    results = InterviewResult.query.filter_by(user_id=user.id).all()

    badge_rules = [
        {"name": "First Step", "desc": "Completed first practice session", "icon": "fa-shoe-prints", "cond": len(results) >= 1},
        {"name": "Dedicated Learner", "desc": "Completed 10 practice sessions", "icon": "fa-book-reader", "cond": len(results) >= 10},
        {"name": "Quiz Master", "desc": "Completed 25 practice sessions", "icon": "fa-crown", "cond": len(results) >= 25},
        {"name": "Perfect Score", "desc": "Scored 10/10 in a session", "icon": "fa-star", "cond": any(r.score == 10 for r in results)},
        {"name": "Consistent", "desc": "Maintained a 5-day streak", "icon": "fa-fire", "cond": (user.streak or 0) >= 5},
        {"name": "Century Club", "desc": "Earned 100 points", "icon": "fa-medal", "cond": (user.points or 0) >= 100},
        {"name": "Half Millennium", "desc": "Earned 500 points", "icon": "fa-trophy", "cond": (user.points or 0) >= 500},
    ]

    for rule in badge_rules:
        if rule["name"] not in existing and rule["cond"]:
            badge = Badge(
                user_id=user.id,
                name=rule["name"],
                description=rule["desc"],
                icon=rule["icon"]
            )
            db.session.add(badge)

    db.session.commit()


def update_streak(user):
    today = datetime.utcnow().date()
    last = user.last_active.date() if user.last_active else None

    if last == today:
        return
    elif last == today - timedelta(days=1):
        user.streak = (user.streak or 0) + 1
    else:
        user.streak = 1

    user.last_active = datetime.utcnow()
    db.session.commit()


# -------------------------------------------------
# AI HELPER FUNCTIONS
# -------------------------------------------------
def generate_theory_questions(topic, count, difficulty):
    if difficulty == "easy":
        level_instruction = "Generate basic definition-level and introductory questions."
    elif difficulty == "medium":
        level_instruction = "Generate conceptual and practical understanding questions."
    else:
        level_instruction = "Generate advanced, scenario-based, deep technical interview questions."

    prompt = f"""
    Generate EXACTLY {count} interview questions on "{topic}".

    Difficulty Level: {difficulty.upper()}

    Instructions:
    - {level_instruction}
    - Do NOT include answers
    - Do NOT add numbering
    - Each question on a new line
    """

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        raw_text = response.choices[0].message.content
        questions = [
            q.strip("-\u2022 ").strip()
            for q in raw_text.split("\n")
            if q.strip()
        ]
        return questions[:count]
    except Exception as e:
        logging.error(f"Failed to generate theory questions: {e}")
        return [f"Failed to generate questions on {topic}. Please try again."]


def get_adaptive_difficulty(user_id, topic):
    """
    Adaptive Difficulty using Exponential Weighted Moving Average (EWMA).
    Unlike simple averaging, EWMA gives more weight to recent scores,
    so the system reacts faster to improvement or decline.

    Formula: EWMA_t = alpha * score_t + (1 - alpha) * EWMA_{t-1}
    Alpha = 0.4 (decay factor - higher = more weight on recent)
    """
    results = InterviewResult.query.filter_by(
        user_id=user_id, topic=topic
    ).order_by(InterviewResult.date.asc()).limit(10).all()

    if not results:
        return "medium"

    alpha = 0.4  # Smoothing factor
    ewma = results[0].score
    for r in results[1:]:
        ewma = alpha * r.score + (1 - alpha) * ewma

    # Also factor in score variance (consistency measure)
    scores = [r.score for r in results]
    variance = sum((s - ewma) ** 2 for s in scores) / len(scores)
    consistency_bonus = -0.5 if variance > 4 else 0.5 if variance < 1 else 0

    adjusted_score = ewma + consistency_bonus

    if adjusted_score >= 7.5:
        return "hard"
    elif adjusted_score >= 4.5:
        return "medium"
    return "easy"


def get_weak_topics(user_id):
    """Identify topics where the user scores below average."""
    results = InterviewResult.query.filter_by(user_id=user_id).all()
    if not results:
        return []

    topic_scores = {}
    for r in results:
        if r.topic not in topic_scores:
            topic_scores[r.topic] = []
        topic_scores[r.topic].append(r.score)

    weak = []
    for topic, scores in topic_scores.items():
        avg = sum(scores) / len(scores)
        if avg < 6:
            weak.append({"topic": topic, "avg_score": round(avg, 1), "attempts": len(scores)})

    return sorted(weak, key=lambda x: x["avg_score"])


# -------------------------------------------------
# ML ALGORITHM 1: TF-IDF + COSINE SIMILARITY
# Topic Recommendation Engine
# -------------------------------------------------
def compute_tfidf(documents):
    """
    Compute TF-IDF vectors from scratch (no sklearn dependency).
    TF(t,d) = (count of t in d) / (total terms in d)
    IDF(t) = log(N / (1 + df(t)))  where df = docs containing t
    """
    N = len(documents)
    if N == 0:
        return [], {}

    # Tokenize: lowercase, split on non-alphanumeric
    tokenized = []
    for doc in documents:
        tokens = re.findall(r'[a-z0-9]+', doc.lower())
        tokenized.append(tokens)

    # Build vocabulary
    vocab = sorted(set(tok for tokens in tokenized for tok in tokens))
    vocab_index = {word: i for i, word in enumerate(vocab)}

    # Document frequency
    df = Counter()
    for tokens in tokenized:
        unique_tokens = set(tokens)
        for tok in unique_tokens:
            df[tok] += 1

    # Compute TF-IDF matrix (list of vectors)
    tfidf_matrix = []
    for tokens in tokenized:
        tf_counts = Counter(tokens)
        total = len(tokens) if tokens else 1
        vector = [0.0] * len(vocab)
        for tok, count in tf_counts.items():
            if tok in vocab_index:
                tf = count / total
                idf = math.log(N / (1 + df[tok]))
                vector[vocab_index[tok]] = tf * idf
        tfidf_matrix.append(vector)

    return tfidf_matrix, vocab_index


def cosine_similarity_vec(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def get_similar_topics(user_id, top_n=5):
    """
    TF-IDF + Cosine Similarity based topic recommender.
    Finds topics studied by other users that are most similar
    to what the current user has studied, then recommends new ones.
    """
    all_results = InterviewResult.query.all()
    if not all_results:
        return []

    # Build per-user "documents" (concatenated topic strings)
    user_topics = defaultdict(list)
    for r in all_results:
        user_topics[r.user_id].append(r.topic)

    if user_id not in user_topics:
        return []

    current_user_topics = set(user_topics[user_id])
    current_user_doc = " ".join(user_topics[user_id])

    # Build document corpus: current user + all other users
    user_ids = [user_id] + [uid for uid in user_topics if uid != user_id]
    documents = [" ".join(user_topics[uid]) for uid in user_ids]

    if len(documents) < 2:
        return []

    tfidf_matrix, _ = compute_tfidf(documents)

    # Find most similar users via cosine similarity
    similarities = []
    for i in range(1, len(user_ids)):
        sim = cosine_similarity_vec(tfidf_matrix[0], tfidf_matrix[i])
        similarities.append((user_ids[i], sim))

    similarities.sort(key=lambda x: x[1], reverse=True)

    # Recommend topics from similar users that current user hasn't tried
    recommended = []
    seen = set()
    for other_uid, sim in similarities[:10]:
        if sim < 0.05:
            break
        for topic in user_topics[other_uid]:
            if topic not in current_user_topics and topic not in seen:
                recommended.append({"topic": topic, "similarity_score": round(sim, 3)})
                seen.add(topic)
                if len(recommended) >= top_n:
                    return recommended

    return recommended


# -------------------------------------------------
# ML ALGORITHM 2: LINEAR REGRESSION
# Score Trend Prediction
# -------------------------------------------------
def linear_regression_predict(user_id, topic=None):
    """
    Simple Linear Regression using Ordinary Least Squares (OLS).
    Predicts the user's next score based on their historical trend.

    Model: score = beta_0 + beta_1 * session_number
    beta_1 = sum((x - x_mean)(y - y_mean)) / sum((x - x_mean)^2)
    beta_0 = y_mean - beta_1 * x_mean
    """
    query = InterviewResult.query.filter_by(user_id=user_id)
    if topic:
        query = query.filter_by(topic=topic)
    results = query.order_by(InterviewResult.date.asc()).all()

    if len(results) < 3:
        return None  # Not enough data for meaningful regression

    n = len(results)
    x_values = list(range(1, n + 1))  # Session numbers
    y_values = [r.score for r in results]

    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n

    # Calculate beta_1 (slope)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    if denominator == 0:
        return {"predicted_next_score": round(y_mean, 1), "trend": "stable", "r_squared": 0}

    beta_1 = numerator / denominator
    beta_0 = y_mean - beta_1 * x_mean

    # Predict next session score
    next_x = n + 1
    predicted = beta_0 + beta_1 * next_x
    predicted = max(0, min(10, predicted))  # Clamp to 0-10

    # Calculate R-squared (goodness of fit)
    ss_res = sum((y - (beta_0 + beta_1 * x)) ** 2 for x, y in zip(x_values, y_values))
    ss_tot = sum((y - y_mean) ** 2 for y in y_values)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    # Determine trend direction
    if beta_1 > 0.2:
        trend = "improving"
    elif beta_1 < -0.2:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "predicted_next_score": round(predicted, 1),
        "trend": trend,
        "slope": round(beta_1, 3),
        "r_squared": round(max(0, r_squared), 3),
        "sessions_analyzed": n
    }


# -------------------------------------------------
# ML ALGORITHM 3: K-MEANS CLUSTERING
# Learner Performance Classification
# -------------------------------------------------
def kmeans_cluster(data_points, k=3, max_iterations=100):
    """
    K-Means clustering from scratch.
    Classifies learners into performance tiers based on
    average score and consistency (inverse variance).

    Features: [normalized_avg_score, normalized_consistency]
    """
    import random

    if len(data_points) < k:
        return None

    dim = len(data_points[0])

    # Initialize centroids using K-Means++ for better convergence
    centroids = [list(data_points[random.randint(0, len(data_points) - 1)])]
    for _ in range(1, k):
        distances = []
        for point in data_points:
            min_dist = min(
                sum((p - c) ** 2 for p, c in zip(point, centroid))
                for centroid in centroids
            )
            distances.append(min_dist)
        total = sum(distances)
        if total == 0:
            centroids.append(list(data_points[random.randint(0, len(data_points) - 1)]))
            continue
        probs = [d / total for d in distances]
        cumulative = 0
        r = random.random()
        for i, p in enumerate(probs):
            cumulative += p
            if cumulative >= r:
                centroids.append(list(data_points[i]))
                break

    # Iterate
    assignments = [0] * len(data_points)
    for iteration in range(max_iterations):
        # Assign points to nearest centroid
        new_assignments = []
        for point in data_points:
            dists = [
                sum((p - c) ** 2 for p, c in zip(point, centroid))
                for centroid in centroids
            ]
            new_assignments.append(dists.index(min(dists)))

        if new_assignments == assignments:
            break  # Converged
        assignments = new_assignments

        # Update centroids
        for j in range(k):
            cluster_points = [data_points[i] for i in range(len(data_points)) if assignments[i] == j]
            if cluster_points:
                centroids[j] = [
                    sum(p[d] for p in cluster_points) / len(cluster_points)
                    for d in range(dim)
                ]

    return assignments, centroids


def classify_learners():
    """
    Uses K-Means to cluster all learners into 3 tiers:
    - Tier 1 (Advanced): High scores, high consistency
    - Tier 2 (Intermediate): Medium scores or inconsistent
    - Tier 3 (Beginner): Low scores, needs improvement

    Features: avg_score (0-10), consistency (0-1 where 1=very consistent)
    """
    users = User.query.filter_by(role='student').all()
    user_features = []
    user_ids = []

    for user in users:
        results = InterviewResult.query.filter_by(user_id=user.id).all()
        if len(results) < 2:
            continue

        scores = [r.score for r in results]
        avg_score = sum(scores) / len(scores)
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        # Consistency: inverse of normalized variance (0-1)
        consistency = 1.0 / (1.0 + variance)

        user_features.append([avg_score / 10.0, consistency])
        user_ids.append(user.id)

    if len(user_features) < 3:
        return {}

    result = kmeans_cluster(user_features, k=3)
    if result is None:
        return {}
    assignments, centroids = result

    # Label clusters by centroid avg_score (highest = Advanced)
    centroid_scores = [(i, c[0]) for i, c in enumerate(centroids)]
    centroid_scores.sort(key=lambda x: x[1], reverse=True)
    tier_labels = {}
    tier_names = ["Advanced", "Intermediate", "Beginner"]
    for rank, (cluster_id, _) in enumerate(centroid_scores):
        tier_labels[cluster_id] = tier_names[rank]

    # Build result
    classification = {}
    for i, uid in enumerate(user_ids):
        classification[uid] = {
            "tier": tier_labels[assignments[i]],
            "avg_score": round(user_features[i][0] * 10, 1),
            "consistency": round(user_features[i][1], 3)
        }

    return classification


# -------------------------------------------------
# ML ALGORITHM 4: COLLABORATIVE FILTERING
# "Students like you also studied..."
# -------------------------------------------------
def collaborative_filtering_recommend(user_id, top_n=5):
    """
    User-based Collaborative Filtering using Pearson Correlation.

    1. Build a user-topic score matrix
    2. Find users most correlated with the target user (Pearson r)
    3. Recommend topics that similar users scored highly on
       but the target user hasn't attempted yet

    Pearson r = sum((x-x_mean)(y-y_mean)) / sqrt(sum((x-x_mean)^2) * sum((y-y_mean)^2))
    """
    all_results = InterviewResult.query.all()
    if not all_results:
        return []

    # Build user-topic score matrix
    user_topic_scores = defaultdict(dict)
    all_topics = set()
    for r in all_results:
        if r.topic not in user_topic_scores[r.user_id]:
            user_topic_scores[r.user_id][r.topic] = []
        user_topic_scores[r.user_id][r.topic].append(r.score)
        all_topics.add(r.topic)

    # Average scores per topic per user
    user_avg = {}
    for uid, topics in user_topic_scores.items():
        user_avg[uid] = {t: sum(s) / len(s) for t, s in topics.items()}

    if user_id not in user_avg:
        return []

    target_scores = user_avg[user_id]
    target_topics = set(target_scores.keys())

    # Calculate Pearson correlation with each other user
    correlations = []
    for other_uid, other_scores in user_avg.items():
        if other_uid == user_id:
            continue

        # Find common topics
        common = target_topics & set(other_scores.keys())
        if len(common) < 2:
            continue

        x_vals = [target_scores[t] for t in common]
        y_vals = [other_scores[t] for t in common]
        x_mean = sum(x_vals) / len(x_vals)
        y_mean = sum(y_vals) / len(y_vals)

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denom_x = math.sqrt(sum((x - x_mean) ** 2 for x in x_vals))
        denom_y = math.sqrt(sum((y - y_mean) ** 2 for y in y_vals))

        if denom_x == 0 or denom_y == 0:
            continue

        pearson_r = numerator / (denom_x * denom_y)
        if pearson_r > 0.1:  # Only consider positively correlated users
            correlations.append((other_uid, pearson_r))

    correlations.sort(key=lambda x: x[1], reverse=True)

    # Weighted score prediction for unseen topics
    topic_predictions = {}
    for topic in all_topics:
        if topic in target_topics:
            continue  # Skip topics user already studied

        weighted_sum = 0
        weight_total = 0
        for other_uid, corr in correlations[:15]:  # Top 15 similar users
            if topic in user_avg[other_uid]:
                weighted_sum += corr * user_avg[other_uid][topic]
                weight_total += abs(corr)

        if weight_total > 0:
            topic_predictions[topic] = weighted_sum / weight_total

    # Return top N recommended topics sorted by predicted score
    recommendations = sorted(topic_predictions.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [{"topic": t, "predicted_score": round(s, 1)} for t, s in recommendations]


# -------------------------------------------------
# ML ALGORITHM 5: BAYESIAN KNOWLEDGE TRACING (BKT)
# Per-topic mastery estimation (used by Khan Academy)
# -------------------------------------------------
def bayesian_knowledge_tracing(user_id):
    """
    Bayesian Knowledge Tracing estimates the probability a student has
    mastered each topic, based on their sequence of correct/incorrect responses.

    Hidden state: L (learned/mastered) — binary latent variable per topic.
    Parameters (standard BKT defaults from literature):
        P(L0)  = 0.1   — prior probability of mastery before any practice
        P(T)   = 0.2   — probability of transitioning from unlearned to learned on each attempt
        P(G)   = 0.15  — probability of guessing correctly despite not knowing
        P(S)   = 0.10  — probability of slipping (wrong answer despite knowing)

    Update rules (forward algorithm):
        P(L|correct)   = P(L) * (1 - P(S)) / P(correct)
        P(L|incorrect) = P(L) * P(S) / P(incorrect)
        After each observation: P(L) = P(L|obs) + (1 - P(L|obs)) * P(T)
    """
    results = InterviewResult.query.filter_by(user_id=user_id)\
        .order_by(InterviewResult.date.asc()).all()

    if not results:
        return {}

    # Group results by topic, preserving order
    topic_sequences = {}
    for r in results:
        if r.topic not in topic_sequences:
            topic_sequences[r.topic] = []
        # Treat score >= 6/10 as "correct" (mastery-level response)
        topic_sequences[r.topic].append(r.score >= 6)

    # BKT parameters
    p_l0 = 0.1   # Prior knowledge
    p_t = 0.2    # Learning/transition rate
    p_g = 0.15   # Guess rate
    p_s = 0.10   # Slip rate

    mastery = {}
    for topic, observations in topic_sequences.items():
        p_l = p_l0  # Start with prior

        for correct in observations:
            if correct:
                # P(correct) = P(L)*(1-P(S)) + (1-P(L))*P(G)
                p_correct = p_l * (1 - p_s) + (1 - p_l) * p_g
                if p_correct > 0:
                    p_l = (p_l * (1 - p_s)) / p_correct
            else:
                # P(incorrect) = P(L)*P(S) + (1-P(L))*(1-P(G))
                p_incorrect = p_l * p_s + (1 - p_l) * (1 - p_g)
                if p_incorrect > 0:
                    p_l = (p_l * p_s) / p_incorrect

            # Apply learning transition
            p_l = p_l + (1 - p_l) * p_t

        mastery[topic] = {
            "mastery_probability": round(p_l, 3),
            "mastered": p_l >= 0.85,
            "attempts": len(observations),
            "label": "Mastered" if p_l >= 0.85 else "Learning" if p_l >= 0.5 else "Needs Work"
        }

    return mastery


# -------------------------------------------------
# ML ALGORITHM 6: EBBINGHAUS FORGETTING CURVE
# Predicts when a student will forget a topic
# -------------------------------------------------
def forgetting_curve_predict(user_id):
    """
    Ebbinghaus Forgetting Curve models memory retention over time.

    Formula: R(t) = e^(-t / S)
    Where:
        R = retention probability (0 to 1)
        t = time elapsed since last study (in days)
        S = memory strength (stability), which increases with repetitions and higher scores

    Memory Strength formula:
        S = base_strength * (1 + 0.5 * repetitions) * score_factor
        base_strength = 3.0 days (default half-life)
        score_factor = avg_score / 7 (normalized around passing)

    Returns topics sorted by urgency (lowest retention first),
    with recommended review dates.
    """
    results = InterviewResult.query.filter_by(user_id=user_id)\
        .order_by(InterviewResult.date.asc()).all()

    if not results:
        return []

    # Group by topic: get last study date, repetition count, avg score
    topic_data = {}
    for r in results:
        if r.topic not in topic_data:
            topic_data[r.topic] = {"scores": [], "last_date": r.date, "count": 0}
        topic_data[r.topic]["scores"].append(r.score)
        topic_data[r.topic]["last_date"] = r.date
        topic_data[r.topic]["count"] += 1

    now = datetime.utcnow()
    predictions = []
    base_strength = 3.0  # Base half-life in days

    for topic, data in topic_data.items():
        avg_score = sum(data["scores"]) / len(data["scores"])
        repetitions = data["count"]
        days_elapsed = max((now - data["last_date"]).total_seconds() / 86400, 0.01)

        # Memory strength increases with repetitions and score quality
        score_factor = max(avg_score / 7.0, 0.3)  # Floor at 0.3 to prevent near-zero
        strength = base_strength * (1 + 0.5 * min(repetitions, 20)) * score_factor

        # Retention = e^(-t/S)
        retention = math.exp(-days_elapsed / strength)

        # Optimal review time: when retention drops to 0.7 (70%)
        # 0.7 = e^(-t_review / S)  =>  t_review = -S * ln(0.7)
        optimal_review_days = -strength * math.log(0.7)
        days_until_review = max(optimal_review_days - days_elapsed, 0)

        predictions.append({
            "topic": topic,
            "retention": round(retention * 100, 1),  # as percentage
            "strength": round(strength, 1),
            "days_since_study": round(days_elapsed, 1),
            "days_until_review": round(days_until_review, 1),
            "review_urgency": "overdue" if retention < 0.5 else "soon" if retention < 0.7 else "ok",
            "last_studied": data["last_date"].strftime("%b %d, %Y")
        })

    # Sort by retention ascending (most forgotten first)
    predictions.sort(key=lambda x: x["retention"])
    return predictions


# -------------------------------------------------
# ML ALGORITHM 7: MARKOV CHAIN TOPIC PREDICTOR
# Predicts next best topic based on study transitions
# -------------------------------------------------
def markov_topic_predict(user_id, top_n=3):
    """
    Builds a first-order Markov Chain from the user's topic study sequence.

    A Markov Chain models transitions between states (topics). The transition
    probability P(next_topic | current_topic) is estimated from historical
    study sequences.

    Transition matrix: T[i][j] = count(i -> j) / count(transitions from i)

    Uses Laplace smoothing to handle unseen transitions:
        T_smooth[i][j] = (count(i -> j) + alpha) / (count(i) + alpha * |topics|)
        alpha = 0.1 (small smoothing to avoid zero probabilities)

    Returns top-N predicted next topics with probabilities.
    """
    results = InterviewResult.query.filter_by(user_id=user_id)\
        .order_by(InterviewResult.date.asc()).all()

    if len(results) < 3:
        return []

    # Build transition counts
    topics = list(set(r.topic for r in results))
    if len(topics) < 2:
        return []

    transition_counts = defaultdict(lambda: defaultdict(int))
    for i in range(len(results) - 1):
        from_topic = results[i].topic
        to_topic = results[i + 1].topic
        transition_counts[from_topic][to_topic] += 1

    # Current topic (most recent)
    current_topic = results[-1].topic

    # Compute transition probabilities with Laplace smoothing
    alpha = 0.1
    n_topics = len(topics)
    from_counts = transition_counts.get(current_topic, {})
    total_from = sum(from_counts.values())

    probabilities = []
    for topic in topics:
        count = from_counts.get(topic, 0)
        prob = (count + alpha) / (total_from + alpha * n_topics)
        probabilities.append((topic, prob))

    # Sort by probability descending, exclude current topic
    probabilities = [(t, p) for t, p in probabilities if t != current_topic]
    probabilities.sort(key=lambda x: x[1], reverse=True)

    return [
        {"topic": t, "probability": round(p * 100, 1)}
        for t, p in probabilities[:top_n]
    ]


# -------------------------------------------------
# ML ALGORITHM 8: NAIVE BAYES RISK CLASSIFIER
# Classifies students as at-risk, on-track, or excelling
# -------------------------------------------------
def naive_bayes_risk_classify(user_id):
    """
    Gaussian Naive Bayes classifier that estimates student risk level
    using multiple features.

    Features:
        1. Average score (0-10)
        2. Score variance (consistency)
        3. Study frequency (sessions per week)
        4. Trend (slope from last 5 sessions)

    Prior class distributions (from educational research baselines):
        - At-Risk:   avg=3.5, var_high=5.0, freq_low=1.0
        - On-Track:  avg=6.0, var_med=2.0,  freq_med=3.0
        - Excelling: avg=8.5, var_low=1.0,  freq_high=5.0

    P(class | features) ∝ P(class) * Π P(feature_i | class)
    where P(feature | class) = Gaussian PDF with class-specific μ and σ
    """
    results = InterviewResult.query.filter_by(user_id=user_id)\
        .order_by(InterviewResult.date.asc()).all()

    if len(results) < 3:
        return None

    scores = [r.score for r in results]
    avg_score = sum(scores) / len(scores)
    variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)

    # Study frequency: sessions per week
    first_date = results[0].date
    last_date = results[-1].date
    weeks = max((last_date - first_date).total_seconds() / (7 * 86400), 1)
    frequency = len(results) / weeks

    # Trend: slope of last 5 scores
    recent = scores[-5:] if len(scores) >= 5 else scores
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    trend = numerator / denominator if denominator > 0 else 0

    # Gaussian PDF helper
    def gaussian_pdf(x, mu, sigma):
        sigma = max(sigma, 0.01)  # prevent division by zero
        return (1 / (sigma * math.sqrt(2 * math.pi))) * \
               math.exp(-0.5 * ((x - mu) / sigma) ** 2)

    # Class definitions: (prior, mean_score, std_score, mean_var, std_var, mean_freq, std_freq, mean_trend, std_trend)
    classes = {
        "at-risk": {
            "prior": 0.25,
            "params": {"score": (3.5, 1.5), "variance": (5.0, 2.0), "frequency": (1.0, 0.8), "trend": (-0.5, 0.5)}
        },
        "on-track": {
            "prior": 0.50,
            "params": {"score": (6.0, 1.5), "variance": (2.0, 1.5), "frequency": (3.0, 1.5), "trend": (0.2, 0.4)}
        },
        "excelling": {
            "prior": 0.25,
            "params": {"score": (8.5, 1.0), "variance": (1.0, 1.0), "frequency": (5.0, 2.0), "trend": (0.5, 0.4)}
        }
    }

    features = {"score": avg_score, "variance": variance, "frequency": frequency, "trend": trend}

    # Compute posterior for each class
    posteriors = {}
    for cls, config in classes.items():
        log_posterior = math.log(config["prior"])
        for feat_name, feat_val in features.items():
            mu, sigma = config["params"][feat_name]
            pdf = gaussian_pdf(feat_val, mu, sigma)
            log_posterior += math.log(max(pdf, 1e-300))  # Avoid log(0)
        posteriors[cls] = log_posterior

    # Normalize with log-sum-exp for numerical stability
    max_log = max(posteriors.values())
    exp_sum = sum(math.exp(v - max_log) for v in posteriors.values())
    probabilities = {
        cls: round(math.exp(v - max_log) / exp_sum, 3)
        for cls, v in posteriors.items()
    }

    predicted_class = max(probabilities, key=probabilities.get)

    return {
        "classification": predicted_class,
        "probabilities": probabilities,
        "features": {
            "avg_score": round(avg_score, 1),
            "score_variance": round(variance, 1),
            "study_frequency": round(frequency, 1),
            "recent_trend": round(trend, 2)
        }
    }


# =================================================================
# ROUTES - AUTHENTICATION
# =================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        raw_password = request.form.get("password", "")
        role = request.form.get("role", "student").strip().lower()

        # Only allow student or teacher via registration (admin is created manually)
        if role not in ("student", "teacher"):
            role = "student"

        # Validate inputs
        if not name or len(name) > 100:
            flash("Please enter a valid name (max 100 characters).", "error")
            return redirect("/register")

        if not validate_email(email):
            flash("Please enter a valid email address.", "error")
            return redirect("/register")

        is_valid, msg = validate_password(raw_password)
        if not is_valid:
            flash(msg, "error")
            return redirect("/register")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "error")
            return redirect("/register")

        password = generate_password_hash(raw_password)
        user = User(name=name, email=email, password=password, plain_password=raw_password, role=role, status='pending', points=0, streak=0)
        db.session.add(user)
        db.session.commit()
        logging.info(f"New user registered (pending approval): {email}")

        flash("Successfully registered. Please wait for admin approval before logging in.", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    # Check if any admin exists — if not, redirect to admin setup
    admin_exists = User.query.filter_by(role="admin").first()
    if not admin_exists:
        return redirect("/setup-admin")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Rate limit: 5 login attempts per minute per IP
        client_ip = request.remote_addr or "unknown"
        if not check_rate_limit(f"login_{client_ip}", max_requests=5, window_seconds=60):
            flash("Too many login attempts. Please wait a minute.", "error")
            return redirect("/login")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            # Check approval status before allowing login
            if user.status == 'pending':
                flash("Your approval is pending. Please contact the administrator for more information.", "warning")
                return redirect("/login")
            elif user.status == 'rejected':
                flash("Your registration was rejected. Please contact the administrator.", "error")
                return redirect("/login")

            login_user(user)
            update_streak(user)
            logging.info(f"User logged in: {email}")
            return redirect("/")

        flash("Invalid email or password.", "error")
        return redirect("/login")

    return render_template("login.html")


@app.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    # If admin already exists, block access to this page
    admin_exists = User.query.filter_by(role="admin").first()
    if admin_exists:
        return redirect("/login")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        raw_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate inputs
        if not name or len(name) > 100:
            flash("Please enter a valid name (max 100 characters).", "error")
            return redirect("/setup-admin")

        if not validate_email(email):
            flash("Please enter a valid email address.", "error")
            return redirect("/setup-admin")

        is_valid, msg = validate_password(raw_password)
        if not is_valid:
            flash(msg, "error")
            return redirect("/setup-admin")

        if raw_password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect("/setup-admin")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "error")
            return redirect("/setup-admin")

        admin = User(
            name=name,
            email=email,
            password=generate_password_hash(raw_password),
            plain_password=raw_password,
            role="admin",
            status="approved",
            points=0,
            streak=0
        )
        db.session.add(admin)
        db.session.commit()
        logging.info(f"Admin account created: {email}")

        flash("Admin account created successfully! Please login.", "success")
        return redirect("/login")

    return render_template("setup_admin.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


# =================================================================
# ROUTES - MAIN PAGES
# =================================================================

@app.route("/")
def home():
    if current_user.is_authenticated:
        return render_template("index.html")
    # If no admin exists yet, go to setup first
    admin_exists = User.query.filter_by(role="admin").first()
    if not admin_exists:
        return redirect("/setup-admin")
    return redirect("/login")


@app.route("/mode")
@login_required
def mode():
    return render_template("mode.html")


@app.route("/start")
@login_required
def start():
    mode = request.args.get("mode")
    topic = request.args.get("topic", "")
    # Get adaptive difficulty suggestion
    suggested_difficulty = "medium"
    if topic:
        suggested_difficulty = get_adaptive_difficulty(current_user.id, topic)
    return render_template("start.html", mode=mode, suggested_difficulty=suggested_difficulty)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:100]
        email = request.form.get("email", "").strip()[:120]
        subject = request.form.get("subject", "General Query")[:100]
        message = request.form.get("message", "").strip()[:2000]

        if not name or not email or not message:
            return jsonify({"status": "error", "message": "All fields are required"}), 400

        # Rate limit contact form: 3 per minute per IP
        client_ip = request.remote_addr or "unknown"
        if not check_rate_limit(f"contact_{client_ip}", max_requests=3, window_seconds=60):
            return jsonify({"status": "error", "message": "Too many submissions. Please wait."}), 429

        msg = ContactMessage(name=name, email=email, subject=subject, message=message)
        db.session.add(msg)
        db.session.commit()
        return jsonify({"status": "success"})
    return render_template("contact.html")


# =================================================================
# ROUTES - QUIZ MODE
# =================================================================

@app.route("/quiz")
@login_required
def quiz():
    topic = sanitize_topic(request.args.get("topic", "DBMS"))
    timed = request.args.get("timed", "false").lower() == "true"
    try:
        duration = min(max(int(request.args.get("duration", 300)), 60), 3600)
    except (ValueError, TypeError):
        duration = 300
    try:
        mcqs = min(int(request.args.get("mcqs", 5)), 20)
    except (ValueError, TypeError):
        mcqs = 5

    prompt = f"""
Generate EXACTLY {mcqs} multiple-choice questions on "{topic}".

STRICT FORMAT:
QUESTION: <text>
A) <option>
B) <option>
C) <option>
D) <option>
ANSWER: <A/B/C/D>

Rules:
- No numbering
- No explanations
- One blank line between questions
"""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        raw = response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API error in quiz: {e}")
        raw = ""

    mcq_blocks = raw.strip().split("\n\n") if raw else []
    questions = []

    for block in mcq_blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) < 6:
            continue

        question = lines[0].replace("QUESTION:", "").strip()
        options = [opt[3:].strip() if len(opt) > 3 else opt.strip() for opt in lines[1:5]]
        answer = lines[5].replace("ANSWER:", "").strip().replace(".", "")

        if len(options) == 4 and answer in ("A", "B", "C", "D"):
            questions.append({
                "question": question,
                "options": options,
                "answer": answer
            })

    if not questions:
        questions = [{
            "question": "AI failed to generate questions. Please retry.",
            "options": ["Retry", "Retry", "Retry", "Retry"],
            "answer": "A"
        }]

    return render_template("quiz.html", topic=topic, questions=questions, timed=timed, duration=duration)


@app.route("/quiz-submit", methods=["POST"])
@login_required
def quiz_submit():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    topic = data.get("topic", "Unknown")
    try:
        score = int(data.get("score", 0))
        total = int(data.get("total", 1))
    except (ValueError, TypeError):
        score, total = 0, 1
    if total <= 0:
        total = 1
    is_timed = data.get("timed", False)

    # Save result (normalize to 0-10 scale)
    normalized_score = min(10, max(0, round((score / total) * 10)))
    result = InterviewResult(
        user_id=current_user.id,
        topic=topic,
        score=normalized_score,
        mode='timed_quiz' if is_timed else 'quiz'
    )
    db.session.add(result)

    # Award points
    award_points(current_user, normalized_score)
    check_and_award_badges(current_user)

    db.session.commit()
    return jsonify({"status": "success", "points_earned": normalized_score})


# =================================================================
# ROUTES - VOICE PRACTICE
# =================================================================

@app.route("/voice")
@login_required
def voice():
    topic = sanitize_topic(request.args.get("topic", "DBMS"))
    try:
        count = min(int(request.args.get("count", 3)), 10)
    except (ValueError, TypeError):
        count = 3
    difficulty = request.args.get("difficulty", "medium")
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    questions = generate_theory_questions(topic, count, difficulty)
    return render_template("voice.html", topic=topic, questions=questions, difficulty=difficulty)


@app.route("/voice-evaluate", methods=["POST"])
@login_required
def voice_evaluate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    topic = data.get("topic", "General")
    questions = data.get("questions", [])
    answers = data.get("answers", [])

    if not questions or not answers or len(questions) != len(answers):
        return jsonify({"error": "Questions and answers are required and must match in count"}), 400

    formatted_text = ""
    for i in range(len(questions)):
        formatted_text += f"""
Question {i+1}:
{questions[i]}

Answer:
{answers[i]}

"""

    prompt = f"""
You are an interview evaluator.

Topic: {topic}

Evaluate each answer separately.

Return STRICT JSON in this format:

{{
  "overall_score": <number>,
  "results": [
    {{
      "question": "...",
      "score": <number>,
      "strengths": ["...", "..."],
      "improvements": ["...", "..."]
    }}
  ]
}}

Evaluation Data:
{formatted_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    ai_output = response.choices[0].message.content

    try:
        # Strip markdown code fences if present
        clean_output = ai_output.strip()
        if clean_output.startswith("```"):
            clean_output = re.sub(r'^```(?:json)?\s*', '', clean_output)
            clean_output = re.sub(r'\s*```$', '', clean_output)

        parsed = json.loads(clean_output)
        overall_score = min(max(int(parsed.get("overall_score", 0)), 0), 10)

        result = InterviewResult(
            user_id=current_user.id,
            topic=sanitize_topic(topic),
            score=overall_score,
            mode='voice'
        )
        db.session.add(result)

        award_points(current_user, overall_score)
        check_and_award_badges(current_user)
        db.session.commit()

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse AI response as JSON: {e}")
        return jsonify({"evaluation": ai_output, "warning": "Score could not be saved"})
    except Exception as e:
        logging.error(f"Error saving voice result: {e}")
        db.session.rollback()

    return jsonify({"evaluation": ai_output})


# =================================================================
# ROUTES - THEORY QUESTIONS
# =================================================================

@app.route("/theory")
@login_required
def theory():
    topic = sanitize_topic(request.args.get("topic", "DBMS"))
    try:
        count = min(int(request.args.get("count", 5)), 20)
    except (ValueError, TypeError):
        count = 5

    try:
        prompt = f"""
Generate EXACTLY {count} theory questions on the topic "{topic}".
- No numbering
- No repetition
- Each question on a new line
"""
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        raw_output = response.choices[0].message.content
        questions = [
            q.strip("-\u2022 ").strip()
            for q in raw_output.split("\n")
            if q.strip()
        ]
    except Exception as e:
        logging.error(f"OpenAI API error in theory: {e}")
        questions = [f"Failed to generate questions on {topic}. Please try again."]

    # Award points for theory practice
    award_points(current_user, 3)
    result = InterviewResult(
        user_id=current_user.id,
        topic=topic,
        score=5,
        mode='theory'
    )
    db.session.add(result)
    check_and_award_badges(current_user)
    db.session.commit()

    return render_template("theory_questions.html", topic=topic, questions=questions)


# =================================================================
# ROUTES - DASHBOARD
# =================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    results = InterviewResult.query.filter_by(
        user_id=current_user.id
    ).order_by(InterviewResult.date).all()

    total_attempts = len(results)
    scores = [r.score for r in results]
    dates = [r.date.strftime("%Y-%m-%d") for r in results]

    average_score = round(sum(scores) / len(scores), 2) if scores else 0
    best_score = max(scores) if scores else 0

    # Weak topics
    weak_topics = get_weak_topics(current_user.id)

    # Topic-wise breakdown
    topic_breakdown = {}
    for r in results:
        if r.topic not in topic_breakdown:
            topic_breakdown[r.topic] = {"scores": [], "count": 0}
        topic_breakdown[r.topic]["scores"].append(r.score)
        topic_breakdown[r.topic]["count"] += 1

    for topic in topic_breakdown:
        s = topic_breakdown[topic]["scores"]
        topic_breakdown[topic]["avg"] = round(sum(s) / len(s), 1)

    # Badges
    badges = Badge.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "dashboard.html",
        total_attempts=total_attempts,
        average_score=average_score,
        best_score=best_score,
        results=results,
        scores=scores,
        dates=dates,
        weak_topics=weak_topics,
        topic_breakdown=topic_breakdown,
        badges=badges,
        streak=current_user.streak or 0,
        points=current_user.points or 0
    )


# =================================================================
# ROUTES - ML RECOMMENDATIONS
# =================================================================

@app.route("/recommendations")
@login_required
def recommendations():
    """ML-powered personalized recommendations page."""
    # 1. Linear Regression: Score prediction
    score_prediction = linear_regression_predict(current_user.id)

    # 2. TF-IDF + Cosine Similarity: Similar topic recommendations
    similar_topics = get_similar_topics(current_user.id, top_n=5)

    # 3. Collaborative Filtering: "Students like you" recommendations
    collab_recommendations = collaborative_filtering_recommend(current_user.id, top_n=5)

    # 4. K-Means: Learner tier classification
    classifications = classify_learners()
    user_tier = classifications.get(current_user.id, None)

    # 5. Weak topics (existing)
    weak_topics = get_weak_topics(current_user.id)

    # 6. Per-topic predictions
    topic_predictions = {}
    user_results = InterviewResult.query.filter_by(user_id=current_user.id).all()
    user_topics = set(r.topic for r in user_results)
    for topic in user_topics:
        pred = linear_regression_predict(current_user.id, topic=topic)
        if pred:
            topic_predictions[topic] = pred

    # 7. Bayesian Knowledge Tracing: Per-topic mastery
    bkt_mastery = bayesian_knowledge_tracing(current_user.id)

    # 8. Ebbinghaus Forgetting Curve: Memory retention
    forgetting_data = forgetting_curve_predict(current_user.id)

    # 9. Markov Chain: Next topic prediction
    markov_predictions = markov_topic_predict(current_user.id, top_n=3)

    # 10. Naive Bayes: Risk classification
    risk_profile = naive_bayes_risk_classify(current_user.id)

    return render_template(
        "recommendations.html",
        score_prediction=score_prediction,
        similar_topics=similar_topics,
        collab_recommendations=collab_recommendations,
        user_tier=user_tier,
        weak_topics=weak_topics,
        topic_predictions=topic_predictions,
        bkt_mastery=bkt_mastery,
        forgetting_data=forgetting_data,
        markov_predictions=markov_predictions,
        risk_profile=risk_profile
    )


@app.route("/api/recommendations")
@login_required
def api_recommendations():
    """JSON API for ML recommendations (used by dashboard)."""
    return jsonify({
        "score_prediction": linear_regression_predict(current_user.id),
        "similar_topics": get_similar_topics(current_user.id, top_n=3),
        "collab_recommendations": collaborative_filtering_recommend(current_user.id, top_n=3),
        "user_tier": classify_learners().get(current_user.id),
        "weak_topics": get_weak_topics(current_user.id)[:3],
        "bkt_mastery": bayesian_knowledge_tracing(current_user.id),
        "forgetting_curve": forgetting_curve_predict(current_user.id)[:3],
        "markov_predictions": markov_topic_predict(current_user.id, top_n=3),
        "risk_profile": naive_bayes_risk_classify(current_user.id)
    })


# =================================================================
# ROUTES - AI CHATBOT (DOUBT SOLVER)
# =================================================================

@app.route("/chatbot")
@login_required
def chatbot():
    history = ChatHistory.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatHistory.created_at.desc()).limit(20).all()
    history.reverse()
    return render_template("chatbot.html", history=history)


@app.route("/chatbot-ask", methods=["POST"])
@login_required
def chatbot_ask():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    message = data.get("message", "").strip()[:2000]
    topic = sanitize_topic(data.get("topic", "General"))

    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Rate limit: 15 AI requests per minute per user
    if not check_rate_limit(f"chatbot_{current_user.id}", max_requests=15, window_seconds=60):
        return jsonify({"error": "Too many requests. Please wait a moment."}), 429

    prompt = f"""You are EduVoxus AI Tutor, a friendly and knowledgeable educational assistant.

Topic context: {topic}

Student's question: {message}

Instructions:
- Give a clear, concise, and educational response
- Use examples where helpful
- If the question is about a concept, explain it step-by-step
- Format your response with markdown for readability
- Be encouraging and supportive
"""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        ai_response = response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API error in chatbot: {e}")
        return jsonify({"error": "AI service temporarily unavailable. Please try again."}), 503

    # Save to history
    chat = ChatHistory(
        user_id=current_user.id,
        message=message,
        response=ai_response,
        topic=topic
    )
    db.session.add(chat)
    award_points(current_user, 1)
    db.session.commit()

    return jsonify({"response": ai_response})


# =================================================================
# ROUTES - LEADERBOARD
# =================================================================

@app.route("/leaderboard")
@login_required
def leaderboard():
    # Top users by points
    top_users = User.query.filter(User.points > 0).order_by(User.points.desc()).limit(50).all()

    # Current user rank
    all_users = User.query.filter(User.points > 0).order_by(User.points.desc()).all()
    user_rank = next((i + 1 for i, u in enumerate(all_users) if u.id == current_user.id), len(all_users) + 1)

    # Weekly top (results from last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_results = db.session.query(
        User.id, User.name,
        db.func.sum(InterviewResult.score).label('weekly_score'),
        db.func.count(InterviewResult.id).label('sessions')
    ).join(InterviewResult).filter(
        InterviewResult.date >= week_ago
    ).group_by(User.id).order_by(db.desc('weekly_score')).limit(10).all()

    return render_template(
        "leaderboard.html",
        top_users=top_users,
        user_rank=user_rank,
        weekly_results=weekly_results
    )


# =================================================================
# ROUTES - COURSES & STUDY MATERIALS
# =================================================================

@app.route("/courses")
@login_required
def courses():
    all_courses = Course.query.order_by(Course.created_at.desc()).all()
    categories = db.session.query(Course.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    return render_template("courses.html", courses=all_courses, categories=categories)


@app.route("/courses/new", methods=["GET", "POST"])
@login_required
def new_course():
    if current_user.role not in ('admin', 'teacher'):
        flash("Only teachers and admins can create courses.", "error")
        return redirect("/courses")

    if request.method == "POST":
        title = request.form.get("title", "").strip()[:200]
        description = request.form.get("description", "").strip()[:2000]
        category = request.form.get("category", "General")[:100]

        if not title or not description:
            flash("Title and description are required.", "error")
            return redirect("/courses/new")

        course = Course(
            title=title,
            description=description,
            category=category,
            created_by=current_user.id
        )
        db.session.add(course)
        db.session.commit()
        flash("Course created successfully!", "success")
        return redirect(f"/courses/{course.id}")

    return render_template("course_new.html")


@app.route("/courses/<int:course_id>")
@login_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    materials = StudyMaterial.query.filter_by(course_id=course_id).order_by(StudyMaterial.uploaded_at.desc()).all()
    return render_template("course_detail.html", course=course, materials=materials)


@app.route("/courses/<int:course_id>/upload", methods=["POST"])
@login_required
def upload_material(course_id):
    course = Course.query.get_or_404(course_id)

    if current_user.role not in ('admin', 'teacher'):
        flash("Only teachers and admins can upload materials.", "error")
        return redirect(f"/courses/{course_id}")

    if 'file' not in request.files:
        flash("No file selected.", "error")
        return redirect(f"/courses/{course_id}")

    file = request.files['file']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(f"/courses/{course_id}")

    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        ext = original_filename.rsplit('.', 1)[1].lower()
        # Use UUID for stored filename to prevent path traversal
        safe_filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'notes', safe_filename)
        file.save(filepath)

        material = StudyMaterial(
            course_id=course_id,
            title=request.form.get("title", original_filename)[:200],
            description=request.form.get("description", "")[:500],
            file_path=safe_filename,
            file_type=ext,
            uploaded_by=current_user.id
        )
        db.session.add(material)
        db.session.commit()
        flash("Material uploaded successfully!", "success")
    else:
        flash("Invalid file type.", "error")

    return redirect(f"/courses/{course_id}")


@app.route("/download/<filename>")
@login_required
def download_file(filename):
    # Sanitize filename to prevent path traversal
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        abort(404)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'notes', safe_name)
    # Verify resolved path is within upload folder
    real_path = os.path.realpath(filepath)
    upload_dir = os.path.realpath(os.path.join(app.config['UPLOAD_FOLDER'], 'notes'))
    if not real_path.startswith(upload_dir):
        abort(403)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    abort(404)


# =================================================================
# ROUTES - DISCUSSION FORUM
# =================================================================

@app.route("/forum")
@login_required
def forum():
    page = max(request.args.get("page", 1, type=int), 1)
    topic_filter = request.args.get("topic", "")[:100]
    search = request.args.get("search", "")[:100]

    query = ForumPost.query
    if topic_filter:
        query = query.filter_by(topic=topic_filter)
    if search:
        query = query.filter(ForumPost.title.contains(search) | ForumPost.content.contains(search))

    posts = query.order_by(ForumPost.created_at.desc()).paginate(page=page, per_page=10)

    topics = db.session.query(ForumPost.topic).distinct().all()
    topics = [t[0] for t in topics if t[0]]

    return render_template("forum.html", posts=posts, topics=topics, current_topic=topic_filter, search=search)


@app.route("/forum/new", methods=["GET", "POST"])
@login_required
def forum_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:200]
        content = request.form.get("content", "").strip()[:5000]
        topic = request.form.get("topic", "General")[:100]

        if not title or not content:
            flash("Title and content are required.", "error")
            return redirect("/forum/new")

        post = ForumPost(
            user_id=current_user.id,
            title=title,
            content=content,
            topic=topic
        )
        db.session.add(post)
        award_points(current_user, 5)
        db.session.commit()
        flash("Post created successfully!", "success")
        return redirect(f"/forum/post/{post.id}")

    return render_template("forum_new.html")


@app.route("/forum/post/<int:post_id>", methods=["GET", "POST"])
@login_required
def forum_post(post_id):
    post = ForumPost.query.get_or_404(post_id)

    if request.method == "POST":
        content = request.form.get("content", "").strip()[:5000]
        if content:
            reply = ForumReply(
                post_id=post_id,
                user_id=current_user.id,
                content=content
            )
            db.session.add(reply)
            award_points(current_user, 2)
            db.session.commit()
            flash("Reply posted!", "success")

    return render_template("forum_post.html", post=post)


@app.route("/forum/post/<int:post_id>/ai-answer", methods=["POST"])
@login_required
def forum_ai_answer(post_id):
    post = ForumPost.query.get_or_404(post_id)

    prompt = f"""You are an AI tutor helping students on a discussion forum.

Topic: {post.topic}
Question: {post.title}
Details: {post.content}

Provide a helpful, educational answer. Use examples. Be concise but thorough."""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        ai_response = response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API error in forum AI answer: {e}")
        return jsonify({"error": "AI service temporarily unavailable. Please try again."}), 503

    reply = ForumReply(
        post_id=post_id,
        user_id=current_user.id,
        content=ai_response,
        is_ai=True
    )
    db.session.add(reply)
    db.session.commit()

    return jsonify({"response": ai_response})


# =================================================================
# ROUTES - CERTIFICATE GENERATION
# =================================================================

@app.route("/certificate/<int:result_id>")
@login_required
def generate_certificate(result_id):
    result = InterviewResult.query.get_or_404(result_id)
    if result.user_id != current_user.id:
        abort(403)

    if result.score < 7:
        flash("Certificates are available for scores 7/10 and above.", "error")
        return redirect("/dashboard")

    return render_template("certificate.html", result=result, user=current_user)


# =================================================================
# ROUTES - USER PROFILE
# =================================================================

@app.route("/profile")
@login_required
def profile():
    results = InterviewResult.query.filter_by(user_id=current_user.id).all()
    badges = Badge.query.filter_by(user_id=current_user.id).all()
    total_sessions = len(results)
    avg_score = round(sum(r.score for r in results) / len(results), 1) if results else 0

    # Topic distribution
    topics = {}
    for r in results:
        topics[r.topic] = topics.get(r.topic, 0) + 1

    return render_template(
        "profile.html",
        user=current_user,
        badges=badges,
        total_sessions=total_sessions,
        avg_score=avg_score,
        topics=topics
    )


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not check_password_hash(current_user.password, current_pw):
        flash("Current password is incorrect.", "error")
        return redirect("/profile")

    if new_pw != confirm_pw:
        flash("New passwords do not match.", "error")
        return redirect("/profile")

    is_valid, msg = validate_password(new_pw)
    if not is_valid:
        flash(msg, "error")
        return redirect("/profile")

    current_user.password = generate_password_hash(new_pw)
    current_user.plain_password = new_pw
    db.session.commit()
    flash("Password updated successfully!", "success")
    return redirect("/profile")


@app.route("/admin/user/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def admin_reset_password(user_id):
    """Admin can reset any user's password."""
    user = User.query.get_or_404(user_id)
    new_pw = request.form.get("new_password", "").strip()

    if not new_pw or len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect("/admin/users")

    user.password = generate_password_hash(new_pw)
    user.plain_password = new_pw
    db.session.commit()
    flash(f"Password reset for {user.name}.", "success")
    return redirect("/admin/users")


# =================================================================
# ROUTES - ADMIN DASHBOARD
# =================================================================

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_sessions = InterviewResult.query.count()
    total_courses = Course.query.count()
    total_posts = ForumPost.query.count()
    total_contacts = ContactMessage.query.filter_by(is_read=False).count()
    pending_registrations = User.query.filter_by(status='pending').count()

    # Pending users list for approval panel
    pending_users = User.query.filter_by(status='pending').order_by(User.created_at.desc()).all()

    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_results = db.session.query(InterviewResult, User).join(User).order_by(
        InterviewResult.date.desc()
    ).limit(10).all()

    # Daily active users (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    daily_active = db.session.query(
        db.func.date(InterviewResult.date),
        db.func.count(db.func.distinct(InterviewResult.user_id))
    ).filter(InterviewResult.date >= week_ago).group_by(
        db.func.date(InterviewResult.date)
    ).all()

    # Contact messages
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(20).all()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_sessions=total_sessions,
        total_courses=total_courses,
        total_posts=total_posts,
        total_contacts=total_contacts,
        pending_registrations=pending_registrations,
        pending_users=pending_users,
        recent_users=recent_users,
        recent_results=recent_results,
        daily_active=daily_active,
        messages=messages
    )


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    page = max(request.args.get("page", 1, type=int), 1)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template("admin_users.html", users=users)


@app.route("/admin/user/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def admin_change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role", "student")
    if new_role in ('student', 'teacher', 'admin'):
        user.role = new_role
        db.session.commit()
        flash(f"Role updated to {new_role} for {user.name}.", "success")
    return redirect("/admin/users")


@app.route("/admin/user/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def admin_approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.status = 'approved'
    db.session.commit()
    logging.info(f"Admin approved user: {user.email}")
    flash(f"{user.name} has been approved.", "success")
    return redirect("/admin")


@app.route("/admin/user/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_required
def admin_reject_user(user_id):
    user = User.query.get_or_404(user_id)
    user.status = 'rejected'
    db.session.commit()
    logging.info(f"Admin rejected user: {user.email}")
    flash(f"{user.name} has been rejected.", "success")
    return redirect("/admin")


@app.route("/admin/message/<int:msg_id>/read", methods=["POST"])
@login_required
@admin_required
def admin_mark_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return jsonify({"status": "success"})


# =================================================================
# ROUTES - BOOKMARKS
# =================================================================

@app.route("/bookmarks")
@login_required
def bookmarks():
    topic_filter = request.args.get("topic", "")[:100]
    query = Bookmark.query.filter_by(user_id=current_user.id)
    if topic_filter:
        query = query.filter_by(topic=topic_filter)
    marks = query.order_by(Bookmark.created_at.desc()).all()
    topics = db.session.query(Bookmark.topic).filter_by(user_id=current_user.id).distinct().all()
    topics = [t[0] for t in topics if t[0]]
    return render_template("bookmarks.html", bookmarks=marks, topics=topics, current_topic=topic_filter)


@app.route("/bookmarks/add", methods=["POST"])
@login_required
def bookmark_add():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400
    question = data.get("question", "").strip()[:2000]
    answer = data.get("answer", "").strip()[:2000]
    topic = sanitize_topic(data.get("topic", "General"))
    source = data.get("source", "quiz")[:20]
    if not question:
        return jsonify({"error": "Question is required"}), 400
    # Check for duplicate
    existing = Bookmark.query.filter_by(user_id=current_user.id, question=question).first()
    if existing:
        return jsonify({"status": "already_exists"})
    bm = Bookmark(user_id=current_user.id, question=question, answer=answer, topic=topic, source=source)
    db.session.add(bm)
    award_points(current_user, 1)
    db.session.commit()
    return jsonify({"status": "success"})


@app.route("/bookmarks/<int:bm_id>/delete", methods=["POST"])
@login_required
def bookmark_delete(bm_id):
    bm = Bookmark.query.get_or_404(bm_id)
    if bm.user_id != current_user.id:
        abort(403)
    db.session.delete(bm)
    db.session.commit()
    return jsonify({"status": "success"})


# =================================================================
# ROUTES - AI FLASHCARDS
# =================================================================

@app.route("/flashcards")
@login_required
def flashcards():
    decks = FlashcardDeck.query.filter_by(user_id=current_user.id).order_by(FlashcardDeck.created_at.desc()).all()
    return render_template("flashcards.html", decks=decks)


@app.route("/flashcards/generate", methods=["POST"])
@login_required
def flashcards_generate():
    topic = sanitize_topic(request.form.get("topic", "General"))
    try:
        count = min(max(int(request.form.get("count", 10)), 5), 20)
    except (ValueError, TypeError):
        count = 10

    if not check_rate_limit(f"flashcard_{current_user.id}", max_requests=5, window_seconds=60):
        flash("Too many requests. Please wait a moment.", "error")
        return redirect("/flashcards")

    prompt = f"""Generate exactly {count} flashcards on "{topic}".
Return ONLY a JSON array, no extra text:
[{{"front": "question or term", "back": "concise answer or definition"}}]
Make them educational, varied in difficulty, and useful for revision."""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
        cards_data = json.loads(raw)
        if not isinstance(cards_data, list) or not cards_data:
            raise ValueError("AI returned invalid flashcard data")
    except Exception as e:
        logging.error(f"Flashcard generation failed: {e}")
        flash("Failed to generate flashcards. Please try again.", "error")
        return redirect("/flashcards")

    deck = FlashcardDeck(user_id=current_user.id, title=f"{topic} Flashcards", topic=topic)
    db.session.add(deck)
    db.session.flush()

    for card in cards_data[:count]:
        fc = Flashcard(
            deck_id=deck.id,
            front=card.get("front", ""),
            back=card.get("back", "")
        )
        db.session.add(fc)

    award_points(current_user, 3)
    check_and_award_badges(current_user)
    db.session.commit()

    flash("Flashcard deck created!", "success")
    return redirect(f"/flashcards/{deck.id}")


@app.route("/flashcards/<int:deck_id>")
@login_required
def flashcard_study(deck_id):
    deck = FlashcardDeck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)
    cards = Flashcard.query.filter_by(deck_id=deck_id).order_by(Flashcard.next_review).all()
    return render_template("flashcard_study.html", deck=deck, cards=cards)


@app.route("/flashcards/<int:deck_id>/review", methods=["POST"])
@login_required
def flashcard_review(deck_id):
    deck = FlashcardDeck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)
    data = request.get_json()
    card_id = data.get("card_id")
    rating = data.get("rating", "medium")  # easy, medium, hard, again

    card = Flashcard.query.get_or_404(card_id)
    if card.deck_id != deck_id:
        abort(400)

    # -------------------------------------------------------
    # SM-2 (SuperMemo 2) Spaced Repetition Algorithm
    # Based on: https://www.supermemo.com/en/archives1990-2015/english/ol/sm2
    #
    # Quality mapping: again=0, hard=2, medium=4, easy=5
    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    # If q < 3: reset interval to 1, keep EF
    # If q >= 3: interval(1)=1, interval(2)=6, interval(n)=interval(n-1)*EF
    # -------------------------------------------------------
    quality_map = {"again": 0, "hard": 2, "medium": 4, "easy": 5}
    q = quality_map.get(rating, 4)

    now = datetime.utcnow()
    card.review_count = (card.review_count or 0) + 1

    ef = card.easiness_factor or 2.5
    ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ef = max(1.3, ef)  # EF cannot go below 1.3
    card.easiness_factor = round(ef, 2)

    if q < 3:
        # Failed recall - reset to beginning
        card.interval = 1
        card.difficulty = 3
    else:
        n = card.review_count
        if n == 1:
            card.interval = 1
        elif n == 2:
            card.interval = 6
        else:
            card.interval = max(1, round((card.interval or 1) * ef))
        card.difficulty = {5: 1, 4: 2, 2: 3, 0: 3}.get(q, 2)

    card.next_review = now + timedelta(days=card.interval)

    award_points(current_user, 1)
    db.session.commit()
    return jsonify({"status": "success"})


@app.route("/flashcards/<int:deck_id>/delete", methods=["POST"])
@login_required
def flashcard_delete(deck_id):
    deck = FlashcardDeck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)
    db.session.delete(deck)
    db.session.commit()
    flash("Deck deleted.", "success")
    return redirect("/flashcards")


# =================================================================
# ROUTES - AI STUDY NOTES
# =================================================================

@app.route("/notes")
@login_required
def notes():
    user_notes = StudyNote.query.filter_by(user_id=current_user.id).order_by(StudyNote.created_at.desc()).all()
    return render_template("notes.html", notes=user_notes)


@app.route("/notes/generate", methods=["POST"])
@login_required
def notes_generate():
    topic = sanitize_topic(request.form.get("topic", "General"))

    if not check_rate_limit(f"notes_{current_user.id}", max_requests=5, window_seconds=60):
        flash("Too many requests. Please wait a moment.", "error")
        return redirect("/notes")

    prompt = f"""Generate comprehensive study notes on "{topic}".

Structure:
## Introduction
Brief overview of the topic

## Key Concepts
List and explain the main concepts

## Detailed Explanation
In-depth coverage with examples

## Important Formulas / Rules
(if applicable to the topic)

## Summary
Quick recap of key points

## Practice Questions
3-5 self-test questions

Use Markdown formatting. Be thorough but concise."""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        content = response.choices[0].message.content
    except Exception as e:
        logging.error(f"Notes generation failed: {e}")
        flash("Failed to generate notes. Please try again.", "error")
        return redirect("/notes")

    note = StudyNote(user_id=current_user.id, topic=topic, content=content)
    db.session.add(note)
    award_points(current_user, 2)
    check_and_award_badges(current_user)
    db.session.commit()

    flash("Notes generated successfully!", "success")
    return redirect(f"/notes/{note.id}")


@app.route("/notes/<int:note_id>")
@login_required
def note_view(note_id):
    note = StudyNote.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        abort(403)
    return render_template("note_view.html", note=note)


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def note_delete(note_id):
    note = StudyNote.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        abort(403)
    db.session.delete(note)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect("/notes")


# =================================================================
# ROUTES - PROGRESS PDF EXPORT
# =================================================================

@app.route("/export-progress")
@login_required
def export_progress():
    results = InterviewResult.query.filter_by(user_id=current_user.id).order_by(InterviewResult.date).all()
    badges = Badge.query.filter_by(user_id=current_user.id).all()
    weak_topics = get_weak_topics(current_user.id)

    total = len(results)
    scores = [r.score for r in results]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    best = max(scores) if scores else 0

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 20, "EduVoxus Progress Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"{current_user.name} | {current_user.email}", ln=True, align="C")
    pdf.cell(0, 8, f"Generated: {datetime.utcnow().strftime('%B %d, %Y')}", ln=True, align="C")
    pdf.ln(10)

    # Summary Stats
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Performance Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(95, 8, f"Total Sessions: {total}", ln=False)
    pdf.cell(95, 8, f"Average Score: {avg_score}/10", ln=True)
    pdf.cell(95, 8, f"Best Score: {best}/10", ln=False)
    pdf.cell(95, 8, f"Points: {current_user.points or 0}", ln=True)
    pdf.cell(95, 8, f"Day Streak: {current_user.streak or 0}", ln=False)
    pdf.cell(95, 8, f"Badges: {len(badges)}", ln=True)
    pdf.ln(5)

    # Session History Table
    if results:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Session History", ln=True)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(96, 165, 250)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(15, 8, "#", 1, 0, "C", True)
        pdf.cell(60, 8, "Topic", 1, 0, "C", True)
        pdf.cell(30, 8, "Mode", 1, 0, "C", True)
        pdf.cell(25, 8, "Score", 1, 0, "C", True)
        pdf.cell(40, 8, "Date", 1, 1, "C", True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        for i, r in enumerate(results[-30:], 1):  # Last 30 sessions
            pdf.cell(15, 7, str(i), 1, 0, "C")
            pdf.cell(60, 7, (r.topic or "N/A")[:30], 1, 0, "L")
            pdf.cell(30, 7, r.mode or "voice", 1, 0, "C")
            pdf.cell(25, 7, f"{r.score}/10", 1, 0, "C")
            pdf.cell(40, 7, r.date.strftime("%Y-%m-%d") if r.date else "", 1, 1, "C")
        pdf.ln(5)

    # Weak Topics
    if weak_topics:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Areas for Improvement", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for wt in weak_topics:
            pdf.cell(0, 7, f"- {wt['topic']}: Avg {wt['avg_score']}/10 ({wt['attempts']} attempts)", ln=True)
        pdf.ln(5)

    # Badges
    if badges:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Badges Earned", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for b in badges:
            pdf.cell(0, 7, f"- {b.name}: {b.description}", ln=True)

    filename = f"eduvoxus_progress_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'certificates', filename)
    pdf.output(filepath)
    return send_file(filepath, as_attachment=True, download_name=filename)


# =================================================================
# ERROR HANDLERS
# =================================================================

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access Denied"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page Not Found"), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    logging.error(f"Internal server error: {e}")
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


# =================================================================
# INITIALIZE & RUN
# =================================================================

with app.app_context():
    db.create_all()

    # Auto-migrate: add missing columns to existing tables (handles production upgrades)
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    existing_columns = {col['name'] for col in inspector.get_columns('user')}
    if 'plain_password' not in existing_columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN plain_password VARCHAR(200)'))
            conn.commit()
        logging.info("Migrated: added plain_password column to user table")

    if 'status' not in existing_columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN status VARCHAR(20) DEFAULT 'approved'"))
            conn.commit()
        logging.info("Migrated: added status column to user table")

    existing_flashcard_cols = {col['name'] for col in inspector.get_columns('flashcard')}
    for col_name, col_def in [
        ('easiness_factor', 'FLOAT DEFAULT 2.5'),
        ('interval', 'INTEGER DEFAULT 0'),
        ('review_count', 'INTEGER DEFAULT 0'),
    ]:
        if col_name not in existing_flashcard_cols:
            with db.engine.connect() as conn:
                conn.execute(text(f'ALTER TABLE flashcard ADD COLUMN {col_name} {col_def}'))
                conn.commit()
            logging.info(f"Migrated: added {col_name} column to flashcard table")

    # Admin is now created via /setup-admin on first visit

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5009))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, port=port)
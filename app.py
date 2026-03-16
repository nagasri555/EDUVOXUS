import os
import json
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from openai import OpenAI
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# -------------------------------------------------
# Load environment & OpenAI client
# -------------------------------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "eduvoxus-secret-key-2024")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eduvox.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'notes'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'certificates'), exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================================================================
# DATABASE MODELS
# =================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20), default='student')  # student, teacher, admin
    points = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('InterviewResult', backref='user', lazy=True)
    chat_messages = db.relationship('ChatHistory', backref='user', lazy=True)
    forum_posts = db.relationship('ForumPost', backref='author', lazy=True)
    forum_replies = db.relationship('ForumReply', backref='author', lazy=True)
    badges = db.relationship('Badge', backref='user', lazy=True)


class InterviewResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    topic = db.Column(db.String(100))
    score = db.Column(db.Integer)
    mode = db.Column(db.String(20), default='voice')  # quiz, voice, theory
    difficulty = db.Column(db.String(20), default='medium')
    date = db.Column(db.DateTime, default=datetime.utcnow)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    materials = db.relationship('StudyMaterial', backref='course', lazy=True)
    creator = db.relationship('User', backref='courses_created')


class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    file_type = db.Column(db.String(10))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader = db.relationship('User', backref='uploaded_materials')


class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    response = db.Column(db.Text)
    topic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    topic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replies = db.relationship('ForumReply', backref='post', lazy=True, order_by='ForumReply.created_at')


class ForumReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    is_ai = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
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
    db.session.commit()


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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
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


def get_adaptive_difficulty(user_id, topic):
    """Determine difficulty based on user's past performance on this topic."""
    results = InterviewResult.query.filter_by(
        user_id=user_id, topic=topic
    ).order_by(InterviewResult.date.desc()).limit(5).all()

    if not results:
        return "medium"

    avg_score = sum(r.score for r in results) / len(results)
    if avg_score >= 8:
        return "hard"
    elif avg_score >= 5:
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


# =================================================================
# ROUTES - AUTHENTICATION
# =================================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "error")
            return redirect("/signup")

        user = User(name=name, email=email, password=password, role='student', points=0, streak=0)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! Please login.", "success")
        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            update_streak(user)
            return redirect("/")

        flash("Invalid email or password.", "error")
        return redirect("/login")

    return render_template("login.html")


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
        msg = ContactMessage(
            name=request.form.get("name", ""),
            email=request.form.get("email", ""),
            subject=request.form.get("subject", "General Query"),
            message=request.form.get("message", "")
        )
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
    topic = request.args.get("topic", "DBMS")
    mcqs = int(request.args.get("mcqs", 5))

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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    raw = response.choices[0].message.content
    mcq_blocks = raw.strip().split("\n\n")
    questions = []

    for block in mcq_blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) < 6:
            continue

        question = lines[0].replace("QUESTION:", "").strip()
        options = [opt[3:].strip() for opt in lines[1:5]]
        answer = lines[5].replace("ANSWER:", "").strip().replace(".", "")

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

    return render_template("quiz.html", topic=topic, questions=questions)


@app.route("/quiz-submit", methods=["POST"])
@login_required
def quiz_submit():
    data = request.get_json()
    topic = data.get("topic", "Unknown")
    score = data.get("score", 0)
    total = data.get("total", 1)

    # Save result (normalize to 0-10 scale)
    normalized_score = round((score / total) * 10)
    result = InterviewResult(
        user_id=current_user.id,
        topic=topic,
        score=normalized_score,
        mode='quiz'
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
    topic = request.args.get("topic", "DBMS")
    count = int(request.args.get("count", 3))
    difficulty = request.args.get("difficulty", "medium")

    questions = generate_theory_questions(topic, count, difficulty)
    return render_template("voice.html", topic=topic, questions=questions, difficulty=difficulty)


@app.route("/voice-evaluate", methods=["POST"])
@login_required
def voice_evaluate():
    data = request.get_json()
    topic = data.get("topic")
    questions = data.get("questions")
    answers = data.get("answers")

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
        parsed = json.loads(ai_output)
        overall_score = parsed.get("overall_score", 0)

        result = InterviewResult(
            user_id=current_user.id,
            topic=topic,
            score=overall_score,
            mode='voice'
        )
        db.session.add(result)

        award_points(current_user, overall_score)
        check_and_award_badges(current_user)
        db.session.commit()

    except Exception as e:
        print("Error saving result:", e)

    return jsonify({"evaluation": ai_output})


# =================================================================
# ROUTES - THEORY QUESTIONS
# =================================================================

@app.route("/theory")
@login_required
def theory():
    topic = request.args.get("topic", "DBMS")
    count = int(request.args.get("count", 5))

    prompt = f"""
Generate EXACTLY {count} theory questions on the topic "{topic}".
- No numbering
- No repetition
- Each question on a new line
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    raw_output = response.choices[0].message.content
    questions = [
        q.strip("-\u2022 ").strip()
        for q in raw_output.split("\n")
        if q.strip()
    ]

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
    message = data.get("message", "")
    topic = data.get("topic", "General")

    if not message.strip():
        return jsonify({"error": "Empty message"}), 400

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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )

    ai_response = response.choices[0].message.content

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
        course = Course(
            title=request.form["title"],
            description=request.form["description"],
            category=request.form.get("category", "General"),
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
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'notes', filename)
        file.save(filepath)

        material = StudyMaterial(
            course_id=course_id,
            title=request.form.get("title", file.filename),
            description=request.form.get("description", ""),
            file_path=filename,
            file_type=filename.rsplit('.', 1)[1].lower(),
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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'notes', filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    abort(404)


# =================================================================
# ROUTES - DISCUSSION FORUM
# =================================================================

@app.route("/forum")
@login_required
def forum():
    page = request.args.get("page", 1, type=int)
    topic_filter = request.args.get("topic", "")
    search = request.args.get("search", "")

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
        post = ForumPost(
            user_id=current_user.id,
            title=request.form["title"],
            content=request.form["content"],
            topic=request.form.get("topic", "General")
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
        content = request.form.get("content", "").strip()
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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )

    ai_response = response.choices[0].message.content

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
        recent_users=recent_users,
        recent_results=recent_results,
        daily_active=daily_active,
        messages=messages
    )


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
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


@app.route("/admin/message/<int:msg_id>/read", methods=["POST"])
@login_required
@admin_required
def admin_mark_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return jsonify({"status": "success"})


# =================================================================
# ERROR HANDLERS
# =================================================================

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access Denied"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page Not Found"), 404


# =================================================================
# INITIALIZE & RUN
# =================================================================

with app.app_context():
    db.create_all()

    # Create default admin if not exists
    admin = User.query.filter_by(email="admin@eduvoxus.com").first()
    if not admin:
        admin = User(
            name="Admin",
            email="admin@eduvoxus.com",
            password=generate_password_hash("admin123"),
            role="admin",
            points=0,
            streak=0
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True, port=5009)
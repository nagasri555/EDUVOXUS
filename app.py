import os
from dotenv import load_dotenv
from openai import OpenAI
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import redirect

# -------------------------------------------------
# Load environment & OpenAI client
# -------------------------------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eduvox.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------------- USER MODEL ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))

# ---------------- INTERVIEW RESULT MODEL ----------------
class InterviewResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    topic = db.Column(db.String(100))
    score = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# -------------------------------------------------
# AI HELPER FUNCTION
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
        q.strip("-• ").strip()
        for q in raw_text.split("\n")
        if q.strip()
    ]

    return questions[:count]

# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return render_template("index.html")
    return redirect("/login")


@app.route("/mode")
def mode():
    return render_template("mode.html")


@app.route("/start")
def start():
    mode = request.args.get("mode")
    return render_template("start.html", mode=mode)


# ---------------- QUIZ (MCQs ONLY) ----------------
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


# ---------------- VOICE PRACTICE ----------------
@app.route("/voice")
@login_required
def voice():
    topic = request.args.get("topic", "DBMS")
    count = int(request.args.get("count", 3))
    difficulty = request.args.get("difficulty", "medium")

    questions = generate_theory_questions(topic, count, difficulty)

    return render_template(
        "voice.html",
        topic=topic,
        questions=questions,
        difficulty=difficulty
    )

# ---------------- VOICE EVALUATION (MULTI QUESTION) ----------------
@app.route("/voice-evaluate", methods=["POST"])
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
    import json

    try:
        parsed = json.loads(ai_output)
        overall_score = parsed.get("overall_score", 0)

        if current_user.is_authenticated:
            result = InterviewResult(
                user_id=current_user.id,
                topic=topic,
                score=overall_score
            )
            db.session.add(result)
            db.session.commit()

    except Exception as e:
        print("Error saving result:", e)

    return jsonify({
        "evaluation": ai_output
    })


# ---------------- THEORY QUESTIONS ----------------
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
        q.strip("-• ").strip()
        for q in raw_output.split("\n")
        if q.strip()
    ]

    return render_template(
        "theory_questions.html",
        topic=topic,
        questions=questions
    )


# ---------------- STATIC PAGES ----------------
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

# ---------------- DASH BOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():
    results = InterviewResult.query.filter_by(
        user_id=current_user.id
    ).order_by(InterviewResult.date).all()

    total_attempts = len(results)
    scores = [r.score for r in results]
    dates = [r.date.strftime("%Y-%m-%d") for r in results]

    average_score = round(sum(scores)/len(scores), 2) if scores else 0
    best_score = max(scores) if scores else 0

    return render_template(
        "dashboard.html",
        total_attempts=total_attempts,
        average_score=average_score,
        best_score=best_score,
        results=results,
        scores=scores,
        dates=dates
    )
# ---------------- authentication ----------------

from flask import redirect

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered"

        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()

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
            return redirect("/")

        return "Invalid email or password"

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

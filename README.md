<p align="center">
  <img src="static/images/hero-bg.png" alt="EduVoxus Banner" width="100%" />
</p>

<h1 align="center">EduVoxus</h1>
<h3 align="center">AI-Powered Adaptive Learning Platform with Intelligent Spaced Repetition</h3>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.1.3-black?logo=flask" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Bootstrap-5.3.2-7952B3?logo=bootstrap&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
</p>

<p align="center">
  <b>EduVoxus</b> transforms traditional learning into an intelligent, adaptive experience. <br/>
  Unlike conventional e-learning platforms that rely on pre-loaded static content, <br/>
  EduVoxus generates everything on-the-fly using AI - from quizzes and flashcards <br/>
  to study notes and voice evaluations - making it infinitely scalable across any topic.
</p>

---

## Why EduVoxus?

| Problem | How EduVoxus Solves It |
|---------|----------------------|
| Static question banks get exhausted | AI generates unlimited questions on any topic dynamically |
| One-size-fits-all difficulty | Adaptive Difficulty Algorithm adjusts based on your performance history |
| Passive video watching | Active learning through quiz, voice, theory, and flashcard modes |
| No personalized feedback | AI evaluates answers and provides strengths + improvements per question |
| Forgetting learned content | Spaced Repetition Algorithm schedules flashcard reviews at optimal intervals |
| Isolated learning | Discussion forum with AI-powered answers + community interaction |
| No motivation system | Gamification with points, streaks, badges, leaderboard, and certificates |

---

## Machine Learning Algorithms & Novel Techniques

> **EduVoxus implements 6 real ML/statistical algorithms from scratch (no sklearn/scipy) — a key differentiator from all existing e-learning platforms.**

### 1. EWMA-Based Adaptive Difficulty Engine

Unlike platforms that use simple averages or fixed level tests, EduVoxus uses **Exponential Weighted Moving Average (EWMA)** with a **variance-based consistency bonus** to adapt difficulty per-topic per-user in real time:

```
Algorithm: EWMA_AdaptiveDifficulty(user_id, topic)
-----------------------------------------------
1. Retrieve last 10 results for (user_id, topic) ordered by date ASC
2. If no history -> return MEDIUM (cold-start default)
3. Initialize: EWMA₀ = score₀
4. For each subsequent score:
       EWMAₜ = α × scoreₜ + (1 - α) × EWMAₜ₋₁     [α = 0.4]
5. Compute variance: σ² = Σ(scoreᵢ - EWMA)² / n
6. Consistency bonus:
       σ² > 4  → bonus = -0.5  (inconsistent → penalize)
       σ² < 1  → bonus = +0.5  (consistent → reward)
       else    → bonus = 0
7. adjusted = EWMA + bonus
8. Decision:
       adjusted ≥ 7.5 → HARD
       adjusted ≥ 4.5 → MEDIUM
       adjusted < 4.5 → EASY
```

**What makes it unique:** BYJU'S and Khan Academy use one-time placement tests. EduVoxus adapts **continuously per topic** — you could be "Hard" in DBMS but "Easy" in Networking simultaneously. The EWMA reacts faster to recent performance changes than simple averaging.

### 2. SM-2 SuperMemo Spaced Repetition Algorithm

Flashcard scheduling uses the **SM-2 algorithm** (the same algorithm behind Anki) — implemented from scratch with AI-generated content:

```
Algorithm: SM2_SpacedRepetition(card, user_rating)
-----------------------------------------------
Input: rating ∈ {Again(0), Hard(2), Good(4), Easy(5)}

1. Update review count: n = n + 1
2. Compute new Easiness Factor:
       EF' = EF + [0.1 - (5 - q) × (0.08 + (5 - q) × 0.02)]
       EF  = max(1.3, EF')
3. If q < 3 (failed):
       interval = 1 day (reset)
4. Else (passed):
       if n == 1: interval = 1 day
       if n == 2: interval = 6 days
       if n >= 3: interval = round(prev_interval × EF)
5. next_review = NOW + interval days

Key SM-2 properties:
  - E-Factor starts at 2.5, decreases with difficulty
  - Minimum E-Factor = 1.3 (prevents cards from disappearing)
  - Failed cards always reset to 1-day interval
  - Intervals grow exponentially for well-known cards
```

**What makes it unique:** Anki/Quizlet require users to create cards manually. EduVoxus **generates** cards via AI AND **schedules** them via SM-2 — zero manual effort with scientifically optimal review timing.

### 3. TF-IDF + Cosine Similarity Topic Recommender

A content-based recommendation engine that finds topics studied by similar users and recommends new ones:

```
Algorithm: TFIDF_TopicRecommender(user_id)
-----------------------------------------------
1. Build per-user "documents" (concatenated topic strings)
2. Tokenize: lowercase, extract alphanumeric tokens
3. Build vocabulary V from all tokens across all users
4. For each user document d:
       TF(t,d)  = count(t in d) / |d|
       IDF(t)   = log(N / (1 + df(t)))
       TF-IDF(t,d) = TF × IDF
5. Compute cosine similarity between target user and all others:
       cos(A,B) = (A · B) / (||A|| × ||B||)
6. Rank users by similarity (threshold > 0.05)
7. Collect topics from top-10 similar users not yet attempted
8. Return ranked recommendations with similarity scores
```

**What makes it unique:** No e-learning platform uses TF-IDF for topic discovery. This finds learning patterns across the user base without requiring explicit preferences.

### 4. Linear Regression Score Predictor (OLS)

Predicts a student's next score using **Ordinary Least Squares** regression on their session history:

```
Algorithm: OLS_ScorePredictor(user_id, topic?)
-----------------------------------------------
1. Retrieve chronological results (minimum 3 sessions required)
2. X = [1, 2, 3, ..., n]  (session numbers)
   Y = [s₁, s₂, s₃, ..., sₙ]  (scores)
3. Compute OLS coefficients:
       β₁ = Σ(xᵢ - x̄)(yᵢ - ȳ) / Σ(xᵢ - x̄)²
       β₀ = ȳ - β₁ × x̄
4. Predict: ŷ(n+1) = β₀ + β₁ × (n+1)    [clamped to 0-10]
5. Compute R²:
       SS_res = Σ(yᵢ - ŷᵢ)²
       SS_tot = Σ(yᵢ - ȳ)²
       R² = 1 - SS_res/SS_tot
6. Classify trend:
       β₁ > 0.2  → "Improving"
       β₁ < -0.2 → "Declining"
       else       → "Stable"
```

**What makes it unique:** Provides per-topic score trajectory predictions with statistical confidence (R²) — students can see if they're improving, stable, or declining in each subject.

### 5. K-Means Clustering for Learner Classification

Classifies all students into performance tiers using unsupervised **K-Means clustering** with **K-Means++ initialization**:

```
Algorithm: KMeans_LearnerClassifier(k=3)
-----------------------------------------------
Features per student:
  f₁ = avg_score / 10        (normalized performance)
  f₂ = 1 / (1 + variance)    (consistency metric, 0-1)

1. Initialize centroids using K-Means++:
       - First centroid: random point
       - Subsequent: probability proportional to D(x)²
2. Repeat until convergence (max 100 iterations):
       a. Assign each student to nearest centroid (Euclidean)
       b. Recompute centroids as cluster means
       c. Stop if assignments unchanged
3. Label clusters by centroid avg_score:
       Highest  → "Advanced"
       Middle   → "Intermediate"
       Lowest   → "Beginner"
4. Return tier + metrics for each student
```

**What makes it unique:** No e-learning platform uses unsupervised ML to dynamically classify learners. Tiers adjust automatically as the user population changes — no manual thresholds.

### 6. Collaborative Filtering (Pearson Correlation)

User-based collaborative filtering recommends topics by finding students with similar score patterns:

```
Algorithm: CollabFilter_Recommend(user_id)
-----------------------------------------------
1. Build user-topic score matrix M[user][topic] = avg_score
2. For each other user:
       a. Find common topics (minimum 2 required)
       b. Compute Pearson correlation:
              r = Σ(xᵢ-x̄)(yᵢ-ȳ) / √[Σ(xᵢ-x̄)² × Σ(yᵢ-ȳ)²]
       c. Keep if r > 0.1 (positively correlated)
3. For each unseen topic:
       predicted_score = Σ(rⱼ × scoreⱼ) / Σ|rⱼ|
       (weighted average across top-15 similar users)
4. Return top-N topics sorted by predicted score
```

**What makes it unique:** Implements "Students like you also studied..." — the same algorithm used by Netflix and Amazon, applied to educational topic discovery.

### 7. Multi-Modal AI Evaluation Pipeline

Voice answers go through a unique evaluation pipeline:

```
Algorithm: VoiceEvaluation(questions[], spoken_answers[])
-----------------------------------------------
1. Browser captures speech via Web Speech API (SpeechRecognition)
2. Transcript sent to server as text
3. AI evaluator prompt constructed with Q&A pairs
4. GPT-4o-mini returns structured JSON:
   {
     overall_score: 0-10,
     results: [{ score, strengths[], improvements[] }]
   }
5. Response sanitized (code fence stripping, JSON validation)
6. XSS-safe rendering via DOM textContent + esc() function
7. Score saved with gamification hooks (points, badges, streak)
```

**What makes it unique:** No e-learning platform combines speech-to-text + AI evaluation + per-question feedback in a single flow.

### 8. Token Bucket Rate Limiter

```
Algorithm: TokenBucketRateLimit(key, max_requests, window_seconds)
-----------------------------------------------
1. Maintain in-memory dict: { key -> [timestamp1, timestamp2, ...] }
2. On request:
   a. Clean timestamps older than window_seconds
   b. If len(timestamps) >= max_requests -> DENY (429)
   c. Else -> ALLOW, append current timestamp

Applied to:
  - Login:     5 requests / 60 seconds (per IP)
  - Chatbot:  15 requests / 60 seconds (per user)
  - Contact:   3 requests / 60 seconds (per IP)
  - Flashcard:  5 requests / 60 seconds (per user)
  - Notes:      5 requests / 60 seconds (per user)
```

### 9. Dynamic Badge Achievement System

```
Algorithm: BadgeEngine(user)
-----------------------------------------------
Badge Rules (evaluated after every scored activity):

  FIRST_STEP      : total_sessions >= 1
  DEDICATED       : total_sessions >= 10
  QUIZ_MASTER     : total_sessions >= 25
  PERFECT_SCORE   : any(score == 10)
  CONSISTENT      : streak >= 5 days
  CENTURY_CLUB    : points >= 100
  HALF_MILLENNIUM : points >= 500

Process:
  1. Load user's existing badges
  2. Evaluate each rule
  3. Award new badges (skip already earned)
  4. Commit to database
```

---

## Features at a Glance

### Learning Modes (6 Modes)

| Mode | Description | AI-Powered |
|------|-------------|:----------:|
| **Quiz Mode** | Interactive MCQs with instant scoring and answer review | Yes |
| **Timed Exam Mode** | Countdown timer with auto-submit, color-coded urgency | Yes |
| **Voice Practice** | Speak answers, get AI evaluation with per-question feedback | Yes |
| **Theory Questions** | Descriptive questions for deep conceptual understanding | Yes |
| **AI Flashcards** | Generate decks with flip animation + spaced repetition | Yes |
| **AI Study Notes** | Comprehensive markdown notes with print support | Yes |

### Platform Features (18 Features)

| # | Feature | ML Algorithm | Description |
|---|---------|:------------:|-------------|
| 1 | **AI Question Generation** | GPT-4o-mini | Unlimited questions on any topic dynamically |
| 2 | **EWMA Adaptive Difficulty** | EWMA | Exponentially weighted difficulty per topic with consistency bonus |
| 3 | **SM-2 Flashcards** | SM-2 SuperMemo | AI-generated flashcards with scientifically optimal review scheduling |
| 4 | **Topic Recommender** | TF-IDF + Cosine Sim | Content-based topic discovery from similar learners |
| 5 | **Score Predictor** | Linear Regression | Predicts next score with trend analysis and R² confidence |
| 6 | **Learner Classification** | K-Means (K-Means++) | Unsupervised clustering into Advanced/Intermediate/Beginner tiers |
| 7 | **Collaborative Filtering** | Pearson Correlation | "Students like you also studied..." recommendations |
| 8 | **Voice Recognition** | Web Speech API | Browser-based speech-to-text for voice practice |
| 9 | **AI Chatbot Tutor** | GPT-4o-mini | Ask any doubt, get instant AI explanations |
| 10 | **Gamification** | Rule Engine | Points, streaks, 7 badges, competitive leaderboard |
| 11 | **Discussion Forum** | - | Community Q&A with AI-powered auto-answers |
| 12 | **Course Management** | - | Teacher/admin course creation with file uploads |
| 13 | **Study Notes Generator** | GPT-4o-mini | AI generates structured markdown notes on any topic |
| 14 | **Timed Exam Mode** | - | Countdown timer with visual urgency indicators |
| 15 | **Bookmarks** | - | Save questions from any mode for later revision |
| 16 | **Certificate Generation** | - | Printable certificates for scores >= 7/10 |
| 17 | **Progress PDF Export** | FPDF2 | Download complete performance report as PDF |
| 18 | **Admin Dashboard** | - | User management, analytics, contact messages |

---

## Tech Stack

### Backend

| Technology | Purpose | Version |
|-----------|---------|---------|
| **Python** | Core language | 3.10+ |
| **Flask** | Web framework | 3.1.3 |
| **Flask-SQLAlchemy** | ORM & database management | 3.1.1 |
| **Flask-Login** | Session-based authentication | 0.6.3 |
| **SQLAlchemy** | SQL toolkit | 2.0.46 |
| **Werkzeug** | WSGI utilities, password hashing | 3.1.6 |
| **SQLite** | Embedded relational database | 3.x |
| **FPDF2** | PDF report & certificate generation | 2.8.3 |

### AI & Machine Learning

| Technology | Purpose |
|-----------|---------|
| **OpenAI GPT-4o-mini** | Question generation, answer evaluation, chatbot, notes, flashcards |
| **Web Speech API** | Browser-native speech recognition (no server-side ML needed) |
| **EWMA Adaptive Difficulty** | Exponential Weighted Moving Average for per-topic difficulty scaling |
| **SM-2 SuperMemo Algorithm** | Scientifically optimal flashcard review scheduling |
| **TF-IDF + Cosine Similarity** | Content-based topic recommendation engine |
| **Linear Regression (OLS)** | Score trend prediction and trajectory analysis |
| **K-Means Clustering (K-Means++)** | Unsupervised learner classification into performance tiers |
| **Collaborative Filtering (Pearson)** | User-based "students like you" topic recommendations |

### Frontend

| Technology | Purpose | Version |
|-----------|---------|---------|
| **Jinja2** | Server-side template engine | 3.1.6 |
| **Bootstrap** | Responsive UI framework | 5.3.2 |
| **Chart.js** | Performance data visualization | Latest |
| **Font Awesome** | Icon library | 6.4.0 |
| **marked.js** | Client-side Markdown rendering | Latest |
| **CSS3** | Glassmorphism design, flip animations, gradients | - |

### Security

| Feature | Implementation |
|---------|---------------|
| **Password Hashing** | Werkzeug `generate_password_hash` / `check_password_hash` |
| **Input Sanitization** | Regex-based topic sanitizer, length truncation |
| **XSS Prevention** | DOM `textContent`, `esc()` helper, Jinja2 auto-escaping |
| **Rate Limiting** | In-memory token bucket per IP/user |
| **Path Traversal Prevention** | `secure_filename()` + `os.path.realpath()` validation |
| **Security Headers** | X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| **UUID File Naming** | Uploaded files renamed to `uuid4.hex` to prevent enumeration |
| **Role-Based Access** | Decorator-based admin/teacher authorization |

---

## Database Architecture

```
                    +------------------+
                    |      User        |
                    |  (UserMixin)     |
                    +------------------+
                    | id (PK)          |
                    | name             |
                    | email (unique)   |
                    | password (hash)  |
                    | role             |
                    | points           |
                    | streak           |
                    | last_active      |
                    +--------+---------+
                             |
          +------------------+------------------+------------------+
          |                  |                  |                  |
+---------v------+  +--------v-------+  +------v--------+  +-----v----------+
| InterviewResult|  |  ChatHistory   |  |   ForumPost   |  |     Badge      |
+----------------+  +----------------+  +---------------+  +----------------+
| user_id (FK)   |  | user_id (FK)   |  | user_id (FK)  |  | user_id (FK)   |
| topic (idx)    |  | message        |  | title         |  | name           |
| score          |  | response       |  | content       |  | description    |
| mode           |  | topic          |  | topic (idx)   |  | icon           |
| difficulty     |  +----------------+  | replies[] --->|  +----------------+
| date (idx)     |                      +------+--------+
+----------------+                             |          +------------------+
                                        +------v--------+ |    Bookmark      |
+------------------+                    |  ForumReply   | +------------------+
|     Course       |                    +---------------+ | user_id (FK)     |
+------------------+                    | post_id (FK)  | | question         |
| title            |                    | user_id (FK)  | | answer           |
| description      |                    | content       | | topic (idx)      |
| category         |                    | is_ai         | | source           |
| created_by (FK)  |                    +---------------+ +------------------+
| materials[] ---> |
+--------+---------+  +------------------+  +------------------+
         |            | FlashcardDeck    |  |   StudyNote      |
+--------v---------+  +------------------+  +------------------+
|  StudyMaterial   |  | user_id (FK)     |  | user_id (FK)     |
+------------------+  | title            |  | topic            |
| course_id (FK)   |  | topic (idx)      |  | content (MD)     |
| title            |  | cards[] -------> |  +------------------+
| file_path        |  +--------+---------+
| file_type        |           |           +------------------+
+------------------+  +--------v---------+ | ContactMessage   |
                      |    Flashcard     | +------------------+
                      +------------------+ | name             |
                      | deck_id (FK)     | | email            |
                      | front            | | subject          |
                      | back             | | message          |
                      | difficulty (0-3) | | is_read          |
                      | easiness_factor  | +------------------+
                      | interval (SM-2)  |
                      | next_review      |
                      | review_count     |
                      +------------------+

Total: 12 Models | 45+ Columns | 15 Indexed Fields | Full Cascade Deletes
```

---

## Project Structure

```
EDUVOXUS/
|
|-- app.py                         # Main Flask application (1900+ lines, 45+ routes, 6 ML algorithms)
|-- generate_report.py             # PDF academic report generator
|-- requirements.txt               # Python dependencies
|-- .env                           # Environment variables (OPENAI_API_KEY)
|-- .gitignore                     # Git ignore rules
|-- README.md                      # This file
|
|-- instance/
|   +-- eduvox.db                  # SQLite database (auto-created)
|
|-- templates/                     # 30 Jinja2 HTML templates
|   |-- base.html                  # Base layout (navbar, orbs, scripts)
|   |-- index.html                 # Landing page with hero section
|   |-- login.html                 # Login with rate limiting
|   |-- signup.html                # Registration with validation
|   |-- mode.html                  # 6-mode learning selector
|   |-- start.html                 # Session config (topic, count, timer)
|   |-- quiz.html                  # MCQ quiz with timer + bookmarks
|   |-- voice.html                 # Voice practice with speech API
|   |-- theory_questions.html      # Theory questions with bookmarks
|   |-- chatbot.html               # AI tutor chat interface
|   |-- flashcards.html            # Flashcard deck manager
|   |-- flashcard_study.html       # Flip card study with SRS rating
|   |-- notes.html                 # AI notes generator
|   |-- note_view.html             # Rendered markdown notes
|   |-- bookmarks.html             # Saved questions browser
|   |-- recommendations.html      # ML-powered AI insights page
|   |-- dashboard.html             # Performance analytics + charts
|   |-- profile.html               # User profile + badges
|   |-- leaderboard.html           # Rankings (all-time + weekly)
|   |-- courses.html               # Course catalog
|   |-- course_new.html            # Course creation form
|   |-- course_detail.html         # Course materials + practice
|   |-- forum.html                 # Discussion forum with search
|   |-- forum_new.html             # Create discussion
|   |-- forum_post.html            # Post detail + AI answer
|   |-- certificate.html           # Printable achievement certificate
|   |-- admin.html                 # Admin analytics dashboard
|   |-- admin_users.html           # User management + pagination
|   |-- about.html                 # 15 feature cards + tech stack
|   |-- contact.html               # Contact form (AJAX)
|   +-- error.html                 # 403/404 error page
|
|-- static/
|   |-- css/
|   |   +-- style.css              # Main stylesheet (glassmorphism, responsive)
|   |-- js/
|   |   +-- main.js                # Client-side JavaScript
|   +-- images/
|       |-- hero-bg.png            # Hero section background
|       +-- about-bg.png           # About page background
|
+-- uploads/
    |-- notes/                     # Uploaded study materials (UUID-named)
    +-- certificates/              # Generated PDF reports
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Rate Limit | Description |
|--------|----------|:----------:|-------------|
| `POST` | `/signup` | - | Register new user |
| `POST` | `/login` | 5/min/IP | Authenticate user |
| `GET` | `/logout` | - | End session |

### Learning Modes
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/quiz?topic=&mcqs=&timed=&duration=` | Start quiz (optionally timed) |
| `POST` | `/quiz-submit` | Submit quiz score |
| `GET` | `/voice?topic=&count=&difficulty=` | Start voice practice |
| `POST` | `/voice-evaluate` | Evaluate spoken answers |
| `GET` | `/theory?topic=&count=` | Generate theory questions |

### AI Features
| Method | Endpoint | Rate Limit | Description |
|--------|----------|:----------:|-------------|
| `POST` | `/chatbot-ask` | 15/min/user | Ask AI tutor |
| `POST` | `/flashcards/generate` | 5/min/user | Generate flashcard deck |
| `POST` | `/flashcards/<id>/review` | - | Submit card rating |
| `POST` | `/notes/generate` | 5/min/user | Generate study notes |
| `POST` | `/forum/post/<id>/ai-answer` | - | Get AI forum answer |

### ML Recommendations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/recommendations` | ML-powered recommendations page (TF-IDF, K-Means, etc.) |
| `GET` | `/api/recommendations` | JSON API for ML recommendations |

### Bookmarks & Progress
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/bookmarks/add` | Bookmark a question |
| `POST` | `/bookmarks/<id>/delete` | Remove bookmark |
| `GET` | `/export-progress` | Download PDF report |
| `GET` | `/certificate/<id>` | View certificate (score >= 7) |

### Courses & Forum
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/courses/new` | Create course (teacher/admin) |
| `POST` | `/courses/<id>/upload` | Upload material |
| `GET` | `/download/<filename>` | Download material |
| `POST` | `/forum/new` | Create discussion post |
| `POST` | `/forum/post/<id>` | Reply to post |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin` | Admin dashboard |
| `GET` | `/admin/users` | User management (paginated) |
| `POST` | `/admin/user/<id>/role` | Change user role |
| `POST` | `/admin/message/<id>/read` | Mark message read |

---

## Competitive Comparison

| Feature | EduVoxus | BYJU'S | Khan Academy | Coursera | Duolingo | Udemy |
|---------|:--------:|:------:|:------------:|:--------:|:--------:|:-----:|
| AI Question Generation | Yes | No | No | No | No | No |
| EWMA Adaptive Difficulty | Yes | No | Partial | No | Partial | No |
| SM-2 Spaced Repetition | Yes | No | No | No | No | No |
| TF-IDF Topic Recommendations | Yes | No | No | No | No | No |
| Linear Regression Score Prediction | Yes | No | No | No | No | No |
| K-Means Learner Clustering | Yes | No | No | No | No | No |
| Collaborative Filtering | Yes | No | No | Partial | No | No |
| Voice-Based Practice | Yes | No | No | No | Yes | No |
| AI Answer Evaluation | Yes | No | No | No | No | No |
| AI Chatbot Tutor | Yes | No | No | No | No | No |
| AI Flashcards + SRS | Yes | No | No | No | Partial | No |
| AI Study Notes | Yes | No | No | No | No | No |
| Timed Exam Mode | Yes | Yes | No | No | Yes | No |
| Discussion Forum | Yes | No | No | Yes | No | Yes |
| Gamification System | Yes | Yes | Yes | Partial | Yes | No |
| Certificate Generation | Yes | Yes | Yes | Yes | Yes | Yes |
| Progress PDF Export | Yes | No | Partial | No | No | No |
| Open Source | Yes | No | No | No | No | No |
| **No Pre-Loaded Content Needed** | **Yes** | No | No | No | No | No |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- Modern web browser (Chrome/Edge recommended for voice features)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/eduvoxus.git
cd eduvoxus

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
# Create .env file with your OpenAI API key:
echo "OPENAI_API_KEY=your-api-key-here" > .env

# 6. Run the application
python app.py
```

The app will start at **http://localhost:5009**

### Default Admin Account

```
Email:    admin@eduvoxus.com
Password: admin123
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | Required | Your OpenAI API key |
| `SECRET_KEY` | `eduvoxus-secret-key-2024` | Flask session secret |
| `AI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `PORT` | `5009` | Server port |
| `FLASK_DEBUG` | `true` | Enable debug mode |

---

## Screenshots

| Home Page | Quiz Mode | AI Flashcards |
|:---------:|:---------:|:-------------:|
| Landing page with hero section | Timed MCQ quiz with bookmarks | Flip-card study with SRS |

| Dashboard | AI Tutor | Voice Practice |
|:---------:|:--------:|:--------------:|
| Performance analytics + charts | Chat-based doubt solving | Speech recognition + AI eval |

| Leaderboard | Study Notes | Forum |
|:-----------:|:-----------:|:-----:|
| Weekly + all-time rankings | AI-generated markdown notes | Community Q&A with AI answers |

---

## Architecture Highlights

```
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|   Browser        | <-> |   Flask Server   | <-> |   SQLite DB      |
|   (Frontend)     |     |   (Backend)      |     |   (Persistence)  |
|                  |     |                  |     |                  |
|  - Bootstrap 5   |     |  - 45+ Routes    |     |  - 12 Models     |
|  - Chart.js      |     |  - Auth System   |     |  - 47+ Columns   |
|  - Web Speech    |     |  - Rate Limiter  |     |  - 15 Indexes    |
|  - marked.js     |     |  - 6 ML Algos    |     |  - Cascade Del.  |
|  - CSS3 Anims    |     |  - Gamification  |     |                  |
|                  |     |                  |     |                  |
+------------------+     +--------+---------+     +------------------+
                                  |
                                  v
                         +------------------+
                         |                  |
                         |   OpenAI API     |
                         |   (GPT-4o-mini)  |
                         |                  |
                         |  - Questions     |
                         |  - Evaluation    |
                         |  - Chatbot       |
                         |  - Flashcards    |
                         |  - Study Notes   |
                         |  - Forum AI      |
                         |                  |
                         +------------------+
```

---

## Unique Selling Points (USP)

1. **6 ML Algorithms from Scratch** - EWMA, SM-2, TF-IDF, Linear Regression, K-Means, Collaborative Filtering — all implemented without sklearn/scipy.
2. **Zero Content Dependency** - No pre-loaded question banks. Works on ANY topic instantly via AI generation.
3. **Multi-Modal Learning** - 6 distinct learning modes in one platform (Quiz, Timed, Voice, Theory, Flashcards, Notes).
4. **EWMA Adaptive Difficulty** - Exponentially weighted, per-topic difficulty with consistency bonuses — far beyond simple averaging.
5. **SM-2 + AI Flashcards** - First platform to combine AI-generated flashcards with the SM-2 SuperMemo algorithm.
6. **ML-Powered Recommendations** - TF-IDF topic similarity + Collaborative Filtering ("students like you") + score trend prediction.
7. **K-Means Learner Tiers** - Unsupervised clustering automatically classifies students into Advanced/Intermediate/Beginner.
8. **Voice-to-AI Evaluation Pipeline** - Speak your answer, AI evaluates with per-question strengths and improvements.
9. **Full Gamification Stack** - Points, streaks, badges, leaderboard, certificates - all interconnected.
10. **Cross-Mode Bookmarks** - Save important questions from any mode and review them in one place.

---

## Future Scope

- Real-time collaborative study rooms with WebSocket
- Video lecture integration with AI-generated timestamps
- Multi-language support (Hindi, Spanish, French)
- Mobile app (React Native / Flutter)
- Peer-to-peer tutoring marketplace
- AI-generated mind maps and concept diagrams
- Integration with Google Classroom / Microsoft Teams
- Proctored exam mode with webcam monitoring
- Deep learning-based knowledge graph construction
- Plugin system for custom learning modules

---

## License

This project is developed as a **Final Year Academic Project**. All rights reserved.

---

<p align="center">
  Built with Python, Flask, and OpenAI | Designed for the future of education
</p>

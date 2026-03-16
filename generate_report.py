"""
EduVoxus Project Report Generator
Generates a comprehensive PDF report with project analysis,
feature comparison, and implementation details.
"""

from fpdf import FPDF
from datetime import datetime
import os


class EduVoxusReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "EduVoxus - AI-Powered E-Learning Platform | Project Report", align="C")
            self.ln(5)
            self.set_draw_color(59, 130, 246)
            self.set_line_width(0.3)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 58, 138)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(59, 130, 246)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(6)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(55, 65, 81)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_section(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(75, 85, 99)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(55, 65, 81)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(55, 65, 81)
        self.cell(8, 6, "-")
        self.multi_cell(0, 6, text)
        self.ln(1)

    def add_table(self, headers, data, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)

        # Header
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(59, 130, 246)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
        self.ln()

        # Data
        self.set_font("Helvetica", "", 9)
        self.set_text_color(55, 65, 81)
        fill = False
        for row in data:
            if self.get_y() > 260:
                self.add_page()
                self.set_font("Helvetica", "B", 9)
                self.set_fill_color(59, 130, 246)
                self.set_text_color(255, 255, 255)
                for i, h in enumerate(headers):
                    self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("Helvetica", "", 9)
                self.set_text_color(55, 65, 81)

            if fill:
                self.set_fill_color(240, 245, 255)
            else:
                self.set_fill_color(255, 255, 255)

            for i, cell in enumerate(row):
                self.cell(col_widths[i], 7, str(cell), border=1, fill=True, align="C")
            self.ln()
            fill = not fill


def generate_report():
    pdf = EduVoxusReport()
    pdf.alias_nb_pages()

    # ===================== COVER PAGE =====================
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 15, "EDUVOXUS", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 10, "AI-Powered E-Learning Platform", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(55, 65, 81)
    pdf.cell(0, 10, "Final Year Project Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(75, 85, 99)
    info_lines = [
        "Project Type: Web Application (Full Stack)",
        "Technology: Flask + OpenAI GPT-4 + SQLite + Bootstrap",
        "Domain: Education Technology (EdTech)",
        f"Date: {datetime.now().strftime('%B %d, %Y')}",
    ]
    for line in info_lines:
        pdf.cell(0, 8, line, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(30)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 8, "Generated automatically by EduVoxus Report Generator", align="C")

    # ===================== TABLE OF CONTENTS =====================
    pdf.add_page()
    pdf.chapter_title("Table of Contents")
    pdf.ln(5)

    toc = [
        ("1.", "Abstract", 3),
        ("2.", "Introduction", 3),
        ("3.", "Problem Statement", 4),
        ("4.", "Objectives", 4),
        ("5.", "System Architecture & Technology Stack", 5),
        ("6.", "Database Design", 6),
        ("7.", "Features Implemented", 7),
        ("8.", "Comparison with Existing Platforms", 10),
        ("9.", "Unique Selling Points (USP)", 11),
        ("10.", "Screenshots / Module Descriptions", 12),
        ("11.", "API Endpoints", 14),
        ("12.", "Security Measures", 15),
        ("13.", "Future Enhancements", 15),
        ("14.", "Viva Preparation Guide", 16),
        ("15.", "Conclusion", 17),
        ("16.", "References", 17),
    ]

    for num, title, page in toc:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(12, 8, num)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(140, 8, title)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(59, 130, 246)
        pdf.cell(0, 8, str(page), align="R", new_x="LMARGIN", new_y="NEXT")

    # ===================== 1. ABSTRACT =====================
    pdf.add_page()
    pdf.chapter_title("1. Abstract")
    pdf.body_text(
        "EduVoxus is an AI-powered e-learning platform designed to transform passive learning into "
        "active, intelligent engagement. Unlike traditional platforms that rely on static, pre-loaded "
        "content, EduVoxus leverages OpenAI's GPT-4 model to dynamically generate questions, evaluate "
        "spoken answers, and provide personalized learning recommendations in real-time."
    )
    pdf.body_text(
        "The platform offers multiple learning modes including MCQ quizzes, voice-based practice with "
        "speech recognition, theory question generation, and an AI-powered chatbot for instant doubt "
        "resolution. It incorporates gamification elements (points, badges, streaks, leaderboards), "
        "role-based access control (student/teacher/admin), course management with study material "
        "uploads, a community discussion forum with AI-assisted answers, and automatic certificate "
        "generation for high achievers."
    )
    pdf.body_text(
        "The system provides adaptive difficulty adjustment based on user performance history, "
        "identifies weak topics, and offers personalized recommendations - making it a comprehensive, "
        "intelligent learning companion. Built with Flask, SQLAlchemy, Bootstrap 5, and Chart.js, "
        "EduVoxus demonstrates full-stack development capabilities with AI integration."
    )
    pdf.body_text(
        "Keywords: AI-powered learning, Natural Language Processing, Speech Recognition, "
        "Adaptive Learning, Gamification, Flask, OpenAI GPT-4, EdTech"
    )

    # ===================== 2. INTRODUCTION =====================
    pdf.chapter_title("2. Introduction")
    pdf.body_text(
        "The education sector has undergone significant digital transformation, especially "
        "post-pandemic. E-learning platforms have become essential tools for students worldwide. "
        "However, most existing platforms suffer from key limitations: they rely on pre-built, "
        "static content that requires constant manual updates, and they lack truly interactive, "
        "AI-driven learning experiences."
    )
    pdf.body_text(
        "EduVoxus addresses these gaps by introducing a platform where content is generated "
        "on-the-fly using artificial intelligence. Students can practice any topic without "
        "the platform needing pre-loaded question banks. The AI adapts to each student's "
        "performance level, making learning personalized and efficient."
    )
    pdf.body_text(
        "The platform also addresses the challenge of interview preparation by providing "
        "voice-based practice where students can speak their answers and receive AI-powered "
        "evaluation with specific feedback on strengths and areas for improvement. This feature "
        "is particularly unique and not found in major e-learning platforms."
    )

    # ===================== 3. PROBLEM STATEMENT =====================
    pdf.add_page()
    pdf.chapter_title("3. Problem Statement")
    pdf.body_text(
        "Existing e-learning platforms face several challenges that EduVoxus aims to solve:"
    )
    problems = [
        "Static Content Dependency - Platforms like BYJU'S and Coursera require massive teams to create and update content. Any new topic requires manual content creation.",
        "Lack of Voice-Based Practice - No major platform offers AI-evaluated voice practice for interview/exam preparation.",
        "One-Size-Fits-All Approach - Most platforms don't adapt difficulty based on individual student performance.",
        "Limited Instant Doubt Resolution - Students often have to wait for instructor responses or search through forums manually.",
        "No Dynamic Question Generation - Question banks are finite and can be memorized, reducing their effectiveness over time.",
        "Missing Gamification - Many platforms lack engagement mechanics like points, badges, and leaderboards.",
        "No Integrated Community - Learning, practice, and discussion are often on separate platforms.",
    ]
    for p in problems:
        pdf.bullet(p)

    # ===================== 4. OBJECTIVES =====================
    pdf.chapter_title("4. Objectives")
    objectives = [
        "Build an AI-powered platform that generates questions dynamically on ANY topic using GPT-4.",
        "Implement voice-based practice with browser speech recognition and AI evaluation.",
        "Create an AI chatbot (doubt solver) for instant educational assistance.",
        "Develop adaptive difficulty that adjusts based on user performance history.",
        "Implement gamification with points, badges, streaks, and a competitive leaderboard.",
        "Build role-based access control with Student, Teacher, and Admin roles.",
        "Create a course management system with study material upload/download capabilities.",
        "Develop a community discussion forum with AI-assisted answers.",
        "Implement automatic certificate generation for high-scoring students.",
        "Provide comprehensive performance analytics with weak topic identification and recommendations.",
        "Build an admin dashboard for platform-wide analytics and user management.",
    ]
    for o in objectives:
        pdf.bullet(o)

    # ===================== 5. SYSTEM ARCHITECTURE =====================
    pdf.add_page()
    pdf.chapter_title("5. System Architecture & Technology Stack")

    pdf.section_title("5.1 Architecture Overview")
    pdf.body_text(
        "EduVoxus follows a monolithic MVC (Model-View-Controller) architecture pattern "
        "built on the Flask micro-framework. The system consists of: "
        "Backend (Flask + Python), AI Layer (OpenAI API), Database (SQLite + SQLAlchemy ORM), "
        "Frontend (Jinja2 templates + Bootstrap 5 + Chart.js), and File Storage (local filesystem)."
    )

    pdf.section_title("5.2 Technology Stack")
    tech_data = [
        ["Backend Framework", "Flask 3.1.3", "Lightweight, flexible Python web framework"],
        ["AI Engine", "OpenAI GPT-4o-mini", "Question generation, answer evaluation, chatbot"],
        ["Database", "SQLite + SQLAlchemy", "Lightweight DB with powerful ORM"],
        ["Authentication", "Flask-Login", "Session-based user authentication"],
        ["Frontend", "Bootstrap 5.3.2", "Responsive CSS framework"],
        ["Charts", "Chart.js", "Interactive data visualization"],
        ["Icons", "Font Awesome 6.4", "Scalable vector icons"],
        ["Voice", "Web Speech API", "Browser-native speech recognition"],
        ["Password Security", "Werkzeug", "PBKDF2-SHA256 password hashing"],
        ["Template Engine", "Jinja2", "Server-side HTML rendering"],
        ["PDF Generation", "fpdf2", "Certificate and report generation"],
    ]
    pdf.add_table(
        ["Component", "Technology", "Purpose"],
        tech_data,
        [40, 50, 100]
    )

    pdf.ln(5)
    pdf.section_title("5.3 Data Flow")
    pdf.body_text(
        "1. User authenticates via Flask-Login session management.\n"
        "2. User selects a learning mode (Quiz/Voice/Theory/Chatbot).\n"
        "3. Flask backend sends prompt to OpenAI API for content generation.\n"
        "4. AI-generated content is rendered via Jinja2 templates.\n"
        "5. User interacts with content (answers questions, speaks, asks doubts).\n"
        "6. Responses are evaluated by AI, scores saved to SQLite.\n"
        "7. Points/badges are awarded, streak is updated.\n"
        "8. Dashboard displays analytics using Chart.js visualizations."
    )

    # ===================== 6. DATABASE DESIGN =====================
    pdf.add_page()
    pdf.chapter_title("6. Database Design")

    pdf.section_title("6.1 Entity-Relationship Overview")
    pdf.body_text(
        "The database consists of 8 interconnected tables designed to support all platform "
        "features including multi-role users, learning results, courses, forum, chat, badges, "
        "and contact messages."
    )

    models = [
        ("User", "id, name, email, password, role, points, streak, last_active, created_at"),
        ("InterviewResult", "id, user_id(FK), topic, score, mode, difficulty, date"),
        ("Course", "id, title, description, category, created_by(FK), created_at"),
        ("StudyMaterial", "id, course_id(FK), title, description, file_path, file_type, uploaded_by(FK), uploaded_at"),
        ("ChatHistory", "id, user_id(FK), message, response, topic, created_at"),
        ("ForumPost", "id, user_id(FK), title, content, topic, created_at"),
        ("ForumReply", "id, post_id(FK), user_id(FK), content, is_ai, created_at"),
        ("Badge", "id, user_id(FK), name, description, icon, earned_at"),
        ("ContactMessage", "id, name, email, subject, message, created_at, is_read"),
    ]

    pdf.add_table(
        ["Model Name", "Fields"],
        models,
        [40, 150]
    )

    pdf.ln(5)
    pdf.section_title("6.2 Relationships")
    relationships = [
        "User 1:N InterviewResult (one user has many results)",
        "User 1:N ChatHistory (one user has many chat messages)",
        "User 1:N ForumPost (one user can create many posts)",
        "User 1:N ForumReply (one user can write many replies)",
        "User 1:N Badge (one user can earn many badges)",
        "User 1:N Course (one user/teacher can create many courses)",
        "Course 1:N StudyMaterial (one course has many materials)",
        "ForumPost 1:N ForumReply (one post has many replies)",
    ]
    for r in relationships:
        pdf.bullet(r)

    # ===================== 7. FEATURES IMPLEMENTED =====================
    pdf.add_page()
    pdf.chapter_title("7. Features Implemented")

    features = [
        ("7.1 Authentication & Authorization", [
            "User registration with form validation and duplicate email check",
            "Login with password hashing (PBKDF2-SHA256 via Werkzeug)",
            "Session management with Flask-Login",
            "Role-based access control: Student, Teacher, Admin",
            "Admin-only routes with custom decorator (@admin_required)",
            "Flash messages for user feedback",
        ]),
        ("7.2 AI-Powered Quiz Mode", [
            "Dynamic MCQ generation using GPT-4o-mini",
            "Configurable question count (3, 5, or 10)",
            "Real-time answer checking with instant scoring",
            "Visual progress circle showing accuracy percentage",
            "Detailed answer review with correct/wrong highlighting",
            "Score saved to database and points awarded",
        ]),
        ("7.3 Voice-Based Practice", [
            "AI-generated interview/theory questions with difficulty levels",
            "Browser-based speech recognition (Web Speech API)",
            "Real-time audio transcription to text",
            "AI evaluation of spoken answers using GPT-4",
            "Per-question scoring with strengths and improvement areas",
            "Overall score calculation and database persistence",
        ]),
        ("7.4 Theory Questions Mode", [
            "AI-generated descriptive questions on any topic",
            "Configurable question count",
            "Clean display with ordered list",
            "Points awarded for completing theory practice",
        ]),
        ("7.5 AI Tutor Chatbot", [
            "Real-time AI-powered doubt solving on any topic",
            "Topic-specific context for better answers",
            "Chat history persistence in database",
            "Markdown-like formatting in responses",
            "Quick topic selector chips for common subjects",
            "Points awarded for asking questions (encourages engagement)",
        ]),
        ("7.6 Gamification System", [
            "Points system: earn points for quizzes, voice practice, theory, chatbot usage",
            "Daily streak tracking with automatic reset",
            "7 achievement badges: First Step, Dedicated Learner, Quiz Master, Perfect Score, Consistent, Century Club, Half Millennium",
            "Competitive leaderboard with All-Time and Weekly views",
            "Badge display on profile and dashboard",
        ]),
        ("7.7 Discussion Forum", [
            "Create discussion posts with topic categorization",
            "Reply system for community interaction",
            "AI-generated answers on any forum question",
            "Search and filter by topic",
            "Pagination for large number of posts",
            "Points awarded for posting and replying",
        ]),
        ("7.8 Course Management", [
            "Create courses with title, description, and category",
            "Upload study materials (PDF, DOC, PPT, images)",
            "Download materials for offline study",
            "Role-based upload permissions (teachers/admins only)",
            "Quick practice links from course pages",
        ]),
        ("7.9 Certificate Generation", [
            "Automatic certificate for scores 7/10 and above",
            "Professional certificate design with borders and signatures",
            "Unique certificate ID for verification",
            "Print-ready layout with CSS @media print",
        ]),
        ("7.10 Performance Dashboard", [
            "Total attempts, average score, best score statistics",
            "Points and streak display",
            "Score trend visualization with Chart.js line chart",
            "Complete practice history with mode and score badges",
            "Weak topic identification with average scores",
            "Topic-wise breakdown with progress bars",
            "Certificate links for qualifying scores",
            "Badge showcase",
        ]),
        ("7.11 Adaptive Learning", [
            "AI analyzes last 5 attempts on a topic to suggest difficulty",
            "Weak topic detection (topics with average score below 6)",
            "Personalized practice recommendations on dashboard",
        ]),
        ("7.12 Admin Dashboard", [
            "Platform-wide statistics (users, sessions, courses, posts, messages)",
            "Recent user registrations table",
            "Recent activity feed",
            "Contact message management with mark-as-read",
            "User management with role assignment (student/teacher/admin)",
        ]),
        ("7.13 User Profile", [
            "Personal profile page with avatar and stats",
            "Badge collection display",
            "Topic distribution chart",
            "Account information display",
        ]),
        ("7.14 Contact System", [
            "Contact form with backend persistence to database",
            "Subject categorization (General, Feedback, Technical Issue, Feature Request)",
            "Admin notification for unread messages",
            "AJAX submission with success feedback",
        ]),
    ]

    for title, items in features:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.section_title(title)
        for item in items:
            pdf.bullet(item)
        pdf.ln(3)

    # ===================== 8. COMPARISON =====================
    pdf.add_page()
    pdf.chapter_title("8. Comparison with Existing Platforms")

    pdf.body_text(
        "The following table compares EduVoxus with major e-learning platforms across key features:"
    )

    comparison_headers = ["Feature", "BYJU'S", "Coursera", "Udemy", "Khan Acad.", "EduVoxus"]
    comparison_data = [
        ["Video Lectures", "Yes", "Yes", "Yes", "Yes", "No"],
        ["Live Classes", "Yes", "Some", "No", "No", "No"],
        ["AI Question Gen.", "No", "No", "No", "No", "YES"],
        ["Voice Practice", "No", "No", "No", "No", "YES"],
        ["AI Chatbot", "No", "No", "No", "No", "YES"],
        ["Adaptive Difficulty", "Yes", "No", "No", "Yes", "YES"],
        ["Dashboard", "Yes", "Yes", "Basic", "Yes", "YES"],
        ["Gamification", "Yes", "Certs", "Certs", "Badges", "YES"],
        ["Multi-role", "Yes", "Yes", "Yes", "Yes", "YES"],
        ["Discussion Forum", "Limited", "Forums", "Q&A", "No", "YES"],
        ["Course Mgmt", "Yes", "Yes", "Yes", "Yes", "YES"],
        ["Certificates", "Yes", "Yes", "Yes", "No", "YES"],
        ["File Upload", "Internal", "Yes", "Yes", "No", "YES"],
        ["Leaderboard", "No", "No", "No", "No", "YES"],
        ["Free & Open", "Paid", "Freemium", "Paid", "Free", "FREE"],
    ]

    pdf.add_table(
        comparison_headers,
        comparison_data,
        [35, 25, 25, 25, 25, 25]
    )

    # ===================== 9. USP =====================
    pdf.add_page()
    pdf.chapter_title("9. Unique Selling Points (USP)")

    usps = [
        ("Dynamic AI Content Generation", "Unlike BYJU'S or Coursera which need pre-built question banks, EduVoxus generates unlimited questions on ANY topic in real-time using GPT-4. Zero content dependency."),
        ("Voice-Based Answer Evaluation", "The only platform that combines speech recognition with AI evaluation for interview preparation. Students speak their answers and get detailed feedback."),
        ("AI Tutor Chatbot", "Instant doubt resolution without waiting for human instructors. Available 24/7 for any topic."),
        ("Adaptive Difficulty", "The system analyzes past performance and automatically suggests appropriate difficulty levels, creating a personalized learning path."),
        ("Integrated Gamification", "Points, badges, streaks, and leaderboards create intrinsic motivation. Students compete and earn recognition."),
        ("AI-Powered Forum", "Discussion forum with one-click AI answer generation - combining community learning with AI assistance."),
        ("Zero Content Cost", "No need to hire content creators or record videos. The AI generates everything dynamically, making scaling virtually free."),
    ]

    for title, desc in usps:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.sub_section(title)
        pdf.body_text(desc)

    # ===================== 10. MODULE DESCRIPTIONS =====================
    pdf.add_page()
    pdf.chapter_title("10. Module Descriptions")

    modules = [
        ("Authentication Module", "Handles user registration, login, logout, and session management. Uses Werkzeug for secure password hashing (PBKDF2-SHA256) and Flask-Login for session handling. Supports three roles: student, teacher, admin."),
        ("Quiz Module", "Generates MCQ questions via OpenAI API with configurable count. Parses structured AI output into question/options/answer format. Client-side scoring with AJAX submission to backend for persistence."),
        ("Voice Practice Module", "Generates interview questions with difficulty levels. Uses Web Speech API for browser-native speech recognition. Transcribed answers are sent to GPT-4 for evaluation with per-question scoring."),
        ("Theory Module", "Generates descriptive theory questions for self-study. Awards participation points. Simple, distraction-free interface."),
        ("AI Chatbot Module", "Full chat interface with topic selection. Sends user messages to GPT-4 with educational context. Stores conversation history. Supports markdown formatting."),
        ("Gamification Module", "Tracks points across all activities. Manages daily streaks with auto-reset. Evaluates 7 badge rules on each activity. Populates leaderboard with weekly and all-time rankings."),
        ("Forum Module", "CRUD operations for discussion posts and replies. Topic-based filtering and search. AI answer generation via OpenAI. Pagination for scalability."),
        ("Course Management Module", "CRUD for courses. File upload with type validation and secure filename handling. Download endpoint with file serving. Role-based access for uploads."),
        ("Certificate Module", "HTML-based certificate with professional layout. Print-ready with CSS @media print rules. Unique certificate ID generation. Score threshold validation (7/10 minimum)."),
        ("Dashboard Module", "Aggregates user performance data. Chart.js visualization for score trends. Weak topic detection algorithm. Topic-wise breakdown with progress bars."),
        ("Admin Module", "Platform-wide statistics. User management with role assignment. Contact message management. Recent activity monitoring."),
        ("Profile Module", "User information display. Badge collection. Topic distribution. Activity statistics."),
    ]

    for title, desc in modules:
        if pdf.get_y() > 245:
            pdf.add_page()
        pdf.sub_section(title)
        pdf.body_text(desc)

    # ===================== 11. API ENDPOINTS =====================
    pdf.add_page()
    pdf.chapter_title("11. API Endpoints")

    endpoints = [
        ["GET /", "Home page (auth required)", "Student"],
        ["GET/POST /signup", "User registration", "Public"],
        ["GET/POST /login", "User authentication", "Public"],
        ["GET /logout", "Session logout", "Auth"],
        ["GET /mode", "Learning mode selection", "Auth"],
        ["GET /start", "Session configuration", "Auth"],
        ["GET /quiz", "MCQ quiz interface", "Auth"],
        ["POST /quiz-submit", "Save quiz score (JSON)", "Auth"],
        ["GET /voice", "Voice practice page", "Auth"],
        ["POST /voice-evaluate", "AI answer evaluation", "Auth"],
        ["GET /theory", "Theory questions", "Auth"],
        ["GET /chatbot", "AI chatbot page", "Auth"],
        ["POST /chatbot-ask", "Send message to AI", "Auth"],
        ["GET /dashboard", "Performance dashboard", "Auth"],
        ["GET /leaderboard", "Rankings page", "Auth"],
        ["GET /courses", "Course listing", "Auth"],
        ["GET/POST /courses/new", "Create course", "Teacher/Admin"],
        ["GET /courses/<id>", "Course detail", "Auth"],
        ["POST /courses/<id>/upload", "Upload material", "Teacher/Admin"],
        ["GET /download/<file>", "Download material", "Auth"],
        ["GET /forum", "Forum listing", "Auth"],
        ["GET/POST /forum/new", "Create post", "Auth"],
        ["GET/POST /forum/post/<id>", "Post detail + reply", "Auth"],
        ["POST /forum/post/<id>/ai-answer", "AI answer", "Auth"],
        ["GET /certificate/<id>", "Generate certificate", "Auth"],
        ["GET /profile", "User profile", "Auth"],
        ["GET /admin", "Admin dashboard", "Admin"],
        ["GET /admin/users", "User management", "Admin"],
        ["POST /admin/user/<id>/role", "Change user role", "Admin"],
        ["GET/POST /contact", "Contact form", "Public"],
    ]

    pdf.add_table(
        ["Endpoint", "Description", "Access"],
        endpoints,
        [55, 95, 40]
    )

    # ===================== 12. SECURITY =====================
    pdf.add_page()
    pdf.chapter_title("12. Security Measures")

    security = [
        "Password Hashing: All passwords are hashed using Werkzeug's PBKDF2-SHA256 algorithm. Plain text passwords are never stored.",
        "Session Management: Flask-Login handles secure session cookies with configurable expiry.",
        "SQL Injection Prevention: SQLAlchemy ORM parameterizes all queries, preventing SQL injection attacks.",
        "CSRF Protection: Flask's session-based approach with secret key provides implicit CSRF protection.",
        "File Upload Security: Werkzeug's secure_filename() sanitizes uploaded filenames. File type validation restricts uploads to allowed extensions only.",
        "Role-Based Access Control: Custom @admin_required decorator restricts sensitive routes. Teacher-only routes check user role before allowing access.",
        "Environment Variables: API keys and secret keys are stored in .env files, not hardcoded in source.",
        "Input Validation: Server-side validation on all form inputs. AI prompt injection is mitigated through structured prompts.",
        "Max Upload Size: 16MB file upload limit prevents denial-of-service through large file uploads.",
    ]
    for s in security:
        pdf.bullet(s)

    # ===================== 13. FUTURE ENHANCEMENTS =====================
    pdf.chapter_title("13. Future Enhancements")

    enhancements = [
        "Email OTP Authentication - Password reset via email OTP for better account security.",
        "Payment Gateway (Razorpay/Stripe) - Premium courses with subscription tiers.",
        "WebSocket Real-Time Quiz - Live multiplayer quiz battles with timers.",
        "Video Lecture Integration - Upload and stream video content within courses.",
        "Progressive Web App (PWA) - Installable app experience without native development.",
        "Multi-Language Support (i18n) - Hindi, Tamil, Telugu language support.",
        "Docker Deployment - Containerized deployment with docker-compose.",
        "PostgreSQL Migration - Production-grade database for scalability.",
        "Redis Caching - Cache AI responses for frequently asked topics.",
        "Rate Limiting - API call throttling to prevent abuse and control costs.",
        "Export Reports - PDF/CSV export of dashboard analytics.",
        "Dark/Light Theme Toggle - User-selectable theme preference.",
    ]
    for e in enhancements:
        pdf.bullet(e)

    # ===================== 14. VIVA GUIDE =====================
    pdf.add_page()
    pdf.chapter_title("14. Viva Preparation Guide")

    pdf.body_text("Below are common viva questions with suggested answers based on this project:")

    viva = [
        ("Q: Why Flask and not Django?",
         "A: Flask is a lightweight micro-framework that gives more control over components. For this project's scope, Flask provides sufficient features without Django's overhead. Flask's flexibility allowed us to choose our own ORM (SQLAlchemy), auth system (Flask-Login), and template engine."),
        ("Q: Why SQLite and not MySQL/PostgreSQL?",
         "A: SQLite was chosen for development simplicity - it requires no separate server setup. In production, we would migrate to PostgreSQL using SQLAlchemy's database-agnostic ORM, requiring only a connection string change."),
        ("Q: How does the AI question generation work?",
         "A: We send structured prompts to OpenAI's GPT-4o-mini model via their API. The prompt specifies exact format (QUESTION/OPTIONS/ANSWER), count, topic, and difficulty. We parse the structured response into Python objects for rendering."),
        ("Q: How do you handle API key security?",
         "A: API keys are stored in a .env file loaded via python-dotenv. The .env file is in .gitignore and never committed to version control. In production, we'd use environment variables or a secrets manager."),
        ("Q: What happens if the OpenAI API is down?",
         "A: The system has fallback error handling that shows a retry message to users. In production, we could add cached questions, alternative AI providers, or a pre-generated question bank as fallback."),
        ("Q: How is voice evaluation accurate?",
         "A: We use structured evaluation prompts that instruct GPT-4 to score each answer on specific criteria. The AI provides per-question scores, strengths, and improvements. While not perfect, it provides consistent and useful feedback."),
        ("Q: How would you scale this for 10,000 users?",
         "A: Migrate to PostgreSQL, add Redis caching for common topics, implement async task queues (Celery) for AI calls, use a load balancer (Nginx), cache AI responses, and implement rate limiting."),
        ("Q: What's your unique contribution vs existing platforms?",
         "A: Three key USPs: (1) Dynamic AI content generation for any topic, (2) Voice-based practice with AI evaluation, (3) Integrated AI chatbot for instant doubt resolution. No major platform offers all three."),
        ("Q: How do you prevent cheating in quizzes?",
         "A: Questions are randomly generated each time (no memorization possible), answer keys are stored in hidden inputs that could be moved server-side, and each quiz session is unique per user."),
        ("Q: Explain the gamification system.",
         "A: Points are earned for every activity (quizzes, voice practice, chatbot usage, forum posts). 7 badges are awarded based on milestones (first session, 10 sessions, perfect score, etc.). Daily streaks track consecutive learning days. The leaderboard shows weekly and all-time rankings."),
    ]

    for q, a in viva:
        if pdf.get_y() > 230:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 58, 138)
        pdf.multi_cell(190, 6, q)
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(55, 65, 81)
        pdf.multi_cell(190, 6, a)
        pdf.ln(5)

    # ===================== 15. CONCLUSION =====================
    pdf.add_page()
    pdf.chapter_title("15. Conclusion")
    pdf.body_text(
        "EduVoxus successfully demonstrates that AI can fundamentally transform the e-learning "
        "experience. By integrating OpenAI's GPT-4 with a full-stack web application, we created "
        "a platform that generates unlimited educational content on-the-fly, evaluates spoken "
        "answers, resolves doubts instantly, and adapts to each student's learning pace."
    )
    pdf.body_text(
        "The project showcases proficiency in multiple areas of software engineering: "
        "full-stack web development (Flask + Bootstrap), database design (SQLAlchemy ORM with "
        "8 interconnected models), AI integration (OpenAI API with structured prompting), "
        "authentication and authorization (role-based access control), file handling (secure "
        "uploads), real-time features (speech recognition, AJAX), data visualization (Chart.js), "
        "and gamification design."
    )
    pdf.body_text(
        "With 14 major features, 30+ API endpoints, 9 database models, and 20+ pages, "
        "EduVoxus represents a comprehensive, production-quality e-learning platform that "
        "stands apart from existing solutions through its unique AI-first approach."
    )

    # ===================== 16. REFERENCES =====================
    pdf.chapter_title("16. References")

    references = [
        "Flask Documentation - https://flask.palletsprojects.com/",
        "OpenAI API Documentation - https://platform.openai.com/docs/",
        "SQLAlchemy Documentation - https://docs.sqlalchemy.org/",
        "Flask-Login Documentation - https://flask-login.readthedocs.io/",
        "Bootstrap 5 Documentation - https://getbootstrap.com/docs/5.3/",
        "Chart.js Documentation - https://www.chartjs.org/docs/",
        "Web Speech API - https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API",
        "Font Awesome Icons - https://fontawesome.com/",
        "fpdf2 Documentation - https://py-pdf.github.io/fpdf2/",
        "Werkzeug Security - https://werkzeug.palletsprojects.com/en/stable/utils/#module-werkzeug.security",
    ]
    for i, ref in enumerate(references, 1):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(55, 65, 81)
        pdf.multi_cell(0, 6, f"[{i}] {ref}")
        pdf.ln(1)

    # ===================== SAVE =====================
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EduVoxus_Project_Report.pdf")
    pdf.output(output_path)
    print(f"\nReport generated successfully!")
    print(f"Location: {output_path}")
    print(f"Pages: {pdf.page_no()}")
    return output_path


if __name__ == "__main__":
    generate_report()

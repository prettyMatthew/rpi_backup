import os
import sqlite3
import base64
from io import BytesIO
from functools import wraps

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    g,
    render_template_string,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from markdown import markdown
from PIL import Image
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-please"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "wiki.db")
os.makedirs(INSTANCE_DIR, exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "로그인이 필요합니다."
login_manager.login_message_category = "warning"
login_manager.init_app(app)

CATEGORIES = [
    "전투기", "폭격기", "수송기", "조기경보기", "공중급유기", "정찰기", "훈련기",
    "무인기", "항공모함", "핵잠수함", "탄도미사일", "순항미사일", "방공체계",
    "우주자산", "기타 전략자산",
]

SPEC_FIELDS = [
    ("manufacturer", "제조사"),
    ("country", "국가"),
    ("role", "주요 임무"),
    ("first_flight", "초도비행"),
    ("introduced", "실전배치"),
    ("status", "운용 상태"),
    ("crew", "승무원"),
    ("length", "길이"),
    ("wingspan", "날개폭"),
    ("height", "높이"),
    ("max_speed", "최대 속도"),
    ("range_km", "항속거리"),
    ("combat_radius", "전투행동반경"),
    ("service_ceiling", "실용상승한도"),
    ("engine", "엔진"),
    ("powerplant", "출력"),
    ("armament", "무장"),
    ("notes", "비고"),
]

BASE_HTML = r'''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title or 'Air Asset Wiki' }}</title>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: Arial, sans-serif; background: #f4f7fb; color: #1f2937; }
        .topbar { background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 14px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.12); }
        .container { width: min(1180px, 94%); margin: 0 auto; }
        .topbar-inner { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
        .logo { color: white; text-decoration: none; font-size: 24px; font-weight: 700; }
        .nav-links { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .nav-links a, .nav-links span { color: white; text-decoration: none; padding: 8px 10px; border-radius: 10px; font-size: 14px; }
        .nav-links a:hover { background: rgba(255,255,255,0.1); }
        .main { padding: 24px 0 40px; }
        .card { background: white; border-radius: 18px; box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08); padding: 22px; margin-bottom: 20px; }
        .hero { padding: 26px; background: linear-gradient(135deg, #eff6ff, #ffffff); border: 1px solid #dbeafe; }
        h1, h2, h3 { margin-top: 0; }
        .search-grid { display: grid; grid-template-columns: 1.4fr 240px 140px; gap: 12px; }
        .asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 18px; }
        .asset-card { background: white; border-radius: 18px; overflow: hidden; box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08); border: 1px solid #e5e7eb; }
        .thumb { width: 100%; height: 190px; object-fit: cover; display: block; background: #dbe4f0; }
        .thumb-placeholder { width: 100%; height: 190px; display: flex; align-items: center; justify-content: center; background: #e2e8f0; color: #64748b; font-weight: 700; }
        .asset-body { padding: 16px; }
        .badge { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #dbeafe; color: #1d4ed8; font-size: 12px; font-weight: 700; margin-bottom: 8px; }
        .muted { color: #64748b; }
        input, select, textarea, button { width: 100%; padding: 12px 14px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 15px; }
        textarea { resize: vertical; }
        label { display: block; margin: 14px 0 8px; font-weight: 700; }
        button { background: #2563eb; color: white; border: none; font-weight: 700; cursor: pointer; margin-top: 18px; }
        .btn-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .btn-link, .btn-danger { display: inline-block; padding: 10px 14px; text-decoration: none; color: white; border-radius: 12px; font-size: 14px; border: none; cursor: pointer; width: auto; }
        .btn-link { background: #334155; }
        .btn-danger { background: #dc2626; }
        .flash { padding: 12px 14px; border-radius: 12px; margin-bottom: 12px; font-weight: 600; }
        .flash-success { background: #dcfce7; color: #166534; }
        .flash-danger { background: #fee2e2; color: #991b1b; }
        .flash-warning { background: #fef3c7; color: #92400e; }
        .flash-info { background: #dbeafe; color: #1e40af; }
        .narrow { max-width: 520px; margin: 30px auto; }
        .detail-image { width: 100%; max-width: 760px; display: block; border-radius: 16px; margin: 18px 0; border: 1px solid #e5e7eb; }
        .wiki-content { line-height: 1.85; font-size: 16px; }
        .wiki-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
        .wiki-content th, .wiki-content td { border: 1px solid #d1d5db; padding: 8px; }
        .summary-box { background: #eff6ff; padding: 14px; border-left: 5px solid #2563eb; border-radius: 12px; margin: 18px 0; font-weight: 700; }
        .detail-head { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
        .spec-table { width: 100%; border-collapse: collapse; margin: 18px 0 24px; border: 1px solid #e5e7eb; }
        .spec-table th, .spec-table td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
        .spec-table th { width: 220px; background: #f8fafc; }
        .history-item { padding: 14px; border: 1px solid #e5e7eb; border-radius: 12px; margin-bottom: 10px; background: #fafcff; }
        .admin-badge { display: inline-block; padding: 5px 9px; border-radius: 999px; background: #fee2e2; color: #991b1b; font-size: 12px; font-weight: 700; }
        .checkbox-inline { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
        .checkbox-inline input { width: auto; }
        .grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .small { font-size: 13px; }
        @media (max-width: 780px) { .search-grid, .grid-two { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="container topbar-inner">
            <a class="logo" href="{{ url_for('home') }}">Air Asset Wiki</a>
            <nav class="nav-links">
                <a href="{{ url_for('home') }}">홈</a>
                {% if current_user.is_authenticated %}
                    <a href="{{ url_for('create_asset') }}">새 문서</a>
                    {% if current_user.is_admin %}<a href="{{ url_for('admin_dashboard') }}">관리자</a>{% endif %}
                    <a href="{{ url_for('admin.index') }}">관리 패널</a>
                    <span>{{ current_user.username }} {% if current_user.is_admin %}<span class="admin-badge">관리자</span>{% endif %}</span>
                    <a href="{{ url_for('logout') }}">로그아웃</a>
                {% else %}
                    <a href="{{ url_for('login') }}">로그인</a>
                    <a href="{{ url_for('register') }}">회원가입</a>
                {% endif %}
            </nav>
        </div>
    </header>
    <main class="main">
        <div class="container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="flash flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            {{ body|safe }}
        </div>
    </main>
</body>
</html>
'''


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.password_hash = row["password_hash"]
        self.is_admin = bool(row["is_admin"])
        self.created_at = row["created_at"]


@login_manager.user_loader
def load_user(user_id):
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(row) if row else None


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def allowed_image_bytes(file_bytes: bytes):
    try:
        img = Image.open(BytesIO(file_bytes))
        fmt = (img.format or "").lower()
        if fmt in {"png", "jpeg", "gif", "webp"}:
            return fmt
    except Exception:
        return None
    return None


def image_bytes_to_data_url(file_bytes: bytes):
    fmt = allowed_image_bytes(file_bytes)
    if not fmt:
        return None

    img = Image.open(BytesIO(file_bytes))
    max_width = 1200
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))

    output = BytesIO()
    save_fmt = "JPEG" if fmt == "jpeg" else fmt.upper()
    if save_fmt == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(output, format=save_fmt, optimize=True, quality=85)
    encoded = base64.b64encode(output.getvalue()).decode("utf-8")
    mime = "image/jpeg" if fmt == "jpeg" else f"image/{fmt}"
    return f"data:{mime};base64,{encoded}"


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            summary TEXT,
            description TEXT,
            description_html TEXT,
            image_data TEXT,
            is_published INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS asset_specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL UNIQUE,
            manufacturer TEXT,
            country TEXT,
            role TEXT,
            first_flight TEXT,
            introduced TEXT,
            status TEXT,
            crew TEXT,
            length TEXT,
            wingspan TEXT,
            height TEXT,
            max_speed TEXT,
            range_km TEXT,
            combat_radius TEXT,
            service_ceiling TEXT,
            engine TEXT,
            powerplant TEXT,
            armament TEXT,
            notes TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS edit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            edited_by INTEGER,
            action_type TEXT NOT NULL,
            title_snapshot TEXT,
            summary_snapshot TEXT,
            description_snapshot TEXT,
            spec_snapshot TEXT,
            edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
            FOREIGN KEY (edited_by) REFERENCES users(id)
        );
        """
    )
    db.commit()
    ensure_default_admin()


def ensure_default_admin():
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            ("admin", generate_password_hash("admin1234")),
        )
        db.commit()


def serialize_specs_from_form(form):
    return {field: form.get(field, "").strip() for field, _ in SPEC_FIELDS}


def specs_to_text(specs_dict):
    lines = []
    for field, label in SPEC_FIELDS:
        value = specs_dict.get(field, "") if specs_dict else ""
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def markdown_to_html(text: str):
    return markdown(
        text or "",
        extensions=["extra", "tables", "fenced_code", "nl2br", "sane_lists"],
    )


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("관리자 권한이 필요합니다.", "danger")
            return redirect(url_for("home"))
        return view_func(*args, **kwargs)
    return wrapper


def render_page(body_html, **context):
    context["body"] = render_template_string(body_html, **context)
    return render_template_string(BASE_HTML, **context)


def save_history(asset_id, edited_by, action_type, title_snapshot, summary_snapshot, description_snapshot, spec_dict):
    db = get_db()
    db.execute(
        """
        INSERT INTO edit_history (
            asset_id, edited_by, action_type,
            title_snapshot, summary_snapshot, description_snapshot, spec_snapshot
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (asset_id, edited_by, action_type, title_snapshot, summary_snapshot, description_snapshot, specs_to_text(spec_dict)),
    )
    db.commit()


def fetch_asset(asset_id):
    return get_db().execute(
        """
        SELECT a.*, u.username AS author_name
        FROM assets a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.id = ?
        """,
        (asset_id,),
    ).fetchone()


def fetch_specs(asset_id):
    return get_db().execute("SELECT * FROM asset_specs WHERE asset_id = ?", (asset_id,)).fetchone()


def fetch_history(asset_id):
    return get_db().execute(
        """
        SELECT h.*, u.username AS editor_name
        FROM edit_history h
        LEFT JOIN users u ON h.edited_by = u.id
        WHERE h.asset_id = ?
        ORDER BY h.id DESC
        """,
        (asset_id,),
    ).fetchall()


class SimpleAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("관리자만 접근 가능합니다.", "danger")
            return redirect(url_for("login"))
        return super().index()


class DummySession:
    def __init__(self, conn):
        self.conn = conn


class AdminProtectedModelView(ModelView):
    can_export = True
    page_size = 50

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        flash("관리자만 접근 가능합니다.", "danger")
        return redirect(url_for("login"))


admin = Admin(
    app,
    name="Air Asset Admin",
    url="/admin-panel",
    index_view=SimpleAdminIndexView(name="대시보드", url="/admin-panel"),
)


@app.route("/")
def home():
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = """
        SELECT a.*, u.username AS author_name
        FROM assets a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.is_published = 1
    """
    params = []
    if q:
        like_q = f"%{q}%"
        sql += " AND (a.title LIKE ? OR a.summary LIKE ? OR a.description LIKE ?)"
        params.extend([like_q, like_q, like_q])
    if category:
        sql += " AND a.category = ?"
        params.append(category)
    sql += " ORDER BY a.updated_at DESC, a.id DESC"
    assets = db.execute(sql, params).fetchall()

    body = r'''
    <section class="card hero">
        <h1>사관학교 러브콜 기다립니다</h1>
        <p>dodolove0429@naver.com.</p>
        <p class="muted">이정도 만들었으면 솔직히 뽑아주셔야죠.</p>
    </section>
    <section class="card">
        <form method="get" class="search-grid">
            <input type="text" name="q" placeholder="기종명, 자산명, 설명 검색" value="{{ q }}">
            <select name="category">
                <option value="">전체 분류</option>
                {% for cat in categories %}
                    <option value="{{ cat }}" {% if category == cat %}selected{% endif %}>{{ cat }}</option>
                {% endfor %}
            </select>
            <button type="submit">검색</button>
        </form>
    </section>
    <section class="asset-grid">
        {% for asset in assets %}
            <article class="asset-card">
                {% if asset['image_data'] %}
                    <img class="thumb" src="{{ asset['image_data'] }}" alt="{{ asset['title'] }}">
                {% else %}
                    <div class="thumb-placeholder">NO IMAGE</div>
                {% endif %}
                <div class="asset-body">
                    <div class="badge">{{ asset['category'] }}</div>
                    <h3><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}" style="text-decoration:none;color:#0f172a;">{{ asset['title'] }}</a></h3>
                    <p>{{ asset['summary'] or '설명이 아직 없습니다.' }}</p>
                    <div class="muted small">작성자: {{ asset['author_name'] or '알 수 없음' }}</div>
                </div>
            </article>
        {% else %}
            <div class="card"><strong>등록된 문서가 없습니다.</strong></div>
        {% endfor %}
    </section>
    '''
    return render_page(body, title="홈 | Air Asset Wiki", assets=assets, q=q, category=category, categories=CATEGORIES)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if not username or not password:
            flash("아이디와 비밀번호를 입력해주세요.", "danger")
            return redirect(url_for("register"))
        if password != password2:
            flash("비밀번호 확인이 일치하지 않습니다.", "danger")
            return redirect(url_for("register"))
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            flash("이미 존재하는 아이디입니다.", "danger")
            return redirect(url_for("register"))
        db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)", (username, generate_password_hash(password)))
        db.commit()
        flash("회원가입이 완료되었습니다. 로그인해주세요.", "success")
        return redirect(url_for("login"))
    body = r'''
    <div class="card narrow">
        <h2>회원가입</h2>
        <form method="post">
            <label>아이디</label><input type="text" name="username" required>
            <label>비밀번호</label><input type="password" name="password" required>
            <label>비밀번호 확인</label><input type="password" name="password2" required>
            <button type="submit">회원가입</button>
        </form>
    </div>
    '''
    return render_page(body, title="회원가입")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
            return redirect(url_for("login"))
        login_user(User(row))
        flash("로그인되었습니다.", "success")
        return redirect(url_for("home"))
    body = r'''
    <div class="card narrow">
        <h2>로그인</h2>
        <form method="post">
            <label>아이디</label><input type="text" name="username" required>
            <label>비밀번호</label><input type="password" name="password" required>
            <button type="submit">로그인</button>
        </form>
        <p class="muted small" style="margin-top:14px;">기본 관리자 계정: admin / admin1234</p>
    </div>
    '''
    return render_page(body, title="로그인")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


@app.route("/create", methods=["GET", "POST"])
@login_required
def create_asset():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        is_published = 1 if (current_user.is_admin or request.form.get("publish_now") == "on") else 0
        file = request.files.get("image")
        if not title or not category:
            flash("제목과 분류는 필수입니다.", "danger")
            return redirect(url_for("create_asset"))
        image_data = None
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("이미지는 png, jpg/jpeg, gif, webp만 가능합니다.", "danger")
                return redirect(url_for("create_asset"))
        specs = serialize_specs_from_form(request.form)
        description_html = markdown_to_html(description)
        db = get_db()
        cur = db.execute(
            "INSERT INTO assets (title, category, summary, description, description_html, image_data, is_published, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, category, summary, description, description_html, image_data, is_published, current_user.id),
        )
        asset_id = cur.lastrowid
        spec_cols = ", ".join([field for field, _ in SPEC_FIELDS])
        placeholders = ", ".join(["?" for _ in SPEC_FIELDS])
        spec_values = [specs[field] for field, _ in SPEC_FIELDS]
        db.execute(f"INSERT INTO asset_specs (asset_id, {spec_cols}) VALUES (?, {placeholders})", [asset_id] + spec_values)
        db.commit()
        save_history(asset_id, current_user.id, "create", title, summary, description, specs)
        flash("새 문서가 등록되었습니다.", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))
    body = r'''
    <div class="card">
        <h2>새 문서 작성</h2>
        <form method="post" enctype="multipart/form-data">
            <label>제목</label><input type="text" name="title" placeholder="예: B-2 Spirit" required>
            <label>분류</label>
            <select name="category" required>
                <option value="">선택하세요</option>
                {% for cat in categories %}<option value="{{ cat }}">{{ cat }}</option>{% endfor %}
            </select>
            <label>짧은 설명</label><input type="text" name="summary" placeholder="카드에 표시될 요약">
            <label>상세 설명 (Markdown 지원)</label><textarea name="description" rows="10"></textarea>
            <label>이미지 업로드</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" checked> 바로 공개</label>{% endif %}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <h3>비행기 / 자산 스펙표</h3>
            <div class="grid-two">
                {% for field, label in spec_fields %}
                    <div>
                        <label>{{ label }}</label>
                        {% if field in ['armament', 'notes'] %}
                            <textarea name="{{ field }}" rows="4"></textarea>
                        {% else %}
                            <input type="text" name="{{ field }}">
                        {% endif %}
                    </div>
                {% endfor %}
            </div>
            <button type="submit">등록하기</button>
        </form>
    </div>
    '''
    return render_page(body, title="새 문서 작성", categories=CATEGORIES, spec_fields=SPEC_FIELDS)


@app.route("/asset/<int:asset_id>")
def asset_detail(asset_id):
    asset = fetch_asset(asset_id)
    if asset is None:
        flash("문서를 찾을 수 없습니다.", "danger")
        return redirect(url_for("home"))
    if not asset["is_published"] and not (current_user.is_authenticated and current_user.is_admin):
        flash("아직 공개되지 않은 문서입니다.", "warning")
        return redirect(url_for("home"))
    specs = fetch_specs(asset_id)
    history = fetch_history(asset_id)
    body = r'''
    <div class="card">
        <div class="detail-head">
            <div>
                <div class="badge">{{ asset['category'] }}</div>
                <h1>{{ asset['title'] }}</h1>
                <div class="muted">작성자: {{ asset['author_name'] or '알 수 없음' }} | 생성: {{ asset['created_at'] }} | 수정: {{ asset['updated_at'] }}</div>
                {% if not asset['is_published'] %}<div class="admin-badge" style="margin-top:10px;">비공개 초안</div>{% endif %}
            </div>
            {% if current_user.is_authenticated %}
                <div class="btn-row">
                    <a class="btn-link" href="{{ url_for('edit_asset', asset_id=asset['id']) }}">수정</a>
                    {% if current_user.is_admin %}
                    <form method="post" action="{{ url_for('delete_asset', asset_id=asset['id']) }}" onsubmit="return confirm('정말 삭제하시겠습니까?');">
                        <button class="btn-danger" type="submit">삭제</button>
                    </form>
                    {% endif %}
                </div>
            {% endif %}
        </div>
        {% if asset['image_data'] %}<img class="detail-image" src="{{ asset['image_data'] }}" alt="{{ asset['title'] }}">{% endif %}
        {% if asset['summary'] %}<div class="summary-box">{{ asset['summary'] }}</div>{% endif %}
        <h2>기본 설명</h2>
        <div class="wiki-content">{{ asset['description_html'] | safe }}</div>
        <h2 style="margin-top:28px;">스펙표</h2>
        <table class="spec-table"><tbody>
            {% for field, label in spec_fields %}
                {% set value = specs[field] if specs else '' %}
                {% if value %}<tr><th>{{ label }}</th><td>{{ value }}</td></tr>{% endif %}
            {% endfor %}
        </tbody></table>
    </div>
    <div class="card">
        <h2>편집 이력</h2>
        {% for row in history %}
            <div class="history-item">
                <strong>{{ row['action_type'] }}</strong>
                <div class="muted small">편집자: {{ row['editor_name'] or '알 수 없음' }} | 시각: {{ row['edited_at'] }}</div>
                <div style="margin-top:8px;"><strong>제목 스냅샷:</strong> {{ row['title_snapshot'] or '' }}</div>
                {% if row['summary_snapshot'] %}<div><strong>요약:</strong> {{ row['summary_snapshot'] }}</div>{% endif %}
                {% if row['spec_snapshot'] %}<pre style="white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:12px;border:1px solid #e5e7eb;">{{ row['spec_snapshot'] }}</pre>{% endif %}
            </div>
        {% else %}
            <div class="muted">편집 이력이 없습니다.</div>
        {% endfor %}
    </div>
    '''
    return render_page(body, title=asset["title"], asset=asset, specs=specs, history=history, spec_fields=SPEC_FIELDS)


@app.route("/edit/<int:asset_id>", methods=["GET", "POST"])
@login_required
def edit_asset(asset_id):
    asset = fetch_asset(asset_id)
    specs = fetch_specs(asset_id)
    if asset is None:
        flash("문서를 찾을 수 없습니다.", "danger")
        return redirect(url_for("home"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        remove_image = request.form.get("remove_image") == "on"
        publish_now = request.form.get("publish_now") == "on"
        file = request.files.get("image")
        if not title or not category:
            flash("제목과 분류는 필수입니다.", "danger")
            return redirect(url_for("edit_asset", asset_id=asset_id))
        image_data = None if remove_image else asset["image_data"]
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("이미지는 png, jpg/jpeg, gif, webp만 가능합니다.", "danger")
                return redirect(url_for("edit_asset", asset_id=asset_id))
        new_specs = serialize_specs_from_form(request.form)
        db = get_db()
        db.execute(
            "UPDATE assets SET title = ?, category = ?, summary = ?, description = ?, description_html = ?, image_data = ?, is_published = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, category, summary, description, markdown_to_html(description), image_data, 1 if (current_user.is_admin and publish_now) else asset["is_published"], asset_id),
        )
        set_clause = ", ".join([f"{field} = ?" for field, _ in SPEC_FIELDS])
        spec_values = [new_specs[field] for field, _ in SPEC_FIELDS]
        db.execute(f"UPDATE asset_specs SET {set_clause} WHERE asset_id = ?", spec_values + [asset_id])
        db.commit()
        save_history(asset_id, current_user.id, "edit", title, summary, description, new_specs)
        flash("문서가 수정되었습니다.", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))
    body = r'''
    <div class="card">
        <h2>문서 수정</h2>
        <form method="post" enctype="multipart/form-data">
            <label>제목</label><input type="text" name="title" value="{{ asset['title'] }}" required>
            <label>분류</label>
            <select name="category" required>
                {% for cat in categories %}<option value="{{ cat }}" {% if asset['category'] == cat %}selected{% endif %}>{{ cat }}</option>{% endfor %}
            </select>
            <label>짧은 설명</label><input type="text" name="summary" value="{{ asset['summary'] or '' }}">
            <label>상세 설명 (Markdown 지원)</label><textarea name="description" rows="10">{{ asset['description'] or '' }}</textarea>
            {% if asset['image_data'] %}
                <label>현재 이미지</label>
                <img class="detail-image" src="{{ asset['image_data'] }}" alt="현재 이미지" style="max-width:320px;">
                <label class="checkbox-inline"><input type="checkbox" name="remove_image"> 현재 이미지 삭제</label>
            {% endif %}
            <label>새 이미지 업로드</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" {% if asset['is_published'] %}checked{% endif %}> 공개 상태 유지/변경</label>{% endif %}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <h3>비행기 / 자산 스펙표 수정</h3>
            <div class="grid-two">
                {% for field, label in spec_fields %}
                    {% set value = specs[field] if specs else '' %}
                    <div>
                        <label>{{ label }}</label>
                        {% if field in ['armament', 'notes'] %}
                            <textarea name="{{ field }}" rows="4">{{ value or '' }}</textarea>
                        {% else %}
                            <input type="text" name="{{ field }}" value="{{ value or '' }}">
                        {% endif %}
                    </div>
                {% endfor %}
            </div>
            <button type="submit">수정 저장</button>
        </form>
    </div>
    '''
    return render_page(body, title="문서 수정", asset=asset, specs=specs, categories=CATEGORIES, spec_fields=SPEC_FIELDS)


@app.route("/delete/<int:asset_id>", methods=["POST"])
@admin_required
def delete_asset(asset_id):
    asset = fetch_asset(asset_id)
    specs = fetch_specs(asset_id)
    if asset is None:
        flash("문서를 찾을 수 없습니다.", "danger")
        return redirect(url_for("home"))
    save_history(asset_id, current_user.id, "delete", asset["title"], asset["summary"], asset["description"], {field: (specs[field] if specs else "") for field, _ in SPEC_FIELDS})
    db = get_db()
    db.execute("DELETE FROM asset_specs WHERE asset_id = ?", (asset_id,))
    db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    db.commit()
    flash("문서가 삭제되었습니다.", "info")
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    assets = db.execute(
        "SELECT a.id, a.title, a.category, a.updated_at, a.is_published, u.username AS author_name FROM assets a LEFT JOIN users u ON a.created_by = u.id ORDER BY a.updated_at DESC"
    ).fetchall()
    body = r'''
    <div class="card"><h2>관리자 페이지</h2><p class="muted">회원 권한, 문서 공개 상태, 전체 현황을 볼 수 있습니다.</p></div>
    <div class="card">
        <h3>회원 목록</h3>
        <table class="spec-table">
            <thead><tr><th>ID</th><th>아이디</th><th>권한</th><th>생성일</th></tr></thead>
            <tbody>
                {% for user in users %}
                <tr><td>{{ user['id'] }}</td><td>{{ user['username'] }}</td><td>{% if user['is_admin'] %}관리자{% else %}일반회원{% endif %}</td><td>{{ user['created_at'] }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="card">
        <h3>전체 문서 현황</h3>
        <table class="spec-table">
            <thead><tr><th>ID</th><th>제목</th><th>분류</th><th>작성자</th><th>공개</th><th>최종 수정</th></tr></thead>
            <tbody>
                {% for asset in assets %}
                <tr>
                    <td>{{ asset['id'] }}</td>
                    <td><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}">{{ asset['title'] }}</a></td>
                    <td>{{ asset['category'] }}</td>
                    <td>{{ asset['author_name'] or '알 수 없음' }}</td>
                    <td>{% if asset['is_published'] %}공개{% else %}비공개{% endif %}</td>
                    <td>{{ asset['updated_at'] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    '''
    return render_page(body, title="관리자 페이지", users=users, assets=assets)


@app.route("/init-db")
def init_db_route():
    init_db()
    return "DB initialized"


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True,host = "0.0.0.0" ,port=5000)

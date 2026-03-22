
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
login_manager.login_message = "Please Log In"
login_manager.login_message_category = "warning"
login_manager.init_app(app)

AIR_CATEGORIES = [
    "Fighters", "Bomber", "Airlifter", "Airbone Early Warning(AEW)", "Ariel Tanker", "Reconnaissance Aircraft", "Trainer",
    "UAV", "Aircraft Carrier", "Submarine", "Ballistic Missile", "Cruise Missile", "Air Defense System",
    "Space Force", "Others",
]

RADIO_CATEGORIES = [
    "General", "Frequency", "Radar", "Communication", "EW", "Information", "Radio Astronomy", "Other"
]

CONSTELLATION_CATEGORIES = [
    "Zodaic", "(N)Constellation", "(S)Constellation", "Seasonal Constellation", "Nebula", "Guide", "Other"
]

SECTION_CONFIG = {
    "air": {
        "name": "Air Atlas",
        "title": "AirAtlas",
        "hero_title": "Aircraft Dictionalry",
        "hero_subtitle": "dodolove0429@naver.com.",
        "hero_desc": "",
        "categories": AIR_CATEGORIES,
    },
    "radio": {
        "name": "Radio Atlas",
        "title": "Radio Atlas",
        "hero_title": "Radio Archieve",
        "hero_subtitle": "",
        "hero_desc": "",
        "categories": RADIO_CATEGORIES,
    },
    "constellation": {
        "name": "Constellation Atlas",
        "title": "Constellation Wiki",
        "hero_title": "Constellation Atlas",
        "hero_subtitle": "",
        "hero_desc": "",
        "categories": CONSTELLATION_CATEGORIES,
    },
}


CONTACT_NAME = "Matthew Doyoon Ahn"
CONTACT_EMAIL = "dodolove0429naver.com"
CONTACT_PHONE = "8210-2277-8844"
CONTACT_NOTE = "Horizon and Beyond"

SECTION_FORM_CONFIG = {
    "air": {
        "headline": "Air Atlas New Document",
        "description": "",
        "title_placeholder": "Ex: F-22 Raptor / B-2 Spirit / E-3 Sentry",
        "summary_placeholder": "Brief Summary",
        "description_placeholder": "Description",
        "field_help": {
            "manufacturer": "Manufacturer",
            "country": "Country",
            "role": "Role",
            "armament": "Armament",
            "notes": "Notes",
        },
    },
    "radio": {
        "headline": "New Radio Atlas Document",
        "description": "Description",
        "title_placeholder": "Ex: Emergency 121.5 MHz / AN-ALQ-99 / X-band",
        "summary_placeholder": "Summary",
        "description_placeholder": "Description",
        "field_help": {
            "manufacturer": "장비 제작사 또는 표준 제정 기관",
            "country": "주요 사용 국가 또는 국제 표준 여부",
            "role": "교신, 감시, 항법, 재밍, SIGINT 등",
            "max_speed": "해당 없으면 비워두고, 대신 주파수/대역폭은 비고에 적어도 됩니다.",
            "notes": "주파수, 대역, 프로토콜, 전술적 의미 등을 자유롭게 기록",
        },
    },
    "constellation": {
        "headline": "별자리 문서 작성",
        "description": "별자리, 관측 포인트, 계절별 특징을 기록하기 좋은 폼입니다.",
        "title_placeholder": "예: Orion / Cassiopeia / Scorpius",
        "summary_placeholder": "대표 밝은 별, 계절, 관측 포인트 요약",
        "description_placeholder": "형태, 찾는 법, 관련 신화, 관측 시기 등을 Markdown으로 작성하세요.",
        "field_help": {
            "manufacturer": "해당 없으면 비워도 됩니다. 망원경/관측 장비 추천을 적어도 됩니다.",
            "country": "북반구/남반구 관측 기준 국가나 지역 메모 가능",
            "role": "관측 포인트, 계절 분류, 교육용 설명 등",
            "notes": "적경/적위, 관측 난이도, 연결되는 별자리 메모",
        },
    },
}

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
        :root {
            --bg: #081120;
            --panel: rgba(12, 23, 41, 0.84);
            --panel-soft: rgba(255,255,255,0.06);
            --card: #ffffff;
            --line: #dbe4f0;
            --text: #0f172a;
            --muted: #64748b;
            --blue: #2563eb;
            --blue-dark: #1d4ed8;
            --sky: #60a5fa;
            --danger: #dc2626;
            --success: #16a34a;
            --shadow: 0 24px 60px rgba(2, 8, 23, 0.18);
        }
        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background:
                radial-gradient(circle at top left, rgba(96,165,250,0.16), transparent 28%),
                radial-gradient(circle at top right, rgba(59,130,246,0.14), transparent 24%),
                linear-gradient(180deg, #06101d 0%, #0b1730 18%, #eef4fb 18%, #f4f7fb 100%);
            color: var(--text);
        }
        .container { width: min(1220px, 94%); margin: 0 auto; }
        .topbar {
            position: sticky; top: 0; z-index: 30;
            backdrop-filter: blur(18px);
            background: rgba(8, 17, 32, 0.82);
            color: white;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .topbar-inner { display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap; padding: 14px 0; }
        .logo-wrap { display: flex; align-items: center; gap: 12px; }
        .logo-mark {
            width: 42px; height: 42px; border-radius: 14px;
            background: linear-gradient(135deg, #1d4ed8, #60a5fa);
            display: grid; place-items: center; font-weight: 800; color: white; box-shadow: 0 12px 25px rgba(37,99,235,0.35);
        }
        .logo { color: white; text-decoration: none; font-size: 23px; font-weight: 800; letter-spacing: -0.02em; }
        .logo-sub { color: rgba(255,255,255,0.7); font-size: 12px; margin-top: 3px; }
        .nav-links { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .nav-links a, .nav-links span {
            color: white; text-decoration: none; padding: 9px 12px; border-radius: 999px; font-size: 14px;
            background: rgba(255,255,255,0.04); border: 1px solid transparent;
        }
        .nav-links a:hover, .nav-links a.active { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.12); }
        .main { padding: 28px 0 56px; }
        .card {
            background: rgba(255,255,255,0.96);
            border-radius: 24px; box-shadow: var(--shadow);
            padding: 24px; margin-bottom: 22px; border: 1px solid rgba(219,228,240,0.95);
        }
        .glass-card {
            background: linear-gradient(145deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06));
            color: white; border: 1px solid rgba(255,255,255,0.1);
            border-radius: 28px; box-shadow: 0 22px 60px rgba(2,8,23,0.22);
        }
        .hero {
            padding: 34px;
            background: linear-gradient(135deg, rgba(219,234,254,0.98), rgba(255,255,255,0.98));
            border: 1px solid #dbeafe;
        }
        h1, h2, h3 { margin-top: 0; letter-spacing: -0.03em; }
        h1 { font-size: clamp(30px, 5vw, 52px); line-height: 1.02; }
        h2 { font-size: 28px; }
        .hero-kicker, .section-kicker {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 7px 12px; border-radius: 999px; font-size: 12px; font-weight: 800; text-transform: uppercase;
            letter-spacing: 0.08em; background: rgba(37,99,235,0.1); color: var(--blue-dark); margin-bottom: 14px;
        }
        .hero-grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 24px; align-items: stretch; }
        .intro-panel { min-height: 100%; }
        .intro-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 18px; }
        .stat-box { border-radius: 20px; padding: 18px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.12); }
        .stat-box strong { display: block; font-size: 26px; margin-bottom: 6px; }
        .muted { color: var(--muted); }
        .small { font-size: 13px; }
        .search-grid { display: grid; grid-template-columns: 1.4fr 240px 140px; gap: 12px; }
        .asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 18px; }
        .asset-card {
            background: rgba(255,255,255,0.98);
            border-radius: 22px; overflow: hidden; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.11);
            border: 1px solid #e5e7eb; transition: transform .2s ease, box-shadow .2s ease;
        }
        .asset-card:hover { transform: translateY(-4px); box-shadow: 0 24px 48px rgba(15,23,42,0.16); }
        .thumb { width: 100%; height: 200px; object-fit: cover; display: block; background: linear-gradient(135deg, #dbe4f0, #eff6ff); }
        .thumb-placeholder {
            width: 100%; height: 200px; display: flex; align-items: center; justify-content: center;
            background: linear-gradient(135deg, #dbeafe, #eff6ff); color: #1e3a8a; font-weight: 800; letter-spacing: 0.08em;
        }
        .asset-body { padding: 18px; }
        .badge {
            display: inline-block; padding: 7px 11px; border-radius: 999px;
            background: #dbeafe; color: #1d4ed8; font-size: 12px; font-weight: 800; margin-bottom: 10px;
        }
        input, select, textarea, button {
            width: 100%; padding: 13px 14px; border: 1px solid #cbd5e1; border-radius: 14px; font-size: 15px;
            background: white; transition: box-shadow .15s ease, border-color .15s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none; border-color: #60a5fa; box-shadow: 0 0 0 4px rgba(96,165,250,0.18);
        }
        textarea { resize: vertical; min-height: 120px; }
        label { display: block; margin: 14px 0 8px; font-weight: 700; }
        button {
            background: linear-gradient(135deg, var(--blue), var(--blue-dark));
            color: white; border: none; font-weight: 800; cursor: pointer; margin-top: 18px;
            box-shadow: 0 14px 32px rgba(37,99,235,0.28);
        }
        button:hover { filter: brightness(1.03); }
        .btn-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .btn-link, .btn-danger, .pill-link, .ghost-link {
            display: inline-block; padding: 11px 15px; text-decoration: none; border-radius: 14px; font-size: 14px; border: none; cursor: pointer; width: auto;
        }
        .btn-link { background: #0f172a; color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .ghost-link { background: rgba(15,23,42,0.06); color: #0f172a; border: 1px solid rgba(15,23,42,0.08); }
        .pill-wrap { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
        .pill-link { background: #e2e8f0; color: #1e293b; }
        .pill-link.active { background: linear-gradient(135deg, var(--blue), var(--blue-dark)); color: white; }
        .section-tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
        .section-tab { display: inline-block; padding: 10px 14px; border-radius: 999px; text-decoration: none; background: #eef2ff; color: #1e3a8a; font-weight: 800; }
        .section-tab.active { background: linear-gradient(135deg, var(--blue), var(--blue-dark)); color: white; }
        .flash { padding: 13px 15px; border-radius: 16px; margin-bottom: 12px; font-weight: 700; border: 1px solid transparent; }
        .flash-success { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
        .flash-danger { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
        .flash-warning { background: #fef3c7; color: #92400e; border-color: #fde68a; }
        .flash-info { background: #dbeafe; color: #1e40af; border-color: #bfdbfe; }
        .narrow { max-width: 560px; margin: 30px auto; }
        .detail-image { width: 100%; max-width: 760px; display: block; border-radius: 18px; margin: 18px 0; border: 1px solid #e5e7eb; }
        .wiki-content { line-height: 1.85; font-size: 16px; }
        .wiki-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
        .wiki-content th, .wiki-content td { border: 1px solid #d1d5db; padding: 8px; }
        .summary-box { background: #eff6ff; padding: 16px; border-left: 5px solid #2563eb; border-radius: 14px; margin: 18px 0; font-weight: 700; }
        .detail-head { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
        .spec-table { width: 100%; border-collapse: collapse; margin: 18px 0 24px; border: 1px solid #e5e7eb; overflow: hidden; border-radius: 18px; }
        .spec-table th, .spec-table td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
        .spec-table th { width: 220px; background: #f8fafc; }
        .history-item { padding: 14px; border: 1px solid #e5e7eb; border-radius: 16px; margin-bottom: 10px; background: #fafcff; }
        .admin-badge { display: inline-block; padding: 5px 9px; border-radius: 999px; background: #fee2e2; color: #991b1b; font-size: 12px; font-weight: 800; }
        .checkbox-inline { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
        .checkbox-inline input { width: auto; }
        .grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .grid-three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .section-card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
        .section-mini-card { border-radius: 22px; padding: 22px; background: white; border: 1px solid #e5e7eb; box-shadow: 0 10px 30px rgba(15,23,42,0.08); }
        .form-section-banner {
            display: flex; gap: 14px; align-items: center; justify-content: space-between; flex-wrap: wrap;
            padding: 18px; border-radius: 20px; background: linear-gradient(135deg, #eff6ff, #ffffff); border: 1px solid #dbeafe; margin-bottom: 18px;
        }
        .field-help { margin-top: 6px; color: var(--muted); font-size: 12px; }
        .footer-banner {
            margin-top: 26px; border-radius: 28px; padding: 22px; background: linear-gradient(135deg, #081120, #10213d 48%, #173056);
            color: white; box-shadow: 0 28px 60px rgba(2,8,23,0.24);
        }
        .footer-grid { display: grid; grid-template-columns: 1fr auto 1fr; gap: 18px; align-items: center; }
        .logo-stack { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
        .logo-slot {
            min-height: 86px; border-radius: 20px; border: 1px dashed rgba(255,255,255,0.28);
            background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; text-align: center;
            color: rgba(255,255,255,0.72); padding: 12px; font-size: 12px; font-weight: 700;
        }
        .footer-contact { text-align: center; }
        .footer-contact h3 { margin-bottom: 8px; color: white; }
        .footer-contact p { margin: 6px 0; color: rgba(255,255,255,0.82); }
        .intro-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }
        .intro-actions a { text-decoration: none; }
        .hero-list { margin: 18px 0 0; padding-left: 18px; line-height: 1.8; }
        .count-chip { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px; background: rgba(255,255,255,0.1); margin: 0 8px 8px 0; font-size: 13px; }
        @media (max-width: 980px) {
            .hero-grid, .section-card-grid, .grid-three, .footer-grid { grid-template-columns: 1fr; }
            .intro-stats { grid-template-columns: 1fr; }
        }
        @media (max-width: 780px) {
            .search-grid, .grid-two { grid-template-columns: 1fr; }
            .topbar-inner { padding: 12px 0; }
            .footer-grid { gap: 22px; }
            .logo-stack { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="container topbar-inner">
            <div class="logo-wrap">
                <div class="logo-mark">AF</div>
                <div>
                    <a class="logo" href="{{ url_for('intro_page') }}">Air Asset Wiki</a>
                    <div class="logo-sub">air · radio · constellation archive</div>
                </div>
            </div>
            <nav class="nav-links">
                <a href="{{ url_for('intro_page') }}" class="{% if active_section == 'intro' %}active{% endif %}">소개</a>
                <a href="{{ url_for('home') }}" class="{% if active_section == 'air' %}active{% endif %}">에어딕셔너리</a>
                <a href="{{ url_for('radio_home') }}" class="{% if active_section == 'radio' %}active{% endif %}">전파</a>
                <a href="{{ url_for('constellation_home') }}" class="{% if active_section == 'constellation' %}active{% endif %}">별자리</a>
                {% if current_user.is_authenticated %}
                    <a href="{{ url_for('create_asset', section=active_section if active_section in ['air','radio','constellation'] else 'air') }}">새 문서</a>
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
            <section class="footer-banner">
                <div class="footer-grid">
                    <div class="logo-stack">
                        {% for idx in range(3) %}
                        <div class="logo-slot">US Armed Force Logo {{ idx + 1 }}<br>왼쪽 이미지 경로 연결 슬롯</div>
                        {% endfor %}
                    </div>
                    <div class="footer-contact">
                        <div class="hero-kicker" style="background:rgba(255,255,255,0.12);color:white;">Contact Banner</div>
                        <h3>{{ contact_name }}</h3>
                        <p>{{ contact_email }}</p>
                        <p>{{ contact_phone }}</p>
                        <p>{{ contact_note }}</p>
                    </div>
                    <div class="logo-stack">
                        {% for idx in range(3) %}
                        <div class="logo-slot">US Armed Force Logo {{ idx + 4 }}<br>오른쪽 이미지 경로 연결 슬롯</div>
                        {% endfor %}
                    </div>
                </div>
            </section>
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


def get_columns(table_name):
    return [row["name"] for row in get_db().execute(f"PRAGMA table_info({table_name})").fetchall()]


def ensure_column(table_name, column_name, ddl):
    columns = get_columns(table_name)
    if column_name not in columns:
        get_db().execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")
        get_db().commit()


def get_section_config(section):
    return SECTION_CONFIG.get(section, SECTION_CONFIG["air"])


def get_categories_for_section(section):
    return get_section_config(section)["categories"]


def normalize_section(section):
    return section if section in SECTION_CONFIG else "air"


def section_label(section):
    return get_section_config(section)["name"]



def get_form_config(section):
    return SECTION_FORM_CONFIG.get(section, SECTION_FORM_CONFIG['air'])


def ensure_specs_row(asset_id):
    db = get_db()
    row = db.execute('SELECT id FROM asset_specs WHERE asset_id = ?', (asset_id,)).fetchone()
    if row:
        return row
    spec_cols = ', '.join([field for field, _ in SPEC_FIELDS])
    placeholders = ', '.join(['' for _ in SPEC_FIELDS])
    db.execute(
        f"INSERT INTO asset_specs (asset_id, {spec_cols}) VALUES (?, {', '.join(['?' for _ in SPEC_FIELDS])})",
        [asset_id] + ['' for _ in SPEC_FIELDS],
    )
    db.commit()
    return db.execute('SELECT id FROM asset_specs WHERE asset_id = ?', (asset_id,)).fetchone()


def safe_section_snapshot_enabled():
    return 'section_snapshot' in get_columns('edit_history')


def get_history_select_clause():
    if safe_section_snapshot_enabled():
        return 'h.*, u.username AS editor_name'
    return "h.*, '' AS section_snapshot, u.username AS editor_name"

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

    ensure_column("assets", "section", "section TEXT NOT NULL DEFAULT 'air'")
    ensure_column("edit_history", "section_snapshot", "section_snapshot TEXT")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS deleted_assets_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_asset_id INTEGER,
            deleted_by INTEGER,
            title_snapshot TEXT,
            section_snapshot TEXT,
            category_snapshot TEXT,
            summary_snapshot TEXT,
            description_snapshot TEXT,
            spec_snapshot TEXT,
            deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    db.execute("UPDATE assets SET section = 'air' WHERE section IS NULL OR section = ''")
    db.execute("UPDATE edit_history SET section_snapshot = 'air' WHERE section_snapshot IS NULL OR section_snapshot = ''")
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
    context.setdefault("active_section", "air")
    context.setdefault("contact_name", CONTACT_NAME)
    context.setdefault("contact_email", CONTACT_EMAIL)
    context.setdefault("contact_phone", CONTACT_PHONE)
    context.setdefault("contact_note", CONTACT_NOTE)
    return render_template_string(BASE_HTML, **context)


def save_history(asset_id, edited_by, action_type, title_snapshot, summary_snapshot, description_snapshot, spec_dict, section_snapshot="air"):
    db = get_db()
    spec_text = specs_to_text(spec_dict)
    if safe_section_snapshot_enabled():
        db.execute(
            """
            INSERT INTO edit_history (
                asset_id, edited_by, action_type,
                title_snapshot, summary_snapshot, description_snapshot, spec_snapshot, section_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                edited_by,
                action_type,
                title_snapshot,
                summary_snapshot,
                description_snapshot,
                spec_text,
                section_snapshot,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO edit_history (
                asset_id, edited_by, action_type,
                title_snapshot, summary_snapshot, description_snapshot, spec_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                edited_by,
                action_type,
                title_snapshot,
                summary_snapshot,
                description_snapshot,
                spec_text,
            ),
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
    ensure_specs_row(asset_id)
    return get_db().execute("SELECT * FROM asset_specs WHERE asset_id = ?", (asset_id,)).fetchone()


def fetch_history(asset_id):
    select_clause = get_history_select_clause()
    return get_db().execute(
        f"""
        SELECT {select_clause}
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


def render_section_home(section):
    section = normalize_section(section)
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    config = get_section_config(section)

    sql = """
        SELECT a.*, u.username AS author_name
        FROM assets a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.is_published = 1 AND a.section = ?
    """
    params = [section]
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
        <div class="section-tabs">
            <a class="section-tab {% if active_section == 'air' %}active{% endif %}" href="{{ url_for('home') }}">에어딕셔너리</a>
            <a class="section-tab {% if active_section == 'radio' %}active{% endif %}" href="{{ url_for('radio_home') }}">전파</a>
            <a class="section-tab {% if active_section == 'constellation' %}active{% endif %}" href="{{ url_for('constellation_home') }}">별자리</a>
        </div>
        <div class="hero-kicker">{{ config['title'] }}</div>
        <h1>{{ config['hero_title'] }}</h1>
        <p style="font-size:18px;margin:0 0 10px;">{{ config['hero_subtitle'] }}</p>
        <p class="muted">{{ config['hero_desc'] }}</p>
        <div class="btn-row" style="margin-top:14px;">
            <a class="ghost-link" href="{{ url_for('intro_page') }}">소개 페이지</a>
            {% if current_user.is_authenticated %}<a class="btn-link" href="{{ url_for('create_asset', section=active_section) }}">이 섹션에 새 문서 작성</a>{% endif %}
        </div>
    </section>
    <section class="card">
        <form method="get" class="search-grid">
            <input type="text" name="q" placeholder="문서명, 설명 검색" value="{{ q }}">
            <select name="category">
                <option value="">전체 분류</option>
                {% for cat in categories %}
                    <option value="{{ cat }}" {% if category == cat %}selected{% endif %}>{{ cat }}</option>
                {% endfor %}
            </select>
            <button type="submit">검색</button>
        </form>
        <div class="pill-wrap">
            <a class="pill-link {% if not category %}active{% endif %}" href="{{ section_url }}">전체</a>
            {% for cat in categories %}
                <a class="pill-link {% if category == cat %}active{% endif %}" href="{{ section_url }}?category={{ cat|urlencode }}{% if q %}&q={{ q|urlencode }}{% endif %}">{{ cat }}</a>
            {% endfor %}
        </div>
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
    section_url_map = {
        "air": url_for("home"),
        "radio": url_for("radio_home"),
        "constellation": url_for("constellation_home"),
    }
    return render_page(
        body,
        title=f"{config['name']} | {config['title']}",
        assets=assets,
        q=q,
        category=category,
        categories=config["categories"],
        config=config,
        active_section=section,
        section_url=section_url_map[section],
    )



@app.route("/intro")
def intro_page():
    db = get_db()
    counts = {
        'air': db.execute("SELECT COUNT(*) FROM assets WHERE section = 'air' AND is_published = 1").fetchone()[0],
        'radio': db.execute("SELECT COUNT(*) FROM assets WHERE section = 'radio' AND is_published = 1").fetchone()[0],
        'constellation': db.execute("SELECT COUNT(*) FROM assets WHERE section = 'constellation' AND is_published = 1").fetchone()[0],
    }
    recent_assets = db.execute(
        "SELECT id, title, category, section, updated_at FROM assets WHERE is_published = 1 ORDER BY updated_at DESC, id DESC LIMIT 6"
    ).fetchall()
    body = r'''
    <section class="glass-card card">
        <div class="hero-grid">
            <div>
                <div class="hero-kicker">Mission Briefing</div>
                <h1>Air · Radio · Constellation<br>통합 아카이브</h1>
                <p style="font-size:18px;line-height:1.8;color:rgba(255,255,255,0.88);margin:0;">항공 전력, 전파·전자전, 별자리 관측 자료를 한곳에 정리하는 개인 아카이브입니다. 문서 검색, 카테고리 탐색, 신규 문서 작성, 관리자 운영까지 한 사이트 안에서 돌아가도록 구성했습니다.</p>
                <div class="intro-actions">
                    <a class="btn-link" href="{{ url_for('home') }}">에어딕셔너리 바로가기</a>
                    <a class="ghost-link" style="color:white;background:rgba(255,255,255,0.1);border-color:rgba(255,255,255,0.18);" href="{{ url_for('radio_home') }}">전파 자료 보기</a>
                    <a class="ghost-link" style="color:white;background:rgba(255,255,255,0.1);border-color:rgba(255,255,255,0.18);" href="{{ url_for('constellation_home') }}">별자리 보기</a>
                </div>
                <ul class="hero-list" style="color:rgba(255,255,255,0.82);">
                    <li>에어딕셔너리: 전투기·폭격기·수송기·ISR 등 확장 데이터베이스</li>
                    <li>전파: 항공용 주파수, 군용 전자전, 레이더/통신 메모 정리</li>
                    <li>별자리: 관측용 문서, 계절별 별자리 정리, 이후 지도 기능 확장 가능</li>
                </ul>
            </div>
            <div class="intro-panel">
                <div class="hero-kicker" style="background:rgba(255,255,255,0.12);color:white;">Archive Status</div>
                <div>
                    <span class="count-chip">에어딕셔너리 {{ counts['air'] }}개</span>
                    <span class="count-chip">전파 {{ counts['radio'] }}개</span>
                    <span class="count-chip">별자리 {{ counts['constellation'] }}개</span>
                </div>
                <div class="intro-stats">
                    <div class="stat-box"><strong>{{ counts['air'] }}</strong><div>Air Assets</div></div>
                    <div class="stat-box"><strong>{{ counts['radio'] }}</strong><div>Radio / EW</div></div>
                    <div class="stat-box"><strong>{{ counts['constellation'] }}</strong><div>Constellation</div></div>
                </div>
            </div>
        </div>
    </section>
    <section class="section-card-grid">
        <article class="section-mini-card">
            <div class="section-kicker">Air</div>
            <h3>에어딕셔너리</h3>
            <p class="muted">항공 전력과 전략자산 문서를 카테고리별로 관리합니다.</p>
            <a class="btn-link" href="{{ url_for('home') }}">들어가기</a>
        </article>
        <article class="section-mini-card">
            <div class="section-kicker">Radio</div>
            <h3>전파</h3>
            <p class="muted">항공용 주파수, 군용 전자전, 통신/레이더 문서를 정리합니다.</p>
            <a class="btn-link" href="{{ url_for('radio_home') }}">들어가기</a>
        </article>
        <article class="section-mini-card">
            <div class="section-kicker">Constellation</div>
            <h3>별자리</h3>
            <p class="muted">별자리와 관측 정보를 기록하는 천문 아카이브입니다.</p>
            <a class="btn-link" href="{{ url_for('constellation_home') }}">들어가기</a>
        </article>
    </section>
    <section class="card">
        <h2>최근 업데이트</h2>
        <div class="asset-grid">
            {% for asset in recent_assets %}
            <article class="asset-card">
                <div class="thumb-placeholder">{{ asset['section']|upper }}</div>
                <div class="asset-body">
                    <div class="badge">{{ asset['category'] }}</div>
                    <h3><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}" style="text-decoration:none;color:#0f172a;">{{ asset['title'] }}</a></h3>
                    <div class="muted small">섹션: {{ asset['section'] }} · 수정: {{ asset['updated_at'] }}</div>
                </div>
            </article>
            {% endfor %}
        </div>
    </section>
    '''
    return render_page(body, title="소개 페이지", counts=counts, recent_assets=recent_assets, active_section="intro")


@app.route("/")
@app.route("/air")
def home():
    return render_section_home("air")


@app.route("/radio")
def radio_home():
    return render_section_home("radio")


@app.route("/constellation")
def constellation_home():
    return render_section_home("constellation")


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
    return render_page(body, title="회원가입", active_section="air")


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
    return render_page(body, title="로그인", active_section="air")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


@app.route("/create", methods=["GET", "POST"])
@login_required
def create_asset():
    requested_section = normalize_section(request.args.get("section", request.form.get("section", "air")))
    categories = get_categories_for_section(requested_section)

    if request.method == "POST":
        section = normalize_section(request.form.get("section", requested_section))
        categories = get_categories_for_section(section)
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        is_published = 1 if (current_user.is_admin or request.form.get("publish_now") == "on") else 0
        file = request.files.get("image")
        if not title or not category:
            flash("제목과 분류는 필수입니다.", "danger")
            return redirect(url_for("create_asset", section=section))
        if category not in categories:
            flash("해당 섹션에서 사용할 수 없는 분류입니다.", "danger")
            return redirect(url_for("create_asset", section=section))
        image_data = None
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("이미지는 png, jpg/jpeg, gif, webp만 가능합니다.", "danger")
                return redirect(url_for("create_asset", section=section))
        specs = serialize_specs_from_form(request.form)
        description_html = markdown_to_html(description)
        db = get_db()
        cur = db.execute(
            "INSERT INTO assets (title, category, summary, description, description_html, image_data, is_published, created_by, section) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, category, summary, description, description_html, image_data, is_published, current_user.id, section),
        )
        asset_id = cur.lastrowid
        spec_cols = ", ".join([field for field, _ in SPEC_FIELDS])
        placeholders = ", ".join(["?" for _ in SPEC_FIELDS])
        spec_values = [specs[field] for field, _ in SPEC_FIELDS]
        db.execute(f"INSERT INTO asset_specs (asset_id, {spec_cols}) VALUES (?, {placeholders})", [asset_id] + spec_values)
        db.commit()
        save_history(asset_id, current_user.id, "create", title, summary, description, specs, section_snapshot=section)
        flash("새 문서가 등록되었습니다.", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))
    form_config = get_form_config(requested_section)
    body = r'''
    <div class="card">
        <div class="form-section-banner">
            <div>
                <div class="hero-kicker">{{ section_label(active_section) }}</div>
                <h2 style="margin-bottom:8px;">{{ form_config['headline'] }}</h2>
                <div class="muted">{{ form_config['description'] }}</div>
            </div>
            <a class="ghost-link" href="{{ url_for('intro_page') }}">소개 페이지</a>
        </div>
        <form method="post" enctype="multipart/form-data">
            <label>문서 섹션</label>
            <select name="section" required onchange="window.location='{{ url_for('create_asset') }}?section=' + this.value;">
                <option value="air" {% if active_section == 'air' %}selected{% endif %}>에어딕셔너리</option>
                <option value="radio" {% if active_section == 'radio' %}selected{% endif %}>전파</option>
                <option value="constellation" {% if active_section == 'constellation' %}selected{% endif %}>별자리</option>
            </select>
            <div class="grid-two">
                <div>
                    <label>제목</label><input type="text" name="title" placeholder="{{ form_config['title_placeholder'] }}" required>
                </div>
                <div>
                    <label>분류</label>
                    <select name="category" required>
                        <option value="">선택하세요</option>
                        {% for cat in categories %}<option value="{{ cat }}">{{ cat }}</option>{% endfor %}
                    </select>
                </div>
            </div>
            <label>짧은 설명</label><input type="text" name="summary" placeholder="{{ form_config['summary_placeholder'] }}">
            <label>상세 설명 (Markdown 지원)</label><textarea name="description" rows="10" placeholder="{{ form_config['description_placeholder'] }}"></textarea>
            <label>이미지 업로드</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" checked> 바로 공개</label>{% endif %}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <h3>문서 상세 정보</h3>
            <div class="grid-two">
                {% for field, label in spec_fields %}
                    <div>
                        <label>{{ label }}</label>
                        {% if field in ['armament', 'notes'] %}
                            <textarea name="{{ field }}" rows="4"></textarea>
                        {% else %}
                            <input type="text" name="{{ field }}">
                        {% endif %}
                        {% if form_config['field_help'].get(field) %}<div class="field-help">{{ form_config['field_help'][field] }}</div>{% endif %}
                    </div>
                {% endfor %}
            </div>
            <button type="submit">등록하기</button>
        </form>
    </div>
    '''
    return render_page(
        body,
        title=f"새 문서 작성 | {section_label(requested_section)}",
        categories=categories,
        spec_fields=SPEC_FIELDS,
        form_config=form_config,
        section_label=section_label,
        active_section=requested_section,
    )


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
    section = normalize_section(asset["section"])
    body = r'''
    <div class="card">
        <div class="detail-head">
            <div>
                <div class="badge">{{ asset['category'] }}</div>
                <h1>{{ asset['title'] }}</h1>
                <div class="muted">섹션: {{ section_name }} | 작성자: {{ asset['author_name'] or '알 수 없음' }} | 생성: {{ asset['created_at'] }} | 수정: {{ asset['updated_at'] }}</div>
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
                {% if row['section_snapshot'] %}<div><strong>섹션:</strong> {{ row['section_snapshot'] }}</div>{% endif %}
                <div style="margin-top:8px;"><strong>제목 스냅샷:</strong> {{ row['title_snapshot'] or '' }}</div>
                {% if row['summary_snapshot'] %}<div><strong>요약:</strong> {{ row['summary_snapshot'] }}</div>{% endif %}
                {% if row['spec_snapshot'] %}<pre style="white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:12px;border:1px solid #e5e7eb;">{{ row['spec_snapshot'] }}</pre>{% endif %}
            </div>
        {% else %}
            <div class="muted">편집 이력이 없습니다.</div>
        {% endfor %}
    </div>
    '''
    return render_page(
        body,
        title=asset["title"],
        asset=asset,
        specs=specs,
        history=history,
        spec_fields=SPEC_FIELDS,
        active_section=section,
        section_name=section_label(section),
    )


@app.route("/edit/<int:asset_id>", methods=["GET", "POST"])
@login_required
def edit_asset(asset_id):
    asset = fetch_asset(asset_id)
    specs = fetch_specs(asset_id)
    if asset is None:
        flash("문서를 찾을 수 없습니다.", "danger")
        return redirect(url_for("home"))
    section = normalize_section(asset["section"])
    categories = get_categories_for_section(section)
    if request.method == "POST":
        section = normalize_section(request.form.get("section", asset["section"]))
        categories = get_categories_for_section(section)
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
        if category not in categories:
            flash("해당 섹션에서 사용할 수 없는 분류입니다.", "danger")
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
            "UPDATE assets SET title = ?, category = ?, summary = ?, description = ?, description_html = ?, image_data = ?, is_published = ?, section = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, category, summary, description, markdown_to_html(description), image_data, 1 if (current_user.is_admin and publish_now) else asset["is_published"], section, asset_id),
        )
        set_clause = ", ".join([f"{field} = ?" for field, _ in SPEC_FIELDS])
        spec_values = [new_specs[field] for field, _ in SPEC_FIELDS]
        ensure_specs_row(asset_id)
        db.execute(f"UPDATE asset_specs SET {set_clause} WHERE asset_id = ?", spec_values + [asset_id])
        db.commit()
        save_history(asset_id, current_user.id, "edit", title, summary, description, new_specs, section_snapshot=section)
        flash("문서가 수정되었습니다.", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))
    ensure_specs_row(asset_id)
    specs = fetch_specs(asset_id)
    form_config = get_form_config(section)
    body = r'''
    <div class="card">
        <div class="form-section-banner">
            <div>
                <div class="hero-kicker">{{ section_label(active_section) }}</div>
                <h2 style="margin-bottom:8px;">{{ form_config['headline'] }} 수정</h2>
                <div class="muted">{{ form_config['description'] }}</div>
            </div>
            <a class="ghost-link" href="{{ url_for('asset_detail', asset_id=asset['id']) }}">문서 보기</a>
        </div>
        <form method="post" enctype="multipart/form-data">
            <label>문서 섹션</label>
            <select name="section" required>
                <option value="air" {% if active_section == 'air' %}selected{% endif %}>에어딕셔너리</option>
                <option value="radio" {% if active_section == 'radio' %}selected{% endif %}>전파</option>
                <option value="constellation" {% if active_section == 'constellation' %}selected{% endif %}>별자리</option>
            </select>
            <div class="grid-two">
                <div>
                    <label>제목</label><input type="text" name="title" value="{{ asset['title'] }}" required>
                </div>
                <div>
                    <label>분류</label>
                    <select name="category" required>
                        {% for cat in categories %}<option value="{{ cat }}" {% if asset['category'] == cat %}selected{% endif %}>{{ cat }}</option>{% endfor %}
                    </select>
                </div>
            </div>
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
            <h3>문서 상세 정보 수정</h3>
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
                        {% if form_config['field_help'].get(field) %}<div class="field-help">{{ form_config['field_help'][field] }}</div>{% endif %}
                    </div>
                {% endfor %}
            </div>
            <button type="submit">수정 저장</button>
        </form>
    </div>
    '''
    return render_page(
        body,
        title="문서 수정",
        asset=asset,
        specs=specs,
        categories=categories,
        spec_fields=SPEC_FIELDS,
        form_config=form_config,
        section_label=section_label,
        active_section=section,
    )


@app.route("/delete/<int:asset_id>", methods=["POST"])
@admin_required
def delete_asset(asset_id):
    asset = fetch_asset(asset_id)
    if asset is None:
        flash("문서를 찾을 수 없습니다.", "danger")
        return redirect(url_for("admin_dashboard"))
    specs = fetch_specs(asset_id)
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO deleted_assets_log (
                original_asset_id, deleted_by, title_snapshot, section_snapshot, category_snapshot,
                summary_snapshot, description_snapshot, spec_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                current_user.id,
                asset["title"],
                normalize_section(asset["section"]),
                asset["category"],
                asset["summary"],
                asset["description"],
                specs_to_text({field: (specs[field] if specs else '') for field, _ in SPEC_FIELDS}),
            ),
        )
        db.execute("DELETE FROM edit_history WHERE asset_id = ?", (asset_id,))
        db.execute("DELETE FROM asset_specs WHERE asset_id = ?", (asset_id,))
        db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        db.commit()
        flash("문서가 삭제되었습니다.", "info")
    except Exception as exc:
        db.rollback()
        flash(f"삭제 중 오류가 발생했습니다: {exc}", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    assets = db.execute(
        "SELECT a.id, a.title, a.section, a.category, a.updated_at, a.is_published, u.username AS author_name FROM assets a LEFT JOIN users u ON a.created_by = u.id ORDER BY a.updated_at DESC"
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
            <thead><tr><th>ID</th><th>섹션</th><th>제목</th><th>분류</th><th>작성자</th><th>공개</th><th>최종 수정</th><th>작업</th></tr></thead>
            <tbody>
                {% for asset in assets %}
                <tr>
                    <td>{{ asset['id'] }}</td>
                    <td>{{ asset['section'] }}</td>
                    <td><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}">{{ asset['title'] }}</a></td>
                    <td>{{ asset['category'] }}</td>
                    <td>{{ asset['author_name'] or '알 수 없음' }}</td>
                    <td>{% if asset['is_published'] %}공개{% else %}비공개{% endif %}</td>
                    <td>{{ asset['updated_at'] }}</td>
                    <td>
                        <div class="btn-row">
                            <a class="ghost-link" href="{{ url_for('edit_asset', asset_id=asset['id']) }}">수정</a>
                            <form method="post" action="{{ url_for('delete_asset', asset_id=asset['id']) }}" onsubmit="return confirm('정말 삭제하시겠습니까?');">
                                <button class="btn-danger" type="submit" style="margin-top:0;">삭제</button>
                            </form>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    '''
    return render_page(body, title="관리자 페이지", users=users, assets=assets, active_section="air")



@app.errorhandler(500)
def internal_error(error):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.rollback()
        except Exception:
            pass
    body = r'''
    <div class="card">
        <h2>서버 오류가 발생했습니다.</h2>
        <p class="muted">관리자 작업 도중 문제가 생기면 다시 시도해보시고, DB 구조가 바뀐 경우에는 앱을 재실행해 초기화 보정이 적용되도록 해주세요.</p>
        <div class="btn-row">
            <a class="btn-link" href="{{ url_for('admin_dashboard') if current_user.is_authenticated and current_user.is_admin else url_for('intro_page') }}">돌아가기</a>
        </div>
    </div>
    '''
    return render_page(body, title='서버 오류', active_section='intro'), 500


@app.route("/init-db")
def init_db_route():
    init_db()
    return "DB initialized"


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)

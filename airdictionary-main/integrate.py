
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
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"
login_manager.init_app(app)

AIR_CATEGORIES = [
    "전투기", "폭격기", "수송기", "조기경보기", "공중급유기", "정찰기", "훈련기",
    "무인기", "항공모함", "핵잠수함", "탄도미사일", "순항미사일", "방공체계",
    "우주자산", "기타 전략자산",
]

RADIO_CATEGORIES = [
    "Radio 일반", "주파수 대역", "레이더", "통신", "전자전", "신호정보", "Radio천문", "기타"
]

CONSTELLATION_CATEGORIES = [
    "황도 12궁", "북반구 Constellation", "남반구 Constellation", "계절별 Constellation", "성단/성운", "관측 가이드", "기타"
]

CATEGORY_DISPLAY_MAP = {
    "전투기": "Fighter", "폭격기": "Bomber", "수송기": "Transport", "조기경보기": "AEW&C",
    "공중급유기": "Tanker", "정찰기": "Reconnaissance", "훈련기": "Trainer", "무인기": "UAV",
    "항공모함": "Aircraft Carrier", "핵잠수함": "Nuclear Submarine", "탄도미사일": "Ballistic Missile",
    "순항미사일": "Cruise Missile", "방공체계": "Air Defense System", "우주자산": "Space Asset",
    "기타 전략자산": "Other Strategic Asset", "Radio 일반": "General Radio", "주파수 대역": "Frequency Band",
    "레이더": "Radar", "통신": "Communications", "전자전": "Electronic Warfare", "신호정보": "SIGINT",
    "Radio천문": "Radio Astronomy", "기타": "Other", "황도 12궁": "Zodiac", "북반구 Constellation": "Northern Hemisphere",
    "남반구 Constellation": "Southern Hemisphere", "계절별 Constellation": "Seasonal Constellation", "성단/성운": "Cluster / Nebula",
    "관측 가이드": "Observation Guide",
}

SECTION_CONFIG = {
    "air": {
        "name": "Air Dictionary",
        "title": "Air Asset Wiki",
        "hero_title": "Strategic Airpower Knowledge Base",
        "hero_subtitle": "A polished archive for airpower, radio spectrum, and constellation research.",
        "hero_desc": "Built as a clean, expandable knowledge system with section-specific forms and administrative tools.",
        "categories": AIR_CATEGORIES,
    },
    "radio": {
        "name": "Radio",
        "title": "Radio Wiki",
        "hero_title": "Radio Spectrum & EW Library",
        "hero_subtitle": "Frequencies, radar, communications, and electronic warfare notes.",
        "hero_desc": "Organize aviation frequencies, spectrum references, and electronic warfare concepts in one place.",
        "categories": RADIO_CATEGORIES,
    },
    "constellation": {
        "name": "Constellation",
        "title": "Constellation Wiki",
        "hero_title": "Constellation Archive",
        "hero_subtitle": "Constellations, seasonal viewing, and astronomy reference notes.",
        "hero_desc": "A dedicated section for stargazing references and sky observation notes.",
        "categories": CONSTELLATION_CATEGORIES,
    },
}


CONTACT_NAME = "Your Name / Team Name"
CONTACT_EMAIL = "your-email@example.com"
CONTACT_PHONE = "010-0000-0000"
CONTACT_NOTE = "Update the banner text and contact details directly in this file."

SECTION_FORM_CONFIG = {
    "air": {
        "headline": "Air Dictionary 문서 작성",
        "description": "항공기·전략자산 중심 입력폼입니다. 기체 개요와 스펙을 자세히 적기 좋게 구성했습니다.",
        "title_placeholder": "예: F-22 Raptor / B-2 Spirit / E-3 Sentry",
        "summary_placeholder": "카드에 보일 짧은 요약을 입력하세요.",
        "description_placeholder": "개발 배경, 실전 운용, 특징, 장단점 등을 Markdown으로 작성하세요.",
        "field_help": {
            "manufacturer": "제작사 또는 주계약업체",
            "country": "주 운용 국가 또는 개발 국가",
            "role": "제공전투, 전략폭격, ISR 등",
            "armament": "대표 무장, 탑재량, 하드포인트 등",
            "notes": "운용 사례, 파생형, 비교 메모",
        },
    },
    "radio": {
        "headline": "Radio 문서 작성",
        "description": "항공 주파수, 레이더, 통신, 전자전 내용을 정리하기 좋게 구성한 폼입니다.",
        "title_placeholder": "예: Emergency 121.5 MHz / AN-ALQ-99 / X-band",
        "summary_placeholder": "주파수 대역 또는 전자전 항목 요약",
        "description_placeholder": "용도, 대역폭, 군/민간 사용 예시, 운용 주의사항 등을 작성하세요.",
        "field_help": {
            "manufacturer": "장비 제작사 또는 표준 제정 기관",
            "country": "주요 사용 국가 또는 국제 표준 여부",
            "role": "교신, 감시, 항법, 재밍, SIGINT 등",
            "max_speed": "해당 없으면 비워두고, 대신 주파수/대역폭은 비고에 적어도 됩니다.",
            "notes": "주파수, 대역, 프로토콜, 전술적 의미 등을 자유롭게 기록",
        },
    },
    "constellation": {
        "headline": "Constellation 문서 작성",
        "description": "Constellation, 관측 포인트, 계절별 특징을 기록하기 좋은 폼입니다.",
        "title_placeholder": "예: Orion / Cassiopeia / Scorpius",
        "summary_placeholder": "대표 밝은 별, 계절, 관측 포인트 요약",
        "description_placeholder": "형태, 찾는 법, 관련 신화, 관측 시기 등을 Markdown으로 작성하세요.",
        "field_help": {
            "manufacturer": "해당 없으면 비워도 됩니다. 망원경/관측 장비 추천을 적어도 됩니다.",
            "country": "북반구/남반구 관측 기준 국가나 지역 메모 가능",
            "role": "관측 포인트, 계절 Category, 교육용 설명 등",
            "notes": "적경/적위, 관측 난이도, 연결되는 Constellation 메모",
        },
    },
}

SPEC_FIELDS = [
    ("manufacturer", "Manufacturer"),
    ("country", "Country"),
    ("role", "Role"),
    ("first_flight", "First Flight"),
    ("introduced", "Introduced"),
    ("status", "Status"),
    ("crew", "Crew"),
    ("length", "Length"),
    ("wingspan", "Wingspan"),
    ("height", "Height"),
    ("max_speed", "Max Speed"),
    ("range_km", "Range"),
    ("combat_radius", "Combat Radius"),
    ("service_ceiling", "Service Ceiling"),
    ("engine", "Engine"),
    ("powerplant", "Powerplant"),
    ("armament", "Armament"),
    ("notes", "Notes"),
]

BASE_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title or 'Strategic Knowledge Archive' }}</title>
    <style>
        :root {
            --surface: rgba(255,255,255,0.96);
            --line: rgba(148,163,184,0.24);
            --line-strong: rgba(148,163,184,0.34);
            --text: #0f172a;
            --muted: #64748b;
            --blue: #2563eb;
            --cyan: #38bdf8;
            --violet: #7c3aed;
            --shadow: 0 24px 60px rgba(2, 8, 23, 0.16);
            --shadow-soft: 0 12px 34px rgba(15,23,42,0.10);
        }
        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        body {
            margin: 0;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background:
                radial-gradient(circle at top left, rgba(56,189,248,0.18), transparent 26%),
                radial-gradient(circle at top right, rgba(124,58,237,0.14), transparent 22%),
                linear-gradient(180deg, #06101d 0%, #0b1730 18%, #eef4fb 18%, #f4f7fb 100%);
            color: var(--text);
        }
        .container { width: min(1220px, 94%); margin: 0 auto; }
        .topbar {
            position: sticky; top: 0; z-index: 30; backdrop-filter: blur(18px);
            background: rgba(8, 17, 32, 0.82); color: white;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .topbar-inner { display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap; padding:14px 0; }
        .logo-wrap { display:flex; align-items:center; gap:12px; }
        .logo-mark {
            width:44px; height:44px; border-radius:15px;
            background: linear-gradient(135deg, var(--blue), var(--cyan), #a855f7);
            display:grid; place-items:center; font-weight:800; color:white; box-shadow: 0 14px 28px rgba(37,99,235,0.30);
        }
        .logo { color:white; text-decoration:none; font-size:23px; font-weight:800; letter-spacing:-0.02em; }
        .logo-sub { color:rgba(255,255,255,0.7); font-size:12px; margin-top:3px; }
        .nav-links { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
        .nav-links a, .nav-links span {
            color:white; text-decoration:none; padding:9px 12px; border-radius:999px; font-size:14px;
            background: rgba(255,255,255,0.04); border:1px solid transparent;
        }
        .nav-links a:hover, .nav-links a.active { background:rgba(255,255,255,0.12); border-color:rgba(255,255,255,0.12); }
        .main { padding:28px 0 56px; }
        .card {
            background: rgba(255,255,255,0.97); border-radius:24px; box-shadow:var(--shadow);
            padding:24px; margin-bottom:22px; border:1px solid rgba(219,228,240,0.95);
        }
        .glass-card {
            background: linear-gradient(145deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06));
            color:white; border:1px solid rgba(255,255,255,0.1); border-radius:28px;
            box-shadow: 0 22px 60px rgba(2,8,23,0.22);
        }
        .hero { padding:34px; background: linear-gradient(135deg, rgba(239,246,255,0.98), rgba(255,255,255,0.98)); border:1px solid #dbeafe; }
        h1, h2, h3 { margin-top:0; letter-spacing:-0.03em; }
        h1 { font-size:clamp(30px, 5vw, 52px); line-height:1.04; margin-bottom:14px; }
        h2 { font-size:clamp(24px, 4vw, 34px); margin-bottom:14px; }
        h3 { font-size:20px; margin-bottom:10px; }
        p { line-height:1.7; }
        .muted { color:var(--muted); }
        .small { font-size:13px; }
        .narrow { width:min(560px, 100%); margin:0 auto; }
        .hero-grid, .asset-grid, .section-card-grid, .intro-stats, .btn-row, .pill-wrap, .search-grid { display:grid; gap:16px; }
        .hero-grid { grid-template-columns:1.5fr 0.9fr; align-items:stretch; }
        .asset-grid { grid-template-columns:repeat(3, minmax(0, 1fr)); }
        .section-card-grid { grid-template-columns:repeat(3, minmax(0, 1fr)); }
        .intro-stats { grid-template-columns:repeat(3, minmax(0, 1fr)); margin-top:18px; }
        .btn-row { grid-template-columns:repeat(auto-fit, minmax(180px, max-content)); align-items:center; justify-content:start; }
        .pill-wrap { grid-template-columns:repeat(auto-fit, minmax(100px, max-content)); }
        .search-grid { grid-template-columns:1.5fr 1fr auto; align-items:end; }
        .section-tabs { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; }
        .section-tab, .ghost-link, .pill-link, .btn-link, button {
            appearance:none; display:inline-flex; align-items:center; justify-content:center; gap:8px;
            text-decoration:none; border:0; cursor:pointer; font-weight:700; transition:.2s ease;
        }
        .section-tab, .pill-link, .ghost-link {
            padding:10px 14px; border-radius:999px; border:1px solid var(--line-strong);
            background: rgba(255,255,255,0.76); color:var(--muted);
        }
        .section-tab.active, .section-tab:hover, .pill-link.active, .pill-link:hover {
            color:white; border-color:transparent; background: linear-gradient(135deg, var(--blue), var(--violet));
            box-shadow: 0 14px 28px rgba(37,99,235,0.18);
        }
        .btn-link, button[type="submit"] {
            background: linear-gradient(135deg, var(--blue), var(--cyan));
            color:white; padding:12px 16px; border-radius:14px; box-shadow: 0 14px 28px rgba(37,99,235,0.18);
        }
        .ghost-link:hover { transform:translateY(-1px); background:white; color:var(--text); }
        input[type="text"], input[type="password"], input[type="file"], select, textarea {
            width:100%; border-radius:16px; border:1px solid var(--line-strong);
            background:rgba(255,255,255,0.95); color:var(--text); padding:13px 14px; font:inherit;
        }
        textarea { min-height:160px; resize:vertical; }
        label { display:block; font-weight:700; margin-bottom:6px; }
        .checkbox-inline { display:flex; align-items:center; gap:8px; }
        .asset-card, .section-mini-card, .intro-panel, .stat-box {
            background: rgba(255,255,255,0.96); border-radius:22px; border:1px solid rgba(226,232,240,0.95);
            box-shadow: var(--shadow-soft);
        }
        .asset-card { overflow:hidden; }
        .asset-body { padding:18px; }
        .thumb, .thumb-placeholder { width:100%; height:220px; display:flex; align-items:center; justify-content:center; }
        .thumb { object-fit:cover; }
        .thumb-placeholder { background:linear-gradient(135deg, #dbeafe, #eff6ff); color:#1e3a8a; font-weight:800; }
        .badge, .admin-badge, .count-chip, .hero-kicker, .section-kicker {
            display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:7px 11px; font-size:12px; font-weight:800;
        }
        .badge { background:rgba(37,99,235,0.10); color:var(--blue); }
        .admin-badge { background:rgba(124,58,237,0.12); color:var(--violet); }
        .count-chip, .hero-kicker { background:rgba(255,255,255,0.14); color:white; border:1px solid rgba(255,255,255,0.12); }
        .section-kicker { background:rgba(37,99,235,0.08); color:var(--blue); }
        .intro-panel { padding:24px; background:rgba(255,255,255,0.08); border-color:rgba(255,255,255,0.1); color:white; }
        .section-mini-card { padding:22px; }
        .stat-box { padding:18px; text-align:center; }
        .stat-box strong { display:block; font-size:34px; margin-bottom:6px; }
        .flash { border-radius:16px; padding:12px 14px; margin-bottom:10px; border:1px solid transparent; font-weight:600; }
        .flash.success { background:rgba(22,163,74,0.10); color:#166534; border-color:rgba(22,163,74,0.18); }
        .flash.info { background:rgba(37,99,235,0.10); color:#1d4ed8; border-color:rgba(37,99,235,0.18); }
        .flash.warning { background:rgba(245,158,11,0.10); color:#b45309; border-color:rgba(245,158,11,0.18); }
        .flash.danger { background:rgba(220,38,38,0.10); color:#b91c1c; border-color:rgba(220,38,38,0.18); }
        .detail-image { width:100%; max-width:360px; border-radius:18px; border:1px solid rgba(226,232,240,0.95); }
        table { width:100%; border-collapse:collapse; }
        th, td { padding:12px 10px; border-bottom:1px solid rgba(226,232,240,0.85); text-align:left; vertical-align:top; }
        th { font-size:13px; text-transform:uppercase; letter-spacing:0.04em; color:#475569; }
        .footer-banner {
            display:block; width:100%; margin-top:40px; padding:24px; border-radius:30px;
            background: linear-gradient(135deg, rgba(8,15,29,0.97), rgba(13,27,55,0.94));
            color:white; box-shadow: 0 26px 70px rgba(2,8,23,0.34), 0 0 0 1px rgba(255,255,255,0.06) inset;
            border:1px solid rgba(255,255,255,0.08);
        }
        .footer-banner-inner { display:grid; grid-template-columns:minmax(220px,1fr) minmax(260px,1.2fr) minmax(220px,1fr); gap:16px; align-items:center; }
        .logo-column { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
        .logo-slot {
            min-height:82px; border-radius:18px; border:1px dashed rgba(255,255,255,0.24); background:rgba(255,255,255,0.05);
            display:flex; align-items:center; justify-content:center; text-align:center; padding:12px; font-size:12px; color:rgba(255,255,255,0.82);
        }
        .footer-center { text-align:center; padding:8px 12px; }
        .footer-center h3 { margin-bottom:8px; font-size:24px; }
        .footer-center p { margin:6px 0; color:rgba(255,255,255,0.82); }
        @media (max-width: 960px) {
            .hero-grid, .asset-grid, .section-card-grid, .intro-stats, .footer-banner-inner { grid-template-columns:1fr; }
            .search-grid { grid-template-columns:1fr; }
        }
    </style>
</head>
<body>
    <div class="topbar">
        <div class="container topbar-inner">
            <div class="logo-wrap">
                <div class="logo-mark">SA</div>
                <div>
                    <a class="logo" href="{{ url_for('intro_page') }}">Strategic Archive</a>
                    <div class="logo-sub">Airpower · Radio Spectrum · Constellations</div>
                </div>
            </div>
            <div class="nav-links">
                <a href="{{ url_for('intro_page') }}" class="{% if active_section == 'intro' %}active{% endif %}">About</a>
                <a href="{{ url_for('home') }}" class="{% if active_section == 'air' %}active{% endif %}">Air Dictionary</a>
                <a href="{{ url_for('radio_home') }}" class="{% if active_section == 'radio' %}active{% endif %}">Radio</a>
                <a href="{{ url_for('constellation_home') }}" class="{% if active_section == 'constellation' %}active{% endif %}">Constellation</a>
                {% if current_user.is_authenticated %}
                    <a href="{{ url_for('create_asset', section=active_section if active_section in ['air','radio','constellation'] else 'air') }}">New Entry</a>
                    {% if current_user.is_admin %}<a href="{{ url_for('admin_dashboard') }}">Admin</a>{% endif %}
                    <a href="{{ url_for('admin.index') }}">Control Panel</a>
                    <span>{{ current_user.username }} {% if current_user.is_admin %}<span class="admin-badge">ADMIN</span>{% endif %}</span>
                    <a href="{{ url_for('logout') }}">Log Out</a>
                {% else %}
                    <a href="{{ url_for('login') }}">Log In</a>
                    <a href="{{ url_for('register') }}">Sign Up</a>
                {% endif %}
            </div>
        </div>
    </div>

    <main class="main">
        <div class="container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="flash {{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            {{ body|safe }}

            <section class="footer-banner" id="contact-banner">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:18px;">
                    <div>
                        <div class="hero-kicker">Footer Banner</div>
                        <h2 style="margin:10px 0 6px;color:white;">Contact & Service Banner</h2>
                        <p style="margin:0;color:rgba(255,255,255,0.78);">This banner appears at the bottom of every page.</p>
                    </div>
                    <a href="{{ url_for('intro_page') }}" class="ghost-link" style="background:rgba(255,255,255,0.08);color:white;border-color:rgba(255,255,255,0.16);">About</a>
                </div>
                <div class="footer-banner-inner">
                    <div class="logo-column">
                        {% for name in ['army.png','navy.png','airforce.png'] %}
                            {% if logo_exists(name) %}
                                <div class="logo-slot" style="padding:8px;"><img src="{{ url_for('static', filename='logos/' ~ name) }}" alt="{{ name }}" style="max-width:100%;max-height:58px;object-fit:contain;"></div>
                            {% else %}
                                <div class="logo-slot"><strong>US Armed Forces</strong><br>{{ name }}</div>
                            {% endif %}
                        {% endfor %}
                    </div>
                    <div class="footer-center">
                        <div class="badge" style="background:rgba(255,255,255,0.12);color:white;">Contact</div>
                        <h3>{{ contact_name }}</h3>
                        <p><strong>Email</strong> · {{ contact_email }}</p>
                        <p><strong>Phone</strong> · {{ contact_phone }}</p>
                        <p class="small" style="color:rgba(255,255,255,0.72);">{{ contact_note }}</p>
                    </div>
                    <div class="logo-column">
                        {% for name in ['marines.png','spaceforce.png','coastguard.png'] %}
                            {% if logo_exists(name) %}
                                <div class="logo-slot" style="padding:8px;"><img src="{{ url_for('static', filename='logos/' ~ name) }}" alt="{{ name }}" style="max-width:100%;max-height:58px;object-fit:contain;"></div>
                            {% else %}
                                <div class="logo-slot"><strong>US Armed Forces</strong><br>{{ name }}</div>
                            {% endif %}
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


def display_category(category):
    return CATEGORY_DISPLAY_MAP.get(category, category)


def logo_exists(filename):
    return os.path.exists(os.path.join(BASE_DIR, "static", "logos", filename))


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
            flash("Administrator Role이 필요합니다.", "danger")
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
    context.setdefault("display_category", display_category)
    context.setdefault("logo_exists", logo_exists)
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
            flash("Administrator만 접근 가능합니다.", "danger")
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
        flash("Administrator만 접근 가능합니다.", "danger")
        return redirect(url_for("login"))


admin = Admin(
    app,
    name="Air Asset Admin",
    url="/admin-panel",
    index_view=SimpleAdminIndexView(name="Dashboard", url="/admin-panel"),
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
            <a class="section-tab {% if active_section == 'air' %}active{% endif %}" href="{{ url_for('home') }}">Air Dictionary</a>
            <a class="section-tab {% if active_section == 'radio' %}active{% endif %}" href="{{ url_for('radio_home') }}">Radio</a>
            <a class="section-tab {% if active_section == 'constellation' %}active{% endif %}" href="{{ url_for('constellation_home') }}">Constellation</a>
        </div>
        <div class="hero-kicker">{{ config['title'] }}</div>
        <h1>{{ config['hero_title'] }}</h1>
        <p style="font-size:18px;margin:0 0 10px;">{{ config['hero_subtitle'] }}</p>
        <p class="muted">{{ config['hero_desc'] }}</p>
        <div class="btn-row" style="margin-top:14px;">
            <a class="ghost-link" href="{{ url_for('intro_page') }}">About</a>
            {% if current_user.is_authenticated %}<a class="btn-link" href="{{ url_for('create_asset', section=active_section) }}">Create a new entry in this section</a>{% endif %}
        </div>
    </section>
    <section class="card">
        <form method="get" class="search-grid">
            <input type="text" name="q" placeholder="Search title or description" value="{{ q }}">
            <select name="category">
                <option value="">All Categories</option>
                {% for cat in categories %}
                    <option value="{{ display_category(cat) }}" {% if category == cat %}selected{% endif %}>{{ display_category(cat) }}</option>
                {% endfor %}
            </select>
            <button type="submit">Search</button>
        </form>
        <div class="pill-wrap">
            <a class="pill-link {% if not category %}active{% endif %}" href="{{ section_url }}">All</a>
            {% for cat in categories %}
                <a class="pill-link {% if category == cat %}active{% endif %}" href="{{ section_url }}?category={{ cat|urlencode }}{% if q %}&q={{ q|urlencode }}{% endif %}">{{ display_category(cat) }}</a>
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
                    <div class="badge">{{ display_category(asset['category']) }}</div>
                    <h3><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}" style="text-decoration:none;color:#0f172a;">{{ asset['title'] }}</a></h3>
                    <p>{{ asset['summary'] or 'No description available yet.' }}</p>
                    <div class="muted small">Author: {{ asset['author_name'] or 'Unknown' }}</div>
                </div>
            </article>
        {% else %}
            <div class="card"><strong>No entries are available yet.</strong></div>
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
                <h1>Air · Radio · Constellation<br>Integrated Archive</h1>
                <p style="font-size:18px;line-height:1.8;color:rgba(255,255,255,0.88);margin:0;">항공 전력, Radio·전자전, Constellation 관측 자료를 한곳에 정리하는 개인 아카이브입니다. 문서 Search, 카테고리 탐색, 신규 문서 작성, Administrator 운영까지 한 사이트 안에서 돌아가도록 구성했습니다.</p>
                <div class="intro-actions">
                    <a class="btn-link" href="{{ url_for('home') }}">Air Dictionary 바로가기</a>
                    <a class="ghost-link" style="color:white;background:rgba(255,255,255,0.1);border-color:rgba(255,255,255,0.18);" href="{{ url_for('radio_home') }}">Radio 자료 보기</a>
                    <a class="ghost-link" style="color:white;background:rgba(255,255,255,0.1);border-color:rgba(255,255,255,0.18);" href="{{ url_for('constellation_home') }}">Constellation 보기</a>
                </div>
                <ul class="hero-list" style="color:rgba(255,255,255,0.82);">
                    <li>Air Dictionary: 전투기·폭격기·수송기·ISR 등 확장 데이터베이스</li>
                    <li>Radio: 항공용 주파수, 군용 전자전, 레이더/통신 메모 정리</li>
                    <li>Constellation: 관측용 문서, 계절별 Constellation 정리, 이후 지도 기능 확장 가능</li>
                </ul>
            </div>
            <div class="intro-panel">
                <div class="hero-kicker" style="background:rgba(255,255,255,0.12);color:white;">Archive Status</div>
                <div>
                    <span class="count-chip">Air Dictionary {{ counts['air'] }}개</span>
                    <span class="count-chip">Radio {{ counts['radio'] }}개</span>
                    <span class="count-chip">Constellation {{ counts['constellation'] }}개</span>
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
            <h3>Air Dictionary</h3>
            <p class="muted">Manage airpower and strategic asset entries by category.</p>
            <a class="btn-link" href="{{ url_for('home') }}">Open</a>
        </article>
        <article class="section-mini-card">
            <div class="section-kicker">Radio</div>
            <h3>Radio</h3>
            <p class="muted">Organize aviation frequencies, military EW topics, and communications/radar references.</p>
            <a class="btn-link" href="{{ url_for('radio_home') }}">Open</a>
        </article>
        <article class="section-mini-card">
            <div class="section-kicker">Constellation</div>
            <h3>Constellation</h3>
            <p class="muted">Constellation와 관측 정보를 기록하는 천문 아카이브입니다.</p>
            <a class="btn-link" href="{{ url_for('constellation_home') }}">Open</a>
        </article>
    </section>
    <section class="card">
        <h2>Recent Updates</h2>
        <div class="asset-grid">
            {% for asset in recent_assets %}
            <article class="asset-card">
                <div class="thumb-placeholder">{{ asset['section']|upper }}</div>
                <div class="asset-body">
                    <div class="badge">{{ display_category(asset['category']) }}</div>
                    <h3><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}" style="text-decoration:none;color:#0f172a;">{{ asset['title'] }}</a></h3>
                    <div class="muted small">Section: {{ asset['section'] }} · Updated: {{ asset['updated_at'] }}</div>
                </div>
            </article>
            {% endfor %}
        </div>
    </section>
    '''
    return render_page(body, title="About", counts=counts, recent_assets=recent_assets, active_section="intro")


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
            flash("Please enter a username and password.", "danger")
            return redirect(url_for("register"))
        if password != password2:
            flash("Password confirmation does not match.", "danger")
            return redirect(url_for("register"))
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            flash("That username already exists.", "danger")
            return redirect(url_for("register"))
        db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)", (username, generate_password_hash(password)))
        db.commit()
        flash("Registration complete. Please log in.", "success")
        return redirect(url_for("login"))
    body = r'''
    <div class="card narrow">
        <h2>Sign Up</h2>
        <form method="post">
            <label>Username</label><input type="text" name="username" required>
            <label>Password</label><input type="password" name="password" required>
            <label>Confirm Password</label><input type="password" name="password2" required>
            <button type="submit">Sign Up</button>
        </form>
    </div>
    '''
    return render_page(body, title="Sign Up", active_section="air")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            flash("Username 또는 Password가 올바르지 않습니다.", "danger")
            return redirect(url_for("login"))
        login_user(User(row))
        flash("You are now logged in.", "success")
        return redirect(url_for("home"))
    body = r'''
    <div class="card narrow">
        <h2>Log In</h2>
        <form method="post">
            <label>Username</label><input type="text" name="username" required>
            <label>Password</label><input type="password" name="password" required>
            <button type="submit">Log In</button>
        </form>
        <p class="muted small" style="margin-top:14px;">Default admin account: admin / admin1234</p>
    </div>
    '''
    return render_page(body, title="Log In", active_section="air")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
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
            flash("Title and category are required.", "danger")
            return redirect(url_for("create_asset", section=section))
        if category not in categories:
            flash("That category is not allowed in this section.", "danger")
            return redirect(url_for("create_asset", section=section))
        image_data = None
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("Images must be png, jpg/jpeg, gif, or webp.", "danger")
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
        flash("The new entry has been created.", "success")
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
            <a class="ghost-link" href="{{ url_for('intro_page') }}">About</a>
        </div>
        <form method="post" enctype="multipart/form-data">
            <label>Entry Section</label>
            <select name="section" required onchange="window.location='{{ url_for('create_asset') }}?section=' + this.value;">
                <option value="air" {% if active_section == 'air' %}selected{% endif %}>Air Dictionary</option>
                <option value="radio" {% if active_section == 'radio' %}selected{% endif %}>Radio</option>
                <option value="constellation" {% if active_section == 'constellation' %}selected{% endif %}>Constellation</option>
            </select>
            <div class="grid-two">
                <div>
                    <label>Title</label><input type="text" name="title" placeholder="{{ form_config['title_placeholder'] }}" required>
                </div>
                <div>
                    <label>Category</label>
                    <select name="category" required>
                        <option value="">Select one</option>
                        {% for cat in categories %}<option value="{{ display_category(cat) }}">{{ display_category(cat) }}</option>{% endfor %}
                    </select>
                </div>
            </div>
            <label>Short Summary</label><input type="text" name="summary" placeholder="{{ form_config['summary_placeholder'] }}">
            <label>Detailed Description (Markdown supported)</label><textarea name="description" rows="10" placeholder="{{ form_config['description_placeholder'] }}"></textarea>
            <label>Upload Image</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" checked> Publish immediately</label>{% endif %}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <h3>Entry Specifications</h3>
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
            <button type="submit">Create Entry</button>
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
        flash("The entry could not be found.", "danger")
        return redirect(url_for("home"))
    if not asset["is_published"] and not (current_user.is_authenticated and current_user.is_admin):
        flash("This entry is not published yet.", "warning")
        return redirect(url_for("home"))
    specs = fetch_specs(asset_id)
    history = fetch_history(asset_id)
    section = normalize_section(asset["section"])
    body = r'''
    <div class="card">
        <div class="detail-head">
            <div>
                <div class="badge">{{ display_category(asset['category']) }}</div>
                <h1>{{ asset['title'] }}</h1>
                <div class="muted">Section: {{ section_name }} | Author: {{ asset['author_name'] or 'Unknown' }} | Created: {{ asset['created_at'] }} | Updated: {{ asset['updated_at'] }}</div>
                {% if not asset['is_published'] %}<div class="admin-badge" style="margin-top:10px;">Private Draft</div>{% endif %}
            </div>
            {% if current_user.is_authenticated %}
                <div class="btn-row">
                    <a class="btn-link" href="{{ url_for('edit_asset', asset_id=asset['id']) }}">Edit</a>
                    {% if current_user.is_admin %}
                    <form method="post" action="{{ url_for('delete_asset', asset_id=asset['id']) }}" onsubmit="return confirm('Are you sure you want to delete this entry?');">
                        <button class="btn-danger" type="submit">Delete</button>
                    </form>
                    {% endif %}
                </div>
            {% endif %}
        </div>
        {% if asset['image_data'] %}<img class="detail-image" src="{{ asset['image_data'] }}" alt="{{ asset['title'] }}">{% endif %}
        {% if asset['summary'] %}<div class="summary-box">{{ asset['summary'] }}</div>{% endif %}
        <h2>Overview</h2>
        <div class="wiki-content">{{ asset['description_html'] | safe }}</div>
        <h2 style="margin-top:28px;">Specifications</h2>
        <table class="spec-table"><tbody>
            {% for field, label in spec_fields %}
                {% set value = specs[field] if specs else '' %}
                {% if value %}<tr><th>{{ label }}</th><td>{{ value }}</td></tr>{% endif %}
            {% endfor %}
        </tbody></table>
    </div>
    <div class="card">
        <h2>Edit History</h2>
        {% for row in history %}
            <div class="history-item">
                <strong>{{ row['action_type'] }}</strong>
                <div class="muted small">Edited by: {{ row['editor_name'] or 'Unknown' }} | Time: {{ row['edited_at'] }}</div>
                {% if row['section_snapshot'] %}<div><strong>섹션:</strong> {{ row['section_snapshot'] }}</div>{% endif %}
                <div style="margin-top:8px;"><strong>Title 스냅샷:</strong> {{ row['title_snapshot'] or '' }}</div>
                {% if row['summary_snapshot'] %}<div><strong>Summary:</strong> {{ row['summary_snapshot'] }}</div>{% endif %}
                {% if row['spec_snapshot'] %}<pre style="white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:12px;border:1px solid #e5e7eb;">{{ row['spec_snapshot'] }}</pre>{% endif %}
            </div>
        {% else %}
            <div class="muted">Edit History이 없습니다.</div>
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
        flash("The entry could not be found.", "danger")
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
            flash("Title and category are required.", "danger")
            return redirect(url_for("edit_asset", asset_id=asset_id))
        if category not in categories:
            flash("That category is not allowed in this section.", "danger")
            return redirect(url_for("edit_asset", asset_id=asset_id))
        image_data = None if remove_image else asset["image_data"]
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("Images must be png, jpg/jpeg, gif, or webp.", "danger")
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
        flash("문서가 Edit되었습니다.", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))
    ensure_specs_row(asset_id)
    specs = fetch_specs(asset_id)
    form_config = get_form_config(section)
    body = r'''
    <div class="card">
        <div class="form-section-banner">
            <div>
                <div class="hero-kicker">{{ section_label(active_section) }}</div>
                <h2 style="margin-bottom:8px;">{{ form_config['headline'] }} Edit</h2>
                <div class="muted">{{ form_config['description'] }}</div>
            </div>
            <a class="ghost-link" href="{{ url_for('asset_detail', asset_id=asset['id']) }}">View Entry</a>
        </div>
        <form method="post" enctype="multipart/form-data">
            <label>Entry Section</label>
            <select name="section" required>
                <option value="air" {% if active_section == 'air' %}selected{% endif %}>Air Dictionary</option>
                <option value="radio" {% if active_section == 'radio' %}selected{% endif %}>Radio</option>
                <option value="constellation" {% if active_section == 'constellation' %}selected{% endif %}>Constellation</option>
            </select>
            <div class="grid-two">
                <div>
                    <label>Title</label><input type="text" name="title" value="{{ asset['title'] }}" required>
                </div>
                <div>
                    <label>Category</label>
                    <select name="category" required>
                        {% for cat in categories %}<option value="{{ display_category(cat) }}" {% if asset['category'] == cat %}selected{% endif %}>{{ display_category(cat) }}</option>{% endfor %}
                    </select>
                </div>
            </div>
            <label>Short Summary</label><input type="text" name="summary" value="{{ asset['summary'] or '' }}">
            <label>Detailed Description (Markdown supported)</label><textarea name="description" rows="10">{{ asset['description'] or '' }}</textarea>
            {% if asset['image_data'] %}
                <label>Current Image</label>
                <img class="detail-image" src="{{ asset['image_data'] }}" alt="Current Image" style="max-width:320px;">
                <label class="checkbox-inline"><input type="checkbox" name="remove_image"> Current Image Delete</label>
            {% endif %}
            <label>새 Upload Image</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" {% if asset['is_published'] %}checked{% endif %}> Keep/change published status</label>{% endif %}
            <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb;">
            <h3>Entry Specifications Edit</h3>
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
            <button type="submit">Edit 저장</button>
        </form>
    </div>
    '''
    return render_page(
        body,
        title="문서 Edit",
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
        flash("The entry could not be found.", "danger")
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
        flash("문서가 Delete되었습니다.", "info")
    except Exception as exc:
        db.rollback()
        flash(f"Delete 중 오류가 발생했습니다: {exc}", "danger")
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
    <div class="card"><h2>Admin Dashboard</h2><p class="muted">회원 Role, 문서 Published 상태, All 현황을 볼 수 있습니다.</p></div>
    <div class="card">
        <h3>User List</h3>
        <table class="spec-table">
            <thead><tr><th>ID</th><th>Username</th><th>Role</th><th>Created</th></tr></thead>
            <tbody>
                {% for user in users %}
                <tr><td>{{ user['id'] }}</td><td>{{ user['username'] }}</td><td>{% if user['is_admin'] %}Administrator{% else %}Member{% endif %}</td><td>{{ user['created_at'] }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="card">
        <h3>All 문서 현황</h3>
        <table class="spec-table">
            <thead><tr><th>ID</th><th>섹션</th><th>Title</th><th>Category</th><th>Author</th><th>Published</th><th>최종 Edit</th><th>Actions</th></tr></thead>
            <tbody>
                {% for asset in assets %}
                <tr>
                    <td>{{ asset['id'] }}</td>
                    <td>{{ asset['section'] }}</td>
                    <td><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}">{{ asset['title'] }}</a></td>
                    <td>{{ display_category(asset['category']) }}</td>
                    <td>{{ asset['author_name'] or 'Unknown' }}</td>
                    <td>{% if asset['is_published'] %}Published{% else %}비Published{% endif %}</td>
                    <td>{{ asset['updated_at'] }}</td>
                    <td>
                        <div class="btn-row">
                            <a class="ghost-link" href="{{ url_for('edit_asset', asset_id=asset['id']) }}">Edit</a>
                            <form method="post" action="{{ url_for('delete_asset', asset_id=asset['id']) }}" onsubmit="return confirm('Are you sure you want to delete this entry?');">
                                <button class="btn-danger" type="submit" style="margin-top:0;">Delete</button>
                            </form>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    '''
    return render_page(body, title="Admin Dashboard", users=users, assets=assets, active_section="air")



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
        <h2>A server error occurred.</h2>
        <p class="muted">Administrator Actions 도중 문제가 생기면 다시 시도해보시고, DB 구조가 바뀐 경우에는 앱을 재실행해 초기화 보정이 적용되도록 해주세요.</p>
        <div class="btn-row">
            <a class="btn-link" href="{{ url_for('admin_dashboard') if current_user.is_authenticated and current_user.is_admin else url_for('intro_page') }}">Go Back</a>
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

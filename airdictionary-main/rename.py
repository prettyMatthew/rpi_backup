
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

AIR_CATEGORIES = [
    "Fighters", "Bomber", "Air Lifter", "Airbone Early Warning(AEW)", "Ariel Tanker", "Reconnaissance Aircraft", "Trainer",
    "UAV", "Aircraft Carrier", "Submarines", "Ballistic Missile", "Cruise Missile", "Air Defense",
    "Space Force", "Strategic Assests",
]

RADIO_CATEGORIES = [
    "General Radio", "Aviation Band", "Radio Frequency", "Radar", "Communication", "EW", "Signal Info", "Radio Astronomy", "Others"
]

CONSTELLATION_CATEGORIES = [
    "Zodiac", "(N)Constellation", "(S)Constellation", "Seasonal Constellation", "Nebula", "Guidance", "Others"
]

SECTION_CONFIG = {
    "air": {
        "name": "Horizon Atlas",
        "title": "Horizon Atlas",
        "hero_title": "Air Dictionary",
        "hero_subtitle": "Horizon atlas Archieve",
        "hero_desc": "",
        "categories": AIR_CATEGORIES,
        "accent": "#2563eb",
        "accent_soft": "#dbeafe",
    },
    "radio": {
        "name": "Radio",
        "title": "Radio Wiki",
        "hero_title": "Radio & EW Archive",
        "hero_subtitle": "Radio Archieve",
        "hero_desc": ":)",
        "categories": RADIO_CATEGORIES,
        "accent": "#7c3aed",
        "accent_soft": "#ede9fe",
    },
    "constellation": {
        "name": "Constellation",
        "title": "Constellation Wiki",
        "hero_title": "Constellation Archive",
        "hero_subtitle": "Information of Constellation",
        "hero_desc": "",
        "categories": CONSTELLATION_CATEGORIES,
        "accent": "#0f766e",
        "accent_soft": "#ccfbf1",
    },
}

AIR_SPEC_FIELDS = [
    ("manufacturer", "MAnufacturing Company"),
    ("country", "Country"),
    ("role", "Role"),
    ("first_flight", "Maiden Flight"),
    ("introduced", "Deployment"),
    ("status", "Operation Status"),
    ("crew", "Cabin"),
    ("length", "Length"),
    ("wingspan", "Wing Width"),
    ("height", "height"),
    ("max_speed", "Maximum Speed"),
    ("range_km", "Range"),
    ("combat_radius", "Radius of Action"),
    ("service_ceiling", "Service Ceiling"),
    ("engine", "Engine"),
    ("powerplant", "Thrust"),
    ("armament", "Armed"),
    ("notes", "Note"),
]

RADIO_SPEC_FIELDS = [
    ("manufacturer", "Manufacturer"),
    ("country", "Country"),
    ("role", "Role"),
    ("first_flight", "Frequency"),
    ("introduced", "Method"),
    ("status", "Status"),
    ("crew", "Usage"),
    ("length", "Channel"),
    ("wingspan", "Wave Length"),
    ("height", "Frequency"),
    ("max_speed", "Wave"),
    ("range_km", "Range"),
    ("combat_radius", "Coverage"),
    ("service_ceiling", "Height"),
    ("engine", "Equipment"),
    ("powerplant", "Encrypt"),
    ("armament", "Main Function"),
    ("notes", "Note"),
]

CONSTELLATION_SPEC_FIELDS = [
    ("manufacturer", "Name"),
    ("country", "Region"),
    ("role", "Characteristic"),
    ("first_flight", "RA"),
    ("introduced", "DEC"),
    ("status", "Visible"),
    ("crew", "Representative Star"),
    ("length", "Area"),
    ("wingspan", "Visible Level"),
    ("height", "NGC"),
    ("max_speed", "Optimal Time to Observe"),
    ("range_km", "Observe Season"),
    ("combat_radius", "Location"),
    ("service_ceiling", "Southern Location"),
    ("engine", "Background"),
    ("powerplant", ""),
    ("armament", "Tips"),
    ("notes", "Notes"),
]

SECTION_SPEC_FIELDS = {
    "air": AIR_SPEC_FIELDS,
    "radio": RADIO_SPEC_FIELDS,
    "constellation": CONSTELLATION_SPEC_FIELDS,
}

BASE_HTML = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title or 'Horizon Atlas' }}</title>
    <style>
        :root{
            --bg:#09111f;
            --panel:#ffffff;
            --text:#0f172a;
            --muted:#64748b;
            --line:#e2e8f0;
            --shadow:0 16px 40px rgba(15,23,42,.10);
            --radius:22px;
            --radius-sm:14px;
            --accent: {{ accent or '#2563eb' }};
            --accent-soft: {{ accent_soft or '#dbeafe' }};
        }
        *{box-sizing:border-box}
        body{
            margin:0;
            font-family: Inter, Pretendard, Arial, sans-serif;
            color:var(--text);
            background:
                radial-gradient(circle at top left, rgba(59,130,246,.10), transparent 28%),
                radial-gradient(circle at top right, rgba(124,58,237,.08), transparent 24%),
                linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
        }
        a{color:inherit}
        .container{width:min(1220px, 94%); margin:0 auto}
        .topbar{
            position:sticky; top:0; z-index:30;
            backdrop-filter: blur(14px);
            background: rgba(9,17,31,.82);
            border-bottom:1px solid rgba(255,255,255,.08);
        }
        .topbar-inner{
            display:flex; justify-content:space-between; align-items:center;
            gap:14px; min-height:76px; flex-wrap:wrap;
        }
        .logo{
            display:flex; align-items:center; gap:12px;
            text-decoration:none; color:#fff; font-size:22px; font-weight:800;
            letter-spacing:-.02em;
        }
        .logo-mark{
            width:40px; height:40px; border-radius:14px;
            background: linear-gradient(135deg, var(--accent), #0ea5e9);
            box-shadow: 0 10px 20px rgba(37,99,235,.35);
        }
        .nav-links{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
        .nav-links a,.nav-links span{
            color:#e5eefc; text-decoration:none; padding:10px 13px; border-radius:12px; font-size:14px;
        }
        .nav-links a:hover,.nav-links a.active{
            background: rgba(255,255,255,.10);
            color:#fff;
        }
        .main{padding:28px 0 48px}
        .hero{
            position:relative;
            overflow:hidden;
            padding:28px;
            border-radius:32px;
            color:#fff;
            background:
                radial-gradient(circle at 85% 20%, rgba(255,255,255,.16), transparent 18%),
                linear-gradient(135deg, color-mix(in srgb, var(--accent) 78%, #07111f 22%), #0f172a 72%);
            box-shadow: 0 24px 50px rgba(15,23,42,.18);
            margin-bottom:20px;
        }
        .hero h1{margin:0 0 8px; font-size:34px; letter-spacing:-.03em}
        .hero p{margin:0 0 10px; max-width:720px; color:#dbeafe}
        .hero .hero-actions{display:flex; gap:10px; flex-wrap:wrap; margin-top:18px}
        .button,.button-secondary,.button-ghost{
            display:inline-flex; align-items:center; justify-content:center; gap:8px;
            min-height:46px; padding:0 16px; border-radius:14px; text-decoration:none;
            font-weight:800; border:none; cursor:pointer; width:auto;
        }
        .button{background:#fff; color:#0f172a}
        .button-secondary{background:var(--accent); color:#fff; box-shadow:0 10px 18px color-mix(in srgb, var(--accent) 34%, transparent)}
        .button-ghost{background:#eef2ff; color:#1e293b}
        .section-tabs{display:flex; flex-wrap:wrap; gap:10px; margin-bottom:16px}
        .section-tab{
            text-decoration:none; font-weight:800; padding:12px 16px; border-radius:14px;
            background:#fff; color:#334155; border:1px solid var(--line); box-shadow:var(--shadow);
        }
        .section-tab.active{
            background:var(--accent); color:#fff; border-color:transparent;
        }
        .card{
            background:rgba(255,255,255,.92);
            border:1px solid rgba(255,255,255,.78);
            border-radius:var(--radius);
            box-shadow:var(--shadow);
            padding:22px;
            margin-bottom:20px;
        }
        .glass{background: rgba(255,255,255,.78); backdrop-filter: blur(8px)}
        .search-grid{display:grid; grid-template-columns:1.45fr 260px 160px; gap:12px}
        .asset-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:18px}
        .asset-card{
            position:relative; overflow:hidden; border-radius:24px;
            background:#fff; border:1px solid #e5edf7; box-shadow:var(--shadow);
            transition: transform .18s ease, box-shadow .18s ease;
        }
        .asset-card:hover{transform:translateY(-3px); box-shadow:0 22px 42px rgba(15,23,42,.14)}
        .thumb{width:100%; height:190px; object-fit:cover; display:block; background:#dbe4f0}
        .thumb-placeholder{
            width:100%; height:190px; display:flex; align-items:center; justify-content:center;
            background:linear-gradient(135deg, var(--accent-soft), #eef2ff);
            color:#334155; font-weight:800; letter-spacing:.08em;
        }
        .asset-body{padding:18px}
        .badge{
            display:inline-flex; align-items:center; min-height:30px;
            padding:0 10px; border-radius:999px; background:var(--accent-soft); color:var(--accent);
            font-size:12px; font-weight:800; margin-bottom:10px;
        }
        .muted{color:var(--muted)}
        .small{font-size:13px}
        .pill-wrap{display:flex; flex-wrap:wrap; gap:10px; margin-top:16px}
        .pill-link{
            display:inline-flex; align-items:center; min-height:38px; padding:0 12px; border-radius:999px;
            text-decoration:none; background:#f8fafc; color:#334155; border:1px solid #e5e7eb; font-weight:700;
        }
        .pill-link.active{background:var(--accent); color:#fff; border-color:transparent}
        input,select,textarea{
            width:100%; min-height:48px; padding:12px 14px; border:1px solid #d6dfeb;
            border-radius:14px; font-size:15px; background:#fff; color:#0f172a;
            outline:none; transition:border-color .15s ease, box-shadow .15s ease;
        }
        input:focus,select:focus,textarea:focus{
            border-color:var(--accent);
            box-shadow:0 0 0 4px color-mix(in srgb, var(--accent) 16%, transparent);
        }
        textarea{resize:vertical; min-height:120px}
        label{display:block; margin:14px 0 8px; font-weight:800}
        .form-intro{
            padding:14px 16px; border-radius:16px; background:linear-gradient(135deg, var(--accent-soft), #fff);
            border:1px solid color-mix(in srgb, var(--accent) 18%, #fff);
            color:#334155; margin-bottom:8px;
        }
        .grid-two{display:grid; grid-template-columns:1fr 1fr; gap:14px}
        .flash{
            padding:14px 16px; border-radius:16px; margin-bottom:12px; font-weight:700; border:1px solid transparent;
            box-shadow:var(--shadow);
        }
        .flash-success{background:#ecfdf5; color:#166534; border-color:#bbf7d0}
        .flash-danger{background:#fef2f2; color:#991b1b; border-color:#fecaca}
        .flash-warning{background:#fffbeb; color:#92400e; border-color:#fde68a}
        .flash-info{background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe}
        .detail-head{display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; align-items:flex-start}
        .detail-image{width:100%; max-width:760px; display:block; border-radius:20px; margin:18px 0; border:1px solid #e5e7eb}
        .summary-box{
            background:linear-gradient(135deg, var(--accent-soft), #ffffff);
            padding:16px; border:1px solid color-mix(in srgb, var(--accent) 22%, #fff);
            border-radius:16px; margin:18px 0; font-weight:700;
        }
        .wiki-content{line-height:1.85; font-size:16px}
        .wiki-content table{border-collapse:collapse; width:100%; margin:12px 0}
        .wiki-content th,.wiki-content td{border:1px solid #d1d5db; padding:8px}
        .spec-table{width:100%; border-collapse:collapse; margin:18px 0 24px; border:1px solid #e5e7eb; overflow:hidden; border-radius:16px}
        .spec-table th,.spec-table td{padding:12px 14px; text-align:left; border-bottom:1px solid #e5e7eb; vertical-align:top}
        .spec-table th{width:230px; background:#f8fafc}
        .history-item{
            padding:14px; border:1px solid #e5e7eb; border-radius:16px; margin-bottom:10px; background:#fafcff;
        }
        .admin-badge{
            display:inline-block; padding:6px 10px; border-radius:999px;
            background:#fee2e2; color:#991b1b; font-size:12px; font-weight:800;
        }
        .checkbox-inline{display:flex; gap:8px; align-items:center; margin-top:12px}
        .checkbox-inline input{width:auto; min-height:auto}
        .narrow{max-width:540px; margin:32px auto}
        .kpi-grid{display:grid; grid-template-columns:repeat(4,1fr); gap:14px}
        .kpi{
            background:#fff; border:1px solid #e5e7eb; border-radius:20px; padding:18px;
        }
        .kpi strong{display:block; font-size:28px; margin-top:8px}
        .split{
            display:grid; grid-template-columns: 1.15fr .85fr; gap:18px;
        }
        .empty-state{
            padding:30px; text-align:center; border-radius:22px; background:#fff; border:1px dashed #cbd5e1;
        }
        hr.soft{margin:24px 0; border:none; border-top:1px solid #e5e7eb}
        @media (max-width: 980px){ .kpi-grid,.split,.search-grid,.grid-two{grid-template-columns:1fr} }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="container topbar-inner">
            <a class="logo" href="{{ url_for('home') }}">
                <span class="logo-mark"></span>
                <span>Horizon Atlas</span>
            </a>
            <nav class="nav-links">
                <a href="{{ url_for('home') }}" class="{% if active_section == 'air' %}active{% endif %}">AirDictionary</a>
                <a href="{{ url_for('radio_home') }}" class="{% if active_section == 'radio' %}active{% endif %}">Radio</a>
                <a href="{{ url_for('constellation_home') }}" class="{% if active_section == 'constellation' %}active{% endif %}">Constellation</a>
                {% if current_user.is_authenticated %}
                    <a href="{{ url_for('create_asset', section=active_section or 'air') }}">New</a>
                    {% if current_user.is_admin %}<a href="{{ url_for('admin_dashboard') }}">Admin</a>{% endif %}
                    <a href="{{ url_for('admin.index') }}">Management</a>
                    <span>{{ current_user.username }} {% if current_user.is_admin %}<span class="admin-badge">Admin</span>{% endif %}</span>
                    <a href="{{ url_for('logout') }}">Logout</a>
                {% else %}
                    <a href="{{ url_for('login') }}">Login</a>
                    <a href="{{ url_for('register') }}">Register</a>
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
"""

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

def normalize_section(section):
    return section if section in SECTION_CONFIG else "air"

def get_section_config(section):
    return SECTION_CONFIG.get(normalize_section(section), SECTION_CONFIG["air"])

def get_spec_fields(section):
    return SECTION_SPEC_FIELDS.get(normalize_section(section), AIR_SPEC_FIELDS)

def section_label(section):
    return get_section_config(section)["name"]

def get_available_categories(section):
    section = normalize_section(section)
    defaults = list(get_section_config(section)["categories"])
    db_rows = get_db().execute(
        "SELECT DISTINCT category FROM assets WHERE section = ? AND category IS NOT NULL AND TRIM(category) != '' ORDER BY category",
        (section,),
    ).fetchall()
    extra = [row["category"] for row in db_rows if row["category"] not in defaults]
    return defaults + extra

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
            section TEXT NOT NULL DEFAULT 'air',
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
    db.execute("UPDATE assets SET section = 'air' WHERE section IS NULL OR section = ''")
    db.commit()
    ensure_default_admin()

def ensure_default_admin():
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            ("", generate_password_hash("")),
        )
        db.commit()

def serialize_specs_from_form(form, section):
    fields = get_spec_fields(section)
    return {field: form.get(field, "").strip() for field, _ in fields}

def specs_to_text(specs_dict, section):
    lines = []
    for field, label in get_spec_fields(section):
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
            flash("Error", "danger")
            return redirect(url_for("home"))
        return view_func(*args, **kwargs)
    return wrapper

def render_page(body_html, **context):
    active_section = normalize_section(context.get("active_section", "air"))
    config = get_section_config(active_section)
    context["body"] = render_template_string(body_html, **context)
    context["accent"] = config["accent"]
    context["accent_soft"] = config["accent_soft"]
    context["active_section"] = active_section
    return render_template_string(BASE_HTML, **context)

def save_history(asset_id, edited_by, action_type, title_snapshot, summary_snapshot, description_snapshot, spec_dict, section_snapshot="air"):
    db = get_db()
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
            specs_to_text(spec_dict, section_snapshot),
            section_snapshot,
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
    row = get_db().execute("SELECT * FROM asset_specs WHERE asset_id = ?", (asset_id,)).fetchone()
    if row:
        return row
    db = get_db()
    db.execute("INSERT OR IGNORE INTO asset_specs (asset_id) VALUES (?)", (asset_id,))
    db.commit()
    return db.execute("SELECT * FROM asset_specs WHERE asset_id = ?", (asset_id,)).fetchone()

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
            flash("Need Access", "danger")
            return redirect(url_for("login"))
        return super().index()

class AdminProtectedModelView(ModelView):
    can_export = True
    page_size = 50
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        flash("Need Access", "danger")
        return redirect(url_for("login"))

admin = Admin(
    app,
    name="Horizon Atlas Admin",
    url="/admin-panel",
    index_view=SimpleAdminIndexView(name="Dashboard", url="/admin-panel"),
)

def section_home_url(section):
    section = normalize_section(section)
    return {
        "air": url_for("home"),
        "radio": url_for("radio_home"),
        "constellation": url_for("constellation_home"),
    }[section]

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

    total_count = db.execute("SELECT COUNT(*) FROM assets WHERE section = ?", (section,)).fetchone()[0]
    published_count = db.execute("SELECT COUNT(*) FROM assets WHERE section = ? AND is_published = 1", (section,)).fetchone()[0]
    category_count = len(get_available_categories(section))
    image_count = db.execute("SELECT COUNT(*) FROM assets WHERE section = ? AND image_data IS NOT NULL AND image_data != ''", (section,)).fetchone()[0]

    body = r"""
    <section class="hero">
        <div class="section-tabs">
            <a class="section-tab {% if active_section == 'air' %}active{% endif %}" href="{{ url_for('home') }}">Airdictionary</a>
            <a class="section-tab {% if active_section == 'radio' %}active{% endif %}" href="{{ url_for('radio_home') }}">Radio</a>
            <a class="section-tab {% if active_section == 'constellation' %}active{% endif %}" href="{{ url_for('constellation_home') }}">Constellation</a>
        </div>
        <h1>{{ config['hero_title'] }}</h1>
        <p><strong>{{ config['hero_subtitle'] }}</strong></p>
        <p>{{ config['hero_desc'] }}</p>
        <div class="hero-actions">
            {% if current_user.is_authenticated %}
                <a class="button" href="{{ url_for('create_asset', section=active_section) }}">Write a new Document</a>
            {% else %}
                <a class="button" href="{{ url_for('login') }}">Login</a>
            {% endif %}
            <a class="button-secondary" href="#asset-list">View Documents</a>
        </div>
    </section>

    <section class="kpi-grid" style="margin-bottom:20px;">
        <div class="kpi"><div class="muted small">All Documents</div><strong>{{ total_count }}</strong></div>
        <div class="kpi"><div class="muted small">Open Document</div><strong>{{ published_count }}</strong></div>
        <div class="kpi"><div class="muted small">Number of Categories</div><strong>{{ category_count }}</strong></div>
        <div class="kpi"><div class="muted small">With Images</div><strong>{{ image_count }}</strong></div>
    </section>

    <section class="card glass">
        <form method="get" class="search-grid">
            <input type="text" name="q" placeholder="Name of Document / Explanation" value="{{ q }}">
            <select name="category">
                <option value="">All Categories</option>
                {% for cat in categories %}
                    <option value="{{ cat }}" {% if category == cat %}selected{% endif %}>{{ cat }}</option>
                {% endfor %}
            </select>
            <button class="button-secondary" type="submit" style="width:100%;">Search</button>
        </form>
        <div class="pill-wrap">
            <a class="pill-link {% if not category %}active{% endif %}" href="{{ section_url }}">All</a>
            {% for cat in categories %}
                <a class="pill-link {% if category == cat %}active{% endif %}" href="{{ section_url }}?category={{ cat|urlencode }}{% if q %}&q={{ q|urlencode }}{% endif %}">{{ cat }}</a>
            {% endfor %}
        </div>
    </section>

    <section id="asset-list" class="asset-grid">
        {% for asset in assets %}
            <article class="asset-card">
                {% if asset['image_data'] %}
                    <img class="thumb" src="{{ asset['image_data'] }}" alt="{{ asset['title'] }}">
                {% else %}
                    <div class="thumb-placeholder">{{ config['name'] }}</div>
                {% endif %}
                <div class="asset-body">
                    <div class="badge">{{ asset['category'] }}</div>
                    <h3 style="margin:0 0 10px;"><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}" style="text-decoration:none;color:#0f172a;">{{ asset['title'] }}</a></h3>
                    <p style="margin:0 0 12px;">{{ asset['summary'] or 'No explanation' }}</p>
                    <div class="muted small">Author: {{ asset['author_name'] or 'Admin' }}</div>
                </div>
            </article>
        {% else %}
            <div class="empty-state">
                <strong>No Documents</strong>
                <p class="muted"If you add new document, then it will show as a card.</p>
            </div>
        {% endfor %}
    </section>
    """
    return render_page(
        body,
        title=f"{config['name']} | {config['title']}",
        assets=assets,
        q=q,
        category=category,
        categories=get_available_categories(section),
        config=config,
        active_section=section,
        section_url=section_home_url(section),
        total_count=total_count,
        published_count=published_count,
        category_count=category_count,
        image_count=image_count,
    )

@app.route("/")
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
            flash("Put ID and Password", "danger")
            return redirect(url_for("register"))
        if password != password2:
            flash("Password doesn't Match. Please try again", "danger")
            return redirect(url_for("register"))
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            flash("Your ID is already taken", "danger")
            return redirect(url_for("register"))
        db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)", (username, generate_password_hash(password)))
        db.commit()
        flash("Signed up successfully! Please Log in", "success")
        return redirect(url_for("login"))
    body = r"""
    <div class="card narrow">
        <h2>Sign Up</h2>
        <form method="post">
            <label>ID</label><input type="text" name="username" required>
            <label>Password</label><input type="password" name="password" required>
            <label>Confirm</label><input type="password" name="password2" required>
            <button class="button-secondary" style="width:100%; margin-top:18px;" type="submit">Sign up</button>
        </form>
    </div>
    """
    return render_page(body, title="Sign up", active_section="air")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            flash("ID or password is not matching", "danger")
            return redirect(url_for("login"))
        login_user(User(row))
        flash("Loged in successfully", "success")
        return redirect(url_for("home"))
    body = r"""
    <div class="card narrow">
        <h2>Log in</h2>
        <form method="post">
            <label>ID</label><input type="text" name="username" required>
            <label>Password</label><input type="password" name="password" required>
            <button class="button-secondary" style="width:100%; margin-top:18px;" type="submit">Login</button>
        </form>
        <p class="muted small" style="margin-top:14px;"></p>
    </div>
    """
    return render_page(body, title="Log in", active_section="air")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Log out", "info")
    return redirect(url_for("home"))

def section_form_intro(section):
    section = normalize_section(section)
    if section == "radio":
        return "Radio Form"
    if section == "constellation":
        return "Constellation Form"
    return "Air Dictionary Form"

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_asset():
    requested_section = normalize_section(request.args.get("section", request.form.get("section", "air")))
    categories = get_available_categories(requested_section)
    spec_fields = get_spec_fields(requested_section)

    if request.method == "POST":
        section = normalize_section(request.form.get("section", requested_section))
        categories = get_available_categories(section)
        spec_fields = get_spec_fields(section)
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        is_published = 1 if (current_user.is_admin or request.form.get("publish_now") == "on") else 0
        file = request.files.get("image")

        if not title or not category:
            flash("Please Write a name and select category", "danger")
            return redirect(url_for("create_asset", section=section))
        if category not in categories:
            flash("Unavailable Category for this section", "danger")
            return redirect(url_for("create_asset", section=section))

        image_data = None
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("Image file is only available: jpg, png, wepb", "danger")
                return redirect(url_for("create_asset", section=section))

        specs = serialize_specs_from_form(request.form, section)
        description_html = markdown_to_html(description)
        db = get_db()
        cur = db.execute(
            "INSERT INTO assets (title, category, summary, description, description_html, image_data, is_published, created_by, section) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, category, summary, description, description_html, image_data, is_published, current_user.id, section),
        )
        asset_id = cur.lastrowid
        spec_cols = ", ".join([field for field, _ in AIR_SPEC_FIELDS])
        placeholders = ", ".join(["?" for _ in AIR_SPEC_FIELDS])
        spec_values = [specs.get(field, "").strip() for field, _ in AIR_SPEC_FIELDS]
        db.execute(f"INSERT INTO asset_specs (asset_id, {spec_cols}) VALUES (?, {placeholders})", [asset_id] + spec_values)
        db.commit()

        save_history(asset_id, current_user.id, "create", title, summary, description, specs, section_snapshot=section)
        flash("새 문서가 등록되었습니다.", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))

    body = r"""
    <div class="card">
        <h2>New</h2>
        <div class="form-intro">{{ form_intro }}</div>
        <form method="post" enctype="multipart/form-data">
            <label>Document Section</label>
            <select name="section" required onchange="window.location='{{ url_for('create_asset') }}?section=' + this.value;">
                <option value="air" {% if active_section == 'air' %}selected{% endif %}>Air Dictionary</option>
                <option value="radio" {% if active_section == 'radio' %}selected{% endif %}>Radio</option>
                <option value="constellation" {% if active_section == 'constellation' %}selected{% endif %}>Constellation</option>
            </select>
            <label>Title</label><input type="text" name="title" placeholder="Ex: F-22 Raptor, Aviation Band, Orion" required>
            <label>Category</label>
            <select name="category" required>
                <option value="">Select</option>
                {% for cat in categories %}<option value="{{ cat }}">{{ cat }}</option>{% endfor %}
            </select>
            <label>Brief Explanation</label><input type="text" name="summary" placeholder="">
            <label>Detailed Explanation (Markdown)</label><textarea name="description" rows="10"></textarea>
            <label>Upload Image</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" checked> Open to everyone</label>{% endif %}
            <hr class="soft">
            <h3>{{ section_label_name }} Details</h3>
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
            <button class="button-secondary" style="width:100%; margin-top:20px;" type="submit">Upload</button>
        </form>
    </div>
    """
    return render_page(
        body,
        title=f"New | {section_label(requested_section)}",
        categories=categories,
        spec_fields=spec_fields,
        active_section=requested_section,
        form_intro=section_form_intro(requested_section),
        section_label_name=section_label(requested_section),
    )

@app.route("/asset/<int:asset_id>")
def asset_detail(asset_id):
    asset = fetch_asset(asset_id)
    if asset is None:
        flash("No information", "danger")
        return redirect(url_for("home"))
    section = normalize_section(asset["section"])
    if not asset["is_published"] and not (current_user.is_authenticated and current_user.is_admin):
        flash("Not published post", "warning")
        return redirect(section_home_url(section))
    specs = fetch_specs(asset_id)
    history = fetch_history(asset_id)
    spec_fields = get_spec_fields(section)

    body = r"""
    <div class="card">
        <div class="detail-head">
            <div>
                <div class="badge">{{ asset['category'] }}</div>
                <h1 style="margin-bottom:8px;">{{ asset['title'] }}</h1>
                <div class="muted">Section: {{ section_name }} | Author: {{ asset['author_name'] or 'Admin' }} | Generated: {{ asset['created_at'] }} | Edited: {{ asset['updated_at'] }}</div>
                {% if not asset['is_published'] %}<div class="admin-badge" style="margin-top:10px;">Private</div>{% endif %}
            </div>
            {% if current_user.is_authenticated %}
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <a class="button-ghost" href="{{ url_for('edit_asset', asset_id=asset['id']) }}">Edit</a>
                    {% if current_user.is_admin %}
                    <form method="post" action="{{ url_for('delete_asset', asset_id=asset['id']) }}" onsubmit="return confirm('Are you sure to delete this post?');">
                        <button class="button-secondary" style="background:#dc2626;" type="submit">Delete</button>
                    </form>
                    {% endif %}
                </div>
            {% endif %}
        </div>
        {% if asset['image_data'] %}<img class="detail-image" src="{{ asset['image_data'] }}" alt="{{ asset['title'] }}">{% endif %}
        {% if asset['summary'] %}<div class="summary-box">{{ asset['summary'] }}</div>{% endif %}
        <h2>Brief Explanation</h2>
        <div class="wiki-content">{{ asset['description_html'] | safe }}</div>
        <h2 style="margin-top:28px;">Detail Information</h2>
        <table class="spec-table"><tbody>
            {% for field, label in spec_fields %}
                {% set value = specs[field] if specs else '' %}
                {% if value %}
                    <tr><th>{{ label }}</th><td>{{ value }}</td></tr>
                {% endif %}
            {% endfor %}
        </tbody></table>
    </div>
    <div class="card">
        <h2>편집 이력</h2>
        {% for row in history %}
            <div class="history-item">
                <strong>{{ row['action_type'] }}</strong>
                <div class="muted small">Editor: {{ row['editor_name'] or 'Admin' }} | Time: {{ row['edited_at'] }}</div>
                {% if row['section_snapshot'] %}<div><strong>Section:</strong> {{ row['section_snapshot'] }}</div>{% endif %}
                <div style="margin-top:8px;"><strong>Title Snapshot:</strong> {{ row['title_snapshot'] or '' }}</div>
                {% if row['summary_snapshot'] %}<div><strong>Summary:</strong> {{ row['summary_snapshot'] }}</div>{% endif %}
                {% if row['spec_snapshot'] %}
                    <pre style="white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:12px;border:1px solid #e5e7eb;">{{ row['spec_snapshot'] }}</pre>
                {% endif %}
            </div>
        {% else %}
            <div class="muted">Edite History</div>
        {% endfor %}
    </div>
    """
    return render_page(
        body,
        title=asset["title"],
        asset=asset,
        specs=specs,
        history=history,
        spec_fields=spec_fields,
        active_section=section,
        section_name=section_label(section),
    )

@app.route("/edit/<int:asset_id>", methods=["GET", "POST"])
@login_required
def edit_asset(asset_id):
    asset = fetch_asset(asset_id)
    if asset is None:
        flash("No Document", "danger")
        return redirect(url_for("home"))
    section = normalize_section(asset["section"])
    specs = fetch_specs(asset_id)
    categories = get_available_categories(section)
    spec_fields = get_spec_fields(section)

    if request.method == "POST":
        section = normalize_section(request.form.get("section", asset["section"]))
        categories = get_available_categories(section)
        spec_fields = get_spec_fields(section)
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        description = request.form.get("description", "").strip()
        remove_image = request.form.get("remove_image") == "on"
        publish_now = request.form.get("publish_now") == "on"
        file = request.files.get("image")

        if not title or not category:
            flash("Write title and Select Category", "danger")
            return redirect(url_for("edit_asset", asset_id=asset_id))
        if category not in categories:
            flash("Unavailable Section", "danger")
            return redirect(url_for("edit_asset", asset_id=asset_id))

        image_data = None if remove_image else asset["image_data"]
        if file and file.filename:
            raw = file.read()
            image_data = image_bytes_to_data_url(raw)
            if not image_data:
                flash("Image is only available: png, jpg, webp", "danger")
                return redirect(url_for("edit_asset", asset_id=asset_id))

        new_specs = serialize_specs_from_form(request.form, section)
        db = get_db()
        db.execute(
            "UPDATE assets SET title = ?, category = ?, summary = ?, description = ?, description_html = ?, image_data = ?, is_published = ?, section = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, category, summary, description, markdown_to_html(description), image_data, 1 if (current_user.is_admin and publish_now) else asset["is_published"], section, asset_id),
        )
        set_clause = ", ".join([f"{field} = ?" for field, _ in AIR_SPEC_FIELDS])
        spec_values = [new_specs.get(field, "") for field, _ in AIR_SPEC_FIELDS]
        db.execute(f"UPDATE asset_specs SET {set_clause} WHERE asset_id = ?", spec_values + [asset_id])
        db.commit()
        save_history(asset_id, current_user.id, "edit", title, summary, description, new_specs, section_snapshot=section)
        flash("Document Edited", "success")
        return redirect(url_for("asset_detail", asset_id=asset_id))

    body = r"""
    <div class="card">
        <h2>Edite Document</h2>
        <div class="form-intro">{{ form_intro }}</div>
        <form method="post" enctype="multipart/form-data">
            <label>Section</label>
            <select name="section" required onchange="window.location='{{ url_for('edit_asset', asset_id=asset['id']) }}?section=' + this.value;">
                <option value="air" {% if active_section == 'air' %}selected{% endif %}>Air Dictionary</option>
                <option value="radio" {% if active_section == 'radio' %}selected{% endif %}>Radio</option>
                <option value="constellation" {% if active_section == 'constellation' %}selected{% endif %}>Constellation</option>
            </select>
            <label>Title</label><input type="text" name="title" value="{{ asset['title'] }}" required>
            <label>Category</label>
            <select name="category" required>
                {% for cat in categories %}<option value="{{ cat }}" {% if asset['category'] == cat %}selected{% endif %}>{{ cat }}</option>{% endfor %}
            </select>
            <label>Brief Explanation</label><input type="text" name="summary" value="{{ asset['summary'] or '' }}">
            <label>Detailed Explanation (Markdown)</label><textarea name="description" rows="10">{{ asset['description'] or '' }}</textarea>
            {% if asset['image_data'] %}
                <label>Current Image</label>
                <img class="detail-image" src="{{ asset['image_data'] }}" alt="Current Image" style="max-width:320px;">
                <label class="checkbox-inline"><input type="checkbox" name="remove_image"> Delete Current Image</label>
            {% endif %}
            <label>Upload New Image</label><input type="file" name="image" accept="image/*">
            {% if current_user.is_admin %}<label class="checkbox-inline"><input type="checkbox" name="publish_now" {% if asset['is_published'] %}checked{% endif %}> Change Status</label>{% endif %}
            <hr class="soft">
            <h3>{{ section_label_name }} Edit Information</h3>
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
            <button class="button-secondary" style="width:100%; margin-top:20px;" type="submit">Save</button>
        </form>
    </div>
    """
    return render_page(
        body,
        title="Edit Information",
        asset=asset,
        specs=specs,
        categories=categories,
        spec_fields=spec_fields,
        active_section=section,
        form_intro=section_form_intro(section),
        section_label_name=section_label(section),
    )

@app.route("/delete/<int:asset_id>", methods=["POST"])
@admin_required
def delete_asset(asset_id):
    asset = fetch_asset(asset_id)
    specs = fetch_specs(asset_id)
    if asset is None:
        flash("Can't find document", "danger")
        return redirect(url_for("home"))
    section = normalize_section(asset["section"])
    save_history(
        asset_id,
        current_user.id,
        "delete",
        asset["title"],
        asset["summary"],
        asset["description"],
        {field: (specs[field] if specs else "") for field, _ in AIR_SPEC_FIELDS},
        section_snapshot=section,
    )
    db = get_db()
    db.execute("DELETE FROM asset_specs WHERE asset_id = ?", (asset_id,))
    db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    db.commit()
    flash("Deleted", "info")
    return redirect(section_home_url(section))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    assets = db.execute(
        "SELECT a.id, a.title, a.section, a.category, a.updated_at, a.is_published, u.username AS author_name FROM assets a LEFT JOIN users u ON a.created_by = u.id ORDER BY a.updated_at DESC"
    ).fetchall()
    body = r"""
    <div class="card"><h2>Admin Page</h2><p class="muted"></p></div>
    <div class="split">
        <div class="card">
            <h3>User List</h3>
            <table class="spec-table">
                <thead><tr><th>ID</th><th>ID</th><th>Authority</th><th>Date of signed up</th></tr></thead>
                <tbody>
                    {% for user in users %}
                    <tr><td>{{ user['id'] }}</td><td>{{ user['username'] }}</td><td>{% if user['is_admin'] %}admin{% else %}general user{% endif %}</td><td>{{ user['created_at'] }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <div class="card">
            <h3>All Document</h3>
            <table class="spec-table">
                <thead><tr><th>ID</th><th>섹션</th><th>Title</th><th>Category</th><th>Author</th><th>Status</th><th>Final Edit</th></tr></thead>
                <tbody>
                    {% for asset in assets %}
                    <tr>
                        <td>{{ asset['id'] }}</td>
                        <td>{{ asset['section'] }}</td>
                        <td><a href="{{ url_for('asset_detail', asset_id=asset['id']) }}">{{ asset['title'] }}</a></td>
                        <td>{{ asset['category'] }}</td>
                        <td>{{ asset['author_name'] or 'Admin' }}</td>
                        <td>{% if asset['is_published'] %}Opened{% else %}Private{% endif %}</td>
                        <td>{{ asset['updated_at'] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_page(body, title="Admin Page", users=users, assets=assets, active_section="air")

@app.route("/init-db")
def init_db_route():
    init_db()
    return "DB initialized"

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)

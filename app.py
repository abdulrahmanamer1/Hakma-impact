# -*- coding: utf-8 -*-
"""
HIKMA IMPACT - نظام إدارة الأداء والأثر التطوعي
نسخة Flask + SQLite (تعمل على سيرفر ويمكن للفريق كله الوصول إليها)
"""
import os
import io
import json
import sqlite3
import uuid
import qrcode
from datetime import datetime, date
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from flask import (
    Flask, request, redirect, url_for, render_template, session,
    g, flash, jsonify, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Persistent storage: on Render/production set HIKMA_DATA_DIR to the mounted
# persistent disk (for example /data). Locally it defaults to the project folder.
DATA_DIR = os.environ.get("HIKMA_DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "hikma.db")

app = Flask(__name__)
app.secret_key = os.environ.get("HIKMA_SECRET_KEY", "hikma-impact-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

CRITERIA_KEYS = ["attendance", "taskCompletion", "initiativeParticipation",
                  "commitment", "teamwork", "creativity"]
CRITERIA_LABELS = {
    "attendance": "الحضور", "taskCompletion": "تنفيذ المهام",
    "initiativeParticipation": "المشاركة بالمبادرات", "commitment": "الالتزام",
    "teamwork": "العمل الجماعي", "creativity": "الإبداع"
}
DEFAULT_WEIGHTS = {"attendance": 20, "taskCompletion": 25, "initiativeParticipation": 20,
                    "commitment": 15, "teamwork": 10, "creativity": 10}
DEFAULT_POINTS = {"attendance": 10, "task": 10, "leader": 25, "participation": 15, "excellent": 20}


# ============================================================ DB ============================================================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 30000")
        # WAL prevents normal reads from blocking writes and is much safer when
        # Gunicorn has more than one worker touching the SQLite database.
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA synchronous = NORMAL")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, username TEXT, password_hash TEXT,
        role TEXT, active INTEGER DEFAULT 1, must_set_password INTEGER DEFAULT 0, last_login TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS members(
        id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, committee TEXT,
        position TEXT, join_date TEXT, status TEXT, notes TEXT, created_at TEXT, photo TEXT);
    CREATE TABLE IF NOT EXISTS news(
        id TEXT PRIMARY KEY, title TEXT, slug TEXT UNIQUE, excerpt TEXT, content TEXT,
        cover_image TEXT, category TEXT, author TEXT, status TEXT, published_at TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS pages(
        id TEXT PRIMARY KEY, title TEXT, slug TEXT UNIQUE, content TEXT, status TEXT,
        show_in_nav INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS administrators(
        id TEXT PRIMARY KEY, name TEXT, position TEXT, committee TEXT,
        date TEXT, responsibilities TEXT);
    CREATE TABLE IF NOT EXISTS committees(
        id TEXT PRIMARY KEY, name TEXT, head TEXT, description TEXT);
    CREATE TABLE IF NOT EXISTS initiatives(
        id TEXT PRIMARY KEY, name TEXT, date TEXT, location TEXT, manager TEXT,
        committee TEXT, hours REAL, status TEXT, description TEXT, goals TEXT);
    CREATE TABLE IF NOT EXISTS initiative_participants(
        initiative_id TEXT, member_id TEXT, start_time TEXT, end_time TEXT, hours REAL DEFAULT 0,
        PRIMARY KEY(initiative_id, member_id));
    CREATE TABLE IF NOT EXISTS tasks(
        id TEXT PRIMARY KEY, title TEXT, assignee TEXT, deadline TEXT,
        priority TEXT, status TEXT, description TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS attendance(
        id TEXT PRIMARY KEY, member_id TEXT, date TEXT, status TEXT, initiative_id TEXT,
        start_time TEXT, end_time TEXT, hours REAL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS evaluations(
        id TEXT PRIMARY KEY, evaluated_user_id TEXT, evaluator_id TEXT, evaluator_name TEXT,
        date TEXT, type TEXT, notes TEXT,
        c_attendance INTEGER, c_taskCompletion INTEGER, c_initiativeParticipation INTEGER,
        c_commitment INTEGER, c_teamwork INTEGER, c_creativity INTEGER);
    CREATE TABLE IF NOT EXISTS points(
        id TEXT PRIMARY KEY, member_id TEXT, value REAL, source TEXT, date TEXT);
    CREATE TABLE IF NOT EXISTS audit_logs(
        id TEXT PRIMARY KEY, action TEXT, target TEXT, by TEXT, date TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS notifications(
        id TEXT PRIMARY KEY, user_id TEXT, target_role TEXT, type TEXT, title TEXT, body TEXT,
        url TEXT, read_at TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS applications(
        id TEXT PRIMARY KEY, applicant_name TEXT, email TEXT, phone TEXT, university TEXT,
        department TEXT, stage TEXT, skills TEXT, interests TEXT, committee TEXT, motivation TEXT,
        status TEXT DEFAULT 'new', created_at TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS events(
        id TEXT PRIMARY KEY, title TEXT, date TEXT, time TEXT, location TEXT, description TEXT,
        status TEXT DEFAULT 'upcoming', cover_image TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS partners(
        id TEXT PRIMARY KEY, name TEXT, description TEXT, logo TEXT, url TEXT, sort_order INTEGER DEFAULT 0, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS media(
        id TEXT PRIMARY KEY, title TEXT, url TEXT, category TEXT, initiative_id TEXT, public INTEGER DEFAULT 1, created_at TEXT);
    CREATE TABLE IF NOT EXISTS goals(
        id TEXT PRIMARY KEY, title TEXT, target REAL DEFAULT 0, current REAL DEFAULT 0, period TEXT, status TEXT DEFAULT 'active', created_at TEXT);
    CREATE TABLE IF NOT EXISTS approvals(
        id TEXT PRIMARY KEY, kind TEXT, target_id TEXT, title TEXT, status TEXT DEFAULT 'pending',
        requested_by TEXT, reviewed_by TEXT, notes TEXT, created_at TEXT, reviewed_at TEXT);
    CREATE TABLE IF NOT EXISTS security_sessions(
        id TEXT PRIMARY KEY, user_id TEXT, ip TEXT, user_agent TEXT, created_at TEXT, last_seen TEXT);
    CREATE TABLE IF NOT EXISTS site_sections(
        id TEXT PRIMARY KEY, section_key TEXT UNIQUE, title TEXT, visible INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0,
        background TEXT DEFAULT '', accent TEXT DEFAULT '', updated_at TEXT);
    CREATE TABLE IF NOT EXISTS nav_items(
        id TEXT PRIMARY KEY, label TEXT, endpoint TEXT, url TEXT, icon TEXT DEFAULT '', visible INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0, is_system INTEGER DEFAULT 1, created_at TEXT);
    CREATE TABLE IF NOT EXISTS role_permissions(
        id TEXT PRIMARY KEY, role TEXT, permission TEXT, allowed INTEGER DEFAULT 1, UNIQUE(role,permission));
    CREATE TABLE IF NOT EXISTS live_sessions(
        id TEXT PRIMARY KEY, title TEXT, description TEXT, initiative_id TEXT, mode TEXT DEFAULT 'internal',
        external_url TEXT, external_platform TEXT, status TEXT DEFAULT 'live', created_by TEXT,
        started_at TEXT, ended_at TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS live_peers(
        id TEXT PRIMARY KEY, session_id TEXT, peer_id TEXT, role TEXT, created_at TEXT, last_seen TEXT,
        UNIQUE(session_id,peer_id));
    CREATE TABLE IF NOT EXISTS live_signals(
        id TEXT PRIMARY KEY, session_id TEXT, sender_id TEXT, target_id TEXT, kind TEXT, payload TEXT,
        created_at TEXT, delivered_at TEXT);
    CREATE TABLE IF NOT EXISTS certificates(
        id TEXT PRIMARY KEY, certificate_no TEXT UNIQUE, recipient_name TEXT, certificate_type TEXT,
        initiative_id TEXT, initiative_name TEXT, issue_date TEXT, hours REAL DEFAULT 0,
        note TEXT, issued_by TEXT, created_at TEXT, status TEXT DEFAULT 'valid',
        verify_token TEXT UNIQUE, qr_path TEXT, template TEXT DEFAULT 'classic', recipient_member_id TEXT);
    """)
    db.commit()
    if db.execute("SELECT COUNT(*) c FROM settings").fetchone()["c"] == 0:
        db.execute("INSERT INTO settings(key,value) VALUES('teamName',?)", ("فريق الحكمة التطوعي",))
        db.execute("INSERT INTO settings(key,value) VALUES('subtitle',?)",
                   ("فريق الحكمة التطوعي — HIKMA IMPACT",))
        db.execute("INSERT INTO settings(key,value) VALUES('weights',?)", (json.dumps(DEFAULT_WEIGHTS),))
        db.execute("INSERT INTO settings(key,value) VALUES('points',?)", (json.dumps(DEFAULT_POINTS),))
        # Lightweight migrations for existing deployments.
    def ensure_column(table, column, definition):
        cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    ensure_column("members", "photo", "TEXT")
    ensure_column("certificates", "status", "TEXT DEFAULT 'valid'")
    ensure_column("certificates", "verify_token", "TEXT")
    ensure_column("certificates", "qr_path", "TEXT")
    ensure_column("certificates", "template", "TEXT DEFAULT 'classic'")
    ensure_column("certificates", "recipient_member_id", "TEXT")
    ensure_column("users", "username", "TEXT")
    ensure_column("users", "active", "INTEGER DEFAULT 1")
    ensure_column("users", "must_set_password", "INTEGER DEFAULT 0")
    ensure_column("users", "last_login", "TEXT")
    ensure_column("users", "password_plain", "TEXT")
    ensure_column("media", "media_type", "TEXT DEFAULT 'link'")
    ensure_column("media", "thumbnail", "TEXT")
    ensure_column("media", "sort_order", "INTEGER DEFAULT 0")
    ensure_column("news", "featured", "INTEGER DEFAULT 0")
    ensure_column("news", "scheduled_at", "TEXT")
    ensure_column("initiatives", "latitude", "REAL")
    ensure_column("initiatives", "longitude", "REAL")
    ensure_column("initiatives", "map_status", "TEXT DEFAULT 'completed'")
    ensure_column("initiatives", "map_note", "TEXT")
    ensure_column("initiatives", "map_date", "TEXT")
    ensure_column("initiatives", "map_visible", "INTEGER DEFAULT 1")
    ensure_column("initiative_participants", "start_time", "TEXT")
    ensure_column("initiative_participants", "end_time", "TEXT")
    ensure_column("initiative_participants", "hours", "REAL DEFAULT 0")
    ensure_column("attendance", "start_time", "TEXT")
    ensure_column("attendance", "end_time", "TEXT")
    ensure_column("attendance", "hours", "REAL DEFAULT 0")
    # Backfill newer appearance/public settings without destroying existing configuration.
    defaults = {
        "accentColor": "#20B486", "navyColor": "#071A2F", "backgroundColor": "#F5F7FA",
        "fontFamily": "Tajawal", "heroTitle": "أثرٌ يُقاس، وقيادةٌ تُصنع",
        "heroText": "منصة HIKMA IMPACT لإدارة الأثر، المبادرات، والأداء التطوعي.",
        "announcement": "", "customCss": "", "siteMode": "public",
        "teamLogo": "", "universityLogo": "", "favicon": "",
        "telegramUrl": "https://t.me/Hikmaht_bot", "siteDescription": "منصة HIKMA IMPACT لإدارة الأثر، المبادرات، والأداء التطوعي.",
        "showPublicAdmins": "1", "showPublicNews": "1", "maintenanceMode": "0",
        "joinButtonVisible": "1", "joinButtonText": "انضم ↗", "joinButtonIcon": "↗", "joinButtonPlacement": "hero", "joinButtonMode": "telegram", "adminLinkVisible": "1",
        "heroBackground": "", "heroVideo": "", "publicBackground": "", "cinematicMode": "1",
        "seoTitle": "HIKMA IMPACT | فريق الحكمة التطوعي", "seoDescription": "منصة HIKMA IMPACT لإدارة الأثر، المبادرات، والأداء التطوعي.", "maintenanceMode": "0",
        "publicNavJson": "", "publicSectionsJson": "", "siteMode": "public",
        "liveEnabled": "0", "liveTitle": "البث المباشر من الميدان", "liveDescription": "تابع مبادرات فريق الحكمة التطوعي مباشرةً.", "liveUrl": "", "livePlatform": "YouTube", "liveMode": "internal", "liveSessionId": "", "liveStunServers": "stun:stun.l.google.com:19302",
    }
    for k,v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))

    # Normalize the official team name on existing deployments without touching user data.
    db.execute("UPDATE settings SET value=REPLACE(value, ?, ?) WHERE value LIKE ?",
               ("فريق الحكمة الطلابي", "فريق الحكمة التطوعي", "%فريق الحكمة الطلابي%"))
    db.execute("UPDATE settings SET value=? WHERE key='teamName' AND (value IS NULL OR value='' OR value='HIKMA IMPACT')", ("فريق الحكمة التطوعي",))

    # ======================================================== INITIAL ADMIN ACCOUNTS ========================================================
    # These directory accounts are created without a usable password.
    # The Creator assigns each account its own password from the Admin Accounts page.
    seed_admins = [
        ("بان حسين", "ban.hussein"),
        ("محمد صادق جاسم", "mohammad.sadiq"),
        ("رامي راسم", "rami.rasim"),
        ("علي احمد", "ali.ahmad"),
        ("منتظر حيدر", "muntather.haider"),
    ]
    for admin_name, username in seed_admins:
        existing = db.execute("SELECT id FROM users WHERE lower(username)=?", (username.lower(),)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO users(id,name,email,username,password_hash,password_plain,role,active,must_set_password,last_login,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (uid("usr"), admin_name, None, username, generate_password_hash(uuid.uuid4().hex), uuid.uuid4().hex, "ADMIN", 1, 1, None, now_iso())
            )
        # Also keep the public administrative directory populated.
        dir_exists = db.execute("SELECT id FROM administrators WHERE name=?", (admin_name,)).fetchone()
        if not dir_exists:
            db.execute(
                "INSERT INTO administrators(id,name,position,committee,date,responsibilities) VALUES(?,?,?,?,?,?)",
                (uid("adm"), admin_name, "إداري", "", date.today().isoformat(), "إدارة ومتابعة أعمال الفريق")
            )

    # ======================================================== OWNER ACCOUNT ========================================================
    # Owner credentials are kept stable across restarts.  The plain value is
    # intentionally retained because the owner requested simple credential
    # storage; the login also accepts the legacy Werkzeug hash.
    OWNER_EMAIL = "Abdulrahman.a.alani1@gmail.com".strip().lower()
    # init_db() runs before a Flask application context exists.
    # Read the existing owner password directly from this initialization DB
    # connection instead of calling get_setting(), which uses flask.g.
    owner_password_row = db.execute(
        "SELECT value FROM settings WHERE key=?",
        ("ownerPassword",)
    ).fetchone()
    OWNER_PASSWORD = os.environ.get("HIKMA_OWNER_PASSWORD", "ABAMAL0027")
    owner = db.execute("SELECT id FROM users WHERE lower(email)=?", (OWNER_EMAIL,)).fetchone()
    if owner:
        # Do NOT reset the owner password on every Render restart.
        db.execute(
            "UPDATE users SET name=?, username=?, role=?, active=1, must_set_password=0, password_hash=?, password_plain=? WHERE id=?",
            ("Abdulrahman Alani", "abdulrahman", "CREATOR", generate_password_hash(OWNER_PASSWORD), OWNER_PASSWORD, owner["id"])
        )
    else:
        db.execute(
            "INSERT INTO users(id,name,email,username,password_hash,password_plain,role,active,must_set_password,last_login,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                "owner_" + uuid.uuid4().hex[:12],
                "Abdulrahman Alani",
                OWNER_EMAIL,
                "abdulrahman",
                generate_password_hash(OWNER_PASSWORD),
                OWNER_PASSWORD,
                "CREATOR",
                1,
                0,
                None,
                now_iso(),
            )
        )
    db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('ownerPassword',?)", (OWNER_PASSWORD,))
    default_nav = [
        ("home","الرئيسية","public_home","/", "⌂",1,10,1),
        ("about","عن الفريق","about_public","/about", "◈",1,20,1),
        ("admins","الإداريون","admins_list","/administrators", "♜",1,30,1),
        ("news","الأخبار","public_news","/news", "▣",1,40,1),
        ("initiatives","المبادرات","initiatives_list","/initiatives", "✦",1,50,1),
        ("committees","اللجان","committees_list","/committees", "◫",1,60,1),
        ("events","الفعاليات","events_public","/events", "◷",1,70,1),
        ("impact","الأثر","impact_public","/impact", "◉",1,80,1),
        ("impact_map","خريطة الأثر","impact_map_public","/impact-map", "⌖",1,85,1),
        ("media","المعرض","media_public","/media", "▧",1,90,1),
        ("partners","الشركاء","partners_public","/partners", "◇",1,100,1),
        ("search","بحث","search_public","/search", "⌕",1,110,1),
    ]
    for key,label,endpoint,url,icon,visible,sort_order,is_system in default_nav:
        db.execute("INSERT OR IGNORE INTO nav_items(id,label,endpoint,url,icon,visible,sort_order,is_system,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   ("nav_"+key,label,endpoint,url,icon,visible,sort_order,is_system,now_iso()))
    default_sections=[
        ("hero","البداية السينمائية",1,10,"hero",""),("news","آخر الأخبار",1,20,"light",""),
        ("impact","الأثر بالأرقام",1,30,"light",""),("impact_map","خريطة الأثر",1,35,"tint",""),("live","البث المباشر",1,38,"dark",""),("initiatives","المبادرات",1,40,"tint",""),
        ("media","الصور والفيديو",1,50,"light",""),("administrators","الإداريون",1,60,"light",""),
        ("committees","اللجان",1,70,"light",""),("events","الفعاليات",1,80,"dark",""),
        ("partners","الشركاء",1,90,"light",""),("join","انضم إلى الفريق",0,100,"join",""),
    ]
    for key,title,visible,sort_order,bg,accent in default_sections:
        db.execute("INSERT OR IGNORE INTO site_sections(id,section_key,title,visible,sort_order,background,accent,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                   ("sec_"+key,key,title,visible,sort_order,bg,accent,now_iso()))
    # Keep the public join CTA only in the hero; disable legacy standalone join section.
    db.execute("UPDATE site_sections SET visible=0 WHERE section_key='join'")
    permission_names=[
        "dashboard","members","administrators","committees","initiatives","tasks","attendance","evaluations",
        "achievements","news","events","media","partners","pages","applications","reports","analytics","goals",
        "approvals","notifications","audit","security","insights","risk","decisions","appearance","navigation",
        "sections","permissions","backup","system","delete","publish","upload_media","manage_admins","live","certificates"
    ]
    for role in ("ADMIN","SUPER_ADMIN","CREATOR"):
        for perm in permission_names:
            allowed = 1 if role in ("SUPER_ADMIN","CREATOR") or perm not in ("permissions","backup","system","security","delete","manage_admins") else 0
            db.execute("INSERT OR IGNORE INTO role_permissions(id,role,permission,allowed) VALUES(?,?,?,?)",(uid("perm"),role,perm,allowed))
    db.commit()
    db.close()


def uid(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso():
    return datetime.utcnow().isoformat()


# ============================================================ SETTINGS HELPERS ============================================================
def get_setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def get_weights():
    return json.loads(get_setting("weights", json.dumps(DEFAULT_WEIGHTS)))


def get_points_config():
    return json.loads(get_setting("points", json.dumps(DEFAULT_POINTS)))


def set_setting(key, value):
    db = get_db()
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
    db.commit()


# ============================================================ AUTH ============================================================
def current_user():
    uid_ = session.get("user_id")
    if not uid_:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (uid_,)).fetchone()

def is_admin():
    u = current_user()
    return bool(u and u["role"] in ("CREATOR", "SUPER_ADMIN", "ADMIN"))

def is_creator():
    u = current_user()
    return bool(u and u["role"] in ("CREATOR", "SUPER_ADMIN"))

PERMISSION_ENDPOINTS = {
    "admin_dashboard":"dashboard","members_list":"members","member_view":"members","admins_list":"administrators","admin_new":"administrators","admin_edit":"administrators","admin_delete":"delete",
    "committees_list":"committees","committee_new":"committees","committee_edit":"committees","committee_delete":"delete",
    "initiatives_list":"initiatives","initiative_new":"initiatives","initiative_edit":"initiatives","initiative_delete":"delete","initiative_participants":"initiatives",
    "tasks_list":"tasks","task_new":"tasks","task_edit":"tasks","task_delete":"delete","attendance_list":"attendance","attendance_new":"attendance",
    "evaluations_list":"evaluations","evaluation_new":"evaluations","achievements":"achievements","news_admin":"news","news_new":"news","news_edit":"news","news_delete":"delete",
    "events_admin":"events","event_delete":"delete","partners_admin":"partners","media_admin":"media","media_upload":"upload_media",
    "page_admin":"pages","page_new":"pages","page_edit":"pages","page_delete":"delete","reports_page":"reports","analytics_page":"analytics","goals_page":"goals",
    "approvals_page":"approvals","approval_review":"approvals","notifications_page":"notifications","audit_log":"audit","security_page":"security","insights_page":"insights","risk_page":"risk","decision_center":"decisions",
    "settings_page":"appearance","certificates_admin":"certificates","certificate_legacy":"certificates","navigation_page":"navigation","sections_page":"sections","permissions_page":"permissions","live_admin":"live","backup_export":"backup","admin_users":"manage_admins","admin_user_new":"manage_admins","admin_user_role":"manage_admins",
}

def has_permission(permission):
    u=current_user()
    if not u: return False
    if u["role"]=="CREATOR": return True
    row=get_db().execute("SELECT allowed FROM role_permissions WHERE role=? AND permission=?",(u["role"],permission)).fetchone()
    return bool(row and row["allowed"])

ADMIN_GET_ENDPOINTS = {
    "settings_page", "certificates_admin", "certificate_legacy", "audit_log", "backup_export", "admin_new", "admin_edit", "admin_delete",
    "admin_users", "admin_user_role", "admin_login", "admin_dashboard", "news_admin", "news_new",
    "news_edit", "news_delete", "page_admin", "page_new", "page_edit", "page_delete",
    "notifications_page", "analytics_page", "goals_page", "approvals_page", "events_admin",
    "partners_admin", "media_admin", "security_page", "certificate", "certificate_view", "insights_page", "risk_page", "decision_center", "navigation_page", "navigation_delete", "sections_page", "permissions_page", "media_upload", "control_center", "upload_public_asset", "live_admin",
}
PUBLIC_ENDPOINTS = {"public_home", "public_news", "public_news_detail", "public_page",
                    "committees_list", "initiatives_list", "initiative_view", "achievements",
                    "admins_list", "events_public", "media_public", "partners_public", "impact_public",
                    "about_public", "search_public", "volunteer_redirect", "api_impact", "impact_map_public", "live_public",
                    "login", "admin_login", "logout", "static", "signup", "live_room", "live_join", "live_peers_api", "live_signal", "live_leave", "certificate_verify"}

@app.before_request
def access_control():
    endpoint = request.endpoint or ""
    # Public GET pages are view-only. Any write request requires an admin.
    if endpoint in PUBLIC_ENDPOINTS:
        return
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if not is_admin():
            if request.is_json:
                return jsonify({"ok": False, "error": "Admin access required"}), 403
            flash("هذه العملية متاحة للإدارة فقط", "error")
            return redirect(url_for("admin_login"))
    if endpoint in ADMIN_GET_ENDPOINTS or any(x in endpoint for x in ("_new", "_edit", "_delete", "backup_")):
        if not is_admin():
            flash("هذه الصفحة متاحة للإدارة فقط", "error")
            return redirect(url_for("admin_login"))
        perm=PERMISSION_ENDPOINTS.get(endpoint)
        if perm and not has_permission(perm):
            return render_template("403.html", permission=perm), 403

def get_live_embed_url(url):
    url=(url or "").strip()
    if not url: return ""
    from urllib.parse import urlparse, parse_qs
    try:
        u=urlparse(url)
        host=u.netloc.lower()
        if "youtube.com" in host:
            if u.path.startswith("/watch"):
                vid=parse_qs(u.query).get("v", [""])[0]
                return f"https://www.youtube.com/embed/{vid}?autoplay=0&rel=0" if vid else ""
            if u.path.startswith("/live/"):
                vid=u.path.split("/live/",1)[1].split("/",1)[0]
                return f"https://www.youtube.com/embed/{vid}?autoplay=0&rel=0" if vid else ""
            if u.path.startswith("/embed/"):
                return url
        if "youtu.be" in host:
            vid=u.path.strip("/").split("/")[0]
            return f"https://www.youtube.com/embed/{vid}?autoplay=0&rel=0" if vid else ""
    except Exception: pass
    return ""

@app.context_processor
def inject_globals():
    return {
        "session_user": current_user(),
        "is_admin": is_admin(),
        "is_creator": is_creator(),
        "team_name": get_setting("teamName", "HIKMA IMPACT"),
        "subtitle": get_setting("subtitle", "فريق الحكمة التطوعي"),
        "site_settings": {k: get_setting(k, "") for k in ["accentColor","navyColor","backgroundColor","fontFamily","heroTitle","heroText","announcement","customCss","teamLogo","universityLogo","favicon","telegramUrl","siteDescription","showPublicAdmins","showPublicNews","joinButtonVisible","joinButtonText","joinButtonIcon","joinButtonPlacement","joinButtonMode","adminLinkVisible","heroBackground","heroVideo","publicBackground","cinematicMode","maintenanceMode","seoTitle","seoDescription","liveEnabled","liveTitle","liveDescription","liveUrl","livePlatform","liveMode","liveSessionId","liveStunServers"]},
        "public_nav": get_db().execute("SELECT * FROM nav_items WHERE visible=1 ORDER BY sort_order").fetchall(),
        "public_sections": get_db().execute("SELECT * FROM site_sections WHERE visible=1 ORDER BY sort_order").fetchall(),
        "current_endpoint": request.endpoint,
        "unread_notifications": (get_db().execute("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL", (session.get("user_id"),)).fetchone()["c"] if session.get("user_id") else 0),
        "telegram_url": get_setting("telegramUrl", "https://t.me/Hikmaht_bot"),
        "public_background": get_setting("publicBackground", ""),
        "latest_public_alerts": get_db().execute("SELECT slug,title FROM news WHERE status='published' ORDER BY published_at DESC,created_at DESC LIMIT 4").fetchall(),
        "live_embed_url": get_live_embed_url(get_setting("liveUrl", "")),
    }

def log_action(action, target):
    db = get_db()
    u = current_user()
    db.execute("INSERT INTO audit_logs(id,action,target,by,date) VALUES(?,?,?,?,?)",
               (uid("log"), action, target, u["name"] if u else "—", now_iso()))
    db.commit()

def add_points(member_id, value, source):
    db = get_db()
    db.execute("INSERT INTO points(id,member_id,value,source,date) VALUES(?,?,?,?,?)",
               (uid("pt"), member_id, value, source, now_iso()))
    db.commit()

@app.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("admin_login"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE lower(email)=? OR lower(username)=?",
            (email, email)
        ).fetchone()
        valid_plain = bool(user and user["active"] and user["role"] in ("CREATOR", "SUPER_ADMIN", "ADMIN") and user["password_plain"] is not None and password == user["password_plain"]) if user else False
        valid_hash = False
        if user and user["password_hash"]:
            try:
                valid_hash = check_password_hash(user["password_hash"], password)
            except Exception:
                valid_hash = False
        if not user or not user["active"] or user["role"] not in ("CREATOR", "SUPER_ADMIN", "ADMIN") or not (valid_plain or valid_hash):
            flash("بيانات الإدارة غير صحيحة", "error")
            return redirect(url_for("admin_login"))
        session["user_id"] = user["id"]
        db=get_db()
        db.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), user["id"]))
        db.execute("INSERT INTO security_sessions(id,user_id,ip,user_agent,created_at,last_seen) VALUES(?,?,?,?,?,?)", (uid("ses"),user["id"],request.headers.get("X-Forwarded-For",request.remote_addr),request.headers.get("User-Agent",""),now_iso(),now_iso()))
        db.commit()
        return redirect(url_for("admin_dashboard"))
    has_admin = get_db().execute("SELECT COUNT(*) c FROM users WHERE role IN ('CREATOR','SUPER_ADMIN','ADMIN')").fetchone()["c"] > 0
    return render_template("admin_login.html", has_admin=has_admin)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    # Public account creation is intentionally disabled in v2.
    return redirect(url_for("admin_login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public_home"))

# ============================================================ COMPUTATION ENGINE ============================================================
def member_score(db, member_id):
    weights = get_weights()
    evs = db.execute("SELECT * FROM evaluations WHERE evaluated_user_id=?", (member_id,)).fetchall()
    if not evs:
        return None
    n = len(evs)
    sums = {k: 0 for k in CRITERIA_KEYS}
    for e in evs:
        for k in CRITERIA_KEYS:
            sums[k] += e[f"c_{k}"] or 0
    total_weight = sum(weights.values()) or 100
    score = 0
    for k in CRITERIA_KEYS:
        score += (sums[k] / n) * (weights.get(k, 0) / total_weight)
    return round(score)


def iraq_now_time():
    """Current Iraq local time, used when a supervisor records entry/exit."""
    if ZoneInfo:
        return datetime.now(ZoneInfo("Asia/Baghdad")).strftime("%H:%M")
    return datetime.utcnow().strftime("%H:%M")

def iraq_today():
    if ZoneInfo:
        return datetime.now(ZoneInfo("Asia/Baghdad")).date().isoformat()
    return datetime.utcnow().date().isoformat()

def duration_hours(start_time, end_time):
    """Return elapsed hours between HH:MM times; supports sessions crossing midnight."""
    if not start_time or not end_time:
        return 0.0
    try:
        sh, sm = [int(x) for x in start_time.split(":")[:2]]
        eh, em = [int(x) for x in end_time.split(":")[:2]]
        start = sh * 60 + sm
        end = eh * 60 + em
        if end < start:
            end += 24 * 60
        return round((end - start) / 60.0, 2)
    except (ValueError, TypeError):
        return 0.0

def member_volunteer_hours(db, member_id):
    attendance = db.execute(
        "SELECT COALESCE(SUM(hours),0) h FROM attendance WHERE member_id=? AND status IN ('Present','Late') AND (initiative_id IS NULL OR initiative_id = '')",
        (member_id,)).fetchone()["h"] or 0
    initiatives = db.execute(
        "SELECT COALESCE(SUM(hours),0) h FROM initiative_participants WHERE member_id=?",
        (member_id,)).fetchone()["h"] or 0
    return round(float(attendance) + float(initiatives), 2)

def member_attendance_pct(db, member_id):
    rows = db.execute("SELECT status FROM attendance WHERE member_id=?", (member_id,)).fetchall()
    if not rows:
        return None
    good = sum(1 for r in rows if r["status"] in ("Present", "Late"))
    return round(good / len(rows) * 100)


def member_points_total(db, member_id):
    row = db.execute("SELECT COALESCE(SUM(value),0) s FROM points WHERE member_id=?", (member_id,)).fetchone()
    return row["s"] or 0


def member_level(db, member_id):
    p = member_points_total(db, member_id)
    s = member_score(db, member_id) or 0
    if p >= 500 and s >= 90:
        return "سفير الحكمة"
    if p >= 300 and s >= 85:
        return "قائد فريق"
    if p >= 150 and s >= 75:
        return "متطوع متقدم"
    if p >= 50 and s >= 60:
        return "عضو نشط"
    return "متطوع"


def recommendation_text(s):
    if s is None:
        return "لا توجد بيانات كافية لتوليد توصية بعد."
    if s >= 85:
        return "أداء متميز واستمرارية عالية في المشاركة."
    if s >= 65:
        return "أداء جيد مع وجود فرص لتحسين بعض الجوانب."
    return "يوصى بمتابعة الأداء وتحسين الالتزام والمشاركة."


def initiative_participant_count(db, initiative_id):
    return db.execute("SELECT COUNT(*) c FROM initiative_participants WHERE initiative_id=?",
                       (initiative_id,)).fetchone()["c"]


def member_initiative_count(db, member_id):
    return db.execute("SELECT COUNT(*) c FROM initiative_participants WHERE member_id=?",
                       (member_id,)).fetchone()["c"]


def fmt_date(d):
    if not d:
        return "—"
    try:
        dt = datetime.fromisoformat(str(d)[:19])
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(d)


app.jinja_env.filters["fmt_date"] = fmt_date


# ============================================================ ADMIN CENTER / NEWS / PAGES ============================================================
@app.route("/admin")
def admin_dashboard():
    db=get_db()
    today=date.today().isoformat()
    stats={
        "members": db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"],
        "active_members": db.execute("SELECT COUNT(*) c FROM members WHERE status IS NULL OR lower(status) IN ('active','نشط')").fetchone()["c"],
        "news": db.execute("SELECT COUNT(*) c FROM news WHERE status='published'").fetchone()["c"],
        "initiatives": db.execute("SELECT COUNT(*) c FROM initiatives").fetchone()["c"],
        "evaluations": db.execute("SELECT COUNT(*) c FROM evaluations").fetchone()["c"],
        "tasks": db.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"],
        "open_tasks": db.execute("SELECT COUNT(*) c FROM tasks WHERE lower(status) NOT IN ('done','completed','مكتملة','منجزة')").fetchone()["c"],
        "overdue": db.execute("SELECT COUNT(*) c FROM tasks WHERE deadline IS NOT NULL AND deadline < ? AND lower(status) NOT IN ('done','completed','مكتملة','منجزة')", (today,)).fetchone()["c"],
        "committees": db.execute("SELECT COUNT(*) c FROM committees").fetchone()["c"],
        "hours": db.execute("SELECT COALESCE(SUM(hours),0) h FROM initiatives").fetchone()["h"] or 0,
        "admins": db.execute("SELECT COUNT(*) c FROM users WHERE role IN ('ADMIN','SUPER_ADMIN') AND active=1").fetchone()["c"],
        "certificates": db.execute("SELECT COUNT(*) c FROM certificates").fetchone()["c"],
        "pending_approvals": db.execute("SELECT COUNT(*) c FROM approvals WHERE lower(status)='pending'").fetchone()["c"],
    }
    recent=db.execute("SELECT * FROM audit_logs ORDER BY date DESC LIMIT 8").fetchall()
    committees=db.execute("SELECT * FROM committees ORDER BY name").fetchall()
    upcoming=db.execute("SELECT * FROM initiatives WHERE date IS NOT NULL AND date >= ? ORDER BY date ASC LIMIT 5", (today,)).fetchall()
    overdue_tasks=db.execute("SELECT * FROM tasks WHERE deadline IS NOT NULL AND deadline < ? AND lower(status) NOT IN ('done','completed','مكتملة','منجزة') ORDER BY deadline ASC LIMIT 6", (today,)).fetchall()
    pending=db.execute("SELECT * FROM tasks WHERE lower(status) NOT IN ('done','completed','مكتملة','منجزة') ORDER BY deadline ASC LIMIT 8").fetchall()
    if is_creator():
        return render_template("owner_dashboard.html", stats=stats, recent=recent, committees=committees, upcoming=upcoming, overdue_tasks=overdue_tasks, pending=pending)
    return render_template("admin_dashboard.html", stats=stats, recent=recent, committees=committees, upcoming=upcoming, overdue_tasks=overdue_tasks, pending=pending)

@app.route("/admin/users")
def admin_users():
    users=get_db().execute("SELECT id,name,email,username,role,active,must_set_password,last_login,created_at FROM users ORDER BY role DESC, created_at DESC").fetchall()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/<uid_>/role", methods=["POST"])
def admin_user_role(uid_):
    if not is_creator():
        flash("تغيير صلاحيات الأدمن متاح لصانع التطبيق فقط", "error")
        return redirect(url_for("admin_users"))
    role=request.form.get("role","ADMIN")
    if role not in ("ADMIN","CREATOR"): role="ADMIN"
    db=get_db(); db.execute("UPDATE users SET role=? WHERE id=?", (role,uid_)); db.commit()
    log_action("Role changed", uid_)
    flash("تم تحديث الصلاحية", "ok")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/new", methods=["GET", "POST"])
def admin_user_new():
    if not is_creator():
        flash("إنشاء الحسابات متاح لصانع التطبيق فقط", "error")
        return redirect(url_for("admin_users"))
    if request.method == "POST":
        name=request.form.get("name", "").strip()
        username=request.form.get("username", "").strip().lower()
        email=request.form.get("email", "").strip().lower() or None
        password=request.form.get("password", "")
        confirm=request.form.get("confirm_password", "")
        role=request.form.get("role", "ADMIN")
        position=request.form.get("position", "إداري").strip()
        committee=request.form.get("committee", "").strip()
        if role not in ("ADMIN", "SUPER_ADMIN"): role="ADMIN"
        if not name or not username or not password:
            flash("الاسم واسم المستخدم والرمز مطلوبة", "error")
            return redirect(request.url)
        if password != confirm:
            flash("الرمزان غير متطابقين", "error")
            return redirect(request.url)
        db=get_db()
        if db.execute("SELECT id FROM users WHERE lower(username)=?", (username,)).fetchone():
            flash("اسم المستخدم مستخدم مسبقًا", "error")
            return redirect(request.url)
        if email and db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone():
            flash("البريد مستخدم مسبقًا", "error")
            return redirect(request.url)
        db.execute("INSERT INTO users(id,name,email,username,password_hash,password_plain,role,active,must_set_password,last_login,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (uid("usr"),name,email,username,generate_password_hash(password),password,role,1,0,None,now_iso()))
        if request.form.get("add_directory"):
            if not db.execute("SELECT id FROM administrators WHERE name=?", (name,)).fetchone():
                db.execute("INSERT INTO administrators(id,name,position,committee,date,responsibilities) VALUES(?,?,?,?,?,?)",
                           (uid("adm"),name,position,committee,date.today().isoformat(),request.form.get("responsibilities", "")))
        db.commit(); log_action("Created admin account",name); flash("تم إنشاء الحساب", "ok")
        return redirect(url_for("admin_users"))
    return render_template("admin_user_form.html")

@app.route("/admin/users/<uid_>/password", methods=["POST"])
def admin_user_password(uid_):
    if not is_creator():
        flash("تغيير رموز الحسابات متاح لصانع التطبيق فقط", "error")
        return redirect(url_for("admin_users"))
    password=request.form.get("password", "")
    confirm=request.form.get("confirm_password", "")
    if len(password) < 6 or password != confirm:
        flash("الرمز يجب أن يكون 6 أحرف/أرقام على الأقل ومتطابقًا", "error")
        return redirect(url_for("admin_users"))
    db=get_db(); u=db.execute("SELECT * FROM users WHERE id=?",(uid_,)).fetchone()
    if not u:
        return redirect(url_for("admin_users"))
    db.execute("UPDATE users SET password_hash=?,password_plain=?,must_set_password=0 WHERE id=?",(generate_password_hash(password),password,uid_))
    db.commit(); log_action("Reset admin password",u["name"]); flash("تم تعيين الرمز", "ok")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/<uid_>/toggle", methods=["POST"])
def admin_user_toggle(uid_):
    if not is_creator():
        flash("إدارة حالة الحسابات متاحة لصانع التطبيق فقط", "error")
        return redirect(url_for("admin_users"))
    db=get_db(); u=db.execute("SELECT * FROM users WHERE id=?",(uid_,)).fetchone()
    if not u:
        return redirect(url_for("admin_users"))
    if u["role"] == "CREATOR":
        flash("لا يمكن إيقاف حساب صانع التطبيق", "error")
        return redirect(url_for("admin_users"))
    db.execute("UPDATE users SET active=? WHERE id=?", (0 if u["active"] else 1, uid_)); db.commit()
    log_action("Toggled admin account",u["name"]); return redirect(url_for("admin_users"))

@app.route("/news")
def public_news():
    db=get_db(); q=request.args.get("q","").strip(); category=request.args.get("category","").strip()
    now=now_iso(); where=["status='published'","(scheduled_at IS NULL OR scheduled_at='' OR scheduled_at<=?)"]; args=[now]
    if q: where.append("(title LIKE ? OR excerpt LIKE ? OR content LIKE ?)"); like=f"%{q}%"; args += [like,like,like]
    if category: where.append("category=?"); args.append(category)
    sql="SELECT * FROM news WHERE "+" AND ".join(where)+" ORDER BY featured DESC,published_at DESC,created_at DESC"
    rows=db.execute(sql,args).fetchall(); categories=[r["category"] for r in db.execute("SELECT DISTINCT category FROM news WHERE status='published' ORDER BY category").fetchall() if r["category"]]
    featured=rows[0] if rows and not q and not category else None
    grid=rows[1:] if featured else rows
    return render_template("news.html", news=grid, featured_news=featured, categories=categories, q=q, active_category=category)

@app.route("/news/<slug>")
def public_news_detail(slug):
    n=get_db().execute("SELECT * FROM news WHERE slug=? AND status='published' AND (scheduled_at IS NULL OR scheduled_at='' OR scheduled_at<=?)", (slug,now_iso())).fetchone()
    if not n: return redirect(url_for("public_news"))
    return render_template("news_detail.html", n=n)

@app.route("/admin/news")
def news_admin():
    rows=get_db().execute("SELECT * FROM news ORDER BY created_at DESC").fetchall()
    return render_template("news_admin.html", news=rows)

@app.route("/admin/news/new", methods=["GET","POST"])
def news_new():
    if request.method=="POST":
        db=get_db(); title=request.form.get("title","").strip(); slug=request.form.get("slug","").strip().lower().replace(" ","-")
        if not title: flash("اكتب عنوان الخبر", "error"); return redirect(request.url)
        if not slug: slug=uuid.uuid4().hex[:10]
        author=(current_user()["name"] if current_user() else "HIKMA IMPACT")
        status=request.form.get("status","draft")
        featured=1 if request.form.get("featured") else 0; scheduled_at=request.form.get("scheduled_at") or None
        db.execute("INSERT INTO news(id,title,slug,excerpt,content,cover_image,category,author,status,published_at,created_at,featured,scheduled_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (uid("news"),title,slug,request.form.get("excerpt",""),request.form.get("content",""),request.form.get("cover_image",""),request.form.get("category","عام"),author,status,now_iso() if status=="published" and not scheduled_at else None,now_iso(),featured,scheduled_at))
        db.commit(); log_action("Created news",title); flash("تم حفظ الخبر", "ok"); return redirect(url_for("news_admin"))
    return render_template("news_form.html", n=None)

@app.route("/admin/news/<nid>/edit", methods=["GET","POST"])
def news_edit(nid):
    db=get_db(); n=db.execute("SELECT * FROM news WHERE id=?",(nid,)).fetchone()
    if not n: return redirect(url_for("news_admin"))
    if request.method=="POST":
        status=request.form.get("status","draft")
        featured=1 if request.form.get("featured") else 0; scheduled_at=request.form.get("scheduled_at") or None
        db.execute("UPDATE news SET title=?,slug=?,excerpt=?,content=?,cover_image=?,category=?,status=?,published_at=?,featured=?,scheduled_at=? WHERE id=?",
                   (request.form.get("title",""),request.form.get("slug",""),request.form.get("excerpt",""),request.form.get("content",""),request.form.get("cover_image",""),request.form.get("category","عام"),status,now_iso() if status=="published" and not scheduled_at else None,featured,scheduled_at,nid))
        db.commit(); log_action("Updated news",n["title"]); flash("تم تحديث الخبر", "ok"); return redirect(url_for("news_admin"))
    return render_template("news_form.html", n=n)

@app.route("/admin/news/<nid>/delete", methods=["POST"])
def news_delete(nid):
    db=get_db(); db.execute("DELETE FROM news WHERE id=?",(nid,)); db.commit(); log_action("Deleted news",nid); return redirect(url_for("news_admin"))

@app.route("/page/<slug>")
def public_page(slug):
    p=get_db().execute("SELECT * FROM pages WHERE slug=? AND status='published'",(slug,)).fetchone()
    if not p: return "<h2 style='font-family:Tajawal'>الصفحة غير موجودة</h2>",404
    return render_template("page_public.html", page=p)

@app.route("/admin/pages")
def page_admin():
    pages=get_db().execute("SELECT * FROM pages ORDER BY sort_order,title").fetchall()
    return render_template("pages_admin.html", pages=pages)

@app.route("/admin/pages/new", methods=["GET","POST"])
def page_new():
    if request.method=="POST":
        db=get_db(); title=request.form.get("title","").strip(); slug=request.form.get("slug","").strip().lower().replace(" ","-") or uuid.uuid4().hex[:10]
        db.execute("INSERT INTO pages(id,title,slug,content,status,show_in_nav,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (uid("page"),title,slug,request.form.get("content",""),request.form.get("status","draft"),1 if request.form.get("show_in_nav") else 0,int(request.form.get("sort_order",0) or 0),now_iso(),now_iso()))
        db.commit(); log_action("Created page",title); return redirect(url_for("page_admin"))
    return render_template("page_form.html", page=None)

@app.route("/admin/pages/<pid>/edit", methods=["GET","POST"])
def page_edit(pid):
    db=get_db(); p=db.execute("SELECT * FROM pages WHERE id=?",(pid,)).fetchone()
    if not p: return redirect(url_for("page_admin"))
    if request.method=="POST":
        db.execute("UPDATE pages SET title=?,slug=?,content=?,status=?,show_in_nav=?,sort_order=?,updated_at=? WHERE id=?",
                   (request.form.get("title",""),request.form.get("slug",""),request.form.get("content",""),request.form.get("status","draft"),1 if request.form.get("show_in_nav") else 0,int(request.form.get("sort_order",0) or 0),now_iso(),pid))
        db.commit(); log_action("Updated page",p["title"]); return redirect(url_for("page_admin"))
    return render_template("page_form.html", page=p)

@app.route("/admin/pages/<pid>/delete", methods=["POST"])
def page_delete(pid):
    db=get_db(); db.execute("DELETE FROM pages WHERE id=?",(pid,)); db.commit(); return redirect(url_for("page_admin"))

# ============================================================ DASHBOARD ============================================================
@app.route("/")
@app.route("/dashboard")
def public_home():
    db = get_db()
    members = db.execute("SELECT * FROM members").fetchall()
    admins = db.execute("SELECT * FROM administrators").fetchall()
    initiatives = db.execute("SELECT * FROM initiatives").fetchall()

    scores = [member_score(db, m["id"]) for m in members]
    scores = [s for s in scores if s is not None]
    atts = [member_attendance_pct(db, m["id"]) for m in members]
    atts = [a for a in atts if a is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else None
    avg_att = round(sum(atts) / len(atts)) if atts else None
    total_hours = sum((i["hours"] or 0) for i in initiatives)

    months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    counts = [0] * 12
    for i in initiatives:
        if i["date"]:
            try:
                mi = datetime.fromisoformat(str(i["date"])[:10]).month - 1
                counts[mi] += 1
            except Exception:
                pass
    max_count = max(counts + [1])

    top_members = []
    for m in members:
        s = member_score(db, m["id"])
        if s is not None:
            top_members.append((m, s))
    top_members.sort(key=lambda x: x[1], reverse=True)
    top_members = top_members[:5]

    latest_news = db.execute("SELECT * FROM news WHERE status='published' ORDER BY published_at DESC, created_at DESC LIMIT 5").fetchall()
    committees = db.execute("SELECT * FROM committees ORDER BY name").fetchall()
    upcoming = db.execute("SELECT * FROM initiatives WHERE date IS NOT NULL AND date >= ? ORDER BY date ASC LIMIT 3", (date.today().isoformat(),)).fetchall()
    featured = db.execute("SELECT * FROM initiatives ORDER BY date DESC LIMIT 6").fetchall()
    public_admins = db.execute("SELECT * FROM administrators ORDER BY date ASC LIMIT 6").fetchall()
    featured_media = db.execute("SELECT * FROM media WHERE public=1 ORDER BY sort_order, created_at DESC LIMIT 4").fetchall()
    partners = db.execute("SELECT * FROM partners WHERE active=1 ORDER BY sort_order,name LIMIT 6").fetchall()
    impact_points = db.execute("SELECT id,name,location,latitude,longitude,date,status,map_status,map_note,map_date,map_visible FROM initiatives WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND COALESCE(map_visible,1)=1 ORDER BY date DESC").fetchall()
    live_session_id=get_setting("liveSessionId", "")
    live_session=db.execute("SELECT ls.*,i.name initiative_name FROM live_sessions ls LEFT JOIN initiatives i ON i.id=ls.initiative_id WHERE ls.id=? AND ls.status='live'",(live_session_id,)).fetchone() if live_session_id else None
    return render_template("public_home.html",
        members_count=len(members), admins_count=len(admins), initiatives_count=len(initiatives),
        total_hours=total_hours, avg_score=avg_score, avg_att=avg_att, latest_news=latest_news,
        months=months, counts=counts, max_count=max_count, top_members=top_members,
        committees=committees, upcoming=upcoming, featured=featured, public_admins=public_admins, featured_media=featured_media, partners=partners, impact_points=impact_points, live_session=live_session, live_session_id=live_session_id, live_mode=get_setting("liveMode","internal"))



# ============================================================ PUBLIC EXPANSION / SEARCH / IMPACT ============================================================
@app.route("/about")
def about_public():
    return render_template("public_info.html", page_title="عن HIKMA IMPACT", page_kicker="ABOUT", page_text=get_setting("siteDescription", "منصة HIKMA IMPACT لإدارة الأثر، المبادرات، والأداء التطوعي."))

@app.route("/impact")
def impact_public():
    db=get_db()
    members=db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"]
    initiatives=db.execute("SELECT COUNT(*) c FROM initiatives").fetchone()["c"]
    hours=db.execute("SELECT COALESCE(SUM(hours),0) h FROM initiatives").fetchone()["h"] or 0
    admins=db.execute("SELECT COUNT(*) c FROM administrators").fetchone()["c"]
    goals=db.execute("SELECT * FROM goals WHERE status='active' ORDER BY created_at DESC").fetchall()
    points=db.execute("SELECT id,name,location,latitude,longitude,date,status,map_status,map_note,map_date,map_visible FROM initiatives WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND COALESCE(map_visible,1)=1 ORDER BY date DESC").fetchall()
    return render_template("impact.html", members=members, initiatives=initiatives, hours=round(hours), admins=admins, goals=goals, points=points)

@app.route("/impact-map")
def impact_map_public():
    points=get_db().execute("SELECT id,name,location,latitude,longitude,date,status,map_status,map_note,map_date,map_visible FROM initiatives WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND COALESCE(map_visible,1)=1 ORDER BY date DESC").fetchall()
    return render_template("impact_map.html", points=points)

@app.route("/live")
def live_public():
    db=get_db()
    session_id=get_setting("liveSessionId", "")
    active=None
    if session_id:
        active=db.execute("SELECT ls.*, i.name initiative_name FROM live_sessions ls LEFT JOIN initiatives i ON i.id=ls.initiative_id WHERE ls.id=? AND ls.status='live'", (session_id,)).fetchone()
    return render_template("live.html", live_session=active, live_url=get_setting("liveUrl", ""), live_title=get_setting("liveTitle", "البث المباشر من الميدان"), live_description=get_setting("liveDescription", "تابع مبادرات فريق الحكمة التطوعي مباشرةً."), live_platform=get_setting("livePlatform", "YouTube"), live_enabled=get_setting("liveEnabled", "0"), live_mode=get_setting("liveMode", "internal"), live_embed_url=get_live_embed_url(get_setting("liveUrl", "")))

@app.route("/live/room/<sid>")
def live_room(sid):
    db=get_db()
    ls=db.execute("SELECT ls.*, i.name initiative_name FROM live_sessions ls LEFT JOIN initiatives i ON i.id=ls.initiative_id WHERE ls.id=? AND ls.status='live'", (sid,)).fetchone()
    if not ls: return redirect(url_for("live_public"))
    return render_template("live_room.html", live_session=ls, is_broadcaster=is_admin())

@app.route("/api/live/session/<sid>/join", methods=["POST"])
def live_join(sid):
    db=get_db(); ls=db.execute("SELECT * FROM live_sessions WHERE id=? AND status='live'",(sid,)).fetchone()
    if not ls: return jsonify({"ok":False,"error":"Live session not found"}),404
    data=request.get_json(silent=True) or {}; peer_id=(data.get("peer_id") or "").strip(); role=(data.get("role") or "viewer").strip()
    if not peer_id: return jsonify({"ok":False,"error":"peer_id required"}),400
    if role=="broadcaster" and not is_admin(): return jsonify({"ok":False,"error":"Admin access required"}),403
    now=now_iso(); db.execute("INSERT INTO live_peers(id,session_id,peer_id,role,created_at,last_seen) VALUES(?,?,?,?,?,?) ON CONFLICT(session_id,peer_id) DO UPDATE SET role=excluded.role,last_seen=excluded.last_seen",(uid("peer"),sid,peer_id,role,now,now)); db.commit()
    return jsonify({"ok":True,"session":sid,"peer_id":peer_id,"role":role})

@app.route("/api/live/session/<sid>/peers")
def live_peers_api(sid):
    peer_id=request.args.get("peer_id",""); db=get_db(); ls=db.execute("SELECT id FROM live_sessions WHERE id=? AND status='live'",(sid,)).fetchone()
    if not ls:return jsonify({"ok":False}),404
    db.execute("UPDATE live_peers SET last_seen=? WHERE session_id=? AND peer_id=?",(now_iso(),sid,peer_id)); db.execute("DELETE FROM live_peers WHERE session_id=? AND last_seen<?",(sid,datetime.utcnow().replace(microsecond=0).isoformat())); db.commit()
    rows=db.execute("SELECT peer_id,role FROM live_peers WHERE session_id=? AND peer_id<>? ORDER BY created_at",(sid,peer_id)).fetchall()
    return jsonify({"ok":True,"peers":[dict(r) for r in rows]})

@app.route("/api/live/session/<sid>/signal", methods=["GET","POST"])
def live_signal(sid):
    db=get_db(); ls=db.execute("SELECT id FROM live_sessions WHERE id=? AND status='live'",(sid,)).fetchone()
    if not ls:return jsonify({"ok":False}),404
    if request.method=="POST":
        data=request.get_json(silent=True) or {}; sender=data.get("sender_id"); target=data.get("target_id"); kind=data.get("kind"); payload=data.get("payload")
        if not sender or not target or kind not in ("offer","answer","ice"): return jsonify({"ok":False,"error":"Invalid signal"}),400
        db.execute("INSERT INTO live_signals(id,session_id,sender_id,target_id,kind,payload,created_at,delivered_at) VALUES(?,?,?,?,?,?,?,NULL)",(uid("sig"),sid,sender,target,kind,json.dumps(payload),now_iso())); db.commit(); return jsonify({"ok":True})
    peer=request.args.get("peer_id",""); rows=db.execute("SELECT id,sender_id,kind,payload FROM live_signals WHERE session_id=? AND target_id=? AND delivered_at IS NULL ORDER BY created_at LIMIT 100",(sid,peer)).fetchall()
    ids=[r["id"] for r in rows]
    if ids: db.executemany("UPDATE live_signals SET delivered_at=? WHERE id=?",[(now_iso(),i) for i in ids]); db.commit()
    return jsonify({"ok":True,"signals":[{"id":r["id"],"sender_id":r["sender_id"],"kind":r["kind"],"payload":json.loads(r["payload"])} for r in rows]})

@app.route("/api/live/session/<sid>/leave", methods=["POST"])
def live_leave(sid):
    data=request.get_json(silent=True) or {}; peer_id=data.get("peer_id",""); db=get_db(); db.execute("DELETE FROM live_peers WHERE session_id=? AND peer_id=?",(sid,peer_id)); db.commit(); return jsonify({"ok":True})

@app.route("/events")
def events_public():
    db=get_db(); rows=db.execute("SELECT * FROM events ORDER BY date ASC, time ASC").fetchall()
    return render_template("events.html", events=rows)

@app.route("/media")
def media_public():
    rows=get_db().execute("SELECT m.*, i.name initiative_name FROM media m LEFT JOIN initiatives i ON i.id=m.initiative_id WHERE m.public=1 ORDER BY m.created_at DESC").fetchall()
    return render_template("media.html", media=rows)

@app.route("/partners")
def partners_public():
    rows=get_db().execute("SELECT * FROM partners WHERE active=1 ORDER BY sort_order, name").fetchall()
    return render_template("partners.html", partners=rows)

@app.route("/volunteer")
def volunteer_redirect():
    return redirect(get_setting("telegramUrl", "https://t.me/Hikmaht_bot"))

@app.route("/search")
def search_public():
    q=request.args.get("q","").strip()
    results=[]
    if q:
        like=f"%{q}%"; db=get_db()
        for r in db.execute("SELECT id,title,slug,excerpt FROM news WHERE status='published' AND (title LIKE ? OR excerpt LIKE ? OR content LIKE ?) ORDER BY published_at DESC LIMIT 10",(like,like,like)).fetchall():
            results.append({"kind":"خبر","title":r["title"],"text":r["excerpt"] or "","url":url_for("public_news_detail",slug=r["slug"])})
        for r in db.execute("SELECT id,name,description FROM initiatives WHERE name LIKE ? OR description LIKE ? ORDER BY date DESC LIMIT 10",(like,like)).fetchall():
            results.append({"kind":"مبادرة","title":r["name"],"text":r["description"] or "","url":url_for("initiative_view",iid=r["id"])})
        for r in db.execute("SELECT id,name,position,committee FROM administrators WHERE name LIKE ? OR position LIKE ? OR committee LIKE ? LIMIT 10",(like,like,like)).fetchall():
            results.append({"kind":"إداري","title":r["name"],"text":r["position"] or r["committee"] or "","url":url_for("admins_list")+"#admin-"+r["id"]})
        for r in db.execute("SELECT id,name,description FROM committees WHERE name LIKE ? OR description LIKE ? LIMIT 10",(like,like)).fetchall():
            results.append({"kind":"لجنة","title":r["name"],"text":r["description"] or "","url":url_for("committees_list")})
    return render_template("search.html", q=q, results=results)

@app.route("/api/impact")
def api_impact():
    db=get_db()
    return jsonify({"ok":True,"team":get_setting("teamName","HIKMA IMPACT"),"members":db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"],"initiatives":db.execute("SELECT COUNT(*) c FROM initiatives").fetchone()["c"],"hours":db.execute("SELECT COALESCE(SUM(hours),0) h FROM initiatives").fetchone()["h"] or 0,"news":db.execute("SELECT COUNT(*) c FROM news WHERE status='published'").fetchone()["c"]})

# ============================================================ ADMIN EXPANSION ============================================================
def notify_role(role, title, body, target_url=None):
    db=get_db(); users=db.execute("SELECT id FROM users WHERE role=? AND active=1",(role,)).fetchall()
    for u in users:
        db.execute("INSERT INTO notifications(id,user_id,target_role,type,title,body,url,read_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(uid("ntf"),u["id"],role,"system",title,body,target_url,None,now_iso()))
    db.commit()

def notify_user(user_id,title,body,target_url=None,kind="system"):
    db=get_db(); db.execute("INSERT INTO notifications(id,user_id,target_role,type,title,body,url,read_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(uid("ntf"),user_id,None,kind,title,body,target_url,None,now_iso())); db.commit()

@app.route("/notifications")
def notifications_page():
    u=current_user()
    if not u: return redirect(url_for("admin_login"))
    rows=get_db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100",(u["id"],)).fetchall()
    return render_template("notifications.html", notifications=rows)

@app.route("/notifications/read/<nid>", methods=["POST"])
def notification_read(nid):
    u=current_user(); db=get_db(); db.execute("UPDATE notifications SET read_at=? WHERE id=? AND user_id=?",(now_iso(),nid,u["id"])); db.commit(); return jsonify({"ok":True})

@app.route("/notifications/read-all", methods=["POST"])
def notification_read_all():
    u=current_user(); get_db().execute("UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL",(now_iso(),u["id"])); get_db().commit(); return jsonify({"ok":True})

@app.route("/admin/analytics")
def analytics_page():
    db=get_db(); months=[]
    for i in range(11,-1,-1):
        y=date.today().year; m=date.today().month-i
        while m<=0: y-=1; m+=12
        prefix=f"{y:04d}-{m:02d}"
        months.append({"label":prefix,"initiatives":db.execute("SELECT COUNT(*) c FROM initiatives WHERE date LIKE ?",(prefix+"%",)).fetchone()["c"],"news":db.execute("SELECT COUNT(*) c FROM news WHERE status='published' AND published_at LIKE ?",(prefix+"%",)).fetchone()["c"]})
    committees=[]
    for c in db.execute("SELECT * FROM committees ORDER BY name").fetchall():
        n=c["name"]; committees.append({"name":n,"members":db.execute("SELECT COUNT(*) c FROM members WHERE committee=?",(n,)).fetchone()["c"],"initiatives":db.execute("SELECT COUNT(*) c FROM initiatives WHERE committee=?",(n,)).fetchone()["c"]})
    return render_template("analytics.html",months=months,committees=committees)

@app.route("/admin/insights")
def insights_page():
    db=get_db(); insights=[]
    overdue=db.execute("SELECT COUNT(*) c FROM tasks WHERE deadline IS NOT NULL AND deadline < ? AND lower(status) NOT IN ('done','completed','مكتملة','منجزة')",(date.today().isoformat(),)).fetchone()["c"]
    if overdue: insights.append(("🚨","تنبيه تشغيلي",f"هناك {overdue} مهام متأخرة تحتاج متابعة."))
    members=db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"]; initiatives=db.execute("SELECT COUNT(*) c FROM initiatives").fetchone()["c"]
    if members and initiatives: insights.append(("📈","فرصة",f"لدى الفريق {members} عضو مقابل {initiatives} مبادرة موثقة."))
    news=db.execute("SELECT COUNT(*) c FROM news WHERE status='published'").fetchone()["c"]
    if news==0: insights.append(("📰","فرصة إعلامية","لا توجد أخبار منشورة حاليًا؛ تفعيل مركز الأخبار سيحسن الحضور العام."))
    if not insights: insights.append(("✅","الوضع مستقر","لا توجد إشارات تشغيلية حرجة حاليًا."))
    return render_template("insights.html",insights=insights)

@app.route("/admin/risk")
def risk_page():
    db=get_db(); risks=[]
    overdue=db.execute("SELECT COUNT(*) c FROM tasks WHERE deadline IS NOT NULL AND deadline < ? AND lower(status) NOT IN ('done','completed','مكتملة','منجزة')",(date.today().isoformat(),)).fetchone()["c"]
    pending=db.execute("SELECT COUNT(*) c FROM approvals WHERE status='pending'").fetchone()["c"]
    if overdue: risks.append(("عالي","مهام متأخرة",f"{overdue} مهمة متأخرة."))
    if pending: risks.append(("متوسط","موافقات معلقة",f"{pending} طلب موافقة بانتظار المراجعة."))
    if not risks: risks.append(("منخفض","لا توجد مخاطر حرجة","الوضع التشغيلي مستقر حسب البيانات الحالية."))
    return render_template("risk.html",risks=risks)

@app.route("/admin/decisions")
def decision_center():
    db=get_db(); decisions=db.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC").fetchall()
    return render_template("decisions.html",decisions=decisions)

@app.route("/admin/goals", methods=["GET","POST"])
def goals_page():
    db=get_db()
    if request.method=="POST":
        title=request.form.get("title","").strip(); target=float(request.form.get("target",0) or 0); period=request.form.get("period","")
        if title: db.execute("INSERT INTO goals(id,title,target,current,period,status,created_at) VALUES(?,?,?,?,?,?,?)",(uid("goal"),title,target,0,period,"active",now_iso())); db.commit(); log_action("Created goal",title)
        return redirect(url_for("goals_page"))
    goals=db.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall(); return render_template("goals.html",goals=goals)

@app.route("/admin/goals/<gid>/progress", methods=["POST"])
def goal_progress(gid):
    val=float(request.form.get("current",0) or 0); db=get_db(); db.execute("UPDATE goals SET current=? WHERE id=?",(val,gid)); db.commit(); log_action("Updated goal",gid); return redirect(url_for("goals_page"))

@app.route("/admin/approvals")
def approvals_page():
    rows=get_db().execute("SELECT * FROM approvals ORDER BY created_at DESC").fetchall(); return render_template("approvals.html", approvals=rows)

@app.route("/admin/approvals/<aid>/review", methods=["POST"])
def approval_review(aid):
    status=request.form.get("status","approved"); notes=request.form.get("notes",""); u=current_user(); db=get_db(); db.execute("UPDATE approvals SET status=?,reviewed_by=?,notes=?,reviewed_at=? WHERE id=?",(status,u["name"],notes,now_iso(),aid)); db.commit(); log_action("Reviewed approval",aid); return redirect(url_for("approvals_page"))

@app.route("/admin/events", methods=["GET","POST"])
def events_admin():
    db=get_db()
    if request.method=="POST":
        db.execute("INSERT INTO events(id,title,date,time,location,description,status,cover_image,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(uid("evt"),request.form.get("title"),request.form.get("date"),request.form.get("time"),request.form.get("location"),request.form.get("description"),request.form.get("status","upcoming"),request.form.get("cover_image",""),now_iso())); db.commit(); log_action("Created event",request.form.get("title")); return redirect(url_for("events_admin"))
    return render_template("events_admin.html",events=db.execute("SELECT * FROM events ORDER BY date DESC").fetchall())

@app.route("/admin/events/<eid>/delete", methods=["POST"])
def event_delete(eid):
    db=get_db(); db.execute("DELETE FROM events WHERE id=?",(eid,)); db.commit(); log_action("Deleted event",eid); return redirect(url_for("events_admin"))

@app.route("/admin/partners", methods=["GET","POST"])
def partners_admin():
    db=get_db()
    if request.method=="POST":
        db.execute("INSERT INTO partners(id,name,description,logo,url,sort_order,active) VALUES(?,?,?,?,?,?,?)",(uid("pr"),request.form.get("name"),request.form.get("description"),request.form.get("logo"),request.form.get("url"),int(request.form.get("sort_order",0) or 0),1)); db.commit(); log_action("Created partner",request.form.get("name")); return redirect(url_for("partners_admin"))
    return render_template("partners_admin.html",partners=db.execute("SELECT * FROM partners ORDER BY sort_order,name").fetchall())

@app.route("/admin/media", methods=["GET","POST"])
def media_admin():
    db=get_db()
    if request.method=="POST":
        db.execute("INSERT INTO media(id,title,url,category,initiative_id,public,created_at) VALUES(?,?,?,?,?,?,?)",(uid("med"),request.form.get("title"),request.form.get("url"),request.form.get("category"),request.form.get("initiative_id") or None,1,now_iso())); db.commit(); log_action("Added media",request.form.get("title")); return redirect(url_for("media_admin"))
    return render_template("media_admin.html",media=db.execute("SELECT m.*,i.name initiative_name FROM media m LEFT JOIN initiatives i ON i.id=m.initiative_id ORDER BY m.created_at DESC").fetchall(),initiatives=db.execute("SELECT * FROM initiatives ORDER BY date DESC").fetchall())

@app.route("/admin/security")
def security_page():
    db=get_db(); rows=db.execute("SELECT s.*,u.name FROM security_sessions s LEFT JOIN users u ON u.id=s.user_id ORDER BY last_seen DESC LIMIT 100").fetchall(); return render_template("security.html",sessions=rows)

@app.route("/certificate/<mid>")
def certificate_legacy(mid):
    if not is_admin(): return redirect(url_for("admin_login"))
    return redirect(url_for("certificates_admin"))


# ============================================================ MEMBERS ============================================================
@app.route("/members")
def members_list():
    db = get_db()
    q = request.args.get("q", "").strip().lower()
    members = db.execute("SELECT * FROM members ORDER BY created_at DESC").fetchall()
    if q:
        members = [m for m in members if q in (m["name"] or "").lower()
                   or q in (m["committee"] or "").lower() or q in (m["position"] or "").lower()]
    data = []
    for m in members:
        data.append({
            "m": m, "score": member_score(db, m["id"]), "points": member_points_total(db, m["id"]),
            "att": member_attendance_pct(db, m["id"]), "level": member_level(db, m["id"]),
            "ini_count": member_initiative_count(db, m["id"])
        })
    return render_template("members_list.html", data=data, q=request.args.get("q", ""))


@app.route("/members/new", methods=["GET", "POST"])
def member_new():
    return member_form()


@app.route("/members/<mid>/edit", methods=["GET", "POST"])
def member_edit(mid):
    return member_form(mid)


def member_form(mid=None):
    db = get_db()
    committees = db.execute("SELECT * FROM committees").fetchall()
    member = db.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone() if mid else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("يرجى إدخال اسم العضو", "error")
            return redirect(request.url)
        photo = request.form.get("photo", "")
        data = (name, request.form.get("email", ""), request.form.get("phone", ""),
                request.form.get("committee", ""), request.form.get("position", "عضو"),
                request.form.get("join_date", ""), request.form.get("status", "Active"),
                request.form.get("notes", ""), photo)
        if mid:
            db.execute("""UPDATE members SET name=?,email=?,phone=?,committee=?,position=?,
                           join_date=?,status=?,notes=?,photo=? WHERE id=?""", data + (mid,))
            log_action("Updated", f"عضو: {name}")
        else:
            db.execute("""INSERT INTO members(id,name,email,phone,committee,position,join_date,status,notes,photo,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (uid("mem"),) + data + (now_iso(),))
            log_action("Created", f"عضو: {name}")
        db.commit()
        flash("تم الحفظ بنجاح", "ok")
        return redirect(url_for("members_list"))
    return render_template("member_form.html", member=member, committees=committees)


@app.route("/members/<mid>/delete", methods=["POST"])
def member_delete(mid):
    db = get_db()
    m = db.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
    if m:
        db.execute("DELETE FROM members WHERE id=?", (mid,))
        db.execute("DELETE FROM initiative_participants WHERE member_id=?", (mid,))
        db.commit()
        log_action("Deleted", f"عضو: {m['name']}")
        flash("تم الحذف", "ok")
    return redirect(url_for("members_list"))


@app.route("/members/<mid>")
def member_view(mid):
    db = get_db()
    m = db.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
    if not m:
        return redirect(url_for("members_list"))
    s = member_score(db, mid)
    a = member_attendance_pct(db, mid)
    p = member_points_total(db, mid)
    weights = get_weights()
    evs = db.execute("SELECT * FROM evaluations WHERE evaluated_user_id=? ORDER BY date", (mid,)).fetchall()

    breakdown = []
    if s is not None:
        for k in CRITERIA_KEYS:
            cavg = sum((e[f"c_{k}"] or 0) for e in evs) / len(evs)
            breakdown.append({"label": CRITERIA_LABELS[k], "value": round(cavg), "weight": weights.get(k, 0)})

    timeline = []
    for e in evs:
        timeline.append({"date": e["date"], "title": "تقييم جديد", "sub": f"النوع: {e['type']}"})
    pts = db.execute("SELECT * FROM points WHERE member_id=?", (mid,)).fetchall()
    for pt in pts:
        timeline.append({"date": pt["date"], "title": "إضافة نقاط", "sub": f"+{pt['value']} — {pt['source'] or ''}"})
    timeline.append({"date": m["created_at"], "title": "انضمام العضو", "sub": m["committee"] or ""})
    timeline = [t for t in timeline if t["date"]]
    timeline.sort(key=lambda x: x["date"])

    ini_count = member_initiative_count(db, mid)
    volunteer_hours = member_volunteer_hours(db, mid)

    return render_template("member_view.html", m=m, score=s, att=a, points=p, volunteer_hours=volunteer_hours,
        level=member_level(db, mid), breakdown=breakdown, timeline=timeline,
        eval_count=len(evs), ini_count=ini_count, recommendation=recommendation_text(s))


@app.route("/admin/members/<mid>/photo", methods=["POST"])
def member_photo_upload(mid):
    f=request.files.get("photo_file")
    if not f or not f.filename: flash("اختر صورة", "error"); return redirect(url_for("member_view", mid=mid))
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in (".jpg",".jpeg",".png",".webp"): flash("صيغة الصورة غير مدعومة", "error"); return redirect(url_for("member_view", mid=mid))
    filename=f"{mid}{ext}"; f.save(os.path.join(UPLOAD_DIR, filename))
    db=get_db(); db.execute("UPDATE members SET photo=? WHERE id=?", (f"uploads/{filename}",mid)); db.commit(); log_action("Updated member photo",mid)
    flash("تم تحديث الصورة الشخصية", "ok"); return redirect(url_for("member_view", mid=mid))

# ============================================================ ADMINISTRATORS ============================================================
@app.route("/administrators")
def admins_list():
    db = get_db()
    admins = db.execute("SELECT * FROM administrators ORDER BY name").fetchall()
    return render_template("administrators_list.html", admins=admins)


@app.route("/administrators/new", methods=["GET", "POST"])
def admin_new():
    return admin_form()


@app.route("/administrators/<aid>/edit", methods=["GET", "POST"])
def admin_edit(aid):
    return admin_form(aid)


def admin_form(aid=None):
    db = get_db()
    committees = db.execute("SELECT * FROM committees").fetchall()
    a = db.execute("SELECT * FROM administrators WHERE id=?", (aid,)).fetchone() if aid else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("يرجى إدخال الاسم", "error")
            return redirect(request.url)
        data = (name, request.form.get("position", ""), request.form.get("committee", ""),
                request.form.get("date", ""), request.form.get("responsibilities", ""))
        if aid:
            db.execute("""UPDATE administrators SET name=?,position=?,committee=?,date=?,responsibilities=?
                           WHERE id=?""", data + (aid,))
        else:
            db.execute("""INSERT INTO administrators(id,name,position,committee,date,responsibilities)
                           VALUES(?,?,?,?,?,?)""", (uid("adm"),) + data)
        db.commit()
        log_action("Updated" if aid else "Created", f"إداري: {name}")
        flash("تم الحفظ بنجاح", "ok")
        return redirect(url_for("admins_list"))
    return render_template("admin_form.html", a=a, committees=committees)


@app.route("/administrators/<aid>/delete", methods=["POST"])
def admin_delete(aid):
    db = get_db()
    db.execute("DELETE FROM administrators WHERE id=?", (aid,))
    db.commit()
    flash("تم الحذف", "ok")
    return redirect(url_for("admins_list"))


# ============================================================ COMMITTEES ============================================================
@app.route("/committees")
def committees_list():
    db = get_db()
    committees = db.execute("SELECT * FROM committees ORDER BY name").fetchall()
    data = []
    for c in committees:
        cnt = db.execute("SELECT COUNT(*) c FROM members WHERE committee=?", (c["name"],)).fetchone()["c"]
        data.append({"c": c, "member_count": cnt})
    return render_template("committees_list.html", data=data)


@app.route("/committees/new", methods=["GET", "POST"])
def committee_new():
    return committee_form()


@app.route("/committees/<cid>/edit", methods=["GET", "POST"])
def committee_edit(cid):
    return committee_form(cid)


def committee_form(cid=None):
    db = get_db()
    c = db.execute("SELECT * FROM committees WHERE id=?", (cid,)).fetchone() if cid else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("أدخل اسم اللجنة", "error")
            return redirect(request.url)
        data = (name, request.form.get("head", ""), request.form.get("description", ""))
        if cid:
            db.execute("UPDATE committees SET name=?,head=?,description=? WHERE id=?", data + (cid,))
        else:
            db.execute("INSERT INTO committees(id,name,head,description) VALUES(?,?,?,?)", (uid("com"),) + data)
        db.commit()
        log_action("Updated" if cid else "Created", f"لجنة: {name}")
        flash("تم الحفظ بنجاح", "ok")
        return redirect(url_for("committees_list"))
    return render_template("committee_form.html", c=c)


@app.route("/committees/<cid>/delete", methods=["POST"])
def committee_delete(cid):
    db = get_db()
    db.execute("DELETE FROM committees WHERE id=?", (cid,))
    db.commit()
    flash("تم الحذف", "ok")
    return redirect(url_for("committees_list"))


# ============================================================ INITIATIVES ============================================================
@app.route("/initiatives")
def initiatives_list():
    db = get_db()
    initiatives = db.execute("SELECT * FROM initiatives ORDER BY date DESC").fetchall()
    data = [{"i": i, "pcount": initiative_participant_count(db, i["id"])} for i in initiatives]
    return render_template("initiatives_list.html", data=data)


@app.route("/initiatives/new", methods=["GET", "POST"])
def initiative_new():
    return initiative_form()


@app.route("/initiatives/<iid>/edit", methods=["GET", "POST"])
def initiative_edit(iid):
    return initiative_form(iid)


def initiative_form(iid=None):
    db = get_db()
    committees = db.execute("SELECT * FROM committees").fetchall()
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    i = db.execute("SELECT * FROM initiatives WHERE id=?", (iid,)).fetchone() if iid else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("أدخل اسم المبادرة", "error")
            return redirect(request.url)
        lat_raw=request.form.get("latitude", "").strip()
        lng_raw=request.form.get("longitude", "").strip()
        try: lat=float(lat_raw) if lat_raw else None
        except Exception: lat=None
        try: lng=float(lng_raw) if lng_raw else None
        except Exception: lng=None
        data = (name, request.form.get("date", ""), request.form.get("location", ""),
                request.form.get("manager", ""), request.form.get("committee", ""),
                float(request.form.get("hours") or 0), request.form.get("status", "Planned"),
                request.form.get("description", ""), request.form.get("goals", ""), lat, lng, request.form.get("map_status","completed"), request.form.get("map_note",""), request.form.get("map_date","") or None, 1 if request.form.get("map_visible") else 0)
        if iid:
            db.execute("""UPDATE initiatives SET name=?,date=?,location=?,manager=?,committee=?,
                           hours=?,status=?,description=?,goals=?,latitude=?,longitude=?,map_status=?,map_note=?,map_date=?,map_visible=? WHERE id=?""", data + (iid,))
            log_action("Updated", f"مبادرة: {name}")
        else:
            db.execute("""INSERT INTO initiatives(id,name,date,location,manager,committee,hours,status,description,goals,latitude,longitude,map_status,map_note,map_date,map_visible)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (uid("ini"),) + data)
            log_action("Created Initiative", f"مبادرة: {name}")
        db.commit()
        flash("تم الحفظ بنجاح", "ok")
        return redirect(url_for("initiatives_list"))
    return render_template("initiative_form.html", i=i, committees=committees, members=members)


@app.route("/initiatives/<iid>/delete", methods=["POST"])
def initiative_delete(iid):
    db = get_db()
    db.execute("DELETE FROM initiatives WHERE id=?", (iid,))
    db.execute("DELETE FROM initiative_participants WHERE initiative_id=?", (iid,))
    db.commit()
    flash("تم الحذف", "ok")
    return redirect(url_for("initiatives_list"))


@app.route("/initiatives/<iid>")
def initiative_view(iid):
    db = get_db()
    i = db.execute("SELECT * FROM initiatives WHERE id=?", (iid,)).fetchone()
    if not i:
        return redirect(url_for("initiatives_list"))
    participants = db.execute("""
        SELECT m.*, ip.start_time, ip.end_time, ip.hours participant_hours
        FROM members m
        JOIN initiative_participants ip ON ip.member_id=m.id
        WHERE ip.initiative_id=? ORDER BY m.name
    """, (iid,)).fetchall()
    return render_template("initiative_view.html", i=i, participants=participants, public_view=not is_admin(), map_token=True)


@app.route("/initiatives/<iid>/participants", methods=["GET", "POST"])
def initiative_participants(iid):
    db = get_db()
    i = db.execute("SELECT * FROM initiatives WHERE id=?", (iid,)).fetchone()
    if not i:
        return redirect(url_for("initiatives_list"))
    if request.method == "POST":
        selected = set(request.form.getlist("participant"))
        existing = db.execute("SELECT member_id FROM initiative_participants WHERE initiative_id=?", (iid,)).fetchall()
        existing_ids = {r["member_id"] for r in existing}
        # Existing participants are never removed by the registration screen.
        # This prevents disabled checkboxes from accidentally deleting active records.
        now_time = iraq_now_time()
        for mid in selected:
            if mid not in existing_ids:
                db.execute(
                    "INSERT INTO initiative_participants(initiative_id, member_id, start_time, end_time, hours) VALUES(?,?,?,?,?)",
                    (iid, mid, now_time, None, 0.0))
        db.commit()
        flash("تم تسجيل المشاركين، ووقت الدخول سُجل تلقائيًا الآن", "ok")
        return redirect(url_for("initiative_participants", iid=iid))
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    selected_rows = db.execute(
        "SELECT member_id,start_time,end_time,hours FROM initiative_participants WHERE initiative_id=?", (iid,)).fetchall()
    selected = {r["member_id"]: r for r in selected_rows}
    return render_template("initiative_participants.html", i=i, members=members, selected=selected)


@app.post("/initiatives/<iid>/participants/<mid>/checkout")
def initiative_participant_checkout(iid, mid):
    db = get_db()
    row = db.execute("SELECT * FROM initiative_participants WHERE initiative_id=? AND member_id=?", (iid, mid)).fetchone()
    if not row:
        flash("المشارك غير مسجل", "error")
        return redirect(url_for("initiative_participants", iid=iid))
    if row["end_time"]:
        flash("تم تسجيل خروج هذا العضو مسبقًا ولا يمكن تسجيله مرة ثانية", "error")
        return redirect(url_for("initiative_participants", iid=iid))
    end_time = iraq_now_time()
    hours = duration_hours(row["start_time"], end_time)
    db.execute("UPDATE initiative_participants SET end_time=?, hours=? WHERE initiative_id=? AND member_id=?",
               (end_time, hours, iid, mid))
    db.commit()
    flash(f"تم تسجيل وقت خروج العضو وحساب {hours} ساعة", "ok")
    return redirect(url_for("initiative_participants", iid=iid))


# ============================================================ TASKS ============================================================
@app.route("/tasks")
def tasks_list():
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    return render_template("tasks_list.html", tasks=tasks)


@app.route("/tasks/new", methods=["GET", "POST"])
def task_new():
    return task_form()


@app.route("/tasks/<tid>/edit", methods=["GET", "POST"])
def task_edit(tid):
    return task_form(tid)


def task_form(tid=None):
    db = get_db()
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    t = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone() if tid else None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("أدخل عنوان المهمة", "error")
            return redirect(request.url)
        assignee = request.form.get("assignee", "")
        status = request.form.get("status", "Todo")
        data = (title, assignee, request.form.get("deadline", ""),
                request.form.get("priority", "متوسطة"), status, request.form.get("description", ""))
        was_completed = bool(tid) and t and t["status"] == "Completed"
        if tid:
            db.execute("""UPDATE tasks SET title=?,assignee=?,deadline=?,priority=?,status=?,description=?
                           WHERE id=?""", data + (tid,))
        else:
            db.execute("""INSERT INTO tasks(id,title,assignee,deadline,priority,status,description,created_at)
                           VALUES(?,?,?,?,?,?,?,?)""", (uid("task"),) + data + (now_iso(),))
        db.commit()
        if status == "Completed" and not was_completed and assignee:
            member = db.execute("SELECT * FROM members WHERE name=?", (assignee,)).fetchone()
            if member:
                pts_cfg = get_points_config()
                add_points(member["id"], pts_cfg.get("task", 10), f"إنجاز مهمة: {title}")
        log_action("Updated" if tid else "Completed Task", f"مهمة: {title}")
        flash("تم الحفظ بنجاح", "ok")
        return redirect(url_for("tasks_list"))
    return render_template("task_form.html", t=t, members=members)


@app.route("/tasks/<tid>/delete", methods=["POST"])
def task_delete(tid):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id=?", (tid,))
    db.commit()
    flash("تم الحذف", "ok")
    return redirect(url_for("tasks_list"))


# ============================================================ ATTENDANCE ============================================================
@app.route("/attendance")
def attendance_list():
    db = get_db()
    rows = db.execute("SELECT * FROM attendance ORDER BY date DESC").fetchall()
    data = []
    for r in rows:
        m = db.execute("SELECT name FROM members WHERE id=?", (r["member_id"],)).fetchone()
        i = db.execute("SELECT name FROM initiatives WHERE id=?", (r["initiative_id"],)).fetchone() if r["initiative_id"] else None
        data.append({"a": r, "member_name": m["name"] if m else "—", "ini_name": i["name"] if i else "—"})
    return render_template("attendance_list.html", data=data)


@app.route("/attendance/new", methods=["GET", "POST"])
def attendance_new():
    db = get_db()
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    if not members:
        flash("أضف عضواً أولاً", "error")
        return redirect(url_for("attendance_list"))
    initiatives = db.execute("SELECT * FROM initiatives ORDER BY date DESC").fetchall()
    if request.method == "POST":
        member_id = request.form.get("member_id")
        status = request.form.get("status", "Present")
        att_date = iraq_today()
        initiative_id = request.form.get("initiative_id") or None
        start_time = iraq_now_time() if status in ("Present", "Late") else None
        end_time = None
        hours = 0.0
        db.execute("INSERT INTO attendance(id,member_id,date,status,initiative_id,start_time,end_time,hours) VALUES(?,?,?,?,?,?,?,?)",
                   (uid("att"), member_id, att_date, status, initiative_id, start_time, end_time, hours))
        db.commit()
        if status == "Present":
            pts_cfg = get_points_config()
            add_points(member_id, pts_cfg.get("attendance", 10), f"حضور بتاريخ {att_date}")
        log_action("Created", "حضور مسجل")
        flash("تم تسجيل الدخول تلقائيًا بالوقت الحالي", "ok")
        return redirect(url_for("attendance_list"))
    return render_template("attendance_form.html", members=members, initiatives=initiatives, today=iraq_today())


@app.post("/attendance/<aid>/checkout")
def attendance_checkout(aid):
    db = get_db()
    row = db.execute("SELECT * FROM attendance WHERE id=?", (aid,)).fetchone()
    if not row:
        flash("سجل الحضور غير موجود", "error")
        return redirect(url_for("attendance_list"))
    if not row["start_time"]:
        flash("لا يوجد وقت دخول لهذا السجل", "error")
        return redirect(url_for("attendance_list"))
    if row["end_time"]:
        flash("تم تسجيل خروج هذا السجل مسبقًا ولا يمكن تسجيله مرة ثانية", "error")
        return redirect(url_for("attendance_list"))
    end_time = iraq_now_time()
    hours = duration_hours(row["start_time"], end_time)
    db.execute("UPDATE attendance SET end_time=?, hours=? WHERE id=?", (end_time, hours, aid))
    db.commit()
    flash(f"تم تسجيل وقت الخروج وحساب {hours} ساعة", "ok")
    return redirect(url_for("attendance_list"))


# ============================================================ EVALUATIONS ============================================================
@app.route("/evaluations")
def evaluations_list():
    db = get_db()
    rows = db.execute("SELECT * FROM evaluations ORDER BY date DESC").fetchall()
    data = []
    for e in rows:
        m = db.execute("SELECT name FROM members WHERE id=?", (e["evaluated_user_id"],)).fetchone()
        vals = [e[f"c_{k}"] or 0 for k in CRITERIA_KEYS]
        avg_s = round(sum(vals) / len(vals))
        data.append({"e": e, "member_name": m["name"] if m else "—", "avg": avg_s})
    return render_template("evaluations_list.html", data=data)


@app.route("/evaluations/new", methods=["GET", "POST"])
def evaluation_new():
    db = get_db()
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    if not members:
        flash("أضف عضواً أولاً", "error")
        return redirect(url_for("evaluations_list"))
    preselect = request.args.get("member_id", "")
    if request.method == "POST":
        member_id = request.form.get("member_id")
        member = db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        criteria = {k: int(request.form.get(f"c_{k}", 50)) for k in CRITERIA_KEYS}
        u = current_user()
        db.execute("""INSERT INTO evaluations(id,evaluated_user_id,evaluator_id,evaluator_name,date,type,notes,
                       c_attendance,c_taskCompletion,c_initiativeParticipation,c_commitment,c_teamwork,c_creativity)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (uid("ev"), member_id, u["id"] if u else "", u["name"] if u else "",
                    request.form.get("date", date.today().isoformat()), request.form.get("type", "تقييم مبادرة"),
                    request.form.get("notes", ""), criteria["attendance"], criteria["taskCompletion"],
                    criteria["initiativeParticipation"], criteria["commitment"], criteria["teamwork"],
                    criteria["creativity"]))
        db.commit()
        avg_s = sum(criteria.values()) / 6
        if avg_s >= 85:
            pts_cfg = get_points_config()
            add_points(member_id, pts_cfg.get("excellent", 20), "تقييم ممتاز")
        log_action("Evaluated", f"تقييم {member['name'] if member else ''} ({request.form.get('type','')})")
        flash("تم حفظ التقييم وتحديث النقاط", "ok")
        return redirect(url_for("evaluations_list"))
    return render_template("evaluation_form.html", members=members, preselect=preselect,
                           criteria_keys=CRITERIA_KEYS, criteria_labels=CRITERIA_LABELS,
                           today=date.today().isoformat())


# ============================================================ ACHIEVEMENTS ============================================================
@app.route("/achievements")
def achievements():
    db = get_db()
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    data = []
    for m in members:
        data.append({
            "m": m, "level": member_level(db, m["id"]),
            "points": member_points_total(db, m["id"]), "score": member_score(db, m["id"])
        })
    return render_template("achievements.html", data=data)


# ============================================================ AUDIT LOG ============================================================
@app.route("/audit-log")
def audit_log():
    db = get_db()
    logs = db.execute("SELECT * FROM audit_logs ORDER BY date DESC").fetchall()
    return render_template("audit_log.html", logs=logs)


# ============================================================ CERTIFICATES ============================================================

def _certificate_qr(cid, certificate_no):
    """Create a verification QR image for a certificate."""
    verify_url = url_for("certificate_verify", certificate_no=certificate_no, _external=True)
    img = qrcode.make(verify_url)
    filename = f"cert-{certificate_no}.png"
    path = os.path.join(UPLOAD_DIR, filename)
    img.save(path)
    return f"uploads/{filename}"

@app.route("/admin/certificates", methods=["GET", "POST"])
def certificates_admin():
    if not has_permission("certificates"):
        return render_template("403.html", permission="certificates"), 403
    db=get_db()
    if request.method=="POST":
        recipient=request.form.get("recipient_name","").strip()
        initiative_id=request.form.get("initiative_id") or None
        cert_type=request.form.get("certificate_type","شهادة مشاركة").strip()
        template=request.form.get("template","classic").strip()
        if template not in ("classic","minimal","impact"): template="classic"
        issue_date=request.form.get("issue_date") or date.today().isoformat()
        note=request.form.get("note","").strip()
        hours=float(request.form.get("hours") or 0)
        member_id=request.form.get("recipient_member_id") or None
        if not recipient:
            flash("اكتب اسم المستفيد", "error"); return redirect(url_for("certificates_admin"))
        ini=db.execute("SELECT * FROM initiatives WHERE id=?",(initiative_id,)).fetchone() if initiative_id else None
        initiative_name=ini["name"] if ini else request.form.get("initiative_name","").strip()
        if hours <= 0 and ini and ini["hours"]:
            hours=float(ini["hours"] or 0)
        no="HIKMA-"+date.today().strftime("%Y")+"-"+uuid.uuid4().hex[:8].upper()
        token=uuid.uuid4().hex
        u=current_user(); cid=uid("cert")
        db.execute("INSERT INTO certificates(id,certificate_no,recipient_name,certificate_type,initiative_id,initiative_name,issue_date,hours,note,issued_by,created_at,status,verify_token,template,recipient_member_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (cid,no,recipient,cert_type,initiative_id,initiative_name,issue_date,hours,note,u["name"] if u else "HIKMA IMPACT",now_iso(),"valid",token,template,member_id))
        db.commit()
        qr_path=_certificate_qr(cid,no)
        db.execute("UPDATE certificates SET qr_path=? WHERE id=?",(qr_path,cid)); db.commit()
        log_action("Created certificate",f"{recipient} · {cert_type} · {no}")
        flash("تم إنشاء الشهادة مع QR للتحقق", "ok")
        return redirect(url_for("certificate_view",cid=cid))
    rows=db.execute("SELECT * FROM certificates ORDER BY created_at DESC LIMIT 100").fetchall()
    return render_template("certificates_admin.html",certificates=rows,initiatives=db.execute("SELECT id,name FROM initiatives ORDER BY date DESC").fetchall(),members=db.execute("SELECT id,name FROM members ORDER BY name").fetchall(),today=date.today().isoformat())

@app.route("/admin/certificates/<cid>/revoke", methods=["POST"])
def certificate_revoke(cid):
    if not has_permission("certificates"): return render_template("403.html",permission="certificates"),403
    db=get_db(); c=db.execute("SELECT * FROM certificates WHERE id=?",(cid,)).fetchone()
    if not c:return "الشهادة غير موجودة",404
    db.execute("UPDATE certificates SET status='revoked' WHERE id=?",(cid)); db.commit()
    log_action("Revoked certificate",c["certificate_no"]); flash("تم إلغاء الشهادة", "ok")
    return redirect(url_for("certificates_admin"))

@app.route("/admin/certificates/<cid>/reissue", methods=["POST"])
def certificate_reissue(cid):
    if not has_permission("certificates"): return render_template("403.html",permission="certificates"),403
    db=get_db(); c=db.execute("SELECT * FROM certificates WHERE id=?",(cid,)).fetchone()
    if not c:return "الشهادة غير موجودة",404
    no="HIKMA-"+date.today().strftime("%Y")+"-"+uuid.uuid4().hex[:8].upper(); token=uuid.uuid4().hex; new_id=uid("cert")
    db.execute("INSERT INTO certificates(id,certificate_no,recipient_name,certificate_type,initiative_id,initiative_name,issue_date,hours,note,issued_by,created_at,status,verify_token,template,recipient_member_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (new_id,no,c["recipient_name"],c["certificate_type"],c["initiative_id"],c["initiative_name"],date.today().isoformat(),c["hours"],c["note"],current_user()["name"],now_iso(),"valid",token,c["template"],c["recipient_member_id"]))
    db.commit(); qr_path=_certificate_qr(new_id,no); db.execute("UPDATE certificates SET qr_path=? WHERE id=?",(qr_path,new_id)); db.commit()
    log_action("Reissued certificate",f"{c['certificate_no']} -> {no}"); flash("تم إصدار نسخة جديدة برقم جديد", "ok")
    return redirect(url_for("certificate_view",cid=new_id))

@app.route("/certificate/view/<cid>")
def certificate_view(cid):
    if not is_admin(): return redirect(url_for("admin_login"))
    c=get_db().execute("SELECT * FROM certificates WHERE id=?",(cid,)).fetchone()
    if not c:return "الشهادة غير موجودة",404
    return render_template("certificate.html", certificate=c, team_logo=get_setting("teamLogo",""), university_logo=get_setting("universityLogo",""), verify_url=url_for("certificate_verify",certificate_no=c["certificate_no"],_external=True))

@app.route("/verify/certificate/<certificate_no>")
def certificate_verify(certificate_no):
    c=get_db().execute("SELECT * FROM certificates WHERE certificate_no=?",(certificate_no,)).fetchone()
    return render_template("certificate_verify.html", certificate=c)

# ============================================================ BRAND / LOGO ============================================================
@app.route("/admin/logo/<kind>", methods=["POST"])
def upload_logo(kind):
    if not is_creator():
        flash("تعديل الشعارات متاح لصانع التطبيق فقط", "error")
        return redirect(url_for("settings_page"))
    if kind not in ("team", "university", "favicon"):
        return redirect(url_for("settings_page"))
    f=request.files.get("logo_file")
    if not f or not f.filename:
        flash("اختر صورة أولاً", "error")
        return redirect(url_for("settings_page"))
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    allowed={".png", ".jpg", ".jpeg", ".webp", ".ico"}
    if ext not in allowed:
        flash("صيغة الصورة غير مدعومة", "error")
        return redirect(url_for("settings_page"))
    filename=f"{kind}-logo{ext}"
    f.save(os.path.join(UPLOAD_DIR, filename))
    set_setting({"team":"teamLogo","university":"universityLogo","favicon":"favicon"}[kind], f"uploads/{filename}")
    log_action("Updated logo",kind); flash("تم تحديث الشعار", "ok")
    return redirect(url_for("settings_page"))

# ============================================================ EXPERIENCE CONTROL CENTER ============================================================
@app.route("/admin/navigation", methods=["GET","POST"])
def navigation_page():
    if request.method=="POST":
        db=get_db()
        ids=request.form.getlist("nav_id")
        for idx,nid in enumerate(ids):
            visible=1 if request.form.get(f"visible_{nid}") else 0
            label=request.form.get(f"label_{nid}","").strip()
            icon=request.form.get(f"icon_{nid}","").strip()
            db.execute("UPDATE nav_items SET label=?,icon=?,visible=?,sort_order=? WHERE id=?",(label,icon,visible,(idx+1)*10,nid))
        # Optional custom navigation item
        if request.form.get("new_label") and request.form.get("new_url"):
            db.execute("INSERT INTO nav_items(id,label,endpoint,url,icon,visible,sort_order,is_system,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(uid("nav"),request.form.get("new_label"),"",request.form.get("new_url"),request.form.get("new_icon","↗"),1,999,0,now_iso()))
        db.commit(); log_action("Updated navigation","Public navigation")
        flash("تم حفظ ترتيب وأسماء وإظهار القوائم", "ok")
        return redirect(url_for("navigation_page"))
    return render_template("navigation_admin.html", nav_items=get_db().execute("SELECT * FROM nav_items ORDER BY sort_order").fetchall())

@app.route("/admin/navigation/<nid>/delete", methods=["POST"])
def navigation_delete(nid):
    db=get_db(); row=db.execute("SELECT * FROM nav_items WHERE id=?",(nid,)).fetchone()
    if row and not row["is_system"]: db.execute("DELETE FROM nav_items WHERE id=?",(nid,)); db.commit(); log_action("Deleted navigation",row["label"])
    return redirect(url_for("navigation_page"))

@app.route("/admin/sections", methods=["GET","POST"])
def sections_page():
    if request.method=="POST":
        db=get_db(); ids=request.form.getlist("section_id")
        for idx,sid in enumerate(ids):
            visible=1 if request.form.get(f"visible_{sid}") else 0
            title=request.form.get(f"title_{sid}","").strip()
            db.execute("UPDATE site_sections SET title=?,visible=?,sort_order=?,background=? WHERE id=?",(title,visible,(idx+1)*10,request.form.get(f"background_{sid}","light"),sid))
        db.commit(); log_action("Updated site sections","Public sections"); flash("تم حفظ ترتيب وإظهار أقسام الصفحة", "ok"); return redirect(url_for("sections_page"))
    return render_template("sections_admin.html", sections=get_db().execute("SELECT * FROM site_sections ORDER BY sort_order").fetchall())

@app.route("/admin/permissions", methods=["GET","POST"])
def permissions_page():
    if not is_creator(): return render_template("403.html",permission="permissions"),403
    roles=["ADMIN","SUPER_ADMIN","CREATOR"]
    permissions=[r["permission"] for r in get_db().execute("SELECT DISTINCT permission FROM role_permissions ORDER BY permission").fetchall()]
    if request.method=="POST":
        db=get_db()
        for role in roles:
            for perm in permissions:
                allowed=1 if request.form.get(f"p_{role}_{perm}") else 0
                db.execute("INSERT INTO role_permissions(id,role,permission,allowed) VALUES(?,?,?,?) ON CONFLICT(role,permission) DO UPDATE SET allowed=excluded.allowed",(uid("perm"),role,perm,allowed))
        db.commit(); log_action("Updated permissions","Role matrix"); flash("تم حفظ مصفوفة الصلاحيات", "ok"); return redirect(url_for("permissions_page"))
    matrix={(r["role"],r["permission"]):r["allowed"] for r in get_db().execute("SELECT role,permission,allowed FROM role_permissions").fetchall()}
    return render_template("permissions_admin.html",roles=roles,permissions=permissions,matrix=matrix)

@app.route("/admin/control-center")
def control_center():
    return redirect(url_for("settings_page"))

@app.route("/admin/media/upload", methods=["POST"])
def media_upload():
    db=get_db(); f=request.files.get("media_file")
    if not f or not f.filename: flash("اختر ملفًا", "error"); return redirect(url_for("media_admin"))
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    allowed_video={".mp4",".webm",".mov",".m4v"}; allowed_image={".jpg",".jpeg",".png",".webp"}
    if ext not in allowed_video|allowed_image: flash("صيغة الملف غير مدعومة", "error"); return redirect(url_for("media_admin"))
    mid=uid("med"); filename=mid+ext; f.save(os.path.join(UPLOAD_DIR,filename))
    mtype="video" if ext in allowed_video else "image"
    db.execute("INSERT INTO media(id,title,url,category,initiative_id,public,created_at,media_type,sort_order) VALUES(?,?,?,?,?,?,?,?,?)",(mid,request.form.get("title") or f.filename, "uploads/"+filename, request.form.get("category","عام"), request.form.get("initiative_id") or None, 1 if request.form.get("public") else 0, now_iso(),mtype,int(request.form.get("sort_order",0) or 0)))
    db.commit(); log_action("Uploaded media",request.form.get("title") or f.filename); flash("تم رفع الوسائط", "ok"); return redirect(url_for("media_admin"))


@app.route("/admin/asset/<kind>", methods=["POST"])
def upload_public_asset(kind):
    if not is_creator(): return render_template("403.html",permission="system"),403
    f=request.files.get("asset_file")
    allowed={"hero_background":{".jpg",".jpeg",".png",".webp"},"hero_video":{".mp4",".webm",".mov",".m4v"},"public_background":{".jpg",".jpeg",".png",".webp"}}
    if kind not in allowed or not f or not f.filename: flash("اختر ملفًا مناسبًا", "error"); return redirect(url_for("settings_page"))
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in allowed[kind]: flash("صيغة الملف غير مدعومة", "error"); return redirect(url_for("settings_page"))
    filename=f"{kind}-{uuid.uuid4().hex[:10]}{ext}"; f.save(os.path.join(UPLOAD_DIR,filename)); set_setting(kind,"uploads/"+filename); log_action("Uploaded public asset",kind); flash("تم رفع الملف وتفعيله", "ok"); return redirect(url_for("settings_page"))

# ============================================================ LIVE CONTROL ============================================================
@app.route("/admin/live", methods=["GET", "POST"])
def live_admin():
    if not has_permission("live"):
        return render_template("403.html", permission="live"), 403
    db=get_db()
    if request.method=="POST":
        action=request.form.get("action","start_internal")
        if action=="stop":
            sid=get_setting("liveSessionId","")
            if sid:
                db.execute("UPDATE live_sessions SET status='ended',ended_at=? WHERE id=?",(now_iso(),sid)); db.execute("DELETE FROM live_peers WHERE session_id=?",(sid,)); db.execute("DELETE FROM live_signals WHERE session_id=?",(sid,))
            set_setting("liveEnabled","0"); set_setting("liveSessionId",""); db.commit(); log_action("Stopped live broadcast",sid); flash("تم إيقاف البث", "ok"); return redirect(url_for("live_admin"))
        title=request.form.get("live_title","البث المباشر من الميدان").strip() or "البث المباشر من الميدان"
        desc=request.form.get("live_description","").strip(); initiative_id=request.form.get("initiative_id") or None; mode=request.form.get("mode","internal")
        if mode=="internal":
            sid=uid("live")
            db.execute("INSERT INTO live_sessions(id,title,description,initiative_id,mode,external_url,external_platform,status,created_by,started_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid,title,desc,initiative_id,"internal","","Internal","live",current_user()["id"],now_iso(),now_iso()))
            old_sid=get_setting("liveSessionId","")
            if old_sid: db.execute("UPDATE live_sessions SET status='ended',ended_at=? WHERE id=?",(now_iso(),old_sid))
            set_setting("liveEnabled","1"); set_setting("liveMode","internal"); set_setting("liveSessionId",sid); set_setting("liveTitle",title); set_setting("liveDescription",desc); set_setting("liveUrl",""); set_setting("livePlatform","Internal")
            db.commit(); log_action("Started internal live broadcast",title); flash("تم فتح غرفة البث داخل HIKMA IMPACT", "ok"); return redirect(url_for("live_room",sid=sid))
        ext=request.form.get("live_url","").strip(); platform=request.form.get("live_platform","YouTube")
        set_setting("liveEnabled","1"); set_setting("liveMode","external"); set_setting("liveSessionId",""); set_setting("liveTitle",title); set_setting("liveDescription",desc); set_setting("liveUrl",ext); set_setting("livePlatform",platform); log_action("Started external live broadcast",title); flash("تم تفعيل البث الخارجي", "ok"); return redirect(url_for("live_admin"))
    active=db.execute("SELECT ls.*,i.name initiative_name FROM live_sessions ls LEFT JOIN initiatives i ON i.id=ls.initiative_id WHERE ls.status='live' ORDER BY ls.started_at DESC LIMIT 1").fetchone()
    sessions=db.execute("SELECT ls.*,i.name initiative_name FROM live_sessions ls LEFT JOIN initiatives i ON i.id=ls.initiative_id ORDER BY ls.created_at DESC LIMIT 20").fetchall()
    return render_template("live_admin.html",active_session=active,sessions=sessions,initiatives=db.execute("SELECT id,name FROM initiatives ORDER BY date DESC").fetchall())

# ============================================================ SETTINGS ============================================================
@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    weights = get_weights()
    points_cfg = get_points_config()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "identity":
            set_setting("teamName", request.form.get("team_name", "HIKMA IMPACT"))
            set_setting("subtitle", request.form.get("subtitle", ""))
            flash("تم الحفظ بنجاح", "ok")
        elif form_type == "weights":
            new_w = {k: int(request.form.get(f"w_{k}", 0) or 0) for k in CRITERIA_KEYS}
            if sum(new_w.values()) != 100:
                flash("مجموع الأوزان يجب أن يساوي 100%", "error")
                return redirect(url_for("settings_page"))
            set_setting("weights", json.dumps(new_w))
            flash("تم حفظ الأوزان", "ok")
        elif form_type == "points":
            new_p = {k: int(request.form.get(f"p_{k}", 0) or 0) for k in DEFAULT_POINTS.keys()}
            set_setting("points", json.dumps(new_p))
            flash("تم حفظ القيم", "ok")
        elif form_type == "appearance":
            for key, field in [("accentColor","accent_color"),("navyColor","navy_color"),("backgroundColor","background_color"),("fontFamily","font_family"),("heroTitle","hero_title"),("heroText","hero_text"),("announcement","announcement"),("customCss","custom_css"),("heroBackground","hero_background"),("heroVideo","hero_video"),("publicBackground","public_background"),("seoTitle","seo_title"),("seoDescription","seo_description")]:
                set_setting(key, request.form.get(field, ""))
            set_setting("cinematicMode", "1" if request.form.get("cinematic_mode") else "0")
            flash("تم تحديث الهوية والمظهر", "ok")
        elif form_type == "public_controls":
            for key, field in [("joinButtonVisible","join_visible"),("joinButtonText","join_text"),("joinButtonIcon","join_icon"),("joinButtonPlacement","join_placement"),("joinButtonMode","join_mode"),("adminLinkVisible","admin_link_visible"),("telegramUrl","telegram_url"),("showPublicAdmins","show_admins"),("showPublicNews","show_news")]:
                set_setting(key, request.form.get(field, "0" if field in ("join_visible","admin_link_visible","show_admins","show_news") else ""))
            flash("تم تحديث زر الانضمام والتحكم العام", "ok")
        return redirect(url_for("settings_page"))
    return render_template("settings.html", weights=weights, points_cfg=points_cfg,
                           criteria_keys=CRITERIA_KEYS, criteria_labels=CRITERIA_LABELS,
                           points_labels={"attendance": "حضور", "task": "إنجاز مهمة", "leader": "قيادة مبادرة",
                                          "participation": "مشاركة فعالة", "excellent": "تقييم ممتاز"})


# ============================================================ REPORTS ============================================================
@app.route("/reports")
def reports_page():
    db = get_db()
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    initiatives = db.execute("SELECT * FROM initiatives ORDER BY date DESC").fetchall()
    return render_template("reports.html", members=members, initiatives=initiatives)


@app.route("/reports/member/<mid>")
def report_member(mid):
    db = get_db()
    m = db.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
    if not m:
        return redirect(url_for("reports_page"))
    s = member_score(db, mid)
    a = member_attendance_pct(db, mid)
    p = member_points_total(db, mid)
    volunteer_hours = member_volunteer_hours(db, mid)
    weights = get_weights()
    initiatives = db.execute("""SELECT i.* FROM initiatives i
        JOIN initiative_participants ip ON ip.initiative_id=i.id WHERE ip.member_id=?""", (mid,)).fetchall()
    return render_template("report_member.html", m=m, score=s, att=a, points=p, volunteer_hours=volunteer_hours, weights=weights,
        criteria_labels=CRITERIA_LABELS, initiatives=initiatives,
        recommendation=recommendation_text(s), today=date.today().isoformat())


@app.route("/reports/initiative/<iid>")
def report_initiative(iid):
    db = get_db()
    i = db.execute("SELECT * FROM initiatives WHERE id=?", (iid,)).fetchone()
    if not i:
        return redirect(url_for("reports_page"))
    participants = db.execute("""SELECT m.* FROM members m
        JOIN initiative_participants ip ON ip.member_id=m.id WHERE ip.initiative_id=?""", (iid,)).fetchall()
    return render_template("report_initiative.html", i=i, participants=participants, today=date.today().isoformat())


@app.route("/reports/monthly")
def report_monthly():
    db = get_db()
    today = date.today()
    initiatives = db.execute("SELECT * FROM initiatives").fetchall()
    ins = [i for i in initiatives if i["date"] and str(i["date"])[:7] == today.strftime("%Y-%m")]
    members_count = db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"]
    hours = sum((i["hours"] or 0) for i in ins)
    return render_template("report_period.html", title="التقرير الشهري للفريق", initiatives=ins,
        members_count=members_count, hours=hours, today=today.isoformat())


@app.route("/reports/annual")
def report_annual():
    db = get_db()
    year = date.today().year
    initiatives = db.execute("SELECT * FROM initiatives").fetchall()
    ins = [i for i in initiatives if i["date"] and str(i["date"])[:4] == str(year)]
    members_count = db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"]
    hours = sum((i["hours"] or 0) for i in ins)
    return render_template("report_period.html", title=f"التقرير السنوي للفريق — {year}", initiatives=ins,
        members_count=members_count, hours=hours, today=date.today().isoformat())


# ============================================================ BACKUP ============================================================
@app.route("/backup/export")
def backup_export():
    """Export a consistent JSON snapshot without changing live data."""
    db = get_db()
    tables = [
        "users", "members", "administrators", "committees", "initiatives",
        "initiative_participants", "tasks", "attendance", "evaluations", "points",
        "audit_logs", "news", "pages", "events", "partners", "media", "goals",
        "approvals", "security_sessions", "site_sections", "nav_items", "role_permissions",
        "notifications", "applications", "live_sessions", "live_peers", "live_signals",
        "certificates"
    ]
    data = {"version": 11, "created_at": now_iso(), "tables": {}}
    with db:
        for t in tables:
            rows = db.execute(f"SELECT * FROM {t}").fetchall()
            data["tables"][t] = [dict(r) for r in rows]
        data["tables"]["settings"] = [dict(r) for r in db.execute("SELECT * FROM settings").fetchall()]
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    buf = io.BytesIO(payload)
    buf.seek(0)
    fname = f"Hikma-Impact-Backup-{date.today().isoformat()}.json"
    return send_file(buf, mimetype="application/json", as_attachment=True, download_name=fname)


@app.route("/backup/import", methods=["POST"])
def backup_import():
    file = request.files.get("backup_file")
    if not file or not file.filename.lower().endswith(".json"):
        flash("الملف غير صالح — اختر نسخة HIKMA IMPACT بصيغة JSON", "error")
        return redirect(url_for("reports_page"))

    try:
        data = json.load(file.stream)
        tables_data = data.get("tables", data)
        if not isinstance(tables_data, dict):
            raise ValueError("invalid backup structure")

        db = get_db()
        table_order = [
            "live_signals", "live_peers", "initiative_participants", "attendance",
            "evaluations", "points", "notifications", "security_sessions", "audit_logs",
            "approvals", "tasks", "media", "events", "goals", "certificates", "applications",
            "news", "pages", "site_sections", "nav_items", "role_permissions", "partners",
            "initiatives", "committees", "administrators", "members", "users", "settings"
        ]

        # Never delete data until the backup has been parsed and validated.
        # The whole restore is one transaction: any failure rolls everything back.
        db.execute("BEGIN IMMEDIATE")
        try:
            for table in table_order:
                if table not in tables_data:
                    continue
                db.execute(f"DELETE FROM {table}")

            restored = 0
            for table in table_order:
                rows = tables_data.get(table)
                if rows is None:
                    continue
                if table == "settings":
                    for row in rows:
                        if not isinstance(row, dict) or "key" not in row:
                            raise ValueError("invalid settings row")
                        db.execute("INSERT INTO settings(key,value) VALUES(?,?)", (row.get("key"), row.get("value")))
                        restored += 1
                    continue

                if not isinstance(rows, list):
                    raise ValueError(f"invalid table: {table}")

                # Restore only columns that actually exist in the current DB.
                # This makes V11 compatible with older backups and preserves
                # defaults/migrations for columns introduced later.
                cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
                for row in rows:
                    if not isinstance(row, dict):
                        raise ValueError(f"invalid row in {table}")
                    keys = [k for k in row.keys() if k in cols]
                    if not keys:
                        continue
                    placeholders = ",".join("?" for _ in keys)
                    db.execute(
                        f"INSERT INTO {table}({','.join(keys)}) VALUES({placeholders})",
                        [row.get(k) for k in keys]
                    )
                    restored += 1

            db.commit()
        except Exception:
            db.rollback()
            raise

        flash(f"تم استيراد النسخة الاحتياطية بنجاح ({restored} سجل)", "ok")
    except Exception as exc:
        app.logger.exception("Backup import failed: %s", exc)
        flash("فشل استيراد النسخة الاحتياطية. لم يتم حذف أو تغيير بياناتك.", "error")
    return redirect(url_for("public_home"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
else:
    init_db()

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
from datetime import datetime, date

from flask import (
    Flask, request, redirect, url_for, render_template, session,
    g, flash, jsonify, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hikma.db")

app = Flask(__name__)
app.secret_key = os.environ.get("HIKMA_SECRET_KEY", "hikma-impact-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
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
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, password_hash TEXT,
        role TEXT, created_at TEXT);
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
        initiative_id TEXT, member_id TEXT,
        PRIMARY KEY(initiative_id, member_id));
    CREATE TABLE IF NOT EXISTS tasks(
        id TEXT PRIMARY KEY, title TEXT, assignee TEXT, deadline TEXT,
        priority TEXT, status TEXT, description TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS attendance(
        id TEXT PRIMARY KEY, member_id TEXT, date TEXT, status TEXT, initiative_id TEXT);
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
    """)
    db.commit()
    if db.execute("SELECT COUNT(*) c FROM settings").fetchone()["c"] == 0:
        db.execute("INSERT INTO settings(key,value) VALUES('teamName',?)", ("HIKMA IMPACT",))
        db.execute("INSERT INTO settings(key,value) VALUES('subtitle',?)",
                   ("فريق الحكمة الطلابي — نظام إدارة الأداء والأثر التطوعي",))
        db.execute("INSERT INTO settings(key,value) VALUES('weights',?)", (json.dumps(DEFAULT_WEIGHTS),))
        db.execute("INSERT INTO settings(key,value) VALUES('points',?)", (json.dumps(DEFAULT_POINTS),))
        # Lightweight migrations for existing deployments.
    def ensure_column(table, column, definition):
        cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    ensure_column("members", "photo", "TEXT")
    # Backfill newer appearance/public settings without destroying existing configuration.
    defaults = {
        "accentColor": "#20B486", "navyColor": "#071A2F", "backgroundColor": "#F5F7FA",
        "fontFamily": "Tajawal", "heroTitle": "أثرٌ يُقاس، وقيادةٌ تُصنع",
        "heroText": "منصة HIKMA IMPACT لإدارة الأثر، المبادرات، والأداء التطوعي.",
        "announcement": "", "customCss": "", "siteMode": "public",
    }
    for k,v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))
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

ADMIN_GET_ENDPOINTS = {
    "settings_page", "audit_log", "backup_export",
    "admin_new", "admin_edit", "admin_delete", "admin_users", "admin_user_role",
    "admin_login", "admin_dashboard", "news_admin", "news_new", "news_edit",
    "news_delete", "page_admin", "page_new", "page_edit", "page_delete",
}
PUBLIC_ENDPOINTS = {"public_home", "public_news", "public_news_detail", "public_page",
                    "login", "admin_login", "logout", "static", "signup"}

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

@app.context_processor
def inject_globals():
    return {
        "session_user": current_user(),
        "is_admin": is_admin(),
        "is_creator": is_creator(),
        "team_name": get_setting("teamName", "HIKMA IMPACT"),
        "subtitle": get_setting("subtitle", "فريق الحكمة الطلابي"),
        "site_settings": {k: get_setting(k, "") for k in ["accentColor","navyColor","backgroundColor","fontFamily","heroTitle","heroText","announcement","customCss"]},
        "current_endpoint": request.endpoint,
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
        user = get_db().execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
        if not user or user["role"] not in ("CREATOR", "SUPER_ADMIN", "ADMIN") or not check_password_hash(user["password_hash"], password):
            flash("بيانات الإدارة غير صحيحة", "error")
            return redirect(url_for("admin_login"))
        session["user_id"] = user["id"]
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
    stats={
        "members": db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"],
        "news": db.execute("SELECT COUNT(*) c FROM news WHERE status='published'").fetchone()["c"],
        "initiatives": db.execute("SELECT COUNT(*) c FROM initiatives").fetchone()["c"],
        "evaluations": db.execute("SELECT COUNT(*) c FROM evaluations").fetchone()["c"],
    }
    recent=db.execute("SELECT * FROM audit_logs ORDER BY date DESC LIMIT 8").fetchall()
    return render_template("admin_dashboard.html", stats=stats, recent=recent)

@app.route("/admin/users")
def admin_users():
    users=get_db().execute("SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC").fetchall()
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

@app.route("/news")
def public_news():
    rows=get_db().execute("SELECT * FROM news WHERE status='published' ORDER BY published_at DESC, created_at DESC").fetchall()
    return render_template("news.html", news=rows)

@app.route("/news/<slug>")
def public_news_detail(slug):
    n=get_db().execute("SELECT * FROM news WHERE slug=? AND status='published'", (slug,)).fetchone()
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
        db.execute("INSERT INTO news(id,title,slug,excerpt,content,cover_image,category,author,status,published_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (uid("news"),title,slug,request.form.get("excerpt",""),request.form.get("content",""),request.form.get("cover_image",""),request.form.get("category","عام"),author,status,now_iso() if status=="published" else None,now_iso()))
        db.commit(); log_action("Created news",title); flash("تم حفظ الخبر", "ok"); return redirect(url_for("news_admin"))
    return render_template("news_form.html", n=None)

@app.route("/admin/news/<nid>/edit", methods=["GET","POST"])
def news_edit(nid):
    db=get_db(); n=db.execute("SELECT * FROM news WHERE id=?",(nid,)).fetchone()
    if not n: return redirect(url_for("news_admin"))
    if request.method=="POST":
        status=request.form.get("status","draft")
        db.execute("UPDATE news SET title=?,slug=?,excerpt=?,content=?,cover_image=?,category=?,status=?,published_at=? WHERE id=?",
                   (request.form.get("title",""),request.form.get("slug",""),request.form.get("excerpt",""),request.form.get("content",""),request.form.get("cover_image",""),request.form.get("category","عام"),status,now_iso() if status=="published" else None,nid))
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
    return render_template("public_home.html",
        members_count=len(members), admins_count=len(admins), initiatives_count=len(initiatives),
        total_hours=total_hours, avg_score=avg_score, avg_att=avg_att, latest_news=latest_news,
        months=months, counts=counts, max_count=max_count, top_members=top_members)


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

    return render_template("member_view.html", m=m, score=s, att=a, points=p,
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
        data = (name, request.form.get("date", ""), request.form.get("location", ""),
                request.form.get("manager", ""), request.form.get("committee", ""),
                float(request.form.get("hours") or 0), request.form.get("status", "Planned"),
                request.form.get("description", ""), request.form.get("goals", ""))
        if iid:
            db.execute("""UPDATE initiatives SET name=?,date=?,location=?,manager=?,committee=?,
                           hours=?,status=?,description=?,goals=? WHERE id=?""", data + (iid,))
            log_action("Updated", f"مبادرة: {name}")
        else:
            db.execute("""INSERT INTO initiatives(id,name,date,location,manager,committee,hours,status,description,goals)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""", (uid("ini"),) + data)
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
    participant_ids = [r["member_id"] for r in db.execute(
        "SELECT member_id FROM initiative_participants WHERE initiative_id=?", (iid,)).fetchall()]
    participants = []
    for pid in participant_ids:
        m = db.execute("SELECT * FROM members WHERE id=?", (pid,)).fetchone()
        if m:
            participants.append(m)
    return render_template("initiative_view.html", i=i, participants=participants)


@app.route("/initiatives/<iid>/participants", methods=["GET", "POST"])
def initiative_participants(iid):
    db = get_db()
    i = db.execute("SELECT * FROM initiatives WHERE id=?", (iid,)).fetchone()
    if not i:
        return redirect(url_for("initiatives_list"))
    if request.method == "POST":
        selected = request.form.getlist("participant")
        db.execute("DELETE FROM initiative_participants WHERE initiative_id=?", (iid,))
        for mid in selected:
            db.execute("INSERT INTO initiative_participants(initiative_id, member_id) VALUES(?,?)", (iid, mid))
        db.commit()
        flash("تم تحديث المشاركين", "ok")
        return redirect(url_for("initiative_view", iid=iid))
    members = db.execute("SELECT * FROM members ORDER BY name").fetchall()
    selected_ids = {r["member_id"] for r in db.execute(
        "SELECT member_id FROM initiative_participants WHERE initiative_id=?", (iid,)).fetchall()}
    return render_template("initiative_participants.html", i=i, members=members, selected_ids=selected_ids)


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
        att_date = request.form.get("date", date.today().isoformat())
        initiative_id = request.form.get("initiative_id") or None
        db.execute("INSERT INTO attendance(id,member_id,date,status,initiative_id) VALUES(?,?,?,?,?)",
                   (uid("att"), member_id, att_date, status, initiative_id))
        db.commit()
        if status == "Present":
            pts_cfg = get_points_config()
            add_points(member_id, pts_cfg.get("attendance", 10), f"حضور بتاريخ {att_date}")
        log_action("Created", "حضور مسجل")
        flash("تم تسجيل الحضور", "ok")
        return redirect(url_for("attendance_list"))
    return render_template("attendance_form.html", members=members, initiatives=initiatives, today=date.today().isoformat())


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
            for key, field in [("accentColor","accent_color"),("navyColor","navy_color"),("backgroundColor","background_color"),("fontFamily","font_family"),("heroTitle","hero_title"),("heroText","hero_text"),("announcement","announcement"),("customCss","custom_css")]:
                set_setting(key, request.form.get(field, ""))
            flash("تم تحديث الهوية والمظهر", "ok")
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
    weights = get_weights()
    initiatives = db.execute("""SELECT i.* FROM initiatives i
        JOIN initiative_participants ip ON ip.initiative_id=i.id WHERE ip.member_id=?""", (mid,)).fetchall()
    return render_template("report_member.html", m=m, score=s, att=a, points=p, weights=weights,
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
    db = get_db()
    tables = ["users", "members", "administrators", "committees", "initiatives",
              "initiative_participants", "tasks", "attendance", "evaluations", "points", "audit_logs", "news", "pages"]
    data = {}
    for t in tables:
        rows = db.execute(f"SELECT * FROM {t}").fetchall()
        data[t] = [dict(r) for r in rows]
    data["settings"] = {r["key"]: r["value"] for r in db.execute("SELECT * FROM settings").fetchall()}
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    buf.seek(0)
    fname = f"Hikma-Impact-Backup-{date.today().isoformat()}.json"
    return send_file(buf, mimetype="application/json", as_attachment=True, download_name=fname)


@app.route("/backup/import", methods=["POST"])
def backup_import():
    file = request.files.get("backup_file")
    if not file:
        flash("الملف غير صالح", "error")
        return redirect(url_for("reports_page"))
    try:
        data = json.load(file.stream)
        db = get_db()
        table_cols = {
            "users": ["id", "name", "email", "password_hash", "role", "created_at"],
            "members": ["id", "name", "email", "phone", "committee", "position", "join_date", "status", "notes", "created_at", "photo"],
            "administrators": ["id", "name", "position", "committee", "date", "responsibilities"],
            "committees": ["id", "name", "head", "description"],
            "initiatives": ["id", "name", "date", "location", "manager", "committee", "hours", "status", "description", "goals"],
            "initiative_participants": ["initiative_id", "member_id"],
            "tasks": ["id", "title", "assignee", "deadline", "priority", "status", "description", "created_at"],
            "attendance": ["id", "member_id", "date", "status", "initiative_id"],
            "evaluations": ["id", "evaluated_user_id", "evaluator_id", "evaluator_name", "date", "type", "notes",
                             "c_attendance", "c_taskCompletion", "c_initiativeParticipation", "c_commitment",
                             "c_teamwork", "c_creativity"],
            "points": ["id", "member_id", "value", "source", "date"],
            "audit_logs": ["id", "action", "target", "by", "date"],
            "news": ["id", "title", "slug", "excerpt", "content", "cover_image", "category", "author", "status", "published_at", "created_at"],
            "pages": ["id", "title", "slug", "content", "status", "show_in_nav", "sort_order", "created_at", "updated_at"],
        }
        for t, cols in table_cols.items():
            if t not in data:
                continue
            db.execute(f"DELETE FROM {t}")
            for row in data[t]:
                placeholders = ",".join(["?"] * len(cols))
                db.execute(f"INSERT INTO {t}({','.join(cols)}) VALUES({placeholders})",
                           [row.get(c) for c in cols])
        if "settings" in data:
            db.execute("DELETE FROM settings")
            for k, v in data["settings"].items():
                db.execute("INSERT INTO settings(key,value) VALUES(?,?)", (k, v))
        db.commit()
        flash("تم استيراد النسخة الاحتياطية", "ok")
    except Exception:
        flash("الملف غير صالح", "error")
    return redirect(url_for("public_home"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
else:
    init_db()

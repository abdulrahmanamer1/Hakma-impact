# -*- coding: utf-8 -*-
import os, sqlite3, uuid, json
from datetime import datetime, date
from flask import Flask, request, redirect, url_for, render_template, session, g, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hikma.db")
UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
app = Flask(__name__)
app.secret_key = os.environ.get("HIKMA_SECRET_KEY", "change-this-secret-in-production")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

for folder in ["news", "members", "administrators", "initiatives"]:
    os.makedirs(os.path.join(UPLOAD_ROOT, folder), exist_ok=True)

OWNER_EMAIL = os.environ.get("HIKMA_OWNER_EMAIL", "Abdulrahman.a.alani1@gmail.com").lower()
OWNER_PASSWORD = os.environ.get("HIKMA_OWNER_PASSWORD", "ABAMAL0027")

CRITERIA = [
    ("attendance", "الحضور", 20), ("taskCompletion", "تنفيذ المهام", 25),
    ("initiativeParticipation", "المشاركة بالمبادرات", 20), ("commitment", "الالتزام", 15),
    ("teamwork", "العمل الجماعي", 10), ("creativity", "الإبداع", 10)
]

def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def now():
    return datetime.utcnow().isoformat(timespec="seconds")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS members(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT, phone TEXT, committee TEXT,
      position TEXT, join_date TEXT, status TEXT, notes TEXT, photo TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS administrators(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, position TEXT, committee TEXT,
      date TEXT, responsibilities TEXT, photo TEXT
    );
    CREATE TABLE IF NOT EXISTS committees(
      id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, head TEXT, description TEXT
    );
    CREATE TABLE IF NOT EXISTS initiatives(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, date TEXT, location TEXT, manager TEXT,
      committee TEXT, hours REAL DEFAULT 0, status TEXT, description TEXT, goals TEXT,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS initiative_images(
      id TEXT PRIMARY KEY, initiative_id TEXT, path TEXT
    );
    CREATE TABLE IF NOT EXISTS initiative_participants(
      initiative_id TEXT, member_id TEXT, PRIMARY KEY(initiative_id, member_id)
    );
    CREATE TABLE IF NOT EXISTS news(
      id TEXT PRIMARY KEY, title TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
      excerpt TEXT, content TEXT, category TEXT, author TEXT, status TEXT,
      published_at TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS news_images(
      id TEXT PRIMARY KEY, news_id TEXT, path TEXT
    );
    CREATE TABLE IF NOT EXISTS evaluations(
      id TEXT PRIMARY KEY, evaluated_user_id TEXT, evaluator_id TEXT, evaluator_name TEXT,
      date TEXT, type TEXT, notes TEXT,
      c_attendance INTEGER, c_taskCompletion INTEGER, c_initiativeParticipation INTEGER,
      c_commitment INTEGER, c_teamwork INTEGER, c_creativity INTEGER
    );
    CREATE TABLE IF NOT EXISTS attendance(
      id TEXT PRIMARY KEY, member_id TEXT, date TEXT, status TEXT, initiative_id TEXT
    );
    CREATE TABLE IF NOT EXISTS tasks(
      id TEXT PRIMARY KEY, title TEXT, assignee TEXT, deadline TEXT, priority TEXT,
      status TEXT, description TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS points(
      id TEXT PRIMARY KEY, member_id TEXT, value REAL, source TEXT, date TEXT
    );
    CREATE TABLE IF NOT EXISTS pages(
      id TEXT PRIMARY KEY, title TEXT, slug TEXT UNIQUE, content TEXT, status TEXT,
      show_in_nav INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS audit_logs(
      id TEXT PRIMARY KEY, action TEXT, target TEXT, by_name TEXT, date TEXT
    );
    """)
    defaults = {
        "teamName":"HIKMA IMPACT",
        "subtitle":"فريق الحكمة الطلابي — نظام إدارة الأداء والأثر التطوعي",
        "heroTitle":"أثرٌ يُقاس، وقيادةٌ تُصنع",
        "heroText":"منصة HIKMA IMPACT لإدارة الأثر، المبادرات، والأداء التطوعي.",
        "accent":"#20B486", "navy":"#071A2F", "background":"#F5F7FA"
    }
    for k,v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
    # Create the owner account automatically on first deployment.
    owner = db.execute("SELECT id FROM users WHERE lower(email)=?",(OWNER_EMAIL,)).fetchone()
    if not owner:
        db.execute("INSERT INTO users VALUES(?,?,?,?,?,?)",
                   (uid("usr"), "Abdulrahman Alani", OWNER_EMAIL,
                    generate_password_hash(OWNER_PASSWORD), "CREATOR", now()))
    db.commit(); db.close()

def setting(key, default=""):
    r=get_db().execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
    return r["value"] if r else default

def current_user():
    uid_=session.get("user_id")
    return get_db().execute("SELECT * FROM users WHERE id=?",(uid_,)).fetchone() if uid_ else None

def admin_required():
    u=current_user()
    return bool(u and u["role"] in ("CREATOR","ADMIN","SUPER_ADMIN"))

def creator_required():
    u=current_user()
    return bool(u and u["role"]=="CREATOR")

def log(action,target=""):
    u=current_user()
    get_db().execute("INSERT INTO audit_logs VALUES(?,?,?,?,?)",
                     (uid("log"),action,target,u["name"] if u else "system",now()))
    get_db().commit()

@app.context_processor
def globals():
    return {
        "user": current_user(), "is_admin": admin_required(), "is_creator": creator_required(),
        "team_name": setting("teamName","HIKMA IMPACT"),
        "subtitle": setting("subtitle",""),
        "site": {k:setting(k) for k in ["heroTitle","heroText","accent","navy","background"]},
        "year": date.today().year
    }

@app.before_request
def protect():
    public = {"public_home","public_news","public_news_detail","public_page","login","admin_login","logout","static"}
    ep=request.endpoint or ""
    if ep in public: return
    if request.method in ("POST","PUT","PATCH","DELETE") and not admin_required():
        flash("هذه العملية متاحة للإدارة فقط.","error")
        return redirect(url_for("admin_login"))
    if ep.startswith("admin_") and not admin_required():
        return redirect(url_for("admin_login"))

def save_images(files, folder):
    paths=[]
    allowed={".jpg",".jpeg",".png",".webp",".gif"}
    for f in files:
        if not f or not f.filename: continue
        ext=os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in allowed: continue
        name=f"{uuid.uuid4().hex}{ext}"
        f.save(os.path.join(UPLOAD_ROOT,folder,name))
        paths.append(f"uploads/{folder}/{name}")
    return paths

@app.route("/")
def public_home():
    db=get_db()
    members=db.execute("SELECT * FROM members WHERE status!='Inactive' ORDER BY created_at DESC").fetchall()
    admins=db.execute("SELECT * FROM administrators ORDER BY name").fetchall()
    initiatives=db.execute("SELECT * FROM initiatives ORDER BY date DESC").fetchall()
    news=db.execute("SELECT * FROM news WHERE status='published' ORDER BY published_at DESC,created_at DESC LIMIT 6").fetchall()
    news_data=[]
    for n in news:
        imgs=db.execute("SELECT path FROM news_images WHERE news_id=? ORDER BY id",(n["id"],)).fetchall()
        news_data.append((n,imgs))
    return render_template("home.html",members=members,admins=admins,initiatives=initiatives,news=news_data)

@app.route("/login",methods=["GET","POST"])
def login(): return redirect(url_for("admin_login"))

@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        u=get_db().execute("SELECT * FROM users WHERE lower(email)=?",(email,)).fetchone()
        if not u or not check_password_hash(u["password_hash"],password):
            flash("البريد أو الرمز غير صحيح.","error"); return redirect(url_for("admin_login"))
        session["user_id"]=u["id"]; return redirect(url_for("admin_dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("public_home"))

@app.route("/admin")
def admin_dashboard():
    db=get_db()
    stats=[
      ("الأعضاء",db.execute("SELECT COUNT(*) c FROM members").fetchone()["c"],"members_list"),
      ("الإداريون",db.execute("SELECT COUNT(*) c FROM administrators").fetchone()["c"],"admins_list"),
      ("اللجان",db.execute("SELECT COUNT(*) c FROM committees").fetchone()["c"],"committees_list"),
      ("المبادرات",db.execute("SELECT COUNT(*) c FROM initiatives").fetchone()["c"],"initiatives_list"),
      ("الأخبار",db.execute("SELECT COUNT(*) c FROM news").fetchone()["c"],"news_admin"),
      ("المستخدمون",db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],"admin_users"),
    ]
    logs=db.execute("SELECT * FROM audit_logs ORDER BY date DESC LIMIT 10").fetchall()
    return render_template("admin_dashboard.html",stats=stats,logs=logs)

@app.route("/admin/users")
def admin_users():
    users=get_db().execute("SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC").fetchall()
    return render_template("admin_users.html",users=users)

@app.route("/admin/users/new",methods=["GET","POST"])
def admin_user_new():
    if not creator_required(): flash("هذه الصفحة لصانع التطبيق فقط.","error"); return redirect(url_for("admin_dashboard"))
    if request.method=="POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        role=request.form.get("role","ADMIN")
        if not name or not email or len(password)<6:
            flash("أكمل البيانات، والرمز يجب أن يكون 6 أحرف على الأقل.","error")
            return redirect(request.url)
        try:
            db=get_db(); db.execute("INSERT INTO users VALUES(?,?,?,?,?,?)",
                (uid("usr"),name,email,generate_password_hash(password),role,now())); db.commit()
            log("Created admin account",email); flash("تم إنشاء الحساب.","ok")
            return redirect(url_for("admin_users"))
        except sqlite3.IntegrityError:
            flash("هذا البريد مستخدم مسبقاً.","error")
    return render_template("user_form.html")

@app.route("/admin/users/<uid_>/delete",methods=["POST"])
def admin_user_delete(uid_):
    if not creator_required(): return redirect(url_for("admin_dashboard"))
    u=get_db().execute("SELECT * FROM users WHERE id=?",(uid_,)).fetchone()
    if u and u["email"].lower()!=OWNER_EMAIL:
        get_db().execute("DELETE FROM users WHERE id=?",(uid_,)); get_db().commit()
    return redirect(url_for("admin_users"))

@app.route("/admin/settings",methods=["GET","POST"])
def admin_settings():
    if request.method=="POST":
        for k in ["teamName","subtitle","heroTitle","heroText","accent","navy","background"]:
            if k in request.form:
                get_db().execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,request.form[k]))
        get_db().commit(); flash("تم تحديث الهوية.","ok")
    return render_template("settings.html")

# ---------- news ----------
@app.route("/news")
def public_news():
    db=get_db(); rows=db.execute("SELECT * FROM news WHERE status='published' ORDER BY published_at DESC,created_at DESC").fetchall()
    data=[(n,db.execute("SELECT path FROM news_images WHERE news_id=? ORDER BY id",(n["id"],)).fetchall()) for n in rows]
    return render_template("news.html",data=data)

@app.route("/news/<slug>")
def public_news_detail(slug):
    db=get_db(); n=db.execute("SELECT * FROM news WHERE slug=? AND status='published'",(slug,)).fetchone()
    if not n: return redirect(url_for("public_news"))
    imgs=db.execute("SELECT path FROM news_images WHERE news_id=? ORDER BY id",(n["id"],)).fetchall()
    return render_template("news_detail.html",n=n,images=imgs)

@app.route("/admin/news")
def news_admin():
    rows=get_db().execute("SELECT * FROM news ORDER BY created_at DESC").fetchall()
    return render_template("news_admin.html",rows=rows)

@app.route("/admin/news/new",methods=["GET","POST"])
def news_new():
    if request.method=="POST":
        db=get_db(); title=request.form.get("title","").strip()
        slug=secure_filename(request.form.get("slug","").strip().lower()) or uuid.uuid4().hex[:10]
        status=request.form.get("status","draft")
        db.execute("INSERT INTO news VALUES(?,?,?,?,?,?,?,?,?,?)",
          (uid("news"),title,slug,request.form.get("excerpt",""),request.form.get("content",""),
           request.form.get("category","عام"),current_user()["name"],status,now() if status=="published" else None,now()))
        nid=db.execute("SELECT id FROM news WHERE slug=?",(slug,)).fetchone()["id"]
        for p in save_images(request.files.getlist("images"),"news"):
            db.execute("INSERT INTO news_images VALUES(?,?,?)",(uid("img"),nid,p))
        db.commit(); log("Created news",title); return redirect(url_for("news_admin"))
    return render_template("news_form.html",n=None)

@app.route("/admin/news/<nid>/delete",methods=["POST"])
def news_delete(nid):
    db=get_db(); imgs=db.execute("SELECT path FROM news_images WHERE news_id=?",(nid,)).fetchall()
    for x in imgs:
        try: os.remove(os.path.join(BASE_DIR,"static",x["path"]))
        except OSError: pass
    db.execute("DELETE FROM news_images WHERE news_id=?",(nid,)); db.execute("DELETE FROM news WHERE id=?",(nid,)); db.commit()
    return redirect(url_for("news_admin"))

# ---------- members ----------
@app.route("/members")
def members_list():
    db=get_db(); members=db.execute("SELECT * FROM members ORDER BY created_at DESC").fetchall()
    return render_template("members.html",members=members)

@app.route("/members/new",methods=["GET","POST"])
def member_new():
    if request.method=="POST":
        db=get_db(); mid=uid("mem")
        photo=save_images(request.files.getlist("photo"),"members")
        db.execute("INSERT INTO members VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (mid,request.form.get("name",""),request.form.get("email",""),request.form.get("phone",""),
           request.form.get("committee",""),request.form.get("position","عضو"),request.form.get("join_date",""),
           request.form.get("status","Active"),request.form.get("notes",""),photo[0] if photo else "",now()))
        db.commit(); return redirect(url_for("members_list"))
    return render_template("member_form.html")

@app.route("/members/<mid>/delete",methods=["POST"])
def member_delete(mid):
    get_db().execute("DELETE FROM members WHERE id=?",(mid,)); get_db().commit(); return redirect(url_for("members_list"))

# ---------- administrators ----------
@app.route("/administrators")
def admins_list():
    admins=get_db().execute("SELECT * FROM administrators ORDER BY name").fetchall()
    return render_template("administrators.html",admins=admins)

@app.route("/administrators/new",methods=["GET","POST"])
def admin_new():
    if request.method=="POST":
        db=get_db(); aid=uid("adm"); photo=save_images(request.files.getlist("photo"),"administrators")
        db.execute("INSERT INTO administrators VALUES(?,?,?,?,?,?,?)",
          (aid,request.form.get("name",""),request.form.get("position",""),request.form.get("committee",""),
           request.form.get("date",""),request.form.get("responsibilities",""),photo[0] if photo else ""))
        db.commit(); return redirect(url_for("admins_list"))
    return render_template("admin_form.html")

@app.route("/administrators/<aid>/delete",methods=["POST"])
def admin_delete(aid):
    get_db().execute("DELETE FROM administrators WHERE id=?",(aid,)); get_db().commit(); return redirect(url_for("admins_list"))

# ---------- committees ----------
@app.route("/committees")
def committees_list():
    rows=get_db().execute("SELECT * FROM committees ORDER BY name").fetchall()
    return render_template("committees.html",rows=rows)

@app.route("/committees/new",methods=["GET","POST"])
def committee_new():
    if request.method=="POST":
        db=get_db(); db.execute("INSERT INTO committees VALUES(?,?,?,?)",
          (uid("com"),request.form.get("name",""),request.form.get("head",""),request.form.get("description",""))); db.commit()
        return redirect(url_for("committees_list"))
    return render_template("committee_form.html")

@app.route("/committees/<cid>/delete",methods=["POST"])
def committee_delete(cid):
    get_db().execute("DELETE FROM committees WHERE id=?",(cid,)); get_db().commit(); return redirect(url_for("committees_list"))

# ---------- initiatives ----------
@app.route("/initiatives")
def initiatives_list():
    db=get_db(); rows=db.execute("SELECT * FROM initiatives ORDER BY date DESC,created_at DESC").fetchall()
    data=[]
    for i in rows:
        imgs=db.execute("SELECT path FROM initiative_images WHERE initiative_id=? ORDER BY id",(i["id"],)).fetchall()
        data.append((i,imgs))
    return render_template("initiatives.html",data=data)

@app.route("/initiatives/new",methods=["GET","POST"])
def initiative_new():
    if request.method=="POST":
        db=get_db(); iid=uid("ini")
        db.execute("INSERT INTO initiatives VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (iid,request.form.get("name",""),request.form.get("date",""),request.form.get("location",""),
           request.form.get("manager",""),request.form.get("committee",""),float(request.form.get("hours") or 0),
           request.form.get("status","Planned"),request.form.get("description",""),request.form.get("goals",""),now()))
        for p in save_images(request.files.getlist("images"),"initiatives"):
            db.execute("INSERT INTO initiative_images VALUES(?,?,?)",(uid("img"),iid,p))
        db.commit(); return redirect(url_for("initiatives_list"))
    return render_template("initiative_form.html")

@app.route("/initiatives/<iid>/delete",methods=["POST"])
def initiative_delete(iid):
    db=get_db(); db.execute("DELETE FROM initiative_images WHERE initiative_id=?",(iid,)); db.execute("DELETE FROM initiatives WHERE id=?",(iid,)); db.commit()
    return redirect(url_for("initiatives_list"))

# ---------- simple placeholders for existing navigation ----------
@app.route("/evaluations")
def evaluations(): return render_template("simple_page.html",title="التقييمات",text="إدارة تقييمات الأعضاء وتحديث درجات الأداء.")
@app.route("/achievements")
def achievements(): return render_template("simple_page.html",title="الإنجازات",text="سجل الإنجازات والنقاط ومستويات الأعضاء.")
@app.route("/attendance")
def attendance(): return render_template("simple_page.html",title="الحضور",text="إدارة الحضور والغياب للمبادرات والفعاليات.")
@app.route("/reports")
def reports(): return render_template("simple_page.html",title="التقارير",text="تقارير الأداء والأثر للفريق.")
@app.route("/tasks")
def tasks(): return render_template("simple_page.html",title="المهام",text="إدارة المهام والمتابعة.")
@app.route("/pages")
def pages(): return render_template("simple_page.html",title="الصفحات",text="إدارة صفحات الموقع.")

@app.route("/admin/seed-admins")
def seed_admins():
    # Optional one-time helper: creates the five requested administrators with generated temporary passwords.
    if not creator_required(): return redirect(url_for("admin_login"))
    names=["بان حسين","محمد صادق جاسم","رامي راسم","علي احمد","منتظر حيدر"]
    db=get_db(); created=[]
    for name in names:
        email=secure_filename(name).replace("-","").replace("_","").lower()+"@hikma.local"
        if db.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone(): continue
        pwd=secrets.token_urlsafe(8)
        db.execute("INSERT INTO users VALUES(?,?,?,?,?,?)",(uid("usr"),name,email,generate_password_hash(pwd),"ADMIN",now()))
        created.append((name,email,pwd))
    db.commit()
    return render_template("seed_admins.html",created=created)

@app.route("/page/<slug>")
def public_page(slug):
    p=get_db().execute("SELECT * FROM pages WHERE slug=? AND status='published'",(slug,)).fetchone()
    if not p: return "<h2>الصفحة غير موجودة</h2>",404
    return render_template("page.html",page=p)

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
else:
    init_db()

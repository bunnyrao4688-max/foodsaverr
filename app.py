"""FoodSaver - Food Waste Reduction Platform (Flask + SQLite)"""
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DATABASE = "foodsaver.db"


# ---------- Database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS donations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER NOT NULL,
        food_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        location TEXT NOT NULL,
        expiry_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'available',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(donor_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donation_id INTEGER NOT NULL,
        requester_id INTEGER NOT NULL,
        message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(donation_id) REFERENCES donations(id),
        FOREIGN KEY(requester_id) REFERENCES users(id));
    """)
    # default admin account
    if not db.execute("SELECT 1 FROM users WHERE email='admin@foodsaver.com'").fetchone():
        db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                   ("Admin", "admin@foodsaver.com", generate_password_hash("admin123"), "admin"))
    db.commit()
    db.close()


# ---------- Auth decorators ----------
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            flash("Admins only.", "error")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return wrapper


def get_stats():
    db = get_db()
    return {
        "donations": db.execute("SELECT COUNT(*) FROM donations").fetchone()[0],
        "food_saved": db.execute("SELECT COALESCE(SUM(quantity),0) FROM donations WHERE status='claimed'").fetchone()[0],
        "available": db.execute("SELECT COUNT(*) FROM donations WHERE status='available'").fetchone()[0],
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
    }


# ---------- Pages ----------
@app.route("/")
def index():
    return render_template("index.html", stats=get_stats())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not name or not email or len(password) < 6:
            flash("Fill all fields. Password must be at least 6 characters.", "error")
            return redirect(url_for("register"))
        try:
            get_db().execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                             (name, email, generate_password_hash(password)))
            get_db().commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form["password"]):
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("admin" if user["role"] == "admin" else "dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/donate", methods=["GET", "POST"])
@login_required
def donate():
    if request.method == "POST":
        food = request.form["food_name"].strip()
        qty = request.form.get("quantity", type=int)
        loc = request.form["location"].strip()
        expiry = request.form["expiry_time"]
        if not food or not loc or not qty or qty < 1 or not expiry:
            flash("Please fill all fields correctly.", "error")
            return redirect(url_for("donate"))
        get_db().execute(
            "INSERT INTO donations(donor_id,food_name,quantity,location,expiry_time) VALUES(?,?,?,?,?)",
            (session["user_id"], food, qty, loc, expiry))
        get_db().commit()
        flash("Thank you! Your donation is now listed.", "success")
        return redirect(url_for("foods"))
    return render_template("donate.html")


@app.route("/foods")
def foods():
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    rows = get_db().execute("""
        SELECT d.*, u.name AS donor FROM donations d JOIN users u ON u.id=d.donor_id
        WHERE d.status='available' AND d.expiry_time > ? ORDER BY d.expiry_time""", (now,)).fetchall()
    return render_template("foods.html", foods=rows)


@app.route("/request/<int:donation_id>", methods=["POST"])
@login_required
def request_food(donation_id):
    db = get_db()
    d = db.execute("SELECT * FROM donations WHERE id=?", (donation_id,)).fetchone()
    if not d or d["status"] != "available":
        flash("Sorry, this food is no longer available.", "error")
    elif d["donor_id"] == session["user_id"]:
        flash("You cannot request your own donation.", "error")
    else:
        db.execute("INSERT INTO requests(donation_id,requester_id,message) VALUES(?,?,?)",
                   (donation_id, session["user_id"], request.form.get("message", "")))
        db.execute("UPDATE donations SET status='claimed' WHERE id=?", (donation_id,))
        db.commit()
        flash(f"Request sent! Pick up '{d['food_name']}' at {d['location']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    uid = session["user_id"]
    my_donations = db.execute("SELECT * FROM donations WHERE donor_id=? ORDER BY id DESC", (uid,)).fetchall()
    my_requests = db.execute("""SELECT r.*, d.food_name, d.quantity, d.location FROM requests r
        JOIN donations d ON d.id=r.donation_id WHERE r.requester_id=? ORDER BY r.id DESC""", (uid,)).fetchall()
    return render_template("dashboard.html", stats=get_stats(),
                           my_donations=my_donations, my_requests=my_requests)


@app.route("/tips")
def tips():
    return render_template("tips.html")


@app.route("/admin")
@login_required
@admin_required
def admin():
    db = get_db()
    users = db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
    donations = db.execute("""SELECT d.*, u.name AS donor FROM donations d
        JOIN users u ON u.id=d.donor_id ORDER BY d.id DESC""").fetchall()
    reqs = db.execute("""SELECT r.*, u.name AS requester, d.food_name FROM requests r
        JOIN users u ON u.id=r.requester_id JOIN donations d ON d.id=r.donation_id ORDER BY r.id DESC""").fetchall()
    return render_template("admin.html", stats=get_stats(), users=users, donations=donations, reqs=reqs)


@app.route("/admin/delete/<int:donation_id>", methods=["POST"])
@login_required
@admin_required
def delete_donation(donation_id):
    db = get_db()
    db.execute("DELETE FROM requests WHERE donation_id=?", (donation_id,))
    db.execute("DELETE FROM donations WHERE id=?", (donation_id,))
    db.commit()
    flash("Donation deleted.", "success")
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)

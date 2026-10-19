import os
import secrets
import sqlite3
from datetime import date, datetime
import csv
import io
from flask import make_response
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "expenditure.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('income', 'expense')),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            UNIQUE(user_id, month),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            title TEXT NOT NULL,
            target_cents INTEGER NOT NULL CHECK(target_cents > 0),
            saved_cents INTEGER NOT NULL DEFAULT 0 CHECK(saved_cents >= 0),
            deadline TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_user_date
            ON transactions(user_id, transaction_date);
    """)
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to view your dashboard.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


def validate_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("_csrf_token", "")
    if not expected or not secrets.compare_digest(submitted, expected):
        flash("Your form session expired. Please try again.", "error")
        return False
    return True


def money_to_cents(raw):
    try:
        value = float(raw)
        if value <= 0 or value > 100000000:
            return None
        # Reject more than two decimal places to avoid confusing rounding.
        cents = round(value * 100)
        if abs(value * 100 - cents) > 0.00001:
            return None
        return int(cents)
    except (TypeError, ValueError):
        return None


def current_user():
    if "user_id" not in session:
        return None
    return get_db().execute(
        "SELECT id, username FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("register"))
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(username) > 30:
            flash("Username must be between 3 and 30 characters.", "error")
        elif not username.replace("_", "").replace("-", "").isalnum():
            flash("Use only letters, numbers, underscores, or hyphens in your username.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        else:
            db = get_db()
            try:
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
                db.commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                flash("Account created. Welcome!", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.", "error")
    return render_template("register.html", title="Create account")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("login"))
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html", title="Log in")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    if not validate_csrf():
        return redirect(url_for("dashboard"))
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        month = date.today().strftime("%Y-%m")

    month_start = f"{month}-01"
    # YYYY-MM is validated above; next month boundary is calculated safely.
    year, mon = map(int, month.split("-"))
    next_year, next_mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    next_month_start = f"{next_year:04d}-{next_mon:02d}-01"

    totals = db.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN kind='income' THEN amount_cents ELSE 0 END), 0) AS income,
          COALESCE(SUM(CASE WHEN kind='expense' THEN amount_cents ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE user_id=? AND transaction_date >= ? AND transaction_date < ?
    """, (user_id, month_start, next_month_start)).fetchone()

    search = request.args.get("q", "").strip()[:80]
    category_filter = request.args.get("category", "").strip()
    kind_filter = request.args.get("kind", "").strip()
    conditions = ["user_id=?", "transaction_date >= ?", "transaction_date < ?"]
    params = [user_id, month_start, next_month_start]
    if search:
        conditions.append("(description LIKE ? OR category LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    valid_categories = {"Food", "Transport", "Shopping", "Bills", "Health", "Education", "Entertainment", "Other", "Salary", "Allowance", "Freelance", "Gift"}
    if category_filter in valid_categories:
        conditions.append("category=?")
        params.append(category_filter)
    if kind_filter in {"income", "expense"}:
        conditions.append("kind=?")
        params.append(kind_filter)
    transactions = db.execute(f"""
        SELECT id, kind, amount_cents, category, description, transaction_date
        FROM transactions WHERE {' AND '.join(conditions)}
        ORDER BY transaction_date DESC, id DESC LIMIT 250
    """, params).fetchall()

    goal = db.execute("SELECT title, target_cents, saved_cents, deadline FROM savings_goals WHERE user_id=?", (user_id,)).fetchone()
    goal_percent = min(100, round(goal["saved_cents"] * 100 / goal["target_cents"])) if goal else 0

    budget = db.execute(
        "SELECT amount_cents FROM budgets WHERE user_id=? AND month=?",
        (user_id, month)
    ).fetchone()
    budget_cents = budget["amount_cents"] if budget else 0
    expenses_cents = totals["expenses"]
    budget_percent = min(100, round(expenses_cents * 100 / budget_cents)) if budget_cents else 0

    category_rows = db.execute("""
        SELECT category, SUM(amount_cents) AS total
        FROM transactions
        WHERE user_id=? AND kind='expense'
          AND transaction_date >= ? AND transaction_date < ?
        GROUP BY category ORDER BY total DESC
    """, (user_id, month_start, next_month_start)).fetchall()

    monthly_rows = db.execute("""
        SELECT substr(transaction_date, 1, 7) AS month,
          SUM(CASE WHEN kind='income' THEN amount_cents ELSE 0 END) AS income,
          SUM(CASE WHEN kind='expense' THEN amount_cents ELSE 0 END) AS expenses
        FROM transactions
        WHERE user_id=? AND transaction_date >= date(?, '-5 months')
          AND transaction_date < ?
        GROUP BY substr(transaction_date, 1, 7)
        ORDER BY month
    """, (user_id, month_start, next_month_start)).fetchall()

    return render_template(
        "dashboard.html", title="Dashboard", user=current_user(), month=month,
        income=totals["income"], expenses=expenses_cents,
        balance=totals["income"] - expenses_cents, transactions=transactions,
        budget_cents=budget_cents, budget_percent=budget_percent,
        search=search, category_filter=category_filter, kind_filter=kind_filter,
        goal=goal, goal_percent=goal_percent,
        category_data=[{"label": r["category"], "value": r["total"] / 100} for r in category_rows],
        monthly_data=[{"month": r["month"], "income": r["income"] / 100,
                       "expenses": r["expenses"] / 100} for r in monthly_rows],
        today=date.today().isoformat()
    )


@app.route("/transactions", methods=["POST"])
@login_required
def add_transaction():
    if not validate_csrf():
        return redirect(url_for("dashboard"))
    kind = request.form.get("kind", "")
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()[:120]
    transaction_date = request.form.get("transaction_date", "")
    cents = money_to_cents(request.form.get("amount", ""))

    allowed_categories = {
        "expense": {"Food", "Transport", "Shopping", "Bills", "Health", "Education", "Entertainment", "Other"},
        "income": {"Salary", "Allowance", "Freelance", "Gift", "Other"}
    }
    try:
        datetime.strptime(transaction_date, "%Y-%m-%d")
        valid_date = True
    except ValueError:
        valid_date = False

    if kind not in allowed_categories or category not in allowed_categories.get(kind, set()):
        flash("Please choose a valid transaction type and category.", "error")
    elif cents is None:
        flash("Enter a valid positive amount with up to two decimal places.", "error")
    elif not valid_date:
        flash("Please choose a valid date.", "error")
    else:
        get_db().execute("""
            INSERT INTO transactions (user_id, kind, amount_cents, category, description, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["user_id"], kind, cents, category, description, transaction_date))
        get_db().commit()
        flash("Transaction added successfully.", "success")
    return redirect(url_for("dashboard", month=transaction_date[:7] if valid_date else date.today().strftime("%Y-%m")))


@app.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    if not validate_csrf():
        return redirect(url_for("dashboard"))
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id=? AND user_id=?",
               (transaction_id, session["user_id"]))
    db.commit()
    flash("Transaction deleted if it belonged to your account.", "info")
    month = request.form.get("month", date.today().strftime("%Y-%m"))
    return redirect(url_for("dashboard", month=month))


@app.route("/budget", methods=["POST"])
@login_required
def save_budget():
    if not validate_csrf():
        return redirect(url_for("dashboard"))
    month = request.form.get("month", "")
    cents = money_to_cents(request.form.get("budget_amount", ""))
    try:
        datetime.strptime(month, "%Y-%m")
        valid_month = True
    except ValueError:
        valid_month = False
    if not valid_month or cents is None:
        flash("Enter a valid month and a positive budget amount.", "error")
    else:
        get_db().execute("""
            INSERT INTO budgets (user_id, month, amount_cents) VALUES (?, ?, ?)
            ON CONFLICT(user_id, month) DO UPDATE SET amount_cents=excluded.amount_cents
        """, (session["user_id"], month, cents))
        get_db().commit()
        flash("Monthly budget saved.", "success")
    return redirect(url_for("dashboard", month=month if valid_month else date.today().strftime("%Y-%m")))


@app.route("/savings-goal", methods=["POST"])
@login_required
def save_savings_goal():
    if not validate_csrf():
        return redirect(url_for("dashboard"))
    title = request.form.get("goal_title", "").strip()[:80]
    target = money_to_cents(request.form.get("target_amount", ""))
    saved_raw = request.form.get("saved_amount", "0").strip() or "0"
    try:
        saved_value = float(saved_raw)
        saved_cents = round(saved_value * 100)
        valid_saved = saved_value >= 0 and saved_value <= 100000000 and abs(saved_value * 100 - saved_cents) < 0.00001
    except (TypeError, ValueError):
        saved_cents, valid_saved = 0, False
    deadline = request.form.get("deadline", "").strip() or None
    valid_deadline = True
    if deadline:
        try:
            datetime.strptime(deadline, "%Y-%m-%d")
        except ValueError:
            valid_deadline = False
    if not title or target is None or not valid_saved or saved_cents > target or not valid_deadline:
        flash("Enter a goal name, valid target, saved amount (not above target), and valid deadline.", "error")
    else:
        get_db().execute("""
            INSERT INTO savings_goals (user_id, title, target_cents, saved_cents, deadline)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET title=excluded.title, target_cents=excluded.target_cents,
              saved_cents=excluded.saved_cents, deadline=excluded.deadline, updated_at=CURRENT_TIMESTAMP
        """, (session["user_id"], title, target, saved_cents, deadline))
        get_db().commit()
        flash("Savings goal saved.", "success")
    return redirect(url_for("dashboard"))


@app.route("/export.csv")
@login_required
def export_csv():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        month = date.today().strftime("%Y-%m")
    year, mon = map(int, month.split("-"))
    next_year, next_mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    start, end = f"{month}-01", f"{next_year:04d}-{next_mon:02d}-01"
    rows = get_db().execute("""
        SELECT transaction_date, kind, category, description, amount_cents
        FROM transactions WHERE user_id=? AND transaction_date >= ? AND transaction_date < ?
        ORDER BY transaction_date DESC, id DESC
    """, (session["user_id"], start, end)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Category", "Description", "Amount (INR)"])
    for row in rows:
        writer.writerow([row["transaction_date"], row["kind"], row["category"], row["description"], f'{row["amount_cents"] / 100:.2f}'])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="spendwise-{month}.csv"'
    return response


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

import csv
import io
import re
import sqlite3
from datetime import date

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for

import ai

app = Flask(__name__)
app.secret_key = "change-this-before-deploying"
DB = "expenses.db"
CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Health", "Entertainment", "Other"]
CURRENCY = "₹"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL, category TEXT NOT NULL,
            date TEXT NOT NULL, note TEXT)""")
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")


def validate(form):
    try:
        amount = float(form.get("amount", ""))
    except ValueError:
        return None, "Enter a valid amount."
    if amount <= 0:
        return None, "Amount must be greater than 0."
    if form.get("category") not in CATEGORIES:
        return None, "Choose a category."
    if not form.get("date"):
        return None, "Pick a date."
    return (amount, form["category"], form["date"], form.get("note", "").strip()[:100]), None


def get_budget(db):
    row = db.execute("SELECT value FROM settings WHERE key='budget'").fetchone()
    return float(row["value"]) if row else 0.0


def fetch(db, month, category):
    sql, params = "SELECT * FROM expenses WHERE 1=1", []
    if month:
        sql += " AND date LIKE ?"
        params.append(month + "%")
    if category:
        sql += " AND category = ?"
        params.append(category)
    return db.execute(sql + " ORDER BY date DESC, id DESC", params).fetchall()


@app.route("/")
def index():
    month = request.args.get("month", date.today().strftime("%Y-%m"))  # "" = all time
    category = request.args.get("category", "")
    db = get_db()
    expenses = fetch(db, month, category)
    total = sum(e["amount"] for e in expenses)
    by_cat = {}
    for e in expenses:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]
    budget = get_budget(db)
    month_total = sum(e["amount"] for e in fetch(db, month, "")) if month else 0
    return render_template(
        "index.html", expenses=expenses, total=total, by_cat=by_cat, budget=budget,
        month_total=month_total, month=month, category=category,
        categories=CATEGORIES, cur=CURRENCY, today=date.today().isoformat())


@app.route("/add", methods=["POST"])
def add():
    values, error = validate(request.form)
    if error:
        flash(error)
    else:
        with get_db() as db:
            db.execute("INSERT INTO expenses (amount, category, date, note) VALUES (?,?,?,?)", values)
        flash("Expense added.")
    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    db = get_db()
    expense = db.execute("SELECT * FROM expenses WHERE id=?", (id,)).fetchone()
    if expense is None:
        return redirect(url_for("index"))
    if request.method == "POST":
        values, error = validate(request.form)
        if error:
            flash(error)
        else:
            with db:
                db.execute("UPDATE expenses SET amount=?, category=?, date=?, note=? WHERE id=?",
                           values + (id,))
            flash("Expense saved.")
            return redirect(url_for("index"))
    return render_template("edit.html", e=expense, categories=CATEGORIES, cur=CURRENCY)


@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    with get_db() as db:
        db.execute("DELETE FROM expenses WHERE id=?", (id,))
    flash("Expense deleted.")
    return redirect(url_for("index"))


@app.route("/budget", methods=["POST"])
def budget():
    try:
        value = float(request.form.get("budget", ""))
        if value < 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid budget.")
        return redirect(url_for("index"))
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('budget', ?)", (str(value),))
    flash("Monthly budget updated.")
    return redirect(url_for("index"))


@app.route("/export")
def export():
    rows = fetch(get_db(), request.args.get("month", ""), request.args.get("category", ""))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Category", "Amount", "Note"])
    for r in rows:
        writer.writerow([r["date"], r["category"], r["amount"], r["note"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expenses.csv"})


# ---------- AI features ----------
def month_summary(db, month):
    by_cat = {}
    rows = fetch(db, month, "")
    for r in rows:
        by_cat[r["category"]] = round(by_cat.get(r["category"], 0) + r["amount"], 2)
    return {"month": month, "total": round(sum(by_cat.values()), 2), "count": len(rows), "by_category": by_cat}


def ai_error(exc):
    return jsonify(error=str(exc)), 502


@app.route("/ai/add", methods=["POST"])
def ai_add():
    text = request.form.get("text", "").strip()[:300]
    if not text:
        flash("Type an expense first, for example: spent 250 on lunch yesterday.")
        return redirect(url_for("index"))
    try:
        data = ai.parse_expense(text, CATEGORIES, date.today().isoformat())
        if "error" in data:
            raise ai.AIError("I could not find an amount. Try: spent 250 on lunch.")
        date.fromisoformat(str(data.get("date")))
    except ai.AIError as exc:
        flash(str(exc))
        return redirect(url_for("index"))
    except ValueError:
        flash("The AI returned an invalid date. Please rephrase and try again.")
        return redirect(url_for("index"))
    values, error = validate({"amount": str(data.get("amount", "")), "category": data.get("category"),
                              "date": data.get("date"), "note": str(data.get("note", ""))})
    if error:
        flash("Could not save: " + error)
    else:
        with get_db() as db:
            db.execute("INSERT INTO expenses (amount, category, date, note) VALUES (?,?,?,?)", values)
        flash(f"Added {CURRENCY}{values[0]:.2f} under {values[1]} on {values[2]}.")
    return redirect(url_for("index"))


@app.route("/ai/insights", methods=["POST"])
def ai_insights():
    month = request.form.get("month") or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        return jsonify(error="Pick a month first."), 400
    y, m = int(month[:4]), int(month[5:])
    prev = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    db = get_db()
    this_m, last_m = month_summary(db, month), month_summary(db, prev)
    if this_m["count"] == 0:
        return jsonify(error="No expenses in that month yet."), 400
    try:
        return jsonify(text=ai.insights(this_m, last_m))
    except ai.AIError as exc:
        return ai_error(exc)


@app.route("/ai/ask", methods=["POST"])
def ai_ask():
    question = request.form.get("question", "").strip()[:200]
    if not question:
        return jsonify(error="Type a question first."), 400
    try:
        f = ai.question_filter(question, CATEGORIES, date.today().isoformat())
        month = f.get("month") if re.fullmatch(r"\d{4}-\d{2}", str(f.get("month"))) else ""
        category = f.get("category") if f.get("category") in CATEGORIES else ""
        rows = fetch(get_db(), month, category)  # the numbers come from SQL, not from the AI
        facts = {"month": month or "all time", "category": category or "all categories",
                 "total": round(sum(r["amount"] for r in rows), 2), "count": len(rows),
                 "largest": [{"date": r["date"], "category": r["category"], "amount": r["amount"], "note": r["note"]}
                             for r in sorted(rows, key=lambda r: -r["amount"])[:5]]}
        return jsonify(text=ai.explain(question, facts))
    except ai.AIError as exc:
        return ai_error(exc)


init_db()

if __name__ == "__main__":
    app.run(debug=True)

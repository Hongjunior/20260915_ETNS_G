import os
import sqlite3
from datetime import date

from flask import Flask, flash, g, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = "etns-todo-app-secret-key"

DATABASE = "/tmp/todo.db" if os.environ.get("VERCEL") else "todo.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'medium',
                is_done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        db.commit()


@app.route("/")
def index():
    db = get_db()
    status_filter = request.args.get("status", "all")

    query = "SELECT * FROM todos"
    params = []
    if status_filter == "active":
        query += " WHERE is_done = 0"
    elif status_filter == "done":
        query += " WHERE is_done = 1"
    query += " ORDER BY is_done ASC, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date IS NULL, due_date ASC, id DESC"

    todos = db.execute(query, params).fetchall()

    total = db.execute("SELECT COUNT(*) AS c FROM todos").fetchone()["c"]
    done = db.execute("SELECT COUNT(*) AS c FROM todos WHERE is_done = 1").fetchone()["c"]

    return render_template(
        "index.html",
        todos=todos,
        status_filter=status_filter,
        total=total,
        done=done,
        today=date.today().isoformat(),
    )


@app.route("/add", methods=["POST"])
def add_todo():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    priority = request.form.get("priority", "medium")

    if not title:
        flash("할일 제목을 입력해주세요.", "error")
        return redirect(url_for("index"))

    db = get_db()
    db.execute(
        "INSERT INTO todos (title, description, due_date, priority) VALUES (?, ?, ?, ?)",
        (title, description, due_date, priority),
    )
    db.commit()
    flash("할일이 추가되었습니다.", "success")
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle_todo(todo_id):
    db = get_db()
    todo = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if todo:
        db.execute(
            "UPDATE todos SET is_done = ? WHERE id = ?",
            (0 if todo["is_done"] else 1, todo_id),
        )
        db.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
def edit_todo(todo_id):
    db = get_db()
    todo = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if not todo:
        flash("할일을 찾을 수 없습니다.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip() or None
        priority = request.form.get("priority", "medium")

        if not title:
            flash("할일 제목을 입력해주세요.", "error")
            return redirect(url_for("edit_todo", todo_id=todo_id))

        db.execute(
            "UPDATE todos SET title = ?, description = ?, due_date = ?, priority = ? WHERE id = ?",
            (title, description, due_date, priority, todo_id),
        )
        db.commit()
        flash("할일이 수정되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template("edit.html", todo=todo)


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete_todo(todo_id):
    db = get_db()
    db.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    db.commit()
    flash("할일이 삭제되었습니다.", "success")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)

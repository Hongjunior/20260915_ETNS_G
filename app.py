import os
from datetime import date

from flask import Flask, flash, redirect, render_template, request, url_for
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = "etns-todo-app-secret-key"

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    db_path = "/tmp/todo.db" if os.environ.get("VERCEL") else "todo.db"
    engine = create_engine(f"sqlite:///{db_path}")

IS_POSTGRES = engine.url.get_backend_name() == "postgresql"


def init_db():
    with engine.begin() as conn:
        if IS_POSTGRES:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS todos (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT,
                        due_date TEXT,
                        priority TEXT NOT NULL DEFAULT 'medium',
                        is_done INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
        else:
            conn.execute(
                text(
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
            )


@app.route("/")
def index():
    status_filter = request.args.get("status", "all")

    where = ""
    if status_filter == "active":
        where = "WHERE is_done = 0"
    elif status_filter == "done":
        where = "WHERE is_done = 1"

    order = """
        ORDER BY is_done ASC,
                 CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 (due_date IS NULL), due_date ASC, id DESC
    """

    with engine.connect() as conn:
        todos = conn.execute(text(f"SELECT * FROM todos {where} {order}")).mappings().all()
        total = conn.execute(text("SELECT COUNT(*) AS c FROM todos")).mappings().first()["c"]
        done = conn.execute(
            text("SELECT COUNT(*) AS c FROM todos WHERE is_done = 1")
        ).mappings().first()["c"]

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

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO todos (title, description, due_date, priority) "
                "VALUES (:title, :description, :due_date, :priority)"
            ),
            {"title": title, "description": description, "due_date": due_date, "priority": priority},
        )
    flash("할일이 추가되었습니다.", "success")
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle_todo(todo_id):
    with engine.begin() as conn:
        todo = conn.execute(
            text("SELECT is_done FROM todos WHERE id = :id"), {"id": todo_id}
        ).mappings().first()
        if todo:
            conn.execute(
                text("UPDATE todos SET is_done = :val WHERE id = :id"),
                {"val": 0 if todo["is_done"] else 1, "id": todo_id},
            )
    return redirect(request.referrer or url_for("index"))


@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
def edit_todo(todo_id):
    with engine.connect() as conn:
        todo = conn.execute(
            text("SELECT * FROM todos WHERE id = :id"), {"id": todo_id}
        ).mappings().first()

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

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE todos SET title = :title, description = :description, "
                    "due_date = :due_date, priority = :priority WHERE id = :id"
                ),
                {
                    "title": title,
                    "description": description,
                    "due_date": due_date,
                    "priority": priority,
                    "id": todo_id,
                },
            )
        flash("할일이 수정되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template("edit.html", todo=todo)


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete_todo(todo_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM todos WHERE id = :id"), {"id": todo_id})
    flash("할일이 삭제되었습니다.", "success")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)

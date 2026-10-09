import ast
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "books.db")


def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT,
            genre TEXT,
            cover_url TEXT,
            avg_rating REAL,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            password_hash TEXT,
            password_salt TEXT,
            token TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (book_id) REFERENCES books(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_book ON ratings(book_id)")

    conn.commit()
    conn.close()
    print(f"Tables ready in {DB_PATH}")


def clean_author(raw):
    if not raw:
        return ""
    raw = str(raw).strip()
    if raw.startswith("["):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)) and parsed:
                return str(parsed[0]).strip().strip("[]'\" ").strip()
        except (ValueError, SyntaxError):
            pass
        raw = raw.strip("[]")
    return raw.split(",")[0].strip().strip("[]'\" ").strip()


def migrate_schema():
    conn = get_connection()
    cursor = conn.cursor()

    migrations = [
        "ALTER TABLE books ADD COLUMN description TEXT",
        "ALTER TABLE users ADD COLUMN password_hash TEXT",
        "ALTER TABLE users ADD COLUMN password_salt TEXT",
        "ALTER TABLE users ADD COLUMN token TEXT",
    ]

    for statement in migrations:
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

    rows = cursor.execute("SELECT id, author FROM books WHERE author LIKE '[%'").fetchall()
    for row in rows:
        cursor.execute("UPDATE books SET author = ? WHERE id = ?", (clean_author(row["author"]), row["id"]))
    conn.commit()

    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_unique ON ratings(user_id, book_id)"
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        cursor.execute(
            "DELETE FROM ratings WHERE id NOT IN "
            "(SELECT MAX(id) FROM ratings GROUP BY user_id, book_id)"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_unique ON ratings(user_id, book_id)"
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()
    migrate_schema()
import sqlite3
import os
DB_PATH = os.path.join(os.path.dirname(__file__), "books.db")
def get_connection():
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
            avg_rating REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
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
if __name__ == "__main__":
    create_tables()
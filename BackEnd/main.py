import hashlib
import re
import secrets
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import recommend
from add_persian_books import seed_persian_books
from database import create_tables, get_connection, migrate_schema
from recommend import get_recommendations, get_taste_profile
API_VERSION = "3"
PBKDF2_ROUNDS = 200_000
LOGIN_REQUIRED_MSG = "برای امتیاز دادن ابتدا وارد حساب کاربری خود شوید"
BAD_CREDENTIALS_MSG = "نام کاربری یا رمز عبور اشتباه است"
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    migrate_schema()
    seed_persian_books()
    try:
        recommend.warm_up()
    except Exception as error:
        print(f"recommender warm-up skipped: {error}")
    yield
app = FastAPI(title="Shelf API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
def hash_password(password: str, salt: Optional[str] = None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ROUNDS
    ).hex()
    return f"pbkdf2${PBKDF2_ROUNDS}${digest}", salt
def verify_password(password: str, salt: str, stored: str) -> bool:
    if stored.startswith("pbkdf2$"):
        _, rounds, digest = stored.split("$", 2)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(rounds)
        ).hex()
    else:
        candidate = hashlib.sha256((salt + password).encode()).hexdigest()
        digest = stored
    return secrets.compare_digest(candidate, digest)
def normalize_query(text: str) -> str:
    return text.replace("ي", "ی").replace("ك", "ک").strip()
class SignupIn(BaseModel):
    name: str
    password: str
class LoginIn(BaseModel):
    name: str
    password: str
class RatingIn(BaseModel):
    user_id: int
    book_id: int
    rating: int
@app.get("/")
def root():
    conn = get_connection()
    books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return {"status": "ok", "api_version": API_VERSION, "books": books, "users": users}
@app.get("/books")
def list_books(limit: int = 24, offset: int = 0, genre: Optional[str] = None):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    conn = get_connection()
    if genre and genre.lower() != "all":
        rows = conn.execute(
            "SELECT * FROM books WHERE genre LIKE ? LIMIT ? OFFSET ?",
            (f"%{genre}%", limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM books LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
@app.get("/books/search")
def search_books(q: str, limit: int = 24):
    limit = max(1, min(limit, 100))
    term = f"%{normalize_query(q)}%"
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? LIMIT ?",
        (term, term, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
@app.get("/books/{book_id}")
def get_book(book_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="کتاب پیدا نشد")
    return dict(row)
@app.post("/signup")
def signup(data: SignupIn):
    name = data.name.strip()
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="این نام کاربری قبلاً ثبت شده است")
    password_hash, salt = hash_password(data.password)
    token = secrets.token_urlsafe(32)
    cursor = conn.execute(
        "INSERT INTO users (name, password_hash, password_salt, token) VALUES (?, ?, ?, ?)",
        (name, password_hash, salt, token),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {"id": user_id, "name": name, "token": token}
@app.post("/login")
def login(data: LoginIn):
    name = data.name.strip()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE name = ? COLLATE NOCASE ORDER BY id LIMIT 1", (name,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS_MSG)
    if not row["password_hash"]:
        password_hash, salt = hash_password(data.password)
        conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (password_hash, salt, row["id"]),
        )
    elif not verify_password(data.password, row["password_salt"], row["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS_MSG)
    token = row["token"] or secrets.token_urlsafe(32)
    conn.execute("UPDATE users SET token = ? WHERE id = ?", (token, row["id"]))
    conn.commit()
    conn.close()
    return {"id": row["id"], "name": row["name"], "token": token}
def require_login(user_id: int, authorization: Optional[str]):
    token = (authorization or "").replace("Bearer", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail=LOGIN_REQUIRED_MSG)
    conn = get_connection()
    row = conn.execute("SELECT token FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row or not row["token"] or not secrets.compare_digest(row["token"], token):
        raise HTTPException(status_code=401, detail=LOGIN_REQUIRED_MSG)
@app.post("/rate")
def rate_book(rating: RatingIn, authorization: Optional[str] = Header(default=None)):
    require_login(rating.user_id, authorization)
    if not (1 <= rating.rating <= 5):
        raise HTTPException(status_code=400, detail="امتیاز باید بین ۱ تا ۵ باشد")
    conn = get_connection()
    book = conn.execute("SELECT id FROM books WHERE id = ?", (rating.book_id,)).fetchone()
    if not book:
        conn.close()
        raise HTTPException(status_code=404, detail="کتاب پیدا نشد")
    conn.execute(
        "INSERT INTO ratings (user_id, book_id, rating) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, book_id) DO UPDATE SET rating = excluded.rating",
        (rating.user_id, rating.book_id, rating.rating),
    )
    conn.commit()
    conn.close()
    return {"status": "saved"}
@app.get("/ratings/{user_id}")
def user_ratings(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT book_id, rating FROM ratings WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return {str(row["book_id"]): row["rating"] for row in rows}
@app.get("/recommendations/{user_id}")
def recommendations(user_id: int, limit: int = 8):
    return get_recommendations(user_id, max(1, min(limit, 24)))
@app.get("/taste/{user_id}")
def taste(user_id: int):
    return get_taste_profile(user_id)
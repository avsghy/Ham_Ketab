from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import get_connection
from recommend import get_recommendations, get_taste_profile
app = FastAPI(title="Shelf API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
class RatingIn(BaseModel):
    user_id: int
    book_id: int
    rating: int
class UserIn(BaseModel):
    name: str
@app.get("/books")
def list_books(limit: int = 24, offset: int = 0, genre: Optional[str] = None):
    """Paginated book list, optionally filtered by genre.
    Example: /books?limit=12&offset=0&genre=Fantasy
    """
    conn = get_connection()
    cursor = conn.cursor()
    if genre and genre.lower() != "all":
        cursor.execute(
            "SELECT * FROM books WHERE genre LIKE ? LIMIT ? OFFSET ?",
            (f"%{genre}%", limit, offset)
        )
    else:
        cursor.execute("SELECT * FROM books LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
@app.get("/books/search")
def search_books(q: str, limit: int = 24):
    """Example: /books/search?q=circe"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? LIMIT ?",
        (f"%{q}%", f"%{q}%", limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
@app.post("/users")
def create_user(user: UserIn):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name) VALUES (?)", (user.name,))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "name": user.name}
@app.post("/rate")
def rate_book(rating: RatingIn):
    if not (1 <= rating.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ratings (user_id, book_id, rating) VALUES (?, ?, ?)",
        (rating.user_id, rating.book_id, rating.rating)
    )
    conn.commit()
    conn.close()
    return {"status": "saved"}
@app.get("/ratings/{user_id}")
def user_ratings(user_id: int):
    """Returns {book_id: rating} for everything this user has already
    rated, so the frontend can pre-fill stars instead of showing every
    book as unrated after a page reload."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT book_id, rating FROM ratings WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return {str(row["book_id"]): row["rating"] for row in rows}
@app.get("/recommendations/{user_id}")
def recommendations(user_id: int, limit: int = 8):
    return get_recommendations(user_id, limit)
@app.get("/taste/{user_id}")
def taste(user_id: int):
    return get_taste_profile(user_id)
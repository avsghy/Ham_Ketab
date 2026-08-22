from collections import Counter
from database import get_connection
GENRE_BLOCKLIST = {
    "books", "favorites", "owned", "to-read", "currently-reading",
    "default", "my-books", "library", "kindle", "ebook", "ebooks",
    "audiobook", "audiobooks", "wish-list", "wishlist", "unread",
    "abandoned", "dnf", "have", "general", "read", "re-read",
}
GENRE_FA = {
    "fantasy": "فانتزی",
    "fiction": "داستانی",
    "science-fiction": "علمی-تخیلی",
    "mystery": "معمایی",
    "romance": "عاشقانه",
    "non-fiction": "غیرداستانی",
    "classics": "کلاسیک",
    "philosophy": "فلسفه",
    "history": "تاریخ",
    "biography": "زندگی‌نامه",
    "memoir": "خاطرات",
    "poetry": "شعر",
    "horror": "ترسناک",
    "thriller": "هیجان‌انگیز",
    "young-adult": "نوجوان",
    "childrens": "کودک",
    "graphic-novels": "رمان مصور",
    "historical-fiction": "داستان تاریخی",
    "contemporary": "معاصر",
    "adventure": "ماجراجویی",
    "dystopia": "دیستوپیا",
    "self-help": "خودیاری",
    "science": "علم",
    "psychology": "روان‌شناسی",
    "art": "هنر",
    "religion": "مذهب",
    "spirituality": "معنویت",
    "business": "کسب‌وکار",
    "cookbooks": "آشپزی",
    "travel": "سفر",
    "humor": "طنز",
    "short-stories": "داستان کوتاه",
    "war": "جنگ",
    "crime": "جنایی",
    "paranormal": "ماوراءالطبیعه",
    "sports": "ورزش",
}
def _fa(genre):
    return GENRE_FA.get(genre, genre)
def _get_user_ratings(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT book_id, rating FROM ratings WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row["book_id"]: row["rating"] for row in rows}
def _all_books():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
def _split_genres(genre_string):
    if not genre_string:
        return []
    raw = [g.strip().strip("[]'\" ").lower() for g in genre_string.split(",") if g.strip()]
    return [g for g in raw if g and g not in GENRE_BLOCKLIST]
def _build_genre_profile(user_ratings, books_by_id):
    profile = Counter()
    for book_id, rating in user_ratings.items():
        book = books_by_id.get(book_id)
        if not book:
            continue
        weight = rating - 3
        for genre in _split_genres(book["genre"]):
            profile[genre] += weight
    return profile
def _popular_fallback(books, limit):
    popular = sorted(books, key=lambda b: b["avg_rating"] or 0, reverse=True)
    return [{**b, "reason": "محبوب بین خوانندگان"} for b in popular[:limit]]
def get_recommendations(user_id, limit=8):
    user_ratings = _get_user_ratings(user_id)
    books = _all_books()
    books_by_id = {b["id"]: b for b in books}
    if not user_ratings:
        return _popular_fallback(books, limit)
    profile = _build_genre_profile(user_ratings, books_by_id)
    scored = []
    for book in books:
        if book["id"] in user_ratings:
            continue
        genres = _split_genres(book["genre"])
        if not genres:
            continue
        score = sum(profile.get(g, 0) for g in genres) / len(genres)
        if score > 0:
            best_genre = max(genres, key=lambda g: profile.get(g, 0))
            scored.append((score, book, best_genre))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:limit]
    if not top:
        return _popular_fallback(books, limit)

    return [
        {**book, "reason": f"چون از کتاب‌های {_fa(genre)} لذت می‌برید"}
        for score, book, genre in top
    ]
def get_taste_profile(user_id, top_n=6):
    user_ratings = _get_user_ratings(user_id)
    books_by_id = {b["id"]: b for b in _all_books()}
    genre_totals = Counter()
    genre_counts = Counter()
    for book_id, rating in user_ratings.items():
        book = books_by_id.get(book_id)
        if not book:
            continue
        for genre in _split_genres(book["genre"]):
            genre_totals[genre] += rating
            genre_counts[genre] += 1
    if not genre_counts:
        return []
    averages = {g: genre_totals[g] / genre_counts[g] for g in genre_counts}
    result = [
        {"genre": _fa(g), "percent": round(((avg - 1) / 4) * 100)}
        for g, avg in averages.items()
    ]
    result.sort(key=lambda row: row["percent"], reverse=True)
    return result[:top_n]
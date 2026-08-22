import csv
import os
import ast
from database import get_connection, create_tables
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MAX_RATINGS = 200_000
def _clean_genre_field(raw_value):
    if not raw_value:
        return ""
    raw_value = raw_value.strip()
    if raw_value.startswith("[") and raw_value.endswith("]"):
        try:
            parsed = ast.literal_eval(raw_value)
            tags = [str(g).strip().lower() for g in parsed if str(g).strip()]
        except (ValueError, SyntaxError):
            stripped = raw_value.strip("[]")
            tags = [g.strip().strip("'\"").lower() for g in stripped.split(",") if g.strip()]
    else:
        tags = [g.strip().strip("'\"").lower() for g in raw_value.split(",") if g.strip()]
    return ", ".join(tags)
def _first_present(fieldnames, *candidates):
    for name in candidates:
        if name in fieldnames:
            return name
    return None
def load_books():
    books_path = os.path.join(DATA_DIR, "books_enriched.csv")
    if not os.path.exists(books_path):
        books_path = os.path.join(DATA_DIR, "books.csv")

    if not os.path.exists(books_path):
        print(f"No books CSV found in {DATA_DIR}. Put books.csv (or "
              f"books_enriched.csv) there first.")
        return
    conn = get_connection()
    cursor = conn.cursor()
    with open(books_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        id_col = _first_present(fields, "book_id", "id")
        title_col = _first_present(fields, "title")
        author_col = _first_present(fields, "authors", "author")
        genre_col = _first_present(fields, "genres", "genre")
        cover_col = _first_present(fields, "image_url", "cover_url")
        rating_col = _first_present(fields, "average_rating", "avg_rating")
        print(f"Reading books from {os.path.basename(books_path)} — "
              f"using columns: id={id_col}, title={title_col}, "
              f"author={author_col}, genre={genre_col}, "
              f"cover={cover_col}, rating={rating_col}")
        rows_to_insert = []
        for row in reader:
            try:
                book_id = int(row[id_col])
            except (ValueError, TypeError):
                continue 
            rows_to_insert.append((
                book_id,
                row.get(title_col, "") or "",
                (row.get(author_col, "") or "").split(",")[0].strip(),
                _clean_genre_field(row.get(genre_col, "")) if genre_col else "",
                row.get(cover_col, "") or "" if cover_col else "",
                float(row[rating_col]) if rating_col and row.get(rating_col) else None,
            ))
        cursor.executemany(
            """INSERT OR REPLACE INTO books (id, title, author, genre, cover_url, avg_rating)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows_to_insert
        )
    conn.commit()
    conn.close()
    print(f"Loaded {len(rows_to_insert)} books.")
def load_ratings():
    ratings_path = os.path.join(DATA_DIR, "ratings.csv")
    if not os.path.exists(ratings_path):
        print(f"No ratings.csv found in {DATA_DIR}. Skipping ratings import "
              f"(this is fine if you only want book browsing/search for now).")
        return
    conn = get_connection()
    cursor = conn.cursor()
    with open(ratings_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        count = 0
        for row in reader:
            if MAX_RATINGS is not None and count >= MAX_RATINGS:
                break
            batch.append((int(row["user_id"]), int(row["book_id"]), int(row["rating"])))
            count += 1
        cursor.executemany(
            "INSERT INTO ratings (user_id, book_id, rating) VALUES (?, ?, ?)",
            batch
        )
    conn.commit()
    conn.close()
    print(f"Loaded {count} ratings"
          f"{' (capped by MAX_RATINGS)' if MAX_RATINGS else ''}.")
def reserve_user_id_range():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (id, name) VALUES (100000, '__seed__')")
    cursor.execute("DELETE FROM users WHERE id = 100000")
    conn.commit()
    conn.close()
if __name__ == "__main__":
    create_tables()
    load_books()
    reserve_user_id_range()
    load_ratings()
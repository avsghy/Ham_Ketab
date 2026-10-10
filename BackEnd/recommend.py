import math
from collections import Counter, defaultdict

from database import get_connection

DATASET_MAX_USER_ID = 100000
PERSIAN_MIN_ID = 90000

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
    "persian-literature": "ادبیات فارسی",
    "tragedy": "تراژدی",
    "satire": "طنز اجتماعی",
    "nonfiction": "غیرداستانی",
}


def _fa(genre):
    return GENRE_FA.get(genre, genre)


AUTHOR_ALIASES = {
    "صادق هدایت": "sadegh hedayat",
    "حافظ شیرازی": "hafez",
    "مولانا جلال‌الدین رومی": "jalaluddin rumi",
    "ژان-ژاک روسو": "jean-jacques rousseau",
    "جورج اورول": "george orwell",
    "گابریل گارسیا مارکز": "gabriel garcía márquez",
    "پائولو کوئیلو": "paulo coelho",
    "الیف شافاک": "elif shafak",
    "ویکتور فرانکل": "viktor e. frankl",
    "فئودور داستایفسکی": "fyodor dostoyevsky",
    "فرانتس کافکا": "franz kafka",
    "آلبر کامو": "albert camus",
    "ژان پل سارتر": "jean-paul sartre",
    "ویکتور هوگو": "victor hugo",
    "لئو تولستوی": "leo tolstoy",
    "فریدریش نیچه": "friedrich nietzsche",
    "آنتوان دو سنت اگزوپری": "antoine de saint-exupéry",
}


PARAMS = {
    "quality": 0.08,
    "popularity": 0.5,
    "cf_base": 0.2,
    "cf_per_rating": 0.05,
    "cf_max": 0.7,
    "content_genre": 0.5,
}

_STATE = {"books": None, "dataset": None}


def _split_genres(genre_string):
    if not genre_string:
        return []
    raw = [g.strip().strip("[]'\" ").lower() for g in genre_string.split(",") if g.strip()]
    return [g for g in raw if g and g not in GENRE_BLOCKLIST]


def _norm_author(author):
    name = (author or "").replace("\u200c", "\u200c").strip()
    key = name.lower()
    return AUTHOR_ALIASES.get(name, AUTHOR_ALIASES.get(key, key))


def _books_index():
    if _STATE["books"] is not None:
        return _STATE["books"]

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, author, genre, cover_url, avg_rating, description FROM books"
    ).fetchall()
    conn.close()

    books = {}
    meta = {}
    df = Counter()
    for row in rows:
        book = dict(row)
        genres = _split_genres(book["genre"])
        books[book["id"]] = book
        meta[book["id"]] = {"genres": genres, "author": _norm_author(book["author"])}
        df.update(set(genres))

    total = max(len(rows), 1)
    idf = {g: max(math.log(total / c), 0.1) for g, c in df.items()}

    _STATE["books"] = {"books": books, "meta": meta, "idf": idf}
    return _STATE["books"]


def _dataset_index():
    if _STATE["dataset"] is not None:
        return _STATE["dataset"]

    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, book_id, rating FROM ratings WHERE user_id <= ?",
        (DATASET_MAX_USER_ID,),
    ).fetchall()
    conn.close()

    user_items = defaultdict(dict)
    for row in rows:
        user_items[row["user_id"]][row["book_id"]] = row["rating"]

    item_raters = defaultdict(list)
    item_count = Counter()
    user_mean = {}
    for user, items in user_items.items():
        user_mean[user] = sum(items.values()) / len(items)
        for book_id, rating in items.items():
            item_raters[book_id].append((user, rating))
            item_count[book_id] += 1

    max_count = max(item_count.values()) if item_count else 1
    pop_norm = {b: math.log1p(n) / math.log1p(max_count) for b, n in item_count.items()}

    _STATE["dataset"] = {
        "pop_norm": pop_norm,
        "user_items": user_items,
        "item_raters": item_raters,
        "item_count": item_count,
        "user_mean": user_mean,
    }
    return _STATE["dataset"]


def _get_user_ratings(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT book_id, rating FROM ratings WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return {row["book_id"]: row["rating"] for row in rows}


def _other_app_users(exclude_user):
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, book_id, rating FROM ratings WHERE user_id > ? AND user_id != ?",
        (DATASET_MAX_USER_ID, exclude_user),
    ).fetchall()
    conn.close()
    users = defaultdict(dict)
    for row in rows:
        users[row["user_id"]][row["book_id"]] = row["rating"]
    return users


def _baseline(ratings):
    values = list(ratings.values())
    if len(values) >= 3 and len(set(values)) > 1:
        return sum(values) / len(values)
    return 3.0


def _content_scores(user_ratings, index):
    books, meta, idf = index["books"], index["meta"], index["idf"]

    profile = Counter()
    author_sum = Counter()
    for book_id, rating in user_ratings.items():
        info = meta.get(book_id)
        if not info:
            continue
        weight = rating - 3
        for genre in info["genres"]:
            profile[genre] += weight * idf[genre]
        if info["author"]:
            author_sum[info["author"]] += weight

    profile_norm = math.sqrt(sum(v * v for v in profile.values()))

    scores = {}
    for book_id, info in meta.items():
        if book_id in user_ratings:
            continue
        genre_part = 0.0
        if profile_norm > 0 and info["genres"]:
            dot = sum(profile.get(g, 0.0) * idf[g] for g in info["genres"])
            book_norm = math.sqrt(sum(idf[g] ** 2 for g in info["genres"]))
            genre_part = dot / (profile_norm * book_norm)
        author_part = 0.0
        if info["author"] and info["author"] in author_sum:
            author_part = math.tanh(author_sum[info["author"]] / 2.0)
        scores[book_id] = (genre_part, author_part)
    return scores, profile, author_sum


def _cf_scores(user_ratings, exclude_user, neighbors_k=60, shrink=3.0):
    data = _dataset_index()
    user_items = data["user_items"]
    item_raters = data["item_raters"]
    user_mean = data["user_mean"]

    extra_items = _other_app_users(exclude_user) if exclude_user is not None else {}
    extra_mean = {u: sum(items.values()) / len(items) for u, items in extra_items.items()}
    extra_by_item = defaultdict(list)
    for u, items in extra_items.items():
        for book_id, rating in items.items():
            extra_by_item[book_id].append((u, rating))

    base = _baseline(user_ratings)
    centered = {b: r - base for b, r in user_ratings.items()}

    dot = defaultdict(float)
    norm_v = defaultdict(float)
    norm_u = defaultdict(float)
    overlap = Counter()

    for book_id, cu in centered.items():
        for v, rv in item_raters.get(book_id, ()):
            if v == exclude_user:
                continue
            cv = rv - user_mean[v]
            dot[v] += cu * cv
            norm_v[v] += cv * cv
            norm_u[v] += cu * cu
            overlap[v] += 1
        for v, rv in extra_by_item.get(book_id, ()):
            cv = rv - extra_mean[v]
            key = ("app", v)
            dot[key] += cu * cv
            norm_v[key] += cv * cv
            norm_u[key] += cu * cu
            overlap[key] += 1

    sims = []
    for v, n in overlap.items():
        denom = math.sqrt(norm_u[v] * norm_v[v])
        if denom <= 0:
            continue
        sim = (dot[v] / denom) * (n / (n + shrink))
        if sim > 0.05:
            sims.append((sim, v))
    sims.sort(key=lambda item: item[0], reverse=True)
    sims = sims[:neighbors_k]
    if not sims:
        return {}, 0

    num = defaultdict(float)
    den = defaultdict(float)
    support = Counter()
    for sim, v in sims:
        if isinstance(v, tuple):
            items, mean = extra_items[v[1]], extra_mean[v[1]]
        else:
            items, mean = user_items[v], user_mean[v]
        for book_id, rating in items.items():
            if book_id in user_ratings:
                continue
            num[book_id] += sim * (rating - mean)
            den[book_id] += sim
            support[book_id] += 1

    scores = {}
    for book_id, n in num.items():
        if support[book_id] < 2:
            continue
        scores[book_id] = max(-1.0, min(1.0, (n / (den[book_id] + 0.5)) / 1.5))
    return scores, len(sims)


def _quality(book):
    avg = book.get("avg_rating") or 0
    if not avg:
        return 0.0
    return max(-1.0, min(1.0, (avg - 3.7) / 0.8))


def _liked_reference(candidate_id, user_ratings, index):
    meta, idf = index["meta"], index["idf"]
    cand = meta[candidate_id]
    cand_genres = set(cand["genres"])
    best, best_score = None, 0.0
    for book_id, rating in user_ratings.items():
        if rating < 4 or book_id not in meta:
            continue
        shared = cand_genres & set(meta[book_id]["genres"])
        if not shared:
            continue
        score = sum(idf[g] for g in shared) * (rating - 3)
        if cand["author"] and cand["author"] == meta[book_id]["author"]:
            score += 5
        if score > best_score:
            best, best_score = book_id, score
    return best


def _cf_weight(n_ratings, n_neighbors):
    if n_neighbors == 0:
        return 0.0
    return min(PARAMS["cf_max"], PARAMS["cf_base"] + PARAMS["cf_per_rating"] * n_ratings)


def _popularity(book_id):
    if book_id >= PERSIAN_MIN_ID:
        return 0.5
    return _dataset_index()["pop_norm"].get(book_id, 0.0)


def _rank(user_ratings, exclude_user=None):
    index = _books_index()
    books, meta = index["books"], index["meta"]

    content, profile, author_sum = _content_scores(user_ratings, index)
    cf, n_neighbors = _cf_scores(user_ratings, exclude_user)
    w = _cf_weight(len(user_ratings), n_neighbors)

    ranked = []
    for book_id, (genre_part, author_part) in content.items():
        if not meta[book_id]["genres"] and not meta[book_id]["author"]:
            continue
        gw = PARAMS["content_genre"]
        content_score = gw * genre_part + (1 - gw) * author_part
        cf_score = cf.get(book_id, 0.0)
        score = (
            (1 - w) * content_score
            + w * cf_score
            + PARAMS["quality"] * _quality(books[book_id])
            + PARAMS["popularity"] * _popularity(book_id)
        )
        ranked.append((score, book_id, genre_part, author_part, cf_score, w))
    ranked.sort(reverse=True)
    return ranked, index


def recommend_for_ratings(user_ratings, limit=8, exclude_user=None):
    ranked, index = _rank(user_ratings, exclude_user)
    books, meta = index["books"], index["meta"]

    picked, per_author = [], Counter()
    for score, book_id, genre_part, author_part, cf_score, w in ranked:
        if score <= 0.02:
            break
        author = meta[book_id]["author"]
        if author and per_author[author] >= 2:
            continue
        per_author[author] += 1
        picked.append((score, book_id, genre_part, author_part, cf_score, w))
        if len(picked) >= limit:
            break

    results = []
    for score, book_id, genre_part, author_part, cf_score, w in picked:
        results.append(
            {
                **books[book_id],
                "reason": _reason(book_id, genre_part, author_part, cf_score, w, user_ratings, index),
                "score": round(score, 4),
            }
        )
    return results


def _reason(book_id, genre_part, author_part, cf_score, w, user_ratings, index):
    books, meta = index["books"], index["meta"]
    gw = PARAMS["content_genre"]
    author_contrib = (1 - w) * (1 - gw) * author_part
    genre_contrib = (1 - w) * gw * genre_part
    cf_contrib = w * cf_score

    best = max(author_contrib, genre_contrib, cf_contrib)
    if best <= 0:
        return "کتابی پرامتیاز و محبوب"

    if best == author_contrib:
        return f"چون به کتاب‌های {books[book_id]['author']} امتیاز خوبی داده‌اید"

    if best == cf_contrib:
        return "خوانندگانی با سلیقه‌ی مشابه شما این کتاب را دوست داشته‌اند"

    ref = _liked_reference(book_id, user_ratings, index)
    if ref:
        return f"چون «{books[ref]['title']}» را دوست داشتید"

    shared = meta[book_id]["genres"][:1]
    if shared:
        return f"چون از کتاب‌های {_fa(shared[0])} لذت می‌برید"
    return "کتابی پرامتیاز و محبوب"


def _popular_fallback(limit):
    index = _books_index()
    books, meta = index["books"], index["meta"]
    counts = _dataset_index()["item_count"]

    def popularity(book):
        n = counts.get(book["id"], 0)
        return (book.get("avg_rating") or 0) * (n / (n + 25.0))

    persian = [b for b in books.values() if b["id"] >= PERSIAN_MIN_ID]
    general = [b for b in books.values() if b["id"] < PERSIAN_MIN_ID]

    persian_slots = max(1, limit // 4)
    top_general = sorted(general, key=popularity, reverse=True)[: limit - persian_slots]
    top_persian = sorted(persian, key=lambda b: b.get("avg_rating") or 0, reverse=True)[:persian_slots]

    results = [{**b, "reason": "محبوب بین خوانندگان"} for b in top_general]
    results += [{**b, "reason": "از شاهکارهای ادبیات فارسی"} for b in top_persian]
    return results


def get_recommendations(user_id, limit=8):
    user_ratings = _get_user_ratings(user_id)
    if not user_ratings:
        return _popular_fallback(limit)

    results = recommend_for_ratings(user_ratings, limit, exclude_user=user_id)
    if not results:
        return _popular_fallback(limit)
    return results


def get_taste_profile(user_id, top_n=6):
    user_ratings = _get_user_ratings(user_id)
    index = _books_index()
    meta = index["meta"]

    totals, counts = Counter(), Counter()
    for book_id, rating in user_ratings.items():
        info = meta.get(book_id)
        if not info:
            continue
        for genre in info["genres"]:
            totals[genre] += rating
            counts[genre] += 1

    if not counts:
        return []

    result = [
        {"genre": _fa(g), "percent": round(((totals[g] / counts[g] - 1) / 4) * 100), "n": counts[g]}
        for g in counts
    ]
    result.sort(key=lambda row: (row["percent"], row["n"]), reverse=True)
    return [{"genre": r["genre"], "percent": r["percent"]} for r in result[:top_n]]


def warm_up():
    _books_index()
    _dataset_index()

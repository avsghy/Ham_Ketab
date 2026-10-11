import math
import random
from collections import Counter, defaultdict

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

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

SVD_FACTORS = 64
SVD_MIN_RATINGS = 20

_STATE = {
    "books": None,
    "dataset": None,
    "svd": None,
    "item_sim": None,
}


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


def build_svd_model(factors=SVD_FACTORS):
    data = _dataset_index()
    user_items = data["user_items"]
    user_mean = data["user_mean"]
    if sum(len(v) for v in user_items.values()) < SVD_MIN_RATINGS:
        return None
    users = sorted(user_items.keys())
    items = sorted({b for u in user_items.values() for b in u})
    u_idx = {u: i for i, u in enumerate(users)}
    i_idx = {b: i for i, b in enumerate(items)}
    rows, cols, vals = [], [], []
    for u, items_r in user_items.items():
        mean = user_mean[u]
        for b, r in items_r.items():
            rows.append(u_idx[u])
            cols.append(i_idx[b])
            vals.append(r - mean)
    R = csr_matrix((vals, (rows, cols)), shape=(len(users), len(items)))
    k = min(factors, min(R.shape) - 1)
    if k < 2:
        return None
    U, sigma, Vt = svds(R.astype(np.float64), k=k)
    order = np.argsort(-sigma)
    sigma = sigma[order]
    U = U[:, order]
    Vt = Vt[order, :]
    model = {
        "users": users,
        "items": items,
        "u_idx": u_idx,
        "i_idx": i_idx,
        "user_factors": U * sigma,
        "item_factors": Vt.T,
        "user_mean": user_mean,
        "k": k,
    }
    _STATE["svd"] = model
    return model


def _cf_scores_svd(user_ratings, exclude_user):
    if _STATE["svd"] is None:
        build_svd_model()
    model = _STATE["svd"]
    if model is None:
        return _cf_scores_item_item(user_ratings, exclude_user)
    if exclude_user is None or exclude_user not in model["u_idx"]:
        return {}, 0
    u_vec = model["user_factors"][model["u_idx"][exclude_user]]
    mean = model["user_mean"][exclude_user]
    raw = model["item_factors"] @ u_vec + mean
    scores = {}
    for b, i in model["i_idx"].items():
        if b in user_ratings:
            continue
        scores[b] = float(max(-1.0, min(1.0, (raw[i] - 3.0) / 1.5)))
    return scores, len(scores)


def _build_item_sim(min_common=3, shrink=5.0):
    if _STATE["item_sim"] is not None:
        return _STATE["item_sim"]
    data = _dataset_index()
    item_raters = data["item_raters"]
    user_mean = data["user_mean"]
    centered = defaultdict(dict)
    for item, raters in item_raters.items():
        for u, r in raters:
            centered[item][u] = r - user_mean[u]
    norms = {i: math.sqrt(sum(v * v for v in rs.values())) for i, rs in centered.items()}
    items = list(centered.keys())
    sim_matrix = defaultdict(dict)
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            ra, rb = centered[a], centered[b]
            if len(ra) < min_common or len(rb) < min_common:
                continue
            common = ra.keys() & rb.keys()
            n = len(common)
            if n < min_common:
                continue
            dot = sum(ra[u] * rb[u] for u in common)
            denom = norms[a] * norms[b]
            if denom <= 0:
                continue
            sim = (dot / denom) * (n / (n + shrink))
            sim_matrix[a][b] = sim
            sim_matrix[b][a] = sim
    _STATE["item_sim"] = sim_matrix
    return sim_matrix


def _cf_scores_item_item(user_ratings, exclude_user):
    sim = _build_item_sim()
    data = _dataset_index()
    user_mean = data["user_mean"]
    if exclude_user is None or exclude_user not in user_mean:
        return {}, 0
    mean = user_mean[exclude_user]
    num = defaultdict(float)
    den = defaultdict(float)
    for b, r in user_ratings.items():
        neighbours = sim.get(b)
        if not neighbours:
            continue
        centered_r = r - mean
        for cand, s in neighbours.items():
            if cand in user_ratings:
                continue
            num[cand] += s * centered_r
            den[cand] += abs(s)
    scores = {}
    for cand, n in num.items():
        if den[cand] <= 0:
            continue
        scores[cand] = max(-1.0, min(1.0, n / (den[cand] + 0.5)))
    return scores, len(scores)


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
            if book_norm > 0:
                genre_part = dot / (profile_norm * book_norm)
        author_part = 0.0
        if info["author"] and info["author"] in author_sum:
            author_part = math.tanh(author_sum[info["author"]] / 2.0)
        scores[book_id] = (genre_part, author_part)
    return scores, profile, author_sum


def _cf_scores(user_ratings, exclude_user):
    return _cf_scores_svd(user_ratings, exclude_user)


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
    books = index["books"]
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
    build_svd_model()


def evaluate(holdout_ratio=0.2, k=10, n_users=200, seed=42):
    random.seed(seed)
    data = _dataset_index()
    users = [u for u, items in data["user_items"].items() if len(items) >= 5]
    random.shuffle(users)
    users = users[:n_users]
    recalls, precisions, ndcgs = [], [], []
    for user in users:
        items = dict(data["user_items"][user])
        rated = list(items.keys())
        random.shuffle(rated)
        cut = max(1, int(len(rated) * holdout_ratio))
        test_items = set(rated[:cut])
        train_items = {b: items[b] for b in rated[cut:]}
        if not train_items or not test_items:
            continue
        recs = recommend_for_ratings(train_items, limit=k, exclude_user=user)
        rec_ids = {r["id"] for r in recs}
        hits = rec_ids & test_items
        recalls.append(len(hits) / len(test_items))
        precisions.append(len(hits) / k)
        dcg = sum(1 / math.log2(i + 2) for i, r in enumerate(recs) if r["id"] in test_items)
        idcg = sum(1 / math.log2(i + 2) for i in range(min(len(test_items), k)))
        ndcgs.append(dcg / idcg if idcg else 0.0)
    if not recalls:
        return {"recall@k": 0.0, "precision@k": 0.0, "ndcg@k": 0.0}
    return {
        "recall@k": sum(recalls) / len(recalls),
        "precision@k": sum(precisions) / len(precisions),
        "ndcg@k": sum(ndcgs) / len(ndcgs),
    }


def tune_params(train_ratings, holdout_ratings, grid=None):
    if grid is None:
        grid = {
            "quality": [0.0, 0.08, 0.15],
            "popularity": [0.3, 0.5, 0.7],
            "cf_max": [0.5, 0.7, 0.9],
        }
    best = None
    keys = list(grid.keys())
    def rec(i, current):
        nonlocal best
        if i == len(keys):
            old = {k: PARAMS[k] for k in current}
            PARAMS.update(current)
            data = _dataset_index()
            recalls, ndcgs = [], []
            for user, items in holdout_ratings.items():
                recs = recommend_for_ratings(train_ratings.get(user, {}), limit=10, exclude_user=user)
                rec_ids = {r["id"] for r in recs}
                hits = rec_ids & set(items.keys())
                recalls.append(len(hits) / max(len(items), 1))
                dcg = sum(1 / math.log2(j + 2) for j, r in enumerate(recs) if r["id"] in items)
                idcg = sum(1 / math.log2(j + 2) for j in range(min(len(items), 10)))
                ndcgs.append(dcg / idcg if idcg else 0.0)
            score = (sum(ndcgs) / len(ndcgs)) if ndcgs else 0.0
            if best is None or score > best[0]:
                best = (score, dict(current))
            PARAMS.update(old)
            return
        for v in grid[keys[i]]:
            current[keys[i]] = v
            rec(i + 1, current)
    rec(0, {})
    if best:
        PARAMS.update(best[1])
    return best
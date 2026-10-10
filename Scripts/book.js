const GENRE_FA = {
  fantasy: "فانتزی",
  fiction: "داستانی",
  "science-fiction": "علمی-تخیلی",
  mystery: "معمایی",
  romance: "عاشقانه",
  "non-fiction": "غیرداستانی",
  classics: "کلاسیک",
  philosophy: "فلسفه",
  history: "تاریخ",
  "persian-literature": "ادبیات فارسی",
  "short-stories": "داستان کوتاه",
  tragedy: "تراژدی",
  satire: "طنز اجتماعی",
  "historical-fiction": "داستان تاریخی",
  adventure: "ماجراجویی",
  "young-adult": "ادبیات داستانی نوجوانان",
  poetry: "شعر",
  thriller: "دلهره آور",
  crime: "جنایی",
  suspense: "تعلیق",
  paranormal: "فراطبیعی",
  contemporary: "معاصر",
  nonfiction: "غیرداستانی",
  spirituality: "عارفانه",
  mysticism: "عرفان",
  anecdotes: "حکایت‌های کوتاه",
  bibliography: "کتاب‌شناسی",
  "chick-lit": "رمان زنانه",
  christian: "مسیحیت",
  comics: "کمیک",
  dystopian: "دیستوپیایی",
  epic: "حماسی",
  essays: "مقاله و جستار",
  ethics: "اخلاق",
  fable: "تمثیل",
  "gay-and-lesbian": "همجنس‌گرایی",
  historical: "تاریخی",
  "humor-and-comedy": "طنز و کمدی",
  inspirational: "الهام‌بخش",
  "magical-realism": "رئالیسم جادویی",
  manga: "مانگا",
  modern: "مدرن",
  music: "موسیقی",
  political: "سیاسی",
  "political-satire": "طنز سیاسی",
  social: "اجتماعی",
  surrealism: "سورئالیسم",
  "war-fiction": "داستان جنگی",
  art: "هنر",
  biography: "زندگینامه",
  business: "کسب و کار",
  "children's": "کودکان",
  cookbooks: "آشپزی",
  "graphic-novels": "رمان گرافیکی",
  horror: "وحشت",
  memoir: "خاطرات",
  psychology: "روانشناسی",
  religion: "دین",
  science: "علم",
  "self-help": "خودیاری",
  sports: "ورزش",
  travel: "سفر",
};
function faGenre(g) {
  return GENRE_FA[g] || g;
}
function getBookIdFromUrl() {
  return new URLSearchParams(window.location.search).get("id");
}
function renderGenreTags(genreString) {
  if (!genreString) return "";
  return genreString
    .split(",")
    .map((g) => g.trim())
    .filter(Boolean)
    .map((g) => `<span class="genre-tag">${escapeHtml(faGenre(g))}</span>`)
    .join("");
}
async function loadBook() {
  const bookId = getBookIdFromUrl();
  const container = document.getElementById("book-detail");
  if (!bookId) {
    container.innerHTML = `<p class="nobookerror">کتابی مشخص نشده است.</p>`;
    return;
  }
  let book;
  try {
    book = await apiJson(`/books/${bookId}`);
  } catch (error) {
    console.error(error);
    container.innerHTML =
      error.status === 404
        ? `<p class="nobookerror">این کتاب پیدا نشد.</p>`
        : `<p class="nobookerror">بارگذاری کتاب انجام نشد.</p>`;
    return;
  }
  let existingRating = 0;
  const session = getSession();
  if (session) {
    try {
      const ratings = await apiJson(`/ratings/${session.id}`);
      existingRating = ratings[String(book.id)] || 0;
    } catch (error) {
      console.error(error);
    }
  }
  document.title = `${book.title} — قفسه`;
  container.innerHTML = `
    <div class="book-detail-cover">${coverMarkup(book)}</div>
    <div class="book-detail-info">
      <h1 class="book-detail-title">${escapeHtml(book.title)}</h1>
      <p class="book-detail-author">${escapeHtml(book.author || "")}</p>
      <div class="genre-tags">${renderGenreTags(book.genre)}</div>
      <p class="book-detail-description">${escapeHtml(book.description || "توضیحی برای این کتاب موجود نیست.")}</p>
      <div class="rating-stars rating-stars-large" id="detail-stars" data-rating="${existingRating}" data-book-id="${book.id}">
        ${[1, 2, 3, 4, 5]
          .map((v) => `<span class="star" data-value="${v}">&#9733;</span>`)
          .join("")}
      </div>
    </div>
  `;
  paintStars(document.getElementById("detail-stars"), existingRating);
}
async function onRate(box, value, session) {
  const previous = parseInt(box.dataset.rating, 10) || 0;
  paintStars(box, value);
  box.dataset.rating = value;
  try {
    await submitRating(box.dataset.bookId, value, session);
  } catch (error) {
    console.error(error);
    paintStars(box, previous);
    box.dataset.rating = previous;
    if (error.status === 401) {
      clearSession();
      showToast(
        `نشست شما منقضی شده است. <a href="../index.html?login=1">دوباره وارد شوید</a>`,
        7000,
      );
    } else {
      showToast("ذخیره‌ی امتیاز انجام نشد. دوباره تلاش کنید.");
    }
  }
}
function onNeedLogin() {
  showToast(
    `برای امتیاز دادن ابتدا <a href="../index.html?login=1">وارد شوید</a>.`,
    7000,
  );
}
document.addEventListener("DOMContentLoaded", async () => {
  bindStarInteractions({ onRate, onNeedLogin });
  await loadBook();
});

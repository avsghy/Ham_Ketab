const API_BASE = "https://ham-ketab-1.onrender.com";
const PAGE_SIZE = 12;
let currentUserId = null;
let browseOffset = 0;
let activeGenre = "all";
let userRatings = {};
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}
function renderBookCard(book, reason) {
  return `
    <article class="book-card" data-book-id="${book.id}">
      <div class="book-cover">
        <img src="${book.cover_url || ""}" alt="${escapeHtml(book.title)}" />
      </div>
      <div class="book-info">
        <h3 class="book-title">${escapeHtml(book.title)}</h3>
        <p class="book-author">${escapeHtml(book.author || "")}</p>
        ${reason ? `<p class="book-reason">${escapeHtml(reason)}</p>` : ""}
        <div class="rating-stars" data-rating="0">
          ${[1, 2, 3, 4, 5]
            .map((v) => `<span class="star" data-value="${v}">&#9733;</span>`)
            .join("")}
        </div>
      </div>
    </article>
  `;
}
async function ensureUser() {
  const storedId = localStorage.getItem("userId");
  const storedName = localStorage.getItem("userName");
  if (storedId) {
    document.querySelector("#user-name").textContent = storedName;
    return storedId;
  }
  const name = window.prompt("اسمت چیه؟", "مهمان") || "مهمان";
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const user = await res.json();
  localStorage.setItem("userId", user.id);
  localStorage.setItem("userName", user.name);
  document.querySelector("#user-name").textContent = user.name;
  return user.id;
}
async function loadUserRatings() {
  const res = await fetch(`${API_BASE}/ratings/${currentUserId}`);
  userRatings = await res.json();
}
function applyStoredRatings(container) {
  container.querySelectorAll(".book-card").forEach((card) => {
    const bookId = card.dataset.bookId;
    const rating = userRatings[bookId];
    if (!rating) return;
    const starsContainer = card.querySelector(".rating-stars");
    starsContainer.dataset.rating = rating;
    starsContainer.querySelectorAll(".star").forEach((s) => {
      s.classList.toggle("filled", parseInt(s.dataset.value, 10) <= rating);
    });
  });
}
async function loadBrowseBooks(reset) {
  if (reset) browseOffset = 0;
  const genreParam =
    activeGenre !== "all" ? `&genre=${encodeURIComponent(activeGenre)}` : "";
  const res = await fetch(
    `${API_BASE}/books?limit=${PAGE_SIZE}&offset=${browseOffset}${genreParam}`,
  );
  const books = await res.json();
  const grid = document.querySelector("#browse-grid");
  if (reset) grid.innerHTML = "";
  grid.insertAdjacentHTML(
    "beforeend",
    books.map((b) => renderBookCard(b)).join(""),
  );
  browseOffset += books.length;
  applyStoredRatings(grid);
  document.querySelector("#load-more").hidden = books.length < PAGE_SIZE;
}
function handleGenreClick(event) {
  document
    .querySelectorAll(".genre-chip")
    .forEach((chip) => chip.classList.remove("active"));
  event.currentTarget.classList.add("active");
  activeGenre = event.currentTarget.dataset.genre;
  loadBrowseBooks(true);
}
function handleLoadMore() {
  loadBrowseBooks(false);
}
async function handleSearch(event) {
  event.preventDefault();
  const query = document.querySelector("#search-input").value.trim();
  if (!query) return;
  const res = await fetch(
    `${API_BASE}/books/search?q=${encodeURIComponent(query)}`,
  );
  const books = await res.json();
  document.querySelector("#search-query-text").textContent = query;
  const searchGrid = document.querySelector("#search-results-grid");
  searchGrid.innerHTML = books.map((b) => renderBookCard(b)).join("");
  applyStoredRatings(searchGrid);
  const section = document.querySelector("#search-results-section");
  const errornobook = section.querySelector(".nobookerror");
  if (searchGrid.childElementCount == 0) {
    if (errornobook) {
      errornobook.remove();
    }
    section.insertAdjacentHTML(
      "beforeend",
      `<p class="nobookerror">هیچ کتابی با این نام یافت نشد!</p>`,
    );
  } else {
    if (errornobook) {
      errornobook.remove();
    }
  }
  section.hidden = false;
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}
function handleStarClick(event) {
  const star = event.target.closest(".star");
  if (!star) return;
  const starsContainer = star.closest(".rating-stars");
  const card = star.closest(".book-card");
  const bookId = card.dataset.bookId;
  const value = parseInt(star.dataset.value, 10);
  starsContainer.querySelectorAll(".star").forEach((s) => {
    s.classList.toggle("filled", parseInt(s.dataset.value, 10) <= value);
  });
  starsContainer.dataset.rating = value;
  fetch(`${API_BASE}/rate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: parseInt(currentUserId, 10),
      book_id: parseInt(bookId, 10),
      rating: value,
    }),
  }).then(() => {
    userRatings[bookId] = value;
    loadRecommendations();
    loadTasteProfile();
  });
}
async function loadRecommendations() {
  const res = await fetch(`${API_BASE}/recommendations/${currentUserId}`);
  const books = await res.json();
  const grid = document.querySelector("#recommendations-grid");
  grid.innerHTML = books.map((b) => renderBookCard(b, b.reason)).join("");
  applyStoredRatings(grid);
}
async function loadTasteProfile() {
  const res = await fetch(`${API_BASE}/taste/${currentUserId}`);
  const genres = await res.json();
  const container = document.querySelector("#taste-bars");
  if (!genres.length) {
    container.innerHTML = `<p class="section-sub">چند کتاب را امتیاز دهید تا سلیقه شما نمایش داده شود.</p>`;
    return;
  }
  container.innerHTML = genres
    .map(
      (g) => `
      <div class="taste-row">
        <span class="taste-label">${escapeHtml(g.genre)}</span>
        <div class="taste-track"><div class="taste-fill" style="width: ${g.percent}%;"></div></div>
        <span class="taste-value">${g.percent}%</span>
      </div>
    `,
    )
    .join("");
}
document.addEventListener("DOMContentLoaded", async () => {
  currentUserId = await ensureUser();
  await loadUserRatings();
  await loadBrowseBooks(true);
  await loadRecommendations();
  await loadTasteProfile();
  document
    .querySelector("#search-form")
    .addEventListener("submit", handleSearch);
  document
    .querySelector("#load-more")
    .addEventListener("click", handleLoadMore);
  document
    .querySelectorAll(".genre-chip")
    .forEach((chip) => chip.addEventListener("click", handleGenreClick));
  document.addEventListener("click", handleStarClick);
});
function waitForImages(container) {
  const imgs = Array.from(container.querySelectorAll("img"));
  return Promise.all(
    imgs.map((img) => {
      if (img.complete) return Promise.resolve();
      return new Promise((resolve) => {
        img.addEventListener("load", resolve, { once: true });
        img.addEventListener("error", resolve, { once: true });
      });
    }),
  );
}
function handleStarHover(event) {
  const star = event.target.closest(".star");
  if (!star) return;
  const starsContainer = star.closest(".rating-stars");
  paintStars(starsContainer, parseInt(star.dataset.value, 10));
}
function handleStarHoverEnd(event) {
  const star = event.target.closest(".star");
  if (!star) return;
  const starsContainer = star.closest(".rating-stars");
  if (starsContainer.contains(event.relatedTarget)) return;
  const savedValue = parseInt(starsContainer.dataset.rating, 10) || 0;
  paintStars(starsContainer, savedValue);
}
document.addEventListener("DOMContentLoaded", async () => {
  currentUserId = await ensureUser();
  await loadUserRatings();
  await loadBrowseBooks(true);
  await loadRecommendations();
  await loadTasteProfile();
  await waitForImages(document.querySelector("#browse-grid"));
  await waitForImages(document.querySelector("#recommendations-grid"));
  const loader = document.getElementById("page-loader");
  if (loader) loader.classList.add("loaded");
  document
    .querySelector("#search-form")
    .addEventListener("submit", handleSearch);
  document
    .querySelector("#load-more")
    .addEventListener("click", handleLoadMore);
  document
    .querySelectorAll(".genre-chip")
    .forEach((chip) => chip.addEventListener("click", handleGenreClick));
  document.addEventListener("click", handleStarClick);
  document.addEventListener("mouseover", handleStarHover);
  document.addEventListener("mouseout", handleStarHoverEnd);
});
setTimeout(function () {
  const loader = document.getElementById("page-loader");
  if (loader && !loader.classList.contains("loaded")) {
    loader.classList.add("loaded");
  }
}, 6500);

const PAGE_SIZE = 12;
const NEED_LOGIN_NOTICE =
  "برای امتیاز دادن به کتاب‌ها ابتدا وارد حساب کاربری خود شوید یا ثبت‌نام کنید.";
let browseOffset = 0;
let activeGenre = "all";
let userRatings = {};
let authMode = "login";
let authSubmitting = false;
let refreshTimer = null;
const PASSWORD_RULES = [
  { test: (p) => p.length >= 8, msg: "حداقل ۸ کاراکتر" },
  { test: (p) => /[a-z]/.test(p), msg: "حداقل یک حرف کوچک انگلیسی" },
  { test: (p) => /[A-Z]/.test(p), msg: "حداقل یک حرف بزرگ انگلیسی" },
  { test: (p) => /[0-9]/.test(p), msg: "حداقل یک عدد" },
  {
    test: (p) => /[^A-Za-z0-9]/.test(p),
    msg: "حداقل یک کاراکتر ویژه (!@#$%^&*…)",
  },
  { test: (p) => !/\s/.test(p), msg: "بدون فاصله یا کاراکتر خالی" },
];
const NAME_RULES = [
  { test: (n) => n.length >= 3, msg: "نام کاربری حداقل ۳ کاراکتر" },
  { test: (n) => n.length <= 30, msg: "نام کاربری حداکثر ۳۰ کاراکتر" },
  {
    test: (n) => /^[\w\u0600-\u06FF .-]+$/.test(n),
    msg: "فقط حروف، عدد، فاصله، نقطه، خط تیره",
  },
];
function validatePassword(pw) {
  for (const rule of PASSWORD_RULES) {
    if (!rule.test(pw)) return rule.msg;
  }
  return null;
}
function validateName(name) {
  for (const rule of NAME_RULES) {
    if (!rule.test(name)) return rule.msg;
  }
  return null;
}
function renderBookCard(book, reason) {
  return `
    <article class="book-card" data-book-id="${book.id}">
      <a class="book-link" href="Pages/book.html?id=${book.id}">
        ${coverMarkup(book)}
        <h3 class="book-title">${escapeHtml(book.title)}</h3>
        <p class="book-author">${escapeHtml(book.author || "")}</p>
      </a>
      ${reason ? `<p class="book-reason">${escapeHtml(reason)}</p>` : ""}
      <div class="rating-stars" data-rating="0">
        ${[1, 2, 3, 4, 5]
          .map((v) => `<span class="star" data-value="${v}">&#9733;</span>`)
          .join("")}
      </div>
    </article>
  `;
}
function gridMessage(text) {
  return `<p class="section-sub grid-message">${text}</p>`;
}
function showAuthModal() {
  document.querySelector("#auth-modal").classList.add("show");
}
function hideAuthModal() {
  document.querySelector("#auth-modal").classList.remove("show");
}
function setAuthError(message) {
  const el = document.querySelector("#auth-error");
  el.hidden = !message;
  el.textContent = message || "";
}
function setAuthNotice(message) {
  const el = document.querySelector("#auth-notice");
  el.hidden = !message;
  el.textContent = message || "";
}
function setAuthMode(mode) {
  authMode = mode;
  setAuthError("");
  const title = document.querySelector("#auth-title");
  const submit = document.querySelector("#auth-submit");
  const toggleText = document.querySelector("#auth-toggle-text");
  const toggleLink = document.querySelector("#auth-toggle-link");
  if (mode === "signup") {
    title.textContent = "ثبت‌نام";
    submit.textContent = "ثبت‌نام";
    toggleText.textContent = "حساب کاربری داری؟ ";
    toggleLink.textContent = "وارد شو";
  } else {
    title.textContent = "ورود";
    submit.textContent = "ورود";
    toggleText.textContent = "حساب کاربری نداری؟ ";
    toggleLink.textContent = "ثبت‌نام کن";
  }
}
function toggleAuthMode(event) {
  event.preventDefault();
  setAuthMode(authMode === "login" ? "signup" : "login");
}
function openAuth(notice) {
  setAuthError("");
  setAuthNotice(notice || "");
  showAuthModal();
  document.querySelector("#auth-username").focus();
}
function resetAuthForm() {
  document.querySelector("#auth-username").value = "";
  const pw = document.querySelector("#auth-password");
  pw.value = "";
  pw.type = "password";
  document.querySelector("#toggle-password").textContent = "🔒";
  setAuthError("");
  setAuthNotice("");
  setAuthMode("login");
}
function friendlyAuthError(status, detail) {
  if (status === 404) {
    return "سرور در دسترس نیست یا هنوز به‌روزرسانی نشده است (۴۰۴). کمی بعد دوباره تلاش کنید.";
  }
  if (status >= 500) return "خطایی در سرور رخ داد. کمی بعد دوباره تلاش کنید.";
  return detail || `خطا (${status})`;
}
async function handleAuthSubmit() {
  if (authSubmitting) return;
  const name = document.querySelector("#auth-username").value.trim();
  const password = document.querySelector("#auth-password").value;
  if (!name || !password) {
    setAuthError("لطفاً نام کاربری و رمز عبور را وارد کنید.");
    return;
  }
  const nameError = validateName(name);
  if (nameError) {
    setAuthError(nameError);
    return;
  }
  if (authMode === "signup") {
    const pwError = validatePassword(password);
    if (pwError) {
      setAuthError(`رمز عبور نامعتبر است: ${pwError}`);
      return;
    }
  }
  const submitBtn = document.querySelector("#auth-submit");
  const originalLabel = submitBtn.textContent;
  authSubmitting = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "لطفاً صبر کنید…";
  try {
    const user = await apiJson(
      authMode === "signup" ? "/signup" : "/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, password }),
      },
      { retries: 1 },
    );
    if (!user || !user.id || !user.token) {
      setAuthError("پاسخ سرور نامعتبر بود. نسخه‌ی بک‌اند را بررسی کنید.");
      return;
    }
    saveSession(user);
    hideAuthModal();
    resetAuthForm();
    renderAuthState();
    await refreshPersonal();
  } catch (error) {
    console.error(error);
    if (error.status) {
      setAuthError(friendlyAuthError(error.status, error.message));
    } else {
      setAuthError("ارتباط با سرور برقرار نشد.");
    }
  } finally {
    authSubmitting = false;
    submitBtn.disabled = false;
    submitBtn.textContent = originalLabel;
  }
}
function handleTogglePassword() {
  const pwInput = document.querySelector("#auth-password");
  const btn = document.querySelector("#toggle-password");
  const showing = pwInput.type === "text";
  pwInput.type = showing ? "password" : "text";
  btn.textContent = showing ? "🔒" : "🔓";
  btn.setAttribute(
    "aria-label",
    showing ? "نمایش رمز عبور" : "پنهان کردن رمز عبور",
  );
  pwInput.focus();
}
function handleLogout() {
  clearSession();
  window.location.reload();
}
function renderAuthState() {
  const session = getSession();
  document.querySelector("#login-btn").hidden = Boolean(session);
  document.querySelector("#logout-btn").hidden = !session;
  const nameEl = document.querySelector("#user-name");
  nameEl.hidden = !session;
  nameEl.textContent = session ? session.name : "";
}
function applyStoredRatings(container) {
  container.querySelectorAll(".book-card").forEach((card) => {
    const rating = userRatings[card.dataset.bookId];
    if (!rating) return;
    const starsContainer = card.querySelector(".rating-stars");
    starsContainer.dataset.rating = rating;
    paintStars(starsContainer, rating);
  });
}
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
async function loadBrowseBooks(reset) {
  if (reset) browseOffset = 0;
  const grid = document.querySelector("#browse-grid");
  const genreParam =
    activeGenre !== "all" ? `&genre=${encodeURIComponent(activeGenre)}` : "";
  try {
    const books = await apiJson(
      `/books?limit=${PAGE_SIZE}&offset=${browseOffset}${genreParam}`,
    );
    if (reset) grid.innerHTML = "";
    if (reset && books.length === 0) {
      grid.innerHTML = gridMessage("کتابی در این دسته پیدا نشد.");
    }
    grid.insertAdjacentHTML(
      "beforeend",
      books.map((b) => renderBookCard(b)).join(""),
    );
    browseOffset += books.length;
    applyStoredRatings(grid);
    document.querySelector("#load-more").hidden = books.length < PAGE_SIZE;
  } catch (error) {
    console.error(error);
    if (reset) grid.innerHTML = gridMessage("بارگذاری کتاب‌ها انجام نشد.");
    else showToast("بارگذاری کتاب‌های بیشتر انجام نشد.");
  }
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
  let books;
  try {
    books = await apiJson(`/books/search?q=${encodeURIComponent(query)}`);
  } catch (error) {
    console.error(error);
    showToast("جستجو انجام نشد. دوباره تلاش کنید.");
    return;
  }
  document.querySelector("#search-query-text").textContent = query;
  const searchGrid = document.querySelector("#search-results-grid");
  searchGrid.innerHTML = books.map((b) => renderBookCard(b)).join("");
  applyStoredRatings(searchGrid);
  const section = document.querySelector("#search-results-section");
  const errornobook = section.querySelector(".nobookerror");
  if (errornobook) errornobook.remove();
  if (searchGrid.childElementCount === 0) {
    section.insertAdjacentHTML(
      "beforeend",
      `<p class="nobookerror">هیچ کتابی با این نام یافت نشد!</p>`,
    );
  }
  section.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}
async function loadRecommendations() {
  const session = getSession();
  const grid = document.querySelector("#recommendations-grid");
  const title = document.querySelector("#reco-title");
  const sub = document.querySelector("#reco-sub");
  if (!session) {
    title.textContent = "محبوب‌ترین کتاب‌ها";
    sub.textContent =
      "برای دریافت پیشنهاد اختصاصی، وارد شوید و به چند کتاب امتیاز بدهید";
  } else if (Object.keys(userRatings).length === 0) {
    title.textContent = "محبوب‌ترین کتاب‌ها";
    sub.textContent =
      "هنوز به کتابی امتیاز نداده‌اید؛ با امتیاز دادن، پیشنهادها اختصاصی می‌شوند";
  } else {
    title.textContent = "پیشنهاد شده برای شما";
    sub.textContent = "بر اساس امتیازها و سلیقه‌ی شما و خوانندگان مشابه";
  }
  try {
    const books = await apiJson(`/recommendations/${session ? session.id : 0}`);
    grid.innerHTML = books.map((b) => renderBookCard(b, b.reason)).join("");
    applyStoredRatings(grid);
  } catch (error) {
    console.error(error);
    grid.innerHTML = gridMessage("بارگذاری پیشنهادها انجام نشد.");
  }
}
async function loadTasteProfile() {
  const session = getSession();
  const container = document.querySelector("#taste-bars");
  if (!session) {
    container.innerHTML = `<p class="section-sub">برای دیدن سلیقه‌ی خود، <a href="#" data-open-login>وارد شوید</a>.</p>`;
    return;
  }
  try {
    const genres = await apiJson(`/taste/${session.id}`);
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
  } catch (error) {
    console.error(error);
    container.innerHTML = `<p class="section-sub">بارگذاری سلیقه انجام نشد.</p>`;
  }
}
async function refreshPersonal() {
  const session = getSession();
  userRatings = {};
  if (session) {
    try {
      userRatings = await apiJson(`/ratings/${session.id}`);
    } catch (error) {
      console.error(error);
    }
  }
  applyStoredRatings(document);
  await Promise.all([loadRecommendations(), loadTasteProfile()]);
}
function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => {
    loadRecommendations();
    loadTasteProfile();
  }, 600);
}
async function onRate(box, value, session) {
  const bookId = box.closest(".book-card").dataset.bookId;
  const previous = userRatings[bookId] || 0;
  paintStars(box, value);
  box.dataset.rating = value;
  try {
    await submitRating(bookId, value, session);
    userRatings[bookId] = value;
    applyStoredRatings(document);
    scheduleRefresh();
  } catch (error) {
    console.error(error);
    paintStars(box, previous);
    box.dataset.rating = previous;
    if (error.status === 401) {
      clearSession();
      renderAuthState();
      openAuth("نشست شما منقضی شده است؛ لطفاً دوباره وارد شوید.");
    } else {
      showToast("ذخیره‌ی امتیاز انجام نشد. دوباره تلاش کنید.");
    }
  }
}
function hideLoader() {
  const loader = document.querySelector("#page-loader");
  if (loader) loader.classList.add("loaded");
}
function bindStaticListeners() {
  document
    .querySelector("#search-form")
    .addEventListener("submit", handleSearch);
  document
    .querySelector("#load-more")
    .addEventListener("click", handleLoadMore);
  document
    .querySelectorAll(".genre-chip")
    .forEach((chip) => chip.addEventListener("click", handleGenreClick));
  document
    .querySelector("#login-btn")
    .addEventListener("click", () => openAuth());
  document.querySelector("#logout-btn").addEventListener("click", handleLogout);
  document
    .querySelector("#auth-submit")
    .addEventListener("click", handleAuthSubmit);
  document
    .querySelector("#auth-toggle-link")
    .addEventListener("click", toggleAuthMode);
  document
    .querySelector("#toggle-password")
    .addEventListener("click", handleTogglePassword);
  ["#auth-username", "#auth-password"].forEach((selector) => {
    document.querySelector(selector).addEventListener("keydown", (event) => {
      if (event.key === "Enter") handleAuthSubmit();
    });
  });
  document.querySelector("#auth-modal").addEventListener("click", (event) => {
    if (event.target.id === "auth-modal") hideAuthModal();
  });
  document.addEventListener("keyup", (event) => {
    if (event.key === "Escape") hideAuthModal();
  });
  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open-login]");
    if (!opener) return;
    event.preventDefault();
    openAuth();
  });
  bindStarInteractions({
    onRate,
    onNeedLogin: () => openAuth(NEED_LOGIN_NOTICE),
  });
}
async function init() {
  bindStaticListeners();
  renderAuthState();
  if (
    new URLSearchParams(window.location.search).has("login") &&
    !getSession()
  ) {
    openAuth();
  }
  try {
    const session = getSession();
    if (session) {
      try {
        userRatings = await apiJson(`/ratings/${session.id}`);
      } catch (error) {
        console.error(error);
      }
    }
    await Promise.all([
      loadBrowseBooks(true),
      loadRecommendations(),
      loadTasteProfile(),
    ]);
    await Promise.all([
      waitForImages(document.querySelector("#browse-grid")),
      waitForImages(document.querySelector("#recommendations-grid")),
    ]);
  } catch (error) {
    console.error(error);
  } finally {
    hideLoader();
  }
}
document.addEventListener("DOMContentLoaded", init);
setTimeout(hideLoader, 6500);
console.log(
  `%c
  ░██     ░██                                    ░██     ░██               ░██               ░██        
  ░██     ░██                                    ░██    ░██                ░██               ░██        
  ░██     ░██  ░██████   ░█████████████          ░██   ░██    ░███████  ░████████  ░██████   ░████████  
  ░██████████       ░██  ░██   ░██   ░██ ░██████ ░███████    ░██    ░██    ░██          ░██  ░██    ░██ 
  ░██     ░██  ░███████  ░██   ░██   ░██         ░██   ░██   ░█████████    ░██     ░███████  ░██    ░██ 
  ░██     ░██ ░██   ░██  ░██   ░██   ░██         ░██    ░██  ░██           ░██    ░██   ░██  ░███   ░██ 
  ░██     ░██  ░█████░██ ░██   ░██   ░██         ░██     ░██  ░███████      ░████  ░█████░██ ░██░█████  
                                                                                                        
                                                                                                        
                                                                                                         `,
  "color: #6366f1;",
);
console.log(`%c Made With ❤️`, "font-size=25px; dir:rtl");

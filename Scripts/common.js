const API_BASE = "https://ham-ketab-1.onrender.com";
const LOGIN_TIP = "برای امتیاز دادن ابتدا وارد شوید";

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function getSession() {
  const id = localStorage.getItem("userId");
  const token = localStorage.getItem("userToken");
  if (!id || !token) {
    if (id || token) clearSession();
    return null;
  }
  return {
    id: parseInt(id, 10),
    name: localStorage.getItem("userName") || "",
    token,
  };
}

function saveSession(user) {
  localStorage.setItem("userId", user.id);
  localStorage.setItem("userName", user.name);
  localStorage.setItem("userToken", user.token);
}

function clearSession() {
  localStorage.removeItem("userId");
  localStorage.removeItem("userName");
  localStorage.removeItem("userToken");
}

function paintStars(starsContainer, value) {
  starsContainer.querySelectorAll(".star").forEach((s) => {
    s.classList.toggle("filled", parseInt(s.dataset.value, 10) <= value);
  });
}

function coverMarkup(book) {
  const hasCover = Boolean(book.cover_url);
  const image = hasCover
    ? `<img src="${escapeHtml(book.cover_url)}" alt="${escapeHtml(book.title)}" onerror="this.parentElement.classList.add('no-cover');this.remove()" />`
    : "";
  return `<div class="book-cover${hasCover ? "" : " no-cover"}">${image}<span class="cover-fallback">${escapeHtml(book.title)}</span></div>`;
}

let serverBanner = null;

function showServerStatus(kind) {
  if (!serverBanner) {
    serverBanner = document.createElement("div");
    document.body.appendChild(serverBanner);
  }
  if (kind === "loading") {
    serverBanner.className = "server-status show";
    serverBanner.textContent =
      "در حال اتصال به سرور… سرور رایگان است و بعد از مدتی بیکاری ممکن است تا یک دقیقه طول بکشد.";
    return;
  }
  serverBanner.className = "server-status show error";
  serverBanner.innerHTML =
    "ارتباط با سرور برقرار نشد. <button type='button' class='server-retry'>تلاش دوباره</button>";
  serverBanner
    .querySelector(".server-retry")
    .addEventListener("click", () => window.location.reload());
}

function hideServerStatus() {
  if (serverBanner) serverBanner.className = "server-status";
}

const RETRYABLE_STATUS = [502, 503, 504];

async function apiFetch(path, options = {}, config = {}) {
  const retries = config.retries ?? 2;
  const timeout = config.timeout ?? 70000;
  let lastError = new Error("network");

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const abortTimer = setTimeout(() => controller.abort(), timeout);
    const slowTimer = setTimeout(() => showServerStatus("loading"), 3000);
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        signal: controller.signal,
      });
      if (RETRYABLE_STATUS.includes(res.status) && attempt < retries) {
        lastError = new Error(`status ${res.status}`);
      } else {
        hideServerStatus();
        return res;
      }
    } catch (error) {
      lastError = error;
    } finally {
      clearTimeout(abortTimer);
      clearTimeout(slowTimer);
    }
    if (attempt < retries) {
      await new Promise((resolve) => setTimeout(resolve, 1500 * (attempt + 1)));
    }
  }

  showServerStatus("error");
  throw lastError;
}

async function apiJson(path, options = {}, config = {}) {
  const res = await apiFetch(path, options, config);
  let data = null;
  if ((res.headers.get("content-type") || "").includes("application/json")) {
    data = await res.json();
  }
  if (!res.ok) {
    const error = new Error((data && data.detail) || `status ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return data;
}

async function submitRating(bookId, value, session) {
  const res = await apiFetch(
    "/rate",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.token}`,
      },
      body: JSON.stringify({
        user_id: session.id,
        book_id: parseInt(bookId, 10),
        rating: value,
      }),
    },
    { retries: 1 },
  );
  if (!res.ok) {
    const error = new Error(`rate failed ${res.status}`);
    error.status = res.status;
    throw error;
  }
}

let loginTooltip = null;

function showLoginTooltip(anchor) {
  if (!loginTooltip) {
    loginTooltip = document.createElement("div");
    loginTooltip.className = "login-tooltip";
    loginTooltip.setAttribute("role", "tooltip");
    loginTooltip.textContent = LOGIN_TIP;
    document.body.appendChild(loginTooltip);
  }
  const rect = anchor.getBoundingClientRect();
  loginTooltip.style.left = `${rect.left + rect.width / 2}px`;
  loginTooltip.style.top = `${rect.top}px`;
  loginTooltip.classList.add("show");
}

function hideLoginTooltip() {
  if (loginTooltip) loginTooltip.classList.remove("show");
}

let toastTimer = null;

function showToast(html, duration = 3500) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.innerHTML = html;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), duration);
}

function bindStarInteractions({ onRate, onNeedLogin }) {
  document.addEventListener("mouseover", (event) => {
    const star = event.target.closest(".star");
    if (!star) return;
    const box = star.closest(".rating-stars");
    if (!getSession()) {
      showLoginTooltip(box);
      return;
    }
    paintStars(box, parseInt(star.dataset.value, 10));
  });

  document.addEventListener(
    "mouseleave",
    (event) => {
      const target = event.target;
      if (!target.classList || !target.classList.contains("rating-stars")) return;
      hideLoginTooltip();
      paintStars(target, parseInt(target.dataset.rating, 10) || 0);
    },
    true,
  );

  document.addEventListener("click", (event) => {
    const star = event.target.closest(".star");
    if (!star) return;
    const box = star.closest(".rating-stars");
    const session = getSession();
    if (!session) {
      showLoginTooltip(box);
      onNeedLogin();
      return;
    }
    onRate(box, parseInt(star.dataset.value, 10), session);
  });
}

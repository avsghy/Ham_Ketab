const darkbtn = document.querySelector(".darkmode");
const body = document.querySelector("body");
const logoimg = document.querySelector(".logoimage");
const savedtheme = localStorage.getItem("theme");
function darkmode() {
  if (!body.classList.contains("dark")) {
    localStorage.setItem("theme", "dark");
    body.classList.add("dark");
    logoimg.src = "Logo/darkmode.png";
    darkbtn.textContent = "☀️";
  } else {
    localStorage.setItem("theme", "light");
    body.classList.remove("dark");
    logoimg.src = "Logo/Logo.png";
    darkbtn.textContent = "🌙";
  }
}
if (savedtheme == "dark") {
  body.classList.add("dark");
  logoimg.src = "Logo/darkmode.png";
  darkbtn.textContent = "☀️";
} else {
  body.classList.remove("dark");
  logoimg.src = "Logo/Logo.png";
  darkbtn.textContent = "🌙";
}
darkbtn.addEventListener("click", darkmode);

const darkbtn = document.querySelector(".darkmode");
const body = document.querySelector("body");
const logoimg = document.querySelector(".logoimage");
const savedtheme = localStorage.getItem("theme");
function darkmode() {
  if (!body.classList.contains("dark")) {
    localStorage.setItem("theme", "dark");
    body.classList.add("dark");
    logoimg.src = "Logo/darkmode.png";
    darkbtn ? (darkbtn.textContent = "☀️") : null;
  } else {
    localStorage.setItem("theme", "light");
    body.classList.remove("dark");
    logoimg ? (logoimg.src = "Logo/Logo.png") : null;
    darkbtn ? (darkbtn.textContent = "🌙") : null;
  }
}
if (savedtheme == "dark") {
  body.classList.add("dark");
  logoimg.src = "Logo/darkmode.png";
  darkbtn ? (darkbtn.textContent = "☀️") : null;
} else {
  body.classList.remove("dark");
  logoimg ? (logoimg.src = "Logo/Logo.png") : null;
  darkbtn ? (darkbtn.textContent = "🌙") : null;
}
darkbtn ? darkbtn.addEventListener("click", darkmode) : null;

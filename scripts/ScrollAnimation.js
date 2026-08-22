const scrollbar = document.querySelector(".scrolled");
window.addEventListener("scroll", function () {
  const scrolltop = document.documentElement.scrollTop;
  const docheight = document.documentElement.scrollHeight;
  const windowheight = window.innerHeight;
  const scrollable = docheight - windowheight;
  const scrollvalue = scrollable > 0 ? scrolltop / scrollable : 0;
  const percentscrollvalue = Math.floor(scrollvalue * 100);
  scrollbar.style.width = `${percentscrollvalue}%`;
});

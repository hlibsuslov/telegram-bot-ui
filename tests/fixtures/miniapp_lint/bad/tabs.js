// MA46: never decides how it opens; MA47: hides the tab bar and pushes no layer
const tg = window.Telegram.WebApp;
function openDetail() {
  document.getElementById('tabbar').hidden = true;
}
document.querySelector('[role=tab]').addEventListener('click', openDetail);

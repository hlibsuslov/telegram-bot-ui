const tg = window.Telegram.WebApp;
const token = process.env.BOT_TOKEN;
tg.MainButton.setText('Pay 💳');
document.querySelector('.go').addEventListener('click', () => tg.requestFullscreen());

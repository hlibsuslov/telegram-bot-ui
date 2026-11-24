const tg = window.Telegram.WebApp;
fetch('/api/me', { method: 'POST', body: JSON.stringify({ user: tg.initDataUnsafe.user }) });

const tg = window.Telegram.WebApp;
window.addEventListener('scroll', () => { tg.HapticFeedback.selectionChanged(); });
if (tg.isVersionAtLeast('8.0')) tg.Accelerometer.start({ refresh_rate: 20 });

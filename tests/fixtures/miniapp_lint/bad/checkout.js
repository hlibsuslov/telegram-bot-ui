const tg = window.Telegram.WebApp;
async function buy(items) {
  const res = await fetch('/api/checkout', { method: 'POST', body: JSON.stringify({ items, total: 840 }) });
  tg.openInvoice((await res.json()).link, (status) => { if (status === 'paid') unlockPremium(); });
}

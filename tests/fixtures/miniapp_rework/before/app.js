// Generated "gym booking" app logic: the starting point of the rework walkthrough. Deliberately web-style.
const tg = window.Telegram && window.Telegram.WebApp;
const CLASSES = [
  { id: 'hiit', title: 'HIIT Blast', time: '07:00', trainer: 'Mira', price: 120, img: 'class.svg', spots: 3 },
  { id: 'yoga', title: 'Morning Yoga', time: '08:30', trainer: 'Leo', price: 90, img: 'class.svg', spots: 0 },
  { id: 'box', title: 'Boxing Basics', time: '18:00', trainer: 'Sam', price: 150, img: 'class.svg', spots: 8 },
];
const TRAINERS = [{ name: 'Mira', tag: 'Strength' }, { name: 'Leo', tag: 'Yoga' }, { name: 'Sam', tag: 'Boxing' }];
let selected = null;

document.getElementById('class-grid').innerHTML = CLASSES.map((c) => `
  <div class="class-card" onclick="pick('${c.id}')">
    <img src="${c.img}">
    <b>${c.title}</b>
    <span class="price-pill">${c.price} XTR</span>
    <div class="more">${c.time} · ${c.trainer} · ${c.spots} spots</div>
  </div>`).join('');
document.getElementById('trainer-row').innerHTML = TRAINERS.map((t) => `
  <div class="trainer"><img src="avatar.svg"><div>${t.name} <span class="verified-badge">✔</span></div><small>${t.tag}</small></div>`).join('');

function pick(id) {
  selected = CLASSES.find((c) => c.id === id);
  localStorage.setItem('lastClass', id);
  alert('Selected ' + selected.title + '! 🎉');
}

document.getElementById('burger').onclick = () => document.getElementById('drawer').classList.toggle('open');
document.getElementById('notif').onchange = (e) => localStorage.setItem('notif', e.target.checked);
if (tg && tg.initDataUnsafe.user) document.getElementById('name').textContent = tg.initDataUnsafe.user.first_name;

document.getElementById('book').onclick = async () => {
  if (!selected) return alert('Pick a class first!');
  if (!confirm('Book ' + selected.title + ' for ' + selected.price + ' XTR?')) return;
  const res = await fetch('/api/checkout', { method: 'POST', body: JSON.stringify({ classId: selected.id, price: selected.price, user: tg.initDataUnsafe.user }) });
  const { link } = await res.json();
  tg.openInvoice(link, (status) => { if (status === 'paid') { alert('Booked! 💪'); document.body.classList.add('member'); } });
};

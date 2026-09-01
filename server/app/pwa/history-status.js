(() => {
  'use strict';

  const list = document.getElementById('history-list');
  if (!list) return;

  const style = document.createElement('style');
  style.textContent = `
    #history-list .pill.denied{background:#fee4e2!important;color:#b42318!important;border:1px solid #f97066!important}
    #history-list .pill.stopped{background:#fff0ee!important;color:#b42318!important;border:1px solid #fda29b!important}
    #history-list .history-card.history-denied{border:1px solid #f97066;background:#fff7f6}
    #history-list .history-denied-note{display:block;margin-top:8px;padding:9px 10px;border-radius:10px;background:#fee4e2;color:#912018;font-weight:800;font-size:12px;line-height:1.35}
  `;
  document.head.appendChild(style);

  const cache = new Map();
  let refreshQueued = false;

  async function snapshot(permit) {
    const key = String(permit || '').trim().toUpperCase();
    if (!key) return null;
    const cached = cache.get(key);
    if (cached && Date.now() - cached.at < 5000) return cached.value;
    try {
      const response = await fetch(`/api/mobile/permit?permit_number=${encodeURIComponent(key)}`, {cache:'no-store'});
      if (!response.ok) return null;
      const value = await response.json();
      cache.set(key, {at:Date.now(), value});
      return value;
    } catch (_) {
      return null;
    }
  }

  function statusLabel(status) {
    if (status === 'denied') return 'Проведение запрещено';
    if (status === 'stopped') return 'Работы остановлены';
    if (status === 'pending') return 'Ожидает разрешения';
    if (status === 'approved') return 'Разрешено';
    return 'Разрешение не требуется';
  }

  async function decorate(card) {
    const permit = card.querySelector('.history-head strong')?.textContent?.trim();
    if (!permit) return;
    const data = await snapshot(permit);
    const approval = data?.approval;
    if (!approval) return;

    const status = String(approval.status || 'none');
    card.dataset.permitStatus = status;
    card.classList.toggle('history-denied', status === 'denied');

    const pills = card.querySelectorAll('.history-meta .pill');
    const statusPill = pills[pills.length - 1];
    if (statusPill) {
      statusPill.classList.remove('pending', 'approved', 'denied', 'stopped');
      if (['pending','approved','denied','stopped'].includes(status)) statusPill.classList.add(status);
      statusPill.textContent = statusLabel(status);
    }

    let note = card.querySelector('.history-denied-note');
    if (status === 'denied') {
      if (!note) {
        note = document.createElement('div');
        note.className = 'history-denied-note';
        card.querySelector('.history-meta')?.insertAdjacentElement('afterend', note);
      }
      const stage = String(approval.denied_stage || approval.denied_field_key || 'Этап работ').trim();
      const reason = String(approval.denied_reason || 'Оператор запретил проведение работ').trim();
      note.textContent = `⛔ ${stage}. Причина: ${reason}`;
    } else {
      note?.remove();
    }
  }

  function refresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    queueMicrotask(async () => {
      refreshQueued = false;
      await Promise.all([...list.querySelectorAll('.history-card')].map(decorate));
    });
  }

  new MutationObserver(refresh).observe(list, {childList:true});
  document.getElementById('history-refresh')?.addEventListener('click', () => setTimeout(refresh, 0));
  document.querySelector('.nav-item[data-tab="history"]')?.addEventListener('click', () => setTimeout(refresh, 50));
  window.addEventListener('online', () => { cache.clear(); refresh(); });
  refresh();
})();

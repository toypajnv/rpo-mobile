(() => {
  'use strict';

  if (document.body?.dataset?.role === 'manager') return;

  const POLL_MS = 5000;
  const originalTitle = document.title || 'РПО Сервер';
  let lastEventId = null;
  let unread = 0;
  let inFlight = false;
  let audioContext = null;
  let interactionUnlocked = false;

  const style = document.createElement('style');
  style.id = 'rpo-live-notification-style';
  style.textContent = `
    .rpo-notification-toggle{border:1px solid #d7e2ef;background:#fff;color:#174a87;border-radius:10px;min-width:40px;height:40px;padding:0 10px;font:inherit;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:6px}
    .rpo-notification-toggle:hover{background:#f3f7fc}.rpo-notification-toggle.enabled{background:#edf8f2;border-color:#b8e2c8;color:#168043}.rpo-notification-toggle.denied{background:#fff4f2;border-color:#f2c5bf;color:#b42318}
    .rpo-new-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;padding:0 6px;margin-left:7px;border-radius:999px;background:#e5484d;color:#fff;font-size:12px;font-weight:800;line-height:1;box-shadow:0 0 0 3px rgba(229,72,77,.12)}
    .rpo-live-toast{position:fixed;z-index:10050;top:22px;right:22px;width:min(390px,calc(100vw - 32px));background:#fff;border:1px solid #cbd9e8;border-left:5px solid #2b74d8;border-radius:16px;box-shadow:0 18px 50px rgba(17,42,76,.22);padding:15px 16px;display:grid;grid-template-columns:42px 1fr auto;gap:12px;align-items:start;transform:translateY(-16px);opacity:0;pointer-events:none;transition:.2s ease}
    .rpo-live-toast.show{transform:translateY(0);opacity:1;pointer-events:auto}.rpo-live-toast .bell{width:42px;height:42px;border-radius:13px;background:#eaf3ff;color:#1f66c1;display:flex;align-items:center;justify-content:center;font-size:22px}.rpo-live-toast .copy{min-width:0}.rpo-live-toast b{display:block;color:#10233f;font-size:16px;margin:1px 0 4px}.rpo-live-toast p{margin:0;color:#4f6078;font-size:13px;line-height:1.4}.rpo-live-toast .details{margin-top:7px;color:#163c70;font-weight:700}.rpo-live-toast button{border:0;background:transparent;color:#60738d;font-size:20px;cursor:pointer;padding:2px}.rpo-live-toast .open{grid-column:2/4;justify-self:start;border:0;background:#eaf3ff;color:#175caf;border-radius:9px;padding:8px 12px;font-size:13px;font-weight:800;cursor:pointer}
    @media (max-width:600px){.rpo-live-toast{top:12px;left:12px;right:12px;width:auto}.rpo-notification-toggle{min-width:38px;height:38px;padding:0 8px}.rpo-notification-toggle .label{display:none}}
  `;
  document.head.appendChild(style);

  const transmissionsLink = document.querySelector('[data-tab-link="transmissions"]');
  const badge = document.createElement('span');
  badge.className = 'rpo-new-badge';
  badge.hidden = true;
  transmissionsLink?.appendChild(badge);

  const toast = document.createElement('div');
  toast.className = 'rpo-live-toast';
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'assertive');
  toast.innerHTML = `
    <div class="bell">🔔</div>
    <div class="copy"><b>Поступили новые данные РПО</b><p class="message"></p><p class="details"></p></div>
    <button type="button" class="close" aria-label="Закрыть">×</button>
    <button type="button" class="open">Открыть переданные данные</button>`;
  document.body.appendChild(toast);

  const messageEl = toast.querySelector('.message');
  const detailsEl = toast.querySelector('.details');
  let toastTimer = null;

  function currentTab(){
    return (location.hash || '#home').slice(1);
  }

  function renderUnread(){
    if (badge){
      badge.hidden = unread <= 0;
      badge.textContent = unread > 99 ? '99+' : String(unread);
    }
    document.title = unread > 0 ? `🔔 (${unread}) ${originalTitle}` : originalTitle;
  }

  function markRead(){
    unread = 0;
    renderUnread();
  }

  function openTransmissions(){
    markRead();
    toast.classList.remove('show');
    if (typeof window.activateTab === 'function') window.activateTab('transmissions');
    else location.hash = '#transmissions';
  }

  transmissionsLink?.addEventListener('click', markRead, true);
  toast.querySelector('.open')?.addEventListener('click', openTransmissions);
  toast.querySelector('.close')?.addEventListener('click', () => toast.classList.remove('show'));

  function unlockAudio(){
    interactionUnlocked = true;
    try {
      audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
      if (audioContext.state === 'suspended') audioContext.resume();
    } catch (_) {}
  }
  window.addEventListener('pointerdown', unlockAudio, {once:true, passive:true});
  window.addEventListener('keydown', unlockAudio, {once:true});

  function playChime(){
    if (!interactionUnlocked) return;
    try {
      audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
      if (audioContext.state === 'suspended') audioContext.resume();
      const now = audioContext.currentTime;
      [660, 880].forEach((frequency, index) => {
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        osc.type = 'sine';
        osc.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, now + index * 0.13);
        gain.gain.exponentialRampToValueAtTime(0.11, now + index * 0.13 + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + index * 0.13 + 0.18);
        osc.connect(gain).connect(audioContext.destination);
        osc.start(now + index * 0.13);
        osc.stop(now + index * 0.13 + 0.2);
      });
    } catch (_) {}
  }

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'rpo-notification-toggle';
  toggle.title = 'Системные уведомления браузера';
  toggle.innerHTML = '<span>🔔</span><span class="label">Уведомления</span>';
  const operatorBox = document.querySelector('header .operator');
  operatorBox?.insertBefore(toggle, operatorBox.firstChild);

  function updateToggle(){
    if (!('Notification' in window)) {
      toggle.hidden = true;
      return;
    }
    toggle.classList.toggle('enabled', Notification.permission === 'granted');
    toggle.classList.toggle('denied', Notification.permission === 'denied');
    toggle.title = Notification.permission === 'granted'
      ? 'Системные уведомления включены'
      : Notification.permission === 'denied'
        ? 'Системные уведомления запрещены в настройках браузера'
        : 'Нажмите, чтобы включить системные уведомления';
  }
  updateToggle();

  toggle.addEventListener('click', async () => {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      try { await Notification.requestPermission(); } catch (_) {}
    }
    updateToggle();
  });

  function systemNotify(count, latest){
    if (!('Notification' in window) || Notification.permission !== 'granted' || !document.hidden) return;
    try {
      const n = new Notification(count === 1 ? 'Новые данные РПО' : `Новые данные РПО: ${count}`, {
        body: latest ? `НД ${latest.permit_number || '—'} · ${latest.worker_name || '—'} · ${latest.stage_label || latest.field_key || 'новый этап'}` : 'Поступила новая информация с мобильного устройства.',
        tag: 'rpo-new-data',
        renotify: true,
      });
      n.onclick = () => { window.focus(); openTransmissions(); n.close(); };
    } catch (_) {}
  }

  function showNotification(newRows){
    const count = newRows.length;
    if (!count) return;
    const latest = newRows.slice().sort((a,b) => Number(b.id || 0) - Number(a.id || 0))[0] || {};
    unread += count;
    renderUnread();
    messageEl.textContent = count === 1 ? 'Получена 1 новая передача с мобильного устройства.' : `Получено новых передач: ${count}.`;
    detailsEl.textContent = `НД ${latest.permit_number || '—'} · ${latest.worker_name || '—'} · ${latest.stage_label || latest.field_key || 'новый этап'}`;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 9000);
    playChime();
    systemNotify(count, latest);

    if (currentTab() === 'transmissions' && !document.hidden) {
      setTimeout(markRead, 1200);
    }
  }

  async function poll(){
    if (inFlight) return;
    inFlight = true;
    try {
      const response = await fetch('/api/operator/transmissions?limit=30', {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {'Accept':'application/json'},
      });
      if (!response.ok) return;
      const rows = await response.json();
      if (!Array.isArray(rows) || !rows.length) return;
      const maxId = Math.max(...rows.map(row => Number(row.id || 0)));
      if (!Number.isFinite(maxId) || maxId <= 0) return;
      if (lastEventId === null) {
        lastEventId = maxId;
        return;
      }
      if (maxId <= lastEventId) return;
      const newRows = rows.filter(row => Number(row.id || 0) > lastEventId);
      lastEventId = maxId;
      showNotification(newRows);
    } catch (error) {
      console.debug('RPO live notifications', error);
    } finally {
      inFlight = false;
    }
  }

  window.addEventListener('hashchange', () => {
    if (currentTab() === 'transmissions') markRead();
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && currentTab() === 'transmissions') markRead();
  });

  poll();
  setInterval(poll, POLL_MS);
})();

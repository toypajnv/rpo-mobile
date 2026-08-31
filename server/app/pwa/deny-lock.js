(() => {
  'use strict';

  const CACHE_KEY = 'rpo_pwa_denied_permit_v1';
  let timer = null;
  let checking = false;

  const $ = id => document.getElementById(id);
  const permitInput = () => $('permit-number');
  const permitNumber = () => String(permitInput()?.value || '').trim().toUpperCase();

  function readCache() {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || 'null'); }
    catch (_) { return null; }
  }
  function writeCache(value) {
    try {
      if (value) localStorage.setItem(CACHE_KEY, JSON.stringify(value));
      else localStorage.removeItem(CACHE_KEY);
    } catch (_) {}
  }

  function ensureOverlay() {
    let overlay = $('rpo-deny-lock');
    if (overlay) return overlay;
    const style = document.createElement('style');
    style.textContent = `
      body.rpo-permit-denied{overflow:hidden!important;background:#8f1111!important}
      body.rpo-permit-denied .topbar{background:#a91414!important}
      body.rpo-permit-denied .no-login{background:rgba(255,255,255,.16)!important;border-color:rgba(255,255,255,.35)!important}
      body.rpo-permit-denied .no-login i{background:#ffb4ab!important}
      #rpo-deny-lock{position:fixed;inset:0;z-index:99999;background:linear-gradient(180deg,#a51212 0%,#c51d1d 54%,#8b1010 100%);color:#fff;display:flex;align-items:center;justify-content:center;padding:calc(env(safe-area-inset-top) + 24px) 22px calc(env(safe-area-inset-bottom) + 24px);text-align:center}
      #rpo-deny-lock[hidden]{display:none!important}
      #rpo-deny-lock .deny-panel{width:min(520px,100%);display:flex;flex-direction:column;gap:14px;align-items:stretch}
      #rpo-deny-lock .deny-icon{width:86px;height:86px;margin:0 auto;border-radius:50%;display:grid;place-items:center;background:#fff;color:#b31313;font-size:54px;font-weight:1000;box-shadow:0 12px 34px rgba(54,0,0,.28)}
      #rpo-deny-lock h1{margin:2px 0 0;font-size:30px;line-height:1.05;font-weight:1000;letter-spacing:.02em}
      #rpo-deny-lock .deny-permit{font-size:20px;font-weight:900;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.28);border-radius:15px;padding:11px 14px}
      #rpo-deny-lock .deny-card{background:#fff;color:#5f1111;border-radius:18px;padding:16px;text-align:left;box-shadow:0 12px 30px rgba(56,0,0,.25)}
      #rpo-deny-lock .deny-card small{display:block;color:#9b4a4a;font-size:12px;margin-bottom:4px}
      #rpo-deny-lock .deny-card strong{display:block;font-size:17px;line-height:1.25;margin-bottom:12px}
      #rpo-deny-lock .deny-reason{font-size:16px;line-height:1.35;font-weight:800;color:#791414;background:#fff1f0;border-radius:12px;padding:12px}
      #rpo-deny-lock .deny-warning{font-weight:900;font-size:16px;line-height:1.35}
      #rpo-deny-lock .deny-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      #rpo-deny-lock button{min-height:52px;border-radius:14px;border:0;font-size:15px;font-weight:900;padding:10px 12px}
      #rpo-deny-lock .deny-check{background:#fff;color:#9c1414}.deny-other{background:rgba(255,255,255,.14);color:#fff!important;border:1px solid rgba(255,255,255,.36)!important}
      #rpo-deny-lock .deny-foot{font-size:12px;color:rgba(255,255,255,.8)}
      @media(max-width:430px){#rpo-deny-lock h1{font-size:26px}#rpo-deny-lock .deny-actions{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);

    overlay = document.createElement('section');
    overlay.id = 'rpo-deny-lock';
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="deny-panel">
        <div class="deny-icon">!</div>
        <h1>ПРОВЕДЕНИЕ РАБОТ ЗАПРЕЩЕНО</h1>
        <div class="deny-permit" id="rpo-deny-permit">НД —</div>
        <div class="deny-card">
          <small>Этап, по которому принято решение</small>
          <strong id="rpo-deny-stage">—</strong>
          <small>Причина запрета</small>
          <div class="deny-reason" id="rpo-deny-reason">Причина не указана</div>
        </div>
        <div class="deny-warning">Не продолжайте работы по этому наряду-допуску до снятия запрета оператором.</div>
        <div class="deny-actions">
          <button type="button" class="deny-check" id="rpo-deny-check">Проверить статус</button>
          <button type="button" class="deny-other" id="rpo-deny-other">Выбрать другой НД</button>
        </div>
        <div class="deny-foot">Статус проверяется автоматически. При отсутствии сети ранее полученный запрет сохраняется на iPhone.</div>
      </div>`;
    document.body.appendChild(overlay);

    $('rpo-deny-check').addEventListener('click', () => checkStatus(true));
    $('rpo-deny-other').addEventListener('click', () => {
      const input = permitInput();
      if (!input) return;
      input.value = '';
      input.dispatchEvent(new Event('input', {bubbles:true}));
      input.dispatchEvent(new Event('change', {bubbles:true}));
      hideLock();
      window.scrollTo({top:0, behavior:'smooth'});
      setTimeout(() => input.focus(), 250);
    });
    return overlay;
  }

  function showLock(summary, permit) {
    const overlay = ensureOverlay();
    const status = summary || {};
    $('rpo-deny-permit').textContent = `НД ${permit}`;
    $('rpo-deny-stage').textContent = status.denied_stage || status.denied_field_key || 'Этап работ';
    $('rpo-deny-reason').textContent = status.denied_reason || 'Оператор запретил проведение работ. Уточните причину у оператора.';
    overlay.hidden = false;
    const wasDenied = document.body.classList.contains('rpo-permit-denied');
    const pill = document.querySelector('.no-login');
    if (pill && !wasDenied) pill.dataset.rpoBeforeDeny = pill.innerHTML;
    document.body.classList.add('rpo-permit-denied');
    if (pill) pill.innerHTML = '<i></i> ЗАПРЕЩЕНО';
  }

  function hideLock() {
    const overlay = ensureOverlay();
    overlay.hidden = true;
    const wasDenied = document.body.classList.contains('rpo-permit-denied');
    document.body.classList.remove('rpo-permit-denied');
    if (!wasDenied) return;
    const pill = document.querySelector('.no-login');
    if (pill) {
      pill.innerHTML = pill.dataset.rpoBeforeDeny || '<i></i> Готово';
      delete pill.dataset.rpoBeforeDeny;
    }
  }

  function applyCachedState() {
    const permit = permitNumber();
    const cached = readCache();
    if (permit && cached?.permit_number === permit && cached?.approval?.status === 'denied') {
      showLock(cached.approval, permit);
      return true;
    }
    hideLock();
    return false;
  }

  async function checkStatus(force = false) {
    const permit = permitNumber();
    if (permit.length < 3 || checking) {
      if (permit.length < 3) hideLock();
      return;
    }
    if (!navigator.onLine) {
      applyCachedState();
      return;
    }
    checking = true;
    const button = $('rpo-deny-check');
    const oldText = button?.textContent;
    if (force && button) { button.disabled = true; button.textContent = 'Проверяю…'; }
    try {
      const response = await fetch(`/api/mobile/permit?permit_number=${encodeURIComponent(permit)}`, {cache:'no-store'});
      if (response.status === 404) {
        const cached = readCache();
        if (cached?.permit_number === permit) writeCache(null);
        hideLock();
        return;
      }
      if (!response.ok) return;
      const data = await response.json();
      if (permitNumber() !== permit) return;
      if (data?.approval?.status === 'denied') {
        writeCache({permit_number: permit, approval: data.approval, checked_at: new Date().toISOString()});
        showLock(data.approval, permit);
      } else {
        const cached = readCache();
        if (cached?.permit_number === permit) writeCache(null);
        hideLock();
      }
    } catch (_) {
      applyCachedState();
    } finally {
      checking = false;
      if (button) { button.disabled = false; button.textContent = oldText || 'Проверить статус'; }
    }
  }

  function scheduleCheck(delay = 250) {
    clearTimeout(timer);
    applyCachedState();
    timer = setTimeout(() => checkStatus(false), delay);
  }

  document.addEventListener('DOMContentLoaded', () => {
    ensureOverlay();
    permitInput()?.addEventListener('input', () => scheduleCheck(450));
    permitInput()?.addEventListener('change', () => scheduleCheck(0));
    $('permit-refresh')?.addEventListener('click', () => scheduleCheck(120));
    applyCachedState();
    scheduleCheck(300);
    setInterval(() => {
      if (document.visibilityState === 'visible' && permitNumber().length >= 3) checkStatus(false);
    }, 5000);
  });
  window.addEventListener('online', () => scheduleCheck(0));
  window.addEventListener('pageshow', () => scheduleCheck(0));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') scheduleCheck(0);
  });
})();

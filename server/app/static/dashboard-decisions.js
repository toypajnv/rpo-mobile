(() => {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .deny-button{border:1px solid #d92d20;background:#fff1f0;color:#b42318;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}
    .deny-button:hover{background:#fee4e2}.allow-button{border:1px solid #17a34a;background:#ecfdf3;color:#087a34;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}
    .decision-controls{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.decision-controls button:disabled{opacity:.55;cursor:wait}
    .badge.denied{background:#fee4e2!important;color:#b42318!important;border:1px solid #f97066!important}
    #works-body tr.rpo-blocked>td{background:#fff7f6}.blocked-permit-note{display:block;margin-top:5px;color:#b42318;font-weight:800;max-width:360px}
    .stage-detail-line.rpo-stage-denied{border-left:4px solid #d92d20;background:#fff4f2;padding-left:10px}
  `;
  document.head.appendChild(style);

  let snapshot = [];
  let refreshTimer = null;
  let tableObserversBound = false;

  function filterQuery() {
    const q = new URLSearchParams({limit: '200'});
    const search = document.querySelector('#global-search')?.value?.trim();
    const unit = document.querySelector('#global-unit')?.value?.trim();
    if (search) q.set('q', search);
    if (unit) q.set('unit', unit);
    return q;
  }

  function actionHtml(item) {
    if (!item?.approval_required || !Number(item.event_id)) return '—';
    if (item.approval_status === 'denied') {
      return `<div class="decision-controls"><button type="button" class="allow-button" data-rpo-decision="approved" data-event-id="${Number(item.event_id)}">Снять запрет</button></div>`;
    }
    const allow = item.approval_status === 'approved' ? '' : `<button type="button" class="allow-button" data-rpo-decision="approved" data-event-id="${Number(item.event_id)}">Разрешить</button>`;
    return `<div class="decision-controls">${allow}<button type="button" class="deny-button" data-rpo-decision="denied" data-event-id="${Number(item.event_id)}">Запретить работы</button></div>`;
  }

  function setBadge(container, item) {
    if (!container) return;
    let badge = container.querySelector('.badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'badge';
      container.prepend(badge);
    }
    badge.classList.remove('done', 'approval-wait', 'neutral', 'denied');
    if (!item.approval_required) {
      badge.classList.add('neutral'); badge.textContent = 'Не требуется';
    } else if (item.approval_status === 'approved') {
      badge.classList.add('done'); badge.textContent = 'Разрешено';
    } else if (item.approval_status === 'denied') {
      badge.classList.add('denied'); badge.textContent = 'ЗАПРЕЩЕНО';
    } else {
      badge.classList.add('approval-wait'); badge.textContent = 'Ожидает';
    }
  }

  function annotateWorks(records) {
    const byPermit = new Map(records.map(record => [String(record.permit_number || '').trim(), record]));
    document.querySelectorAll('#works-body tr').forEach(row => {
      const cells = row.querySelectorAll('td');
      const permit = cells[2]?.textContent?.trim() || '';
      const record = byPermit.get(permit);
      if (!record) return;
      const approval = record.approval || {};
      const blocked = approval.status === 'denied';
      row.classList.toggle('rpo-blocked', blocked);

      if (cells[5]) {
        let badge = cells[5].querySelector('.badge');
        if (!badge) { badge = document.createElement('span'); badge.className = 'badge'; cells[5].prepend(badge); }
        badge.classList.toggle('denied', blocked);
        if (blocked) {
          badge.textContent = 'ПРОВЕДЕНИЕ ЗАПРЕЩЕНО';
          let note = cells[5].querySelector('.blocked-permit-note');
          if (!note) { note = document.createElement('small'); note.className = 'blocked-permit-note'; cells[5].appendChild(note); }
          const reason = approval.denied_reason ? ` Причина: ${approval.denied_reason}` : '';
          note.textContent = `${approval.denied_stage || 'Этап работ'}.${reason}`;
        } else {
          cells[5].querySelector('.blocked-permit-note')?.remove();
        }
      }

      const items = new Map((record.stage_items || []).map(item => [String(item.key), item]));
      row.querySelectorAll('.stage-detail-line').forEach(line => {
        const key = line.querySelector('small')?.textContent?.trim() || '';
        const item = items.get(key);
        if (!item) return;
        line.classList.toggle('rpo-stage-denied', item.approval_status === 'denied');
        let approvalBox = line.querySelector('.stage-approval');
        if (!approvalBox) { approvalBox = document.createElement('span'); approvalBox.className = 'stage-approval'; line.appendChild(approvalBox); }
        setBadge(approvalBox, item);
        approvalBox.querySelectorAll('[data-approve-event],.decision-controls').forEach(el => el.remove());
        const holder = document.createElement('span');
        holder.innerHTML = actionHtml(item);
        approvalBox.append(...holder.childNodes);
        if (item.approval_status === 'denied' && approval.denied_field_key === item.key && approval.denied_reason) {
          let reason = line.querySelector('.blocked-permit-note');
          if (!reason) { reason = document.createElement('small'); reason.className = 'blocked-permit-note'; line.appendChild(reason); }
          reason.textContent = `Причина запрета: ${approval.denied_reason}`;
        } else {
          line.querySelector('.blocked-permit-note')?.remove();
        }
      });
    });
  }

  function annotateSnapshot() {
    if (!snapshot.length) return;
    annotateWorks(snapshot);
  }

  function bindTableObservers() {
    if (tableObserversBound) return;
    tableObserversBound = true;
    const body = document.querySelector('#works-body');
    if (body) new MutationObserver(() => queueMicrotask(annotateSnapshot)).observe(body, {childList:true});
  }

  async function refreshDecisions() {
    clearTimeout(refreshTimer);
    try {
      const response = await fetch('/api/operator/events?' + filterQuery().toString(), {credentials:'same-origin', cache:'no-store'});
      if (!response.ok) return;
      snapshot = await response.json();
      annotateSnapshot();
    } catch (_) {
    } finally {
      refreshTimer = setTimeout(refreshDecisions, 2200);
    }
  }

  async function submitDecision(button) {
    const eventId = Number(button.dataset.eventId);
    const decision = button.dataset.rpoDecision;
    if (!eventId || !['approved','denied'].includes(decision)) return;
    let reason = '';
    if (decision === 'denied') {
      reason = prompt('Укажите причину запрета проведения работ по этому НД:') ?? '';
      reason = reason.trim();
      if (!reason) return;
      if (reason.length < 3) { alert('Причина запрета должна содержать не менее 3 символов.'); return; }
      if (!confirm('Запретить проведение работ? На телефоне этот НД будет полностью заблокирован красным экраном.')) return;
    } else if (!confirm('Разрешить проведение работ и снять блокировку НД по этому этапу?')) {
      return;
    }

    button.disabled = true;
    const old = button.textContent;
    button.textContent = decision === 'denied' ? 'Запрещаю…' : 'Разрешаю…';
    try {
      const response = await fetch(`/api/operator/events/${eventId}/decision`, {
        method: 'POST', credentials:'same-origin',
        headers: {'Content-Type':'application/json','Accept':'application/json'},
        body: JSON.stringify({decision, reason}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Не удалось изменить решение');
      if (typeof window.refreshFilteredViews === 'function') await window.refreshFilteredViews();
      await refreshDecisions();
    } catch (error) {
      alert(error.message || 'Ошибка решения оператора');
      button.disabled = false; button.textContent = old;
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-rpo-decision]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    submitDecision(button);
  }, true);

  document.addEventListener('DOMContentLoaded', () => {
    bindTableObservers();
    refreshDecisions();
  });
})();

(() => {
  'use strict';

  const managerMode = document.body.dataset.role === 'manager';
  const style = document.createElement('style');
  style.textContent = `
    .deny-button{border:1px solid #d92d20;background:#fff1f0;color:#b42318;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}
    .deny-button:hover{background:#fee4e2}.allow-button{border:1px solid #17a34a;background:#ecfdf3;color:#087a34;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}
    .decision-controls,.permit-decision-controls,.transmission-deny-control{display:flex;flex-direction:column;gap:6px;align-items:stretch}
    .decision-controls button,.permit-decision-controls button,.transmission-deny-control button{width:100%}
    .decision-controls button:disabled,.permit-decision-controls button:disabled,.transmission-deny-control button:disabled{opacity:.55;cursor:wait}
    .badge.denied{background:#fee4e2!important;color:#b42318!important;border:1px solid #f97066!important}
    #works-body tr.rpo-blocked>td{background:#fff7f6}.blocked-permit-note{display:block;margin-top:5px;color:#b42318;font-weight:800;max-width:360px}
    .stage-detail-line.rpo-stage-denied{border-left:4px solid #d92d20;background:#fff4f2;padding-left:10px}
    #works-body td:last-child .permit-decision-controls{margin-bottom:6px}
    #works-body .approve-button,#transmissions-body .approve-button,#transmissions-body .review-controls{display:none!important}
  `;
  document.head.appendChild(style);

  let snapshot = [];
  let refreshTimer = null;
  let tableObserversBound = false;
  let transmissionAnnotationQueued = false;

  function filterQuery() {
    const q = new URLSearchParams({limit: '200'});
    const search = document.querySelector('#global-search')?.value?.trim();
    const unit = document.querySelector('#global-unit')?.value?.trim();
    if (search) q.set('q', search);
    if (unit) q.set('unit', unit);
    return q;
  }

  function isPending(item) {
    return Boolean(
      item?.approval_required &&
      item.approval_status === 'pending' &&
      Number(item.event_id)
    );
  }

  function actionHtml(item, className = 'decision-controls') {
    if (managerMode || !isPending(item)) return '';
    const eventId = Number(item.event_id);
    return `<div class="${className}" data-rpo-control-event="${eventId}"><button type="button" class="allow-button" data-rpo-decision="approved" data-event-id="${eventId}">Разрешить</button><button type="button" class="deny-button" data-rpo-decision="denied" data-event-id="${eventId}">Запретить работы</button></div>`;
  }

  function syncControls(container, item, className, position = 'append') {
    if (!container) return;
    const existing = container.querySelector(`.${className}`);
    if (managerMode || !isPending(item)) {
      existing?.remove();
      return;
    }

    const eventId = Number(item.event_id);
    const completeExisting = existing &&
      existing.dataset.rpoControlEvent === String(eventId) &&
      existing.querySelector('[data-rpo-decision="approved"]') &&
      existing.querySelector('[data-rpo-decision="denied"]');
    if (completeExisting) return;

    existing?.remove();
    const holder = document.createElement('span');
    holder.innerHTML = actionHtml(item, className);
    const controls = holder.firstElementChild;
    if (!controls) return;
    if (position === 'prepend') container.prepend(controls);
    else container.appendChild(controls);
  }

  function setBadge(container, item) {
    if (!container) return;
    let badge = container.querySelector('.badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'badge';
      container.prepend(badge);
    }
    badge.classList.remove('done', 'approval-wait', 'neutral', 'denied', 'rejected');
    if (!item.approval_required) {
      badge.classList.add('neutral'); badge.textContent = 'Не требуется';
    } else if (item.approval_status === 'approved') {
      badge.classList.add('done'); badge.textContent = 'Разрешено';
    } else if (item.approval_status === 'denied') {
      badge.classList.add('denied'); badge.textContent = 'ЗАПРЕЩЕНО';
    } else if (item.approval_status === 'rejected') {
      badge.classList.add('neutral'); badge.textContent = 'Отклонено';
    } else {
      badge.classList.add('approval-wait'); badge.textContent = 'Ожидает';
    }
  }

  function removeLegacyFinishButtons(root) {
    root?.querySelectorAll('button').forEach(button => {
      const text = button.textContent?.trim().toLocaleLowerCase('ru-RU') || '';
      if (text === 'завершить работы' || text === 'завершить работу') button.remove();
    });
  }

  function decisionItemForPermit(record) {
    const items = Array.isArray(record?.stage_items) ? record.stage_items : [];
    return [...items].reverse().find(item =>
      item && item.key !== 'AZ' && isPending(item)
    ) || null;
  }

  function annotatePermitAction(row, record) {
    if (!row || !record) return;
    const cells = row.querySelectorAll('td');
    const actionCell = cells[9];
    if (!actionCell) return;

    removeLegacyFinishButtons(row);
    const item = (record.status_class === 'done' || record.status_class === 'stopped')
      ? null
      : decisionItemForPermit(record);

    if (!item) {
      actionCell.querySelector('.permit-decision-controls')?.remove();
      if (!actionCell.textContent.trim()) actionCell.textContent = '—';
      return;
    }

    if (actionCell.textContent.trim() === '—') actionCell.textContent = '';
    syncControls(actionCell, item, 'permit-decision-controls', 'prepend');
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
        badge.classList.remove('done', 'approval-wait', 'neutral', 'denied');
        if (blocked) {
          badge.classList.add('denied');
          badge.textContent = 'ПРОВЕДЕНИЕ ЗАПРЕЩЕНО';
          let note = cells[5].querySelector('.blocked-permit-note');
          if (!note) { note = document.createElement('small'); note.className = 'blocked-permit-note'; cells[5].appendChild(note); }
          const reason = approval.denied_reason ? ` Причина: ${approval.denied_reason}` : '';
          note.textContent = `${approval.denied_stage || 'Этап работ'}.${reason}`;
        } else {
          badge.classList.add(approval.status === 'approved' ? 'done' : approval.status === 'pending' ? 'approval-wait' : 'neutral');
          badge.textContent = approval.label || 'Разрешений пока нет';
          cells[5].querySelector('.blocked-permit-note')?.remove();
        }
      }

      annotatePermitAction(row, record);

      const items = new Map((record.stage_items || []).map(item => [String(item.key), item]));
      row.querySelectorAll('.stage-detail-line').forEach(line => {
        const key = line.querySelector('small')?.textContent?.trim() || '';
        const item = items.get(key);
        if (!item) return;
        line.classList.toggle('rpo-stage-denied', item.approval_status === 'denied');
        let approvalBox = line.querySelector('.stage-approval');
        if (!approvalBox) { approvalBox = document.createElement('span'); approvalBox.className = 'stage-approval'; line.appendChild(approvalBox); }
        setBadge(approvalBox, item);
        approvalBox.querySelectorAll('[data-approve-event]').forEach(el => el.remove());
        syncControls(approvalBox, item, 'decision-controls');
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

  function transmissionEventId(row) {
    return Number(
      row.dataset.eventId ||
      row.querySelector('[data-review-event]')?.dataset.reviewEvent ||
      row.querySelector('[data-approve-event]')?.dataset.approveEvent ||
      row.querySelector('[data-rpo-decision]')?.dataset.eventId ||
      0
    );
  }

  function annotateTransmissions() {
    document.querySelectorAll('#transmissions-body tr').forEach(row => {
      const cells = row.querySelectorAll('td');
      const statusText = cells[7]?.textContent?.trim() || '';
      const actionCell = cells[8];
      if (!actionCell) return;

      const eventId = transmissionEventId(row);
      actionCell.querySelectorAll('.review-controls,.approve-button').forEach(el => el.remove());
      removeLegacyFinishButtons(actionCell);

      const pending = statusText.includes('Ожидает') && eventId > 0;
      const item = pending ? {
        approval_required: true,
        approval_status: 'pending',
        event_id: eventId,
      } : null;

      if (!item || managerMode) {
        actionCell.querySelector('.transmission-deny-control')?.remove();
        if (!actionCell.textContent.trim()) actionCell.textContent = '—';
        return;
      }

      if (actionCell.textContent.trim() === '—') actionCell.textContent = '';
      syncControls(actionCell, item, 'transmission-deny-control');
    });
  }

  function annotateSnapshot() {
    if (snapshot.length) annotateWorks(snapshot);
    annotateTransmissions();
  }

  function queueTransmissionAnnotation() {
    if (transmissionAnnotationQueued) return;
    transmissionAnnotationQueued = true;
    queueMicrotask(() => {
      transmissionAnnotationQueued = false;
      annotateTransmissions();
    });
  }

  function bindTableObservers() {
    if (tableObserversBound) return;
    tableObserversBound = true;
    const worksBody = document.querySelector('#works-body');
    const transmissionsBody = document.querySelector('#transmissions-body');
    if (worksBody) new MutationObserver(() => queueMicrotask(annotateSnapshot)).observe(worksBody, {childList:true});
    if (transmissionsBody) new MutationObserver(queueTransmissionAnnotation).observe(transmissionsBody, {childList:true, subtree:true});
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
    } else if (!confirm('Разрешить проведение работ по этому этапу?')) {
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

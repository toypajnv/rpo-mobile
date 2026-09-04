(() => {
  'use strict';

  const managerMode = document.body.dataset.role === 'manager';
  const style = document.createElement('style');
  style.textContent = `
    .review-controls{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
    .review-approve{border:1px solid #17a34a;background:#ecfdf3;color:#087a34;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}
    .review-reject{border:1px solid #d92d20;background:#fff1f0;color:#b42318;border-radius:9px;padding:7px 10px;font-weight:800;cursor:pointer}
    .review-controls button:disabled{opacity:.55;cursor:wait}
    .badge.rejected{background:#f2f4f7!important;color:#475467!important;border:1px solid #98a2b3!important}
    #transmissions-body tr.rpo-rejected>td{background:#f8f9fb}
  `;
  document.head.appendChild(style);

  let timer = null;

  function filterQuery() {
    const q = new URLSearchParams({limit: '300'});
    const search = document.querySelector('#global-search')?.value?.trim();
    const unit = document.querySelector('#global-unit')?.value?.trim();
    if (search) q.set('q', search);
    if (unit) q.set('unit', unit);
    return q;
  }

  function badgeHtml(item) {
    if (item.approval_status === 'approved') return '<span class="badge done">Разрешено</span>';
    if (item.approval_status === 'rejected') return '<span class="badge rejected">Отклонено</span>';
    if (item.approval_status === 'denied') return '<span class="badge denied">ЗАПРЕЩЕНО</span>';
    if (item.approval_status === 'pending') return '<span class="badge approval-wait">Ожидает</span>';
    return '<span class="badge neutral">Не рассмотрено</span>';
  }

  function reviewActions(item) {
    if (managerMode || !Number(item.id)) return '—';
    if (item.approval_status === 'denied') return '—';
    if (item.approval_status === 'rejected') {
      return `<div class="review-controls"><button type="button" class="review-approve" data-review-decision="approved" data-review-event="${Number(item.id)}">Разрешить</button></div>`;
    }
    if (item.approval_status === 'approved') {
      return `<div class="review-controls"><button type="button" class="review-reject" data-review-decision="rejected" data-review-event="${Number(item.id)}">Отклонить</button></div>`;
    }
    return `<div class="review-controls"><button type="button" class="review-approve" data-review-decision="approved" data-review-event="${Number(item.id)}">Разрешить</button><button type="button" class="review-reject" data-review-decision="rejected" data-review-event="${Number(item.id)}">Отклонить</button></div>`;
  }

  function annotate(rows) {
    const domRows = Array.from(document.querySelectorAll('#transmissions-body tr'));
    domRows.forEach((row, index) => {
      const item = rows[index];
      if (!item) return;
      row.dataset.eventId = String(item.id || '');
      row.classList.toggle('rpo-rejected', item.approval_status === 'rejected');
      const cells = row.querySelectorAll('td');
      if (cells[7]) cells[7].innerHTML = badgeHtml(item);
      if (cells[8]) cells[8].innerHTML = reviewActions(item);
    });
  }

  async function refreshReview() {
    clearTimeout(timer);
    try {
      const response = await fetch('/api/operator/transmissions?' + filterQuery().toString(), {credentials:'same-origin', cache:'no-store'});
      if (!response.ok) return;
      annotate(await response.json());
    } catch (_) {
    } finally {
      timer = setTimeout(refreshReview, 2400);
    }
  }

  async function submitReview(button) {
    const eventId = Number(button.dataset.reviewEvent);
    const decision = button.dataset.reviewDecision;
    if (!eventId || !['approved','rejected'].includes(decision)) return;

    let reason = '';
    if (decision === 'rejected') {
      reason = (prompt('Укажите причину отклонения переданных данных:') ?? '').trim();
      if (!reason) return;
      if (reason.length < 3) {
        alert('Причина отклонения должна содержать не менее 3 символов.');
        return;
      }
      if (!confirm('Отклонить эту передачу? Если это актуальное значение этапа, сервер восстановит предыдущее корректное значение.')) return;
    } else if (!confirm('Разрешить эту передачу и считать данные корректными?')) {
      return;
    }

    button.disabled = true;
    const old = button.textContent;
    button.textContent = decision === 'rejected' ? 'Отклоняю…' : 'Разрешаю…';
    try {
      const response = await fetch(`/api/operator/transmissions/${eventId}/review`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type':'application/json','Accept':'application/json'},
        body: JSON.stringify({decision, reason}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить решение');
      if (typeof window.refreshFilteredViews === 'function') await window.refreshFilteredViews();
      await refreshReview();
    } catch (error) {
      alert(error.message || 'Ошибка обработки передачи');
      button.disabled = false;
      button.textContent = old;
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-review-event]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    submitReview(button);
  }, true);

  document.addEventListener('DOMContentLoaded', refreshReview);
})();

(() => {
  'use strict';
  const uxEsc = (value='') => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
  const uxFmt = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  };

  const css = `
    .ux-attention{margin:0 0 22px}.ux-attention-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 12px}.ux-attention-head h2{margin:0;font-size:20px}.ux-attention-head p{margin:3px 0 0;color:#76859a;font-size:13px}.ux-attention-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.ux-attention-card{border:1px solid #e1e8f2;border-radius:16px;background:#fff;padding:15px;box-shadow:0 4px 16px rgba(17,54,91,.05);min-width:0}.ux-attention-card.pending{border-left:4px solid #e8a11b}.ux-attention-card.stopped{border-left:4px solid #df4949}.ux-attention-card.recent{border-left:4px solid #2879e8}.ux-attention-card .ux-kicker{display:flex;justify-content:space-between;gap:10px;color:#758398;font-size:12px;margin-bottom:8px}.ux-attention-card h3{font-size:16px;margin:0 0 4px;color:#17324f}.ux-attention-card p{font-size:13px;margin:0 0 10px;color:#66778b;line-height:1.35}.ux-attention-actions{display:flex;gap:8px;flex-wrap:wrap}.ux-attention-actions button{border:0;border-radius:9px;padding:8px 11px;font-weight:700;cursor:pointer}.ux-attention-actions .ux-open{background:#eef5ff;color:#1262cf}.ux-attention-actions .ux-approve{background:#1262cf;color:#fff}.ux-empty{grid-column:1/-1;padding:24px;text-align:center;color:#718095;border:1px dashed #d7e0ec;border-radius:15px;background:#fbfcfe}.ux-drawer-backdrop{position:fixed;inset:0;background:rgba(8,25,44,.28);z-index:90;display:none}.ux-drawer-backdrop.open{display:block}.ux-drawer{position:absolute;right:0;top:0;bottom:0;width:min(520px,94vw);background:#f7f9fc;box-shadow:-18px 0 48px rgba(14,35,60,.18);padding:22px;overflow:auto}.ux-drawer-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px}.ux-drawer-head h2{margin:0;font-size:22px}.ux-drawer-head p{margin:4px 0 0;color:#718095}.ux-drawer-close{border:0;background:#e9eef5;border-radius:10px;width:38px;height:38px;font-size:22px;cursor:pointer}.ux-permit-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}.ux-permit-meta div{background:#fff;border:1px solid #e1e8f2;border-radius:12px;padding:11px}.ux-permit-meta small{display:block;color:#7b899b;margin-bottom:4px}.ux-permit-meta b{color:#17324f}.ux-stage-timeline{display:grid;gap:9px}.ux-stage-item{background:#fff;border:1px solid #e1e8f2;border-radius:13px;padding:12px}.ux-stage-item-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.ux-stage-item h4{margin:0;font-size:14px}.ux-stage-item small{color:#7b899b}.ux-stage-item strong{display:block;margin-top:7px;font-size:13px}.ux-stage-item em{display:block;margin-top:5px;color:#68798d;font-size:12px;font-style:normal}.ux-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:11px;font-weight:700;background:#eef2f7;color:#657487}.ux-pill.pending{background:#fff3dc;color:#a66b00}.ux-pill.approved{background:#e6f6ec;color:#198847}.ux-pill.stopped{background:#ffe8e8;color:#bc3333}@media(max-width:1200px){.ux-attention-grid{grid-template-columns:1fr 1fr}}@media(max-width:760px){.ux-attention-grid{grid-template-columns:1fr}.ux-permit-meta{grid-template-columns:1fr}}
  `;
  const style = document.createElement('style');
  style.dataset.ux21 = 'dashboard';
  style.textContent = css;
  document.head.appendChild(style);

  function ensureShell(){
    const home = document.querySelector('#tab-home');
    if (!home || document.querySelector('#ux-attention')) return;
    const section = document.createElement('section');
    section.id = 'ux-attention';
    section.className = 'ux-attention';
    section.innerHTML = `<div class="ux-attention-head"><div><h2>Требуют внимания</h2><p>Разрешения, остановки и последние изменения — без поиска по таблицам</p></div><button type="button" class="filter-reset" data-ux-refresh>Обновить</button></div><div id="ux-attention-grid" class="ux-attention-grid"><div class="ux-empty">Загрузка...</div></div>`;
    const stats = home.querySelector('.stats');
    if (stats) stats.insertAdjacentElement('afterend', section); else home.prepend(section);

    const backdrop = document.createElement('div');
    backdrop.id = 'ux-drawer-backdrop';
    backdrop.className = 'ux-drawer-backdrop';
    backdrop.innerHTML = `<aside class="ux-drawer" role="dialog" aria-modal="true" aria-label="Карточка наряда-допуска"><div class="ux-drawer-head"><div><h2 id="ux-drawer-title">Наряд-допуск</h2><p id="ux-drawer-subtitle"></p></div><button type="button" class="ux-drawer-close" data-ux-close>×</button></div><div id="ux-drawer-body"></div></aside>`;
    document.body.appendChild(backdrop);
  }

  function approvalPill(item){
    if (item.approval_required === false) return '<span class="ux-pill">Не требуется</span>';
    if (item.approval_status === 'approved') return '<span class="ux-pill approved">Разрешено</span>';
    return '<span class="ux-pill pending">Ожидает</span>';
  }

  async function loadAttention(){
    ensureShell();
    const grid = document.querySelector('#ux-attention-grid');
    if (!grid) return;
    try {
      const [tr, wr] = await Promise.all([
        fetch('/api/operator/transmissions?limit=120', {credentials:'same-origin', cache:'no-store'}),
        fetch('/api/operator/events?limit=200', {credentials:'same-origin', cache:'no-store'}),
      ]);
      if (!tr.ok || !wr.ok) return;
      const transmissions = await tr.json();
      const works = await wr.json();
      window.__rpoUxWorks = works;
      const pending = transmissions.filter(x => x.approval_required && x.approval_status !== 'approved').slice(0,4);
      const stopped = works.filter(x => x.status_class === 'stopped').slice(0,3);
      const recent = works.filter(x => x.status_class !== 'stopped' && !(x.approval?.pending_count > 0)).slice(0,3);
      const cards = [];
      pending.forEach(x => cards.push(`<article class="ux-attention-card pending"><div class="ux-kicker"><span>${uxEsc(x.structural_unit||'—')}</span><span>${uxEsc(uxFmt(x.received_at))}</span></div><h3>${uxEsc(x.permit_number)} · ${uxEsc(x.stage_label)}</h3><p>${uxEsc(x.worker_name)}<br>${uxEsc(x.field_value)}</p><div class="ux-attention-actions"><button class="ux-approve" data-approve-event="${Number(x.id)}">Разрешить</button><button class="ux-open" data-ux-permit="${uxEsc(x.permit_number)}">Открыть НД</button></div></article>`));
      stopped.forEach(x => cards.push(`<article class="ux-attention-card stopped"><div class="ux-kicker"><span>${uxEsc(x.structural_unit||'—')}</span><span>${uxEsc(uxFmt(x.updated_at))}</span></div><h3>${uxEsc(x.permit_number)} · Работы остановлены</h3><p>${uxEsc(x.worker_name)}. Требуется контроль причины остановки и последующего возобновления.</p><div class="ux-attention-actions"><button class="ux-open" data-ux-permit="${uxEsc(x.permit_number)}">Открыть НД</button></div></article>`));
      recent.forEach(x => cards.push(`<article class="ux-attention-card recent"><div class="ux-kicker"><span>${uxEsc(x.structural_unit||'—')}</span><span>${uxEsc(uxFmt(x.updated_at))}</span></div><h3>${uxEsc(x.permit_number)} · ${uxEsc(x.status)}</h3><p>${uxEsc(x.worker_name)} · заполнено ${Number(x.stage_count)||0} из ${Number(x.stage_total)||0} этапов.</p><div class="ux-attention-actions"><button class="ux-open" data-ux-permit="${uxEsc(x.permit_number)}">Открыть НД</button></div></article>`));
      grid.innerHTML = cards.length ? cards.join('') : '<div class="ux-empty">Сейчас нет работ, требующих внимания оператора.</div>';
    } catch (error) {
      console.error('dashboard UX attention', error);
    }
  }

  function openDrawer(permitNumber){
    const works = Array.isArray(window.__rpoUxWorks) ? window.__rpoUxWorks : [];
    const item = works.find(x => String(x.permit_number) === String(permitNumber));
    if (!item) return;
    const backdrop = document.querySelector('#ux-drawer-backdrop');
    const body = document.querySelector('#ux-drawer-body');
    document.querySelector('#ux-drawer-title').textContent = item.permit_number;
    document.querySelector('#ux-drawer-subtitle').textContent = `${item.worker_name} · ${item.structural_unit || 'Подразделение не указано'}`;
    const approval = item.approval || {};
    const stages = (item.stage_items || []).map(stage => `<article class="ux-stage-item"><div class="ux-stage-item-head"><div><h4>${uxEsc(stage.label)}</h4><small>${uxEsc(stage.key)}</small></div>${stage.key==='AZ'?'<span class="ux-pill stopped">Остановка</span>':approvalPill(stage)}</div><strong>${uxEsc(stage.value)}</strong>${stage.comment?`<em>${uxEsc(stage.comment)}</em>`:''}${stage.approval_required&&stage.approval_status!=='approved'&&Number(stage.event_id)?`<div class="ux-attention-actions" style="margin-top:9px"><button class="ux-approve" data-approve-event="${Number(stage.event_id)}">Разрешить этап</button></div>`:''}</article>`).join('');
    body.innerHTML = `<div class="ux-permit-meta"><div><small>Состояние</small><b>${uxEsc(item.status)}</b></div><div><small>Разрешение</small><b>${uxEsc(approval.label||'Разрешений пока нет')}</b></div><div><small>Прогресс</small><b>${Number(item.stage_count)||0} из ${Number(item.stage_total)||0}</b></div><div><small>Обновлено</small><b>${uxEsc(uxFmt(item.updated_at))}</b></div></div><div class="ux-stage-timeline">${stages || '<div class="ux-empty">Этапы ещё не передавались.</div>'}</div>`;
    backdrop?.classList.add('open');
  }

  document.addEventListener('click', (event) => {
    const open = event.target.closest('[data-ux-permit]');
    if (open) { openDrawer(open.dataset.uxPermit); return; }
    if (event.target.closest('[data-ux-close]') || event.target.id === 'ux-drawer-backdrop') document.querySelector('#ux-drawer-backdrop')?.classList.remove('open');
    if (event.target.closest('[data-ux-refresh]')) loadAttention();
  });

  document.addEventListener('keydown', event => { if (event.key === 'Escape') document.querySelector('#ux-drawer-backdrop')?.classList.remove('open'); });
  setTimeout(loadAttention, 200);
  setInterval(loadAttention, 5000);
})();

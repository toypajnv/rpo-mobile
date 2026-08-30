(() => {
  'use strict';

  const STAGES = [
    {id:'PREPARATION',title:'Подготовка',kind:'range',optional:false},
    {id:'TRANSFER_WORK',title:'Передача объекта',kind:'datetime',optional:false},
    {id:'ACTUAL_WORK',title:'Фактическое начало и окончание работ',kind:'range',optional:false},
    {id:'STOP_WORK',title:'Остановка работ',kind:'stop',optional:false},
    {id:'RESUME_WORK',title:'Возобновление работ',kind:'resume',optional:false},
    {id:'EXTEND_WORK',title:'Продление РПО',kind:'extension',optional:false},
    {id:'REPLACEMENTS',title:'Замена исполнителей работ',kind:'replacements',optional:true},
  ];

  const $ = id => document.getElementById(id);
  const permit = $('permit-number');
  const worker = $('worker-name');
  const unit = $('structural-unit');
  const stageSelect = $('stage-select');
  const stageFields = $('stage-fields');
  const saveButton = $('save-stage');
  const formCard = permit?.closest('.form-card');
  const nativeStageCard = stageSelect?.closest('section.card');
  const checklist = document.querySelector('.checklist');
  const approvalCard = $('approval-card');

  if (!permit || !worker || !unit || !stageSelect || !stageFields || !saveButton) return;

  document.documentElement.classList.add('ux-enhanced');
  nativeStageCard?.classList.add('ux-native-stage-card');

  let historyFilter = 'all';

  function validPermit() {
    return permit.value.trim().length >= 3 && worker.value.trim().length >= 3 && unit.value;
  }

  function selectedStageMeta() {
    return STAGES.find(s => s.id === stageSelect.value) || STAGES[0];
  }

  function optionDone(id) {
    const option = [...stageSelect.options].find(o => o.value === id);
    if (!option) return false;
    let done = option.textContent.trim().startsWith('✓');
    if (done && id === stageSelect.value) {
      const meta = selectedStageMeta();
      if (meta.kind === 'range') {
        const d2 = $('secondary-date')?.value || '';
        const t2 = $('secondary-time')?.value || '';
        if (!d2 || !t2) done = false;
      }
    }
    return done;
  }

  function approvalStatus() {
    if (!approvalCard || approvalCard.hidden) return 'none';
    if (approvalCard.classList.contains('stopped')) return 'stopped';
    if (approvalCard.classList.contains('pending')) return 'pending';
    if (approvalCard.classList.contains('approved')) return 'approved';
    return 'other';
  }

  function recommendedStage() {
    if (approvalStatus() === 'stopped') return STAGES.find(s => s.id === 'RESUME_WORK');
    return STAGES.filter(s => !s.optional).find(s => !optionDone(s.id)) || null;
  }

  function contextualAction() {
    const stage = selectedStageMeta();
    const primaryReady = Boolean($('primary-date')?.value && $('primary-time')?.value);
    const secondaryBlank = !($('secondary-date')?.value || $('secondary-time')?.value);
    switch (stage.id) {
      case 'PREPARATION': return !primaryReady ? 'Передать начало подготовки' : secondaryBlank ? 'Передать окончание подготовки' : 'Передать изменения подготовки';
      case 'TRANSFER_WORK': return 'Передать объект';
      case 'ACTUAL_WORK': return !primaryReady ? 'Передать фактическое начало' : secondaryBlank ? 'Передать фактическое окончание' : 'Передать изменения по работам';
      case 'STOP_WORK': return 'Передать остановку работ';
      case 'RESUME_WORK': return 'Передать возобновление работ';
      case 'EXTEND_WORK': return 'Передать продление РПО';
      case 'REPLACEMENTS': return 'Передать замену исполнителей';
      default: return 'Передать данные этапа';
    }
  }

  function createOverview() {
    if ($('ux-permit-overview')) return;
    const overview = document.createElement('section');
    overview.id = 'ux-permit-overview';
    overview.className = 'ux-permit-overview';
    overview.innerHTML = `
      <div class="ux-overview-head">
        <div class="ux-overview-copy"><strong id="ux-permit-number"></strong><span id="ux-permit-meta"></span></div>
        <button type="button" class="ux-overview-edit" id="ux-overview-edit">✎ Изменить</button>
      </div>
      <div class="ux-next-action">
        <div><small>Следующее действие</small><b id="ux-next-action-label">—</b></div>
        <button type="button" id="ux-next-open" hidden>Открыть</button>
      </div>`;
    formCard.insertAdjacentElement('afterend', overview);
    $('ux-overview-edit').addEventListener('click', () => {
      formCard.classList.toggle('ux-collapsed');
      if (!formCard.classList.contains('ux-collapsed')) permit.focus({preventScroll:false});
    });
    $('ux-next-open').addEventListener('click', () => {
      const next = recommendedStage();
      if (!next) return;
      stageSelect.value = next.id;
      stageSelect.dispatchEvent(new Event('change', {bubbles:true}));
      stageFields.scrollIntoView({behavior:'smooth', block:'start'});
    });
  }

  function updateOverview() {
    const overview = $('ux-permit-overview');
    if (!overview) return;
    const ready = validPermit();
    overview.classList.toggle('visible', Boolean(ready));
    if (!ready) {
      formCard.classList.remove('ux-collapsed');
      return;
    }
    $('ux-permit-number').textContent = permit.value.trim().toUpperCase();
    $('ux-permit-meta').textContent = `${unit.value} · ${worker.value.trim()}`;
    const next = recommendedStage();
    const nextLabel = approvalStatus() === 'stopped' ? 'Возобновление работ' : next ? next.title : 'Обязательные этапы заполнены';
    $('ux-next-action-label').textContent = nextLabel;
    const open = $('ux-next-open');
    open.hidden = !next || next.id === stageSelect.value;
    if (!formCard.dataset.uxCollapsedOnce) {
      formCard.dataset.uxCollapsedOnce = '1';
      formCard.classList.add('ux-collapsed');
    }
  }

  function createStageRail() {
    if ($('ux-stage-section')) return;
    const section = document.createElement('section');
    section.id = 'ux-stage-section';
    section.className = 'ux-stage-section';
    section.innerHTML = `<div class="ux-stage-heading"><b>Ход наряда-допуска</b><span id="ux-stage-count">0/6</span></div><div id="ux-stage-rail" class="ux-stage-rail"></div>`;
    nativeStageCard.insertAdjacentElement('beforebegin', section);
  }

  function updateStageRail() {
    const rail = $('ux-stage-rail');
    if (!rail) return;
    const selected = stageSelect.value;
    const completed = STAGES.filter(s => !s.optional && optionDone(s.id)).length;
    $('ux-stage-count').textContent = `${completed}/${STAGES.filter(s => !s.optional).length}`;
    rail.innerHTML = STAGES.map((stage, index) => {
      const done = optionDone(stage.id);
      const active = selected === stage.id;
      const cls = ['ux-stage-chip', done?'done':'', active?'active':'', stage.optional?'optional':''].filter(Boolean).join(' ');
      const status = done ? 'Передано' : active ? 'Текущий этап' : stage.optional ? 'Необязательно' : 'Не заполнено';
      return `<button type="button" class="${cls}" data-ux-stage="${stage.id}"><span class="ux-stage-index">${done?'✓':index+1}</span><strong>${stage.title}</strong><small>${status}</small></button>`;
    }).join('');
    rail.querySelectorAll('[data-ux-stage]').forEach(button => button.addEventListener('click', () => {
      stageSelect.value = button.dataset.uxStage;
      stageSelect.dispatchEvent(new Event('change', {bubbles:true}));
    }));
    const active = rail.querySelector('.ux-stage-chip.active');
    active?.scrollIntoView({behavior:'smooth', block:'nearest', inline:'center'});
  }

  function sentNote() {
    stageFields.querySelector('.ux-sent-note')?.remove();
    const stage = selectedStageMeta();
    let text = '';
    if (optionDone(stage.id)) {
      text = 'Этот этап полностью передан на сервер. Изменяйте значения только если нужна корректировка.';
    } else if (stage.kind === 'range' && $('primary-date')?.value && $('primary-time')?.value && !$('secondary-date')?.value && !$('secondary-time')?.value && approvalStatus() !== 'none') {
      text = 'Начало уже заполнено. При передаче окончания повторно отправятся только новые данные.';
    }
    if (!text) return;
    const note = document.createElement('div');
    note.className = 'ux-sent-note';
    note.innerHTML = `<b>✓</b><span>${text}</span>`;
    stageFields.querySelector('.subtitle')?.insertAdjacentElement('afterend', note);
  }

  function readinessText() {
    const checks = [
      ['check-worker','Укажите ФИО ответственного'],
      ['check-unit','Выберите подразделение'],
      ['check-permit','Проверьте номер НД'],
      ['check-stage','Заполните обязательные поля этапа'],
    ];
    const missing = checks.find(([id]) => !$(id)?.classList.contains('ok'));
    return missing ? missing[1] : 'Готово к передаче. Уже переданные значения повторно не отправятся.';
  }

  function updateReadiness() {
    if (!checklist) return;
    let status = checklist.querySelector('.ux-readiness');
    if (!status) {
      status = document.createElement('div');
      status.className = 'ux-readiness';
      checklist.appendChild(status);
    }
    const ready = Boolean($('check-worker')?.classList.contains('ok') && $('check-unit')?.classList.contains('ok') && $('check-permit')?.classList.contains('ok') && $('check-stage')?.classList.contains('ok'));
    checklist.classList.toggle('ready', ready);
    checklist.classList.toggle('needs-input', !ready);
    status.innerHTML = `<b>${ready?'✓':'!'}</b><span>${readinessText()}</span>`;
  }

  function updateActionButton() {
    const span = saveButton.querySelector('span:last-child');
    if (span) span.textContent = contextualAction();
    else saveButton.textContent = contextualAction();
  }

  function updateConnectionBadge() {
    const badge = document.querySelector('.no-login');
    if (!badge) return;
    const queue = document.getElementById('queue-notice');
    const failed = queue && !queue.hidden && /ошиб/i.test($('queue-text')?.textContent || '');
    const online = navigator.onLine;
    const dotClass = failed ? 'error' : online ? '' : 'offline';
    badge.innerHTML = `<span class="ux-status-dot ${dotClass}"></span>${failed?'Проверить':online?'Готово':'Офлайн'}`;
  }

  function createHistoryTools() {
    const history = $('tab-history');
    const list = $('history-list');
    if (!history || !list || $('ux-history-tools')) return;
    const tools = document.createElement('div');
    tools.id = 'ux-history-tools';
    tools.className = 'ux-history-tools';
    tools.innerHTML = `<input id="ux-history-search" class="ux-history-search" type="search" placeholder="Номер НД, ФИО или подразделение"><div class="ux-history-filters"><button type="button" class="ux-filter active" data-history-filter="all">Все</button><button type="button" class="ux-filter" data-history-filter="pending">Ожидают</button><button type="button" class="ux-filter" data-history-filter="approved">Разрешено</button></div>`;
    list.insertAdjacentElement('beforebegin', tools);
    $('ux-history-search').addEventListener('input', applyHistoryFilter);
    tools.querySelectorAll('[data-history-filter]').forEach(button => button.addEventListener('click', () => {
      historyFilter = button.dataset.historyFilter;
      tools.querySelectorAll('[data-history-filter]').forEach(x => x.classList.toggle('active', x === button));
      applyHistoryFilter();
    }));
  }

  function applyHistoryFilter() {
    const query = ($('ux-history-search')?.value || '').trim().toLowerCase();
    document.querySelectorAll('#history-list .history-card').forEach(card => {
      const text = card.textContent.toLowerCase();
      const matchesQuery = !query || text.includes(query);
      const matchesStatus = historyFilter === 'all' || (historyFilter === 'pending' ? /ожидает разрешения/i.test(text) : /разрешено/i.test(text));
      card.hidden = !(matchesQuery && matchesStatus);
    });
  }

  function refreshUx() {
    updateOverview();
    updateStageRail();
    sentNote();
    updateActionButton();
    updateReadiness();
    updateConnectionBadge();
    applyHistoryFilter();
  }

  createOverview();
  createStageRail();
  createHistoryTools();

  ['input','change'].forEach(type => document.addEventListener(type, event => {
    if (event.target.closest?.('#tab-form')) queueMicrotask(refreshUx);
  }));
  window.addEventListener('online', refreshUx);
  window.addEventListener('offline', refreshUx);
  document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => setTimeout(refreshUx, 0)));

  new MutationObserver(() => queueMicrotask(refreshUx)).observe(stageSelect, {childList:true, subtree:true, characterData:true});
  new MutationObserver(() => queueMicrotask(refreshUx)).observe(stageFields, {childList:true, subtree:true});
  if (approvalCard) new MutationObserver(() => queueMicrotask(refreshUx)).observe(approvalCard, {attributes:true, childList:true, subtree:true});
  const historyList = $('history-list');
  if (historyList) new MutationObserver(() => queueMicrotask(applyHistoryFilter)).observe(historyList, {childList:true, subtree:true});

  setTimeout(refreshUx, 0);
  setInterval(updateConnectionBadge, 3000);
})();

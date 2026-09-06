(() => {
  'use strict';

  const root = document.getElementById('instruction-root');
  if (!root) return;

  const risks = [
    {id:'movement',icon:'🚜',title:'Движущаяся техника / механизмы',measures:['Определите границы безопасной зоны и исключите нахождение людей в зоне движения.','По возможности устраните источник опасности либо ограничьте контакт с ним.']},
    {id:'height',icon:'🪜',title:'Падение с высоты',measures:['Проверьте исправность системы защиты от падения и средств индивидуальной защиты.','Проверьте леса, подмости, лестницы и точки крепления перед использованием.']},
    {id:'pressure',icon:'⏱',title:'Давление / энергия среды',measures:['Убедитесь, что опасная энергия изолирована и давление снижено до безопасного состояния.','Проверьте блокировки, предупреждающие знаки и невозможность ошибочного включения.']},
    {id:'electric',icon:'⚡',title:'Электричество',measures:['Изолируйте источники энергии перед ремонтом и обслуживанием оборудования.','Проверьте надёжность отключения и невозможность самопроизвольного включения.']},
    {id:'fire',icon:'🔥',title:'Пожар / взрыв',measures:['Обсудите возможные источники воспламенения и меры по их исключению.','При изменении условий немедленно остановите работу и повторно оцените опасности.']},
    {id:'gas',icon:'☣',title:'Газ / вредные вещества',measures:['Проверьте исправность газоанализатора, СИЗОД и спасательного оборудования, если они требуются условиями работ.','При первых признаках отравления, удушения или срабатывании газоанализатора немедленно прекратите работу.']},
    {id:'temperature',icon:'🌡',title:'Высокая / низкая температура',measures:['Обсудите источники высокой или низкой температуры и возможность контакта с ними.','Определите необходимые средства защиты и безопасный порядок выполнения операций.']},
    {id:'people',icon:'👥',title:'Персонал / нештатные действия',measures:['Уточните зону ответственности каждого работника и порядок взаимодействия.','Напомните право приостановить работу, если требования безопасности невозможно соблюдать.']},
  ];

  const knowledge = [
    {category:'Наряд-допуск',title:'Что проверить перед началом работ',body:['Требования наряда-допуска понятны исполнителям.','Меры безопасности, указанные в наряде-допуске, выполнены.','Инструмент, оборудование, СИЗ и СКЗ исправны и готовы к применению.'],source:'Основные правила безопасности / РОИ'},
    {category:'Наряд-допуск',title:'Если изменились условия работы',body:['Остановите работу.','Сообщите руководителю.','Повторно обсудите опасности, меры безопасности и порядок действий.'],source:'Пять шагов безопасности / РОИ'},
    {category:'Наряд-допуск',title:'Когда нужен повторный инструктаж',body:['Изменилась производственная задача.','Изменился состав исполнителей.','Изменилось место проведения работ.','Работы были остановлены или выявлены ранее неучтённые опасности.'],source:'Памятка «Риск ориентированный инструктаж»'},
    {category:'Высота',title:'Работы на высоте',body:['Проверьте исправность системы защиты от падения перед использованием.','Проверьте устойчивость и состояние лесов, подмостей и лестниц.','Не продолжайте работу при недостаточной видимости и других небезопасных условиях.'],source:'Основные правила безопасности'},
    {category:'Изоляция энергии',title:'Изоляция источников энергии',body:['Перед ремонтом и обслуживанием изолируйте опасные источники энергии.','Проверьте блокировки и предупреждающие знаки.','Не снимайте блокировки до полного завершения работ и проверки оборудования.'],source:'Основные правила безопасности'},
    {category:'Газоопасные',title:'Газоанализатор и СИЗОД',body:['Проверьте исправность газоанализатора, СИЗОД и спасательного оборудования.','Контролируйте воздушную среду в соответствии с условиями проведения работ.','При срабатывании газоанализатора или признаках отравления немедленно прекратите работу.'],source:'Основные правила безопасности'},
    {category:'Грузоподъёмные',title:'Стропы и груз',body:['Подбирайте стропы по массе груза и схеме строповки.','Проверьте исправность строп и грузозахватных приспособлений.','Не находитесь в зоне возможного падения груза.'],source:'Основные правила безопасности'},
  ];

  let view = 'home';
  let step = 1;
  let selected = new Set();
  let knowledgeCategory = 'Все';
  let knowledgeQuery = '';

  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const permitValue = () => document.getElementById('permit-number')?.value.trim().toUpperCase() || '';
  const workerValue = () => document.getElementById('worker-name')?.value.trim() || '';
  const unitValue = () => document.getElementById('structural-unit')?.value || '';
  const completionKey = () => `rpo_instruction_${permitValue() || 'general'}`;
  const completion = () => localStorage.getItem(completionKey()) || '';

  function permitCard() {
    const permit = permitValue();
    const worker = workerValue();
    const unit = unitValue();
    return `<div class="instruction-permit"><div class="instruction-permit-icon">📄</div><div class="instruction-permit-copy"><strong>${permit ? `НД ${escapeHtml(permit)}` : 'НД не выбран'}</strong><span>${escapeHtml(unit || 'Выберите НД во вкладке «Работа»')}</span>${worker ? `<span>${escapeHtml(worker)}</span>` : ''}</div><div class="instruction-status">Перед началом работ</div></div>`;
  }

  function progress(active) {
    const labels = ['Подготовка','Опасности','Меры','Нештатные','Готовность'];
    return `<div class="instruction-progress">${labels.map((label,i)=>`<div class="instruction-step-marker ${active===i+1?'active':''}"><span>${i+1}</span>${label}</div>`).join('')}</div>`;
  }

  function shell(content) {
    root.innerHTML = `<div class="instruction-shell">${content}</div>`;
  }

  function renderHome() {
    view = 'home';
    const done = completion();
    shell(`
      <div class="instruction-title"><h1>Помощник при инструктаже</h1><p>Короткие подсказки для проведения риск-ориентированного инструктажа перед началом работ.</p></div>
      <div class="instruction-info">РОИ — модель проведения инструктажа и не является отдельным видом инструктажа.</div>
      ${permitCard()}
      ${done ? `<div class="instruction-tip green">✓ Последнее прохождение помощника: ${escapeHtml(done)}</div>` : ''}
      <div class="instruction-card"><h2>Что сделать сейчас</h2>
        <button type="button" class="instruction-primary-tile" data-instruction-action="start"><span class="play">▶</span><span><strong>Провести инструктаж</strong><small>5 последовательных шагов</small></span><span class="arrow">›</span></button>
        <div class="instruction-shortcuts">
          <button type="button" class="instruction-shortcut" data-instruction-step="2"><span>🛡</span><b>Основные опасности</b><i>›</i></button>
          <button type="button" class="instruction-shortcut" data-instruction-step="3"><span>⛑</span><b>Меры безопасности</b><i>›</i></button>
          <button type="button" class="instruction-shortcut" data-instruction-step="4"><span>⚠</span><b>Нештатная ситуация</b><i>›</i></button>
          <button type="button" class="instruction-shortcut" data-instruction-action="knowledge"><span>📖</span><b>Мини-база знаний</b><i>›</i></button>
        </div>
      </div>
      ${progress(0)}
      <button type="button" class="instruction-main-button" data-instruction-action="start">▶ Начать инструктаж</button>`);
    bindHome();
  }

  function bindHome() {
    root.querySelectorAll('[data-instruction-action="start"]').forEach(btn=>btn.addEventListener('click',()=>{step=1;renderFlow();}));
    root.querySelector('[data-instruction-action="knowledge"]')?.addEventListener('click',renderKnowledge);
    root.querySelectorAll('[data-instruction-step]').forEach(btn=>btn.addEventListener('click',()=>{step=Number(btn.dataset.instructionStep)||1;renderFlow();}));
  }

  function stepOne() {
    const rows = [
      ['📋','Последовательность этапов и операций','Обсудите, какие работы будут выполняться и в какой последовательности.'],
      ['👥','Зона ответственности каждого работника','Уточните роли и обязанности участников работ.'],
      ['🔧','Состояние инструмента и оборудования','Проверьте исправность и пригодность к работе.'],
      ['⛑','Наличие и исправность СИЗ и СКЗ','Убедитесь, что необходимые средства защиты есть и исправны.'],
    ];
    return `<div class="instruction-flow-head"><h2>Обсудите характер предстоящей работы</h2><p>Совместно с исполнителями проговорите, что и как будет выполняться.</p></div><div class="instruction-list">${rows.map(r=>`<div class="instruction-list-row"><div class="instruction-emoji">${r[0]}</div><div><strong>${r[1]}</strong><p>${r[2]}</p></div></div>`).join('')}</div><div class="instruction-tip">💡 Подсказка: попросите одного из работников кратко повторить порядок действий.</div>`;
  }

  function stepTwo() {
    return `<div class="instruction-flow-head"><h2>Определите основные опасности</h2><p>Выберите опасности, которые нужно обсудить с бригадой перед началом работ.</p></div><div class="instruction-risk-grid">${risks.map(r=>`<button type="button" class="instruction-risk ${selected.has(r.id)?'selected':''}" data-risk="${r.id}"><span class="ri">${r.icon}</span><strong>${r.title}</strong><span class="check">${selected.has(r.id)?'✓':'○'}</span></button>`).join('')}</div><div class="instruction-info">Выбранные опасности будут использованы в подсказках по мерам безопасности.</div>`;
  }

  function stepThree() {
    const items = risks.filter(r=>selected.has(r.id));
    const cards = items.length ? items.map(r=>`<article class="instruction-measure"><h3>${r.icon} ${r.title}</h3><ul>${r.measures.map(m=>`<li>${m}</li>`).join('')}</ul></article>`).join('') : `<div class="instruction-tip">На предыдущем шаге опасности не выбраны. Используйте общую последовательность: устранить источник → ограничить контакт → применить организационные меры и СИЗ.</div>`;
    return `<div class="instruction-flow-head"><h2>Обсудите меры безопасности</h2><p>Для каждого выявленного риска проговорите конкретные меры защиты.</p></div>${cards}<div class="instruction-tip green">Напомните: каждый исполнитель имеет право отказаться от работы или приостановить её, если требования безопасности невозможно соблюдать, и должен сообщить об этом руководителю.</div>`;
  }

  function stepFour() {
    const rows = [
      ['⚠','Что может пойти не так','Обсудите возможные непредвиденные ситуации для конкретной работы.'],
      ['🛑','Остановка работы','При изменении условий прекратите выполнение операции и сообщите руководителю.'],
      ['🚪','Эвакуация','Обсудите порядок выхода из опасной зоны и место безопасного сбора, если это предусмотрено объектом.'],
      ['📞','Связь','Проверьте средства связи и уточните используемые на объекте номера экстренных служб.'],
    ];
    return `<div class="instruction-flow-head"><h2>Обсудите действия в нештатной ситуации</h2><p>Бригада должна заранее понимать порядок действий при изменении обстановки.</p></div><div class="instruction-list">${rows.map(r=>`<div class="instruction-list-row"><div class="instruction-emoji">${r[0]}</div><div><strong>${r[1]}</strong><p>${r[2]}</p></div></div>`).join('')}</div>`;
  }

  function stepFive() {
    return `<div class="instruction-flow-head"><h2>Определите готовность приступить к безопасному выполнению работ</h2><p>Завершите инструктаж коротким устным опросом и убедитесь, что у работников не осталось вопросов.</p></div><div class="instruction-card"><h2>Задайте 2–3 вопроса</h2><p>1. Какова последовательность вашей работы?</p><p>2. Какие основные опасности есть на этом рабочем месте?</p><p>3. Что вы сделаете, если условия работы изменятся?</p><p>4. Какие меры защиты необходимо соблюдать?</p></div><div class="instruction-tip green">Перед завершением: выясните, есть ли дополнительные вопросы; проверьте знания устным опросом по специфике работы и технологическим операциям; ответственное лицо принимает решение о готовности к безопасному выполнению работ.</div>`;
  }

  function renderFlow() {
    view = 'flow';
    const bodies = {1:stepOne,2:stepTwo,3:stepThree,4:stepFour,5:stepFive};
    const nextLabels = {1:'Далее: опасности',2:'Далее: меры',3:'Далее: нештатные',4:'Далее: готовность'};
    shell(`<div class="instruction-title"><h1>Инструктаж: шаг ${step} из 5</h1></div>${bodies[step]()}${progress(step)}<div class="instruction-flow-actions"><button type="button" class="instruction-secondary-button" data-flow-back>${step===1?'К обзору':'Назад'}</button>${step<5?`<button type="button" class="instruction-main-button" data-flow-next>${nextLabels[step]}</button>`:`<button type="button" class="instruction-main-button green" data-flow-complete>Завершить помощник</button>`}</div>`);
    root.querySelector('[data-flow-back]')?.addEventListener('click',()=>{if(step>1){step--;renderFlow();}else renderHome();});
    root.querySelector('[data-flow-next]')?.addEventListener('click',()=>{if(step<5){step++;renderFlow();}});
    root.querySelector('[data-flow-complete]')?.addEventListener('click',()=>{const now=new Date().toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});localStorage.setItem(completionKey(),now);renderHome();});
    root.querySelectorAll('[data-risk]').forEach(btn=>btn.addEventListener('click',()=>{const id=btn.dataset.risk;if(selected.has(id))selected.delete(id);else selected.add(id);renderFlow();}));
  }

  function renderKnowledge() {
    view = 'knowledge';
    const categories = ['Все','Наряд-допуск','Газоопасные','Высота','Изоляция энергии','Грузоподъёмные'];
    const filtered = knowledge.filter(card => (knowledgeCategory==='Все'||card.category===knowledgeCategory) && (!knowledgeQuery || `${card.title} ${card.body.join(' ')}`.toLowerCase().includes(knowledgeQuery.toLowerCase())));
    shell(`<div class="instruction-title"><h1>Мини-база знаний</h1><p>Краткие подсказки по материалам РОИ, методики «Пять шагов» и основных правил безопасности.</p></div><input id="instruction-search" class="instruction-search" type="search" placeholder="Что нужно уточнить?" value="${escapeHtml(knowledgeQuery)}"><div class="instruction-chips">${categories.map(c=>`<button type="button" class="instruction-chip ${knowledgeCategory===c?'active':''}" data-knowledge-category="${c}">${c}</button>`).join('')}</div>${filtered.length?filtered.map(card=>`<article class="knowledge-card"><h3>${card.title}</h3><ul>${card.body.map(x=>`<li>${x}</li>`).join('')}</ul><div class="knowledge-source">Источник: ${card.source}</div></article>`).join(''):'<div class="instruction-empty">По запросу ничего не найдено в локальной базе подсказок.</div>'}<button type="button" class="instruction-main-button" data-knowledge-back>Вернуться к инструктажу</button>`);
    root.querySelector('#instruction-search')?.addEventListener('input',e=>{knowledgeQuery=e.target.value;renderKnowledge();const field=root.querySelector('#instruction-search');field?.focus();field?.setSelectionRange(knowledgeQuery.length,knowledgeQuery.length);});
    root.querySelectorAll('[data-knowledge-category]').forEach(btn=>btn.addEventListener('click',()=>{knowledgeCategory=btn.dataset.knowledgeCategory;renderKnowledge();}));
    root.querySelector('[data-knowledge-back]')?.addEventListener('click',renderHome);
  }

  document.querySelector('[data-tab="instruction"]')?.addEventListener('click',()=>{
    if (view === 'home') renderHome();
  });
  document.getElementById('permit-number')?.addEventListener('change',()=>{if(view==='home')renderHome();});
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&view==='home')renderHome();});
  renderHome();
})();

(() => {
  'use strict';

  const PWA_VERSION = '1.2.1';
  const ANDROID_API_VERSION = '2.0.1';
  const UNITS = ['ЦДПН-1','ЦДПН-2','ЦДПН-3','ЦДПН-4','ЦППН-1','ЦППН-2','ЦСДиТГ','ЦСиР','ЦТОиРТ-1','ЦТОиРТ-2'];
  const STAGES = [
    {id:'PREPARATION',title:'Подготовка',kind:'range',events:[['AT','Начало подготовки'],['AU','Окончание подготовки']]},
    {id:'TRANSFER_WORK',title:'Передача объекта',kind:'datetime',events:[['AV','Передача ОП к ОБПР']]},
    {id:'ACTUAL_WORK',title:'Фактическое начало и окончание работ',kind:'range',events:[['AY','Фактическое начало работ'],['BC','Фактическое окончание работ']]},
    {id:'STOP_WORK',title:'Остановка работ',kind:'stop',events:[['AZ','Остановка работ']]},
    {id:'RESUME_WORK',title:'Возобновление работ',kind:'resume',events:[['BA','Возобновление работ']]},
    {id:'EXTEND_WORK',title:'Продление РПО',kind:'extension',events:[['BE','Продление РПО']]},
    {id:'REPLACEMENTS',title:'Замена исполнителей работ',kind:'replacements',events:[['RI','Замена исполнителей работ']],optional:true},
  ];
  const REQUIRED_STAGE_IDS = STAGES.filter(s => !s.optional).map(s => s.id);
  const STORAGE = {
    device:'rpo_pwa_device_v1', queue:'rpo_pwa_queue_v1', memories:'rpo_pwa_memories_v1',
    saved:'rpo_pwa_saved_v1', worker:'rpo_pwa_worker_v1', unit:'rpo_pwa_unit_v1', installHidden:'rpo_pwa_install_hidden_v1'
  };

  const $ = id => document.getElementById(id);
  const worker = $('worker-name');
  const unit = $('structural-unit');
  const permit = $('permit-number');
  const stageSelect = $('stage-select');
  const stageFields = $('stage-fields');
  const saveButton = $('save-stage');

  let serverFields = {};
  let currentApproval = null;
  let permitLookupTimer = null;
  let approvalTimer = null;
  let baselineFingerprint = '';
  let replacementCounter = 1;
  let remotePermitSuggestions = [];
  let permitSuggestionTimer = null;
  let noNewEvents = false;

  function jsonRead(key, fallback) {
    try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback; }
    catch (_) { return fallback; }
  }
  function jsonWrite(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
  function makeId() { return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  function deviceId() {
    let id = localStorage.getItem(STORAGE.device);
    if (!id) { id = `pwa-${makeId()}`; localStorage.setItem(STORAGE.device, id); }
    return id;
  }
  function stripLatin(value) { return String(value || '').replace(/[A-Za-z]/g, ''); }
  function hasLatin(value) { return /[A-Za-z]/.test(String(value || '')); }
  function sanitizeTextInput(input, messageId) {
    input.addEventListener('input', () => {
      const hadLatin = hasLatin(input.value);
      if (hadLatin) input.value = stripLatin(input.value);
      if (messageId && hadLatin) {
        const el = $(messageId); el.textContent = 'Используйте русскую раскладку: латинские буквы не принимаются';
        setTimeout(() => { if (el.textContent.startsWith('Используйте')) el.textContent = ''; }, 2600);
      }
      updateChecklist();
    });
  }

  function permitValid(value=permit.value) {
    return /^[0-9А-ЯЁ._/\\\- ]{3,80}$/u.test(String(value).trim().toUpperCase());
  }
  function pad(n) { return String(n).padStart(2,'0'); }
  function dateValue(date) { return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}`; }
  function timeValue(date) { return `${pad(date.getHours())}:${pad(date.getMinutes())}`; }
  function humanDate(isoDate) {
    if (!isoDate) return '';
    const [y,m,d] = isoDate.split('-');
    return y && m && d ? `${d}.${m}.${y}` : '';
  }
  function humanDateTime(date, time) { return `${humanDate(date)} ${time}`.trim(); }
  function localDateFromServer(value) {
    if (!value) return {date:'',time:''};
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? {date:'',time:''} : {date:dateValue(d),time:timeValue(d)};
  }
  function toEventIso(date, time) {
    const d = new Date(`${date}T${time}:00`);
    return Number.isNaN(d.getTime()) ? null : d.toISOString();
  }
  function validateOperationalDateTime(date, time) {
    if (!date || !time) return 'Укажите дату и время';
    const d = new Date(`${date}T${time}:00`);
    if (Number.isNaN(d.getTime())) return 'Проверьте дату и время';
    const now = Date.now();
    if (d.getTime() > now + 5*60*1000) return 'Дата и время фактического этапа не могут быть в будущем';
    if (d.getTime() < now - 45*24*60*60*1000) return 'Дата события слишком старая';
    return '';
  }

  function memories() { return jsonRead(STORAGE.memories, []); }
  function rememberPermit() {
    const p = permit.value.trim().toUpperCase();
    if (!permitValid(p)) return;
    const items = memories().filter(x => x.permitNumber !== p);
    items.unshift({permitNumber:p,workerName:worker.value.trim(),structuralUnit:unit.value,updatedAt:new Date().toISOString()});
    jsonWrite(STORAGE.memories, items.slice(0,40));
    renderPermitSuggestions();
  }
  function combinedPermitSuggestions() {
    const byPermit = new Map();
    [...memories().map(m=>({permit_number:m.permitNumber,worker_name:m.workerName,structural_unit:m.structuralUnit||''})), ...remotePermitSuggestions]
      .forEach(item=>{const key=String(item.permit_number||'').toUpperCase();if(key&&!byPermit.has(key))byPermit.set(key,item);});
    return [...byPermit.values()];
  }
  function selectPermitSuggestion(item) {
    permit.value=stripLatin(item.permit_number||'').toUpperCase();
    if(item.worker_name)worker.value=stripLatin(item.worker_name);
    if(UNITS.includes(item.structural_unit))unit.value=item.structural_unit;
    const menu=$('permit-suggestion-menu');if(menu)menu.hidden=true;
    lookupPermit(true);updateChecklist();
  }
  function renderPermitSuggestions() {
    const items=combinedPermitSuggestions();
    const list=$('permit-suggestions');
    list.replaceChildren(...items.map(m=>{const option=document.createElement('option');option.value=m.permit_number;option.label=m.worker_name||m.structural_unit||'';return option;}));
    const menu=$('permit-suggestion-menu');if(!menu)return;
    const q=permit.value.trim().toUpperCase();
    const filtered=items.filter(m=>!q||String(m.permit_number||'').toUpperCase().includes(q)).slice(0,8);
    if(document.activeElement!==permit||!filtered.length){menu.hidden=true;menu.innerHTML='';return;}
    menu.innerHTML=filtered.map((m,i)=>`<button type="button" class="permit-suggestion-item" data-index="${i}"><strong>${escapeHtml(m.permit_number)}</strong><span>${escapeHtml(m.worker_name||m.structural_unit||'Ранее заполненный НД')}</span></button>`).join('');
    menu.hidden=false;
    menu.querySelectorAll('[data-index]').forEach(btn=>btn.addEventListener('mousedown',e=>e.preventDefault()));
    menu.querySelectorAll('[data-index]').forEach(btn=>btn.addEventListener('click',()=>selectPermitSuggestion(filtered[Number(btn.dataset.index)])));
  }
  async function fetchRemotePermitSuggestions() {
    const q=permit.value.trim().toUpperCase();
    if(q.length<3||!navigator.onLine){remotePermitSuggestions=[];renderPermitSuggestions();return;}
    try{const r=await fetch(`/api/mobile/permit-suggestions?q=${encodeURIComponent(q)}&limit=8`,{cache:'no-store'});if(r.ok)remotePermitSuggestions=await r.json();}
    catch(_){}
    renderPermitSuggestions();
  }
  function schedulePermitSuggestions(){clearTimeout(permitSuggestionTimer);renderPermitSuggestions();if(permit.value.trim().length>=3)permitSuggestionTimer=setTimeout(fetchRemotePermitSuggestions,250);}

  function savedStore() { return jsonRead(STORAGE.saved, {}); }
  function savedForPermit() {
    const p = permit.value.trim().toUpperCase();
    return new Set((savedStore()[p] || []));
  }
  function markStageSaved(stageId) {
    const p=permit.value.trim().toUpperCase(); if (!p) return;
    const store=savedStore(); const set=new Set(store[p] || []); set.add(stageId); store[p]=[...set]; jsonWrite(STORAGE.saved,store);
  }
  function serverSavedStages() {
    const keys = new Set(Object.keys(serverFields || {}));
    const out = new Set();
    STAGES.forEach(s => {
      const eventKeys=s.events.map(x=>x[0]);
      if (s.kind==='range' ? keys.has(eventKeys[0]) : eventKeys.every(k=>keys.has(k))) out.add(s.id);
    });
    return out;
  }
  function allSavedStages() { return new Set([...savedForPermit(), ...serverSavedStages()]); }

  function renderStageOptions() {
    const saved=allSavedStages();
    const current=stageSelect.value || STAGES[0].id;
    stageSelect.replaceChildren(...STAGES.map(s => {
      const o=document.createElement('option'); o.value=s.id; o.textContent=`${saved.has(s.id)?'✓ ':''}${s.title}${s.optional?' · необязательно':''}`; return o;
    }));
    if (STAGES.some(s=>s.id===current)) stageSelect.value=current;
    $('saved-count').textContent=`${REQUIRED_STAGE_IDS.filter(id=>saved.has(id)).length}/${REQUIRED_STAGE_IDS.length}`;
  }
  function currentStage() { return STAGES.find(s=>s.id===stageSelect.value) || STAGES[0]; }

  function inputBlock(title, prefix, optional=false) {
    return `<div class="field-block"><label>${title}${optional?' <span class="muted-inline">(можно заполнить позже)</span>':''}</label><div class="datetime-grid"><input class="date-control" id="${prefix}-date" type="date"><input class="time-control" id="${prefix}-time" type="time" step="60"></div><div class="now-row"><button type="button" class="now-button" data-now="${prefix}">◷ Сейчас</button><div class="field-error" id="${prefix}-error"></div></div></div>`;
  }
  function fieldServer(key) { return (serverFields && serverFields[key]) || null; }
  function setDateTimeFromField(prefix,key) {
    const field=fieldServer(key); if(!field) return;
    const parsed=localDateFromServer(field.event_time); const d=$(`${prefix}-date`),t=$(`${prefix}-time`); if(d)d.value=parsed.date;if(t)t.value=parsed.time;
  }
  function filterDynamicLatin(input) {
    input.addEventListener('input',()=>{ if(hasLatin(input.value)){input.value=stripLatin(input.value); showFlash(false,'Русская раскладка','Латинские буквы не принимаются.');} updateChecklist(); });
  }
  function bindDynamicInputs() {
    stageFields.querySelectorAll('input,textarea,select').forEach(el=>el.addEventListener('input',updateChecklist));
    stageFields.querySelectorAll('textarea[type="text"],input[data-russian="true"],textarea[data-russian="true"]').forEach(filterDynamicLatin);
    stageFields.querySelectorAll('[data-now]').forEach(btn=>btn.addEventListener('click',()=>{
      const now=new Date(); const prefix=btn.dataset.now; $(`${prefix}-date`).value=dateValue(now); $(`${prefix}-time`).value=timeValue(now); updateChecklist();
    }));
  }
  function renderStageFields() {
    const s=currentStage(); replacementCounter=1;
    let html=`<h2>${s.title}</h2><p class="subtitle">${s.optional?'Необязательный раздел. Заполняйте только при необходимости.':'Заполните фактические данные этапа.'}</p>`;
    if(s.kind==='range') {
      html+=inputBlock(s.events[0][1],'primary',false)+inputBlock(s.events[1][1],'secondary',true);
      html+=`<div class="field-block"><label>Комментарий (необязательно)</label><textarea id="stage-comment" data-russian="true" class="textarea" placeholder="Комментарий к этапу"></textarea></div>`;
    } else if(s.kind==='datetime') {
      html+=inputBlock(s.events[0][1],'primary',false)+`<div class="field-block"><label>Комментарий (необязательно)</label><textarea id="stage-comment" data-russian="true" class="textarea" placeholder="Комментарий к этапу"></textarea></div>`;
    } else if(s.kind==='stop') {
      html+=inputBlock('Дата и время остановки','primary',false)+`<div class="field-block"><label>Причина остановки</label><textarea id="stop-reason" data-russian="true" class="textarea" placeholder="Обязательно укажите причину"></textarea><div class="field-error" id="comment-error"></div></div>`;
    } else if(s.kind==='resume') {
      html+=inputBlock('Дата и время возобновления','primary',false)+`<div class="field-block"><label>Комментарий (обязательно)</label><textarea id="stage-comment" data-russian="true" class="textarea" placeholder="Укажите условия или основание возобновления"></textarea><div class="field-error" id="comment-error"></div></div>`;
    } else if(s.kind==='extension') {
      html+=`<div class="field-block"><label>Новая дата окончания работ</label><input id="extension-date" class="date-control" type="date"><div class="now-row"><button type="button" id="extension-tomorrow" class="now-button">Выбрать завтра</button><div class="field-error" id="extension-error"></div></div></div><div class="field-block"><label>Комментарий (необязательно)</label><textarea id="stage-comment" data-russian="true" class="textarea" placeholder="Причина или примечание"></textarea></div>`;
    } else if(s.kind==='replacements') {
      html+=`<div id="replacement-list" class="replacement-list"></div><button type="button" id="add-replacement" class="add-replacement">＋ Добавить ещё исполнителя</button><div class="field-error" id="replacement-error"></div>`;
    }
    stageFields.innerHTML=html;
    bindDynamicInputs();
    if(s.kind==='range') { setDateTimeFromField('primary',s.events[0][0]); setDateTimeFromField('secondary',s.events[1][0]); const f=fieldServer(s.events[0][0])||fieldServer(s.events[1][0]); if(f&&$('stage-comment'))$('stage-comment').value=f.comment||''; }
    else if(['datetime','stop','resume'].includes(s.kind)) { setDateTimeFromField('primary',s.events[0][0]); const f=fieldServer(s.events[0][0]); if(f){ if(s.kind==='stop'&&$('stop-reason'))$('stop-reason').value=f.comment||''; else if($('stage-comment'))$('stage-comment').value=f.comment||''; } }
    else if(s.kind==='extension') { const f=fieldServer('BE'); if(f){ const [d,m,y]=(f.field_value||'').split('.'); if(y&&m&&d)$('extension-date').value=`${y}-${m}-${d}`; if($('stage-comment'))$('stage-comment').value=f.comment||''; } $('extension-tomorrow').addEventListener('click',()=>{const d=new Date();d.setDate(d.getDate()+1);$('extension-date').value=dateValue(d);updateChecklist();}); }
    else if(s.kind==='replacements') { const f=fieldServer('RI'); const rows=decodeReplacements(f?.field_value||''); rows.forEach((r,i)=>addReplacementRow(r.name,r.position,i===0)); $('add-replacement').addEventListener('click',()=>addReplacementRow('','')); }
    baselineFingerprint=stageFingerprint();
    updateChecklist();
  }

  function decodeReplacements(value) {
    const rows=String(value||'').split(/\r?\n/).map(line=>line.split('\t')).filter(p=>p.length>=2&&((p[0]||'').trim()||(p[1]||'').trim())).map(p=>({name:(p[0]||'').trim(),position:(p.slice(1).join('\t')||'').trim()}));
    return rows.length?rows:[{name:'',position:''}];
  }
  function addReplacementRow(name='',position='',first=false) {
    const list=$('replacement-list'); if(!list)return;
    const idx=replacementCounter++;
    const box=document.createElement('div'); box.className='replacement-item'; box.dataset.replacement=String(idx);
    box.innerHTML=`<div class="replacement-head"><strong>Исполнитель ${list.children.length+1}</strong>${first?'':'<button type="button" class="remove-replacement">Удалить</button>'}</div><div class="field-block"><label>ФИО</label><input data-role="replacement-name" data-russian="true" class="control" type="text" placeholder="Например: Петров П.П." value="${escapeHtml(name)}"></div><div class="field-block"><label>Должность / профессия</label><input data-role="replacement-position" data-russian="true" class="control" type="text" placeholder="Например: электромонтёр" value="${escapeHtml(position)}"></div>`;
    list.appendChild(box); box.querySelectorAll('input').forEach(filterDynamicLatin); box.querySelector('.remove-replacement')?.addEventListener('click',()=>{box.remove();renumberReplacements();updateChecklist();}); updateChecklist();
  }
  function renumberReplacements(){ document.querySelectorAll('.replacement-item').forEach((el,i)=>{const strong=el.querySelector('.replacement-head strong');if(strong)strong.textContent=`Исполнитель ${i+1}`;}); }
  function escapeHtml(value){ return String(value||'').replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch])); }

  function stageFingerprint() {
    const vals=[currentStage().id]; stageFields.querySelectorAll('input,textarea,select').forEach(el=>vals.push(`${el.id||el.dataset.role||''}:${el.value}`)); return vals.join('|');
  }
  function stageReady() {
    const s=currentStage();
    if(s.kind==='range') {
      const d1=$('primary-date')?.value,t1=$('primary-time')?.value,d2=$('secondary-date')?.value,t2=$('secondary-time')?.value;
      if(validateOperationalDateTime(d1,t1))return false;
      if(!d2&&!t2)return true; if(!d2||!t2||validateOperationalDateTime(d2,t2))return false;
      return new Date(`${d2}T${t2}:00`)>=new Date(`${d1}T${t1}:00`);
    }
    if(['datetime','stop','resume'].includes(s.kind)) {
      if(validateOperationalDateTime($('primary-date')?.value,$('primary-time')?.value))return false;
      if(s.kind==='stop')return ($('stop-reason')?.value.trim().length||0)>=3;
      if(s.kind==='resume')return ($('stage-comment')?.value.trim().length||0)>=3;
      return true;
    }
    if(s.kind==='extension'){const v=$('extension-date')?.value;if(!v)return false;const d=new Date(`${v}T00:00:00`),today=new Date();today.setHours(0,0,0,0);return d>=today;}
    if(s.kind==='replacements'){const rows=replacementRows();return rows.length>0&&rows.every(r=>r.name.trim().length>=3&&r.position.trim().length>=2);}
    return false;
  }
  function setCheck(id,ok){const el=$(id);if(!el)return;el.classList.toggle('ok',ok);const s=el.querySelector('span');if(s)s.textContent=ok?'✓':'○';}
  function updateChecklist(){setCheck('check-worker',worker.value.trim().length>=3);setCheck('check-unit',UNITS.includes(unit.value));setCheck('check-permit',permitValid());setCheck('check-stage',stageReady());setCheck('check-saved',allSavedStages().has(currentStage().id)&&stageFingerprint()===baselineFingerprint);}

  function clearErrors(){document.querySelectorAll('.field-error').forEach(el=>el.textContent='');}
  function makeEvent(key,label,iso,value,comment) { return {client_event_id:makeId(),device_id:deviceId(),worker_name:worker.value.trim(),structural_unit:unit.value,permit_number:permit.value.trim().toUpperCase(),field_key:key,stage_label:label,event_time:iso,field_value:value,comment:comment||''}; }
  function replacementRows(){return [...document.querySelectorAll('.replacement-item')].map(el=>({name:el.querySelector('[data-role="replacement-name"]')?.value.trim()||'',position:el.querySelector('[data-role="replacement-position"]')?.value.trim()||''})).filter(r=>r.name||r.position);}
  function buildEvents() {
    clearErrors(); let ok=true;
    if(worker.value.trim().length<3){$('worker-error').textContent='Укажите ФИО ответственного';ok=false;}
    if(!UNITS.includes(unit.value)){$('unit-error').textContent='Выберите структурное подразделение';ok=false;}
    if(!permitValid()){$('permit-error').textContent=permit.value.trim().length<3?'Введите номер наряда-допуска':'Номер НД содержит недопустимые символы';ok=false;}
    const s=currentStage(),events=[];
    if(s.kind==='range') {
      const d1=$('primary-date').value,t1=$('primary-time').value,d2=$('secondary-date').value,t2=$('secondary-time').value,comment=$('stage-comment').value.trim();
      const e1=validateOperationalDateTime(d1,t1); if(e1){$('primary-error').textContent=e1;ok=false;}
      if((d2&&!t2)||(!d2&&t2)){$('secondary-error').textContent='Укажите дату и время окончания полностью или оставьте оба поля пустыми';ok=false;}
      let e2=''; if(d2&&t2){e2=validateOperationalDateTime(d2,t2);if(e2){$('secondary-error').textContent=e2;ok=false;}if(!e2&&new Date(`${d2}T${t2}:00`)<new Date(`${d1}T${t1}:00`)){$('secondary-error').textContent='Окончание не может быть раньше начала';ok=false;}}
      if(ok){events.push(makeEvent(s.events[0][0],s.events[0][1],toEventIso(d1,t1),humanDateTime(d1,t1),comment));if(d2&&t2)events.push(makeEvent(s.events[1][0],s.events[1][1],toEventIso(d2,t2),humanDateTime(d2,t2),comment));}
    } else if(['datetime','stop','resume'].includes(s.kind)) {
      const d=$('primary-date').value,t=$('primary-time').value,err=validateOperationalDateTime(d,t);if(err){$('primary-error').textContent=err;ok=false;}
      let comment=$('stage-comment')?.value.trim()||'';if(s.kind==='stop'){comment=$('stop-reason').value.trim();if(comment.length<3){$('comment-error').textContent='Укажите причину остановки';ok=false;}}
      if(s.kind==='resume'&&comment.length<3){$('comment-error').textContent='Комментарий при возобновлении обязателен';ok=false;}
      if(ok)events.push(makeEvent(s.events[0][0],s.events[0][1],toEventIso(d,t),humanDateTime(d,t),comment));
    } else if(s.kind==='extension') {
      const v=$('extension-date').value; const d=v?new Date(`${v}T00:00:00`):null;const today=new Date();today.setHours(0,0,0,0);if(!d||Number.isNaN(d.getTime())){$('extension-error').textContent='Проверьте дату продления';ok=false;}else if(d<today){$('extension-error').textContent='Дата продления не может быть в прошлом';ok=false;}
      if(ok)events.push(makeEvent('BE','Продление РПО',new Date().toISOString(),humanDate(v),$('stage-comment').value.trim()));
    } else if(s.kind==='replacements') {
      const rows=replacementRows();if(!rows.length||!rows.every(r=>r.name.length>=3&&r.position.length>=2)){$('replacement-error').textContent='Для каждой замены укажите ФИО и должность / профессию';ok=false;}if(ok)events.push(makeEvent('RI','Замена исполнителей работ',new Date().toISOString(),rows.map(r=>`${r.name}\t${r.position}`).join('\n'),''));
    }
    if(!ok){noNewEvents=false;return [];}
    const fresh=events.filter(event=>{const old=fieldServer(event.field_key);return !old||String(old.field_value||'').trim()!==String(event.field_value||'').trim()||String(old.comment||'').trim()!==String(event.comment||'').trim();});
    noNewEvents=events.length>0&&fresh.length===0;
    return fresh;
  }

  function queue(){return jsonRead(STORAGE.queue,[]);}
  function saveQueue(items){jsonWrite(STORAGE.queue,items);renderQueueNotice();}
  function enqueue(events){const q=queue();events.forEach(payload=>q.push({id:payload.client_event_id,payload,status:'pending',error:'',createdAt:new Date().toISOString()}));saveQueue(q);}
  function queueCounts(){const q=queue();return {pending:q.filter(x=>x.status==='pending').length,failed:q.filter(x=>x.status==='failed').length};}
  function renderQueueNotice(){const c=queueCounts(),box=$('queue-notice');if(!c.pending&&!c.failed){box.hidden=true;return;}box.hidden=false;$('queue-title').textContent=c.failed?'Есть записи, требующие проверки':'Данные ожидают отправки';$('queue-text').textContent=`В очереди: ${c.pending}. Ошибок: ${c.failed}. Данные сохранены на этом iPhone.`;}
  async function syncQueue(showMessage=false){if(!navigator.onLine){renderQueueNotice();if(showMessage)showFlash(true,'Нет сети','Данные сохранены на устройстве и будут отправлены автоматически.');return;}let q=queue(),sent=0,failed=0;for(const item of q.filter(x=>x.status==='pending')){try{const r=await fetch('/api/mobile/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item.payload)});if(r.ok){item.status='sent';sent++;}else if(r.status===422||r.status===400){const body=await r.json().catch(()=>({}));item.status='failed';item.error=typeof body.detail==='string'?body.detail:'Сервер отклонил данные';failed++;}else{break;}}catch(_){break;}}q=q.filter(x=>x.status!=='sent');saveQueue(q);if(showMessage){if(failed)showFlash(false,'Проверьте данные',`${failed} записей сервер отклонил. Исправьте данные и нажмите «Повторить».`);else if(sent)showFlash(true,'Передано на сервер','Дождитесь статуса «Работы можно проводить».');else if(q.some(x=>x.status==='pending'))showFlash(true,'Сохранено локально','Отправка повторится автоматически.');}if(sent){await lookupPermit(true);await loadHistory();}}
  function retryFailed(){const q=queue();q.forEach(x=>{if(x.status==='failed'){x.status='pending';x.error='';}});saveQueue(q);syncQueue(true);}

  function showFlash(success,title,text){const box=$('flash');box.hidden=false;box.className=`notice ${success?'info-notice':'queue-notice'}`;$('flash-icon').textContent=success?'✓':'!';$('flash-title').textContent=title;$('flash-text').textContent=text;clearTimeout(showFlash.timer);showFlash.timer=setTimeout(()=>{box.hidden=true;},5500);}

  function renderApproval(approval){currentApproval=approval||null;const card=$('approval-card');if(!approval||approval.status==='none'){card.hidden=true;return;}card.hidden=false;card.className=`approval-card ${approval.status}`;const map={pending:['◷','Ожидает разрешения',`Передано на сервер. Ожидающих разрешения этапов: ${approval.pending_count||1}.`],approved:['✓','Работы можно проводить','Оператор подтвердил последние переданные этапы.'],stopped:['!','Работы остановлены','Для возобновления передайте этап «Возобновление работ» и дождитесь разрешения оператора.'],not_required:['•','Разрешение не требуется','Для этого события отдельное разрешение не требуется.']};const v=map[approval.status]||['•',approval.label||'Статус',''];$('approval-icon').textContent=v[0];$('approval-title').textContent=v[1];$('approval-text').textContent=v[2];}

  function hasStageDraft(){return stageFingerprint()!==baselineFingerprint;}
  function applyPermitData(data,preserveDraft=false){serverFields=data.fields||{};if(data.worker_name)worker.value=stripLatin(data.worker_name);if(UNITS.includes(data.structural_unit))unit.value=data.structural_unit;renderApproval(data.approval);renderStageOptions();if(!preserveDraft)renderStageFields();else updateChecklist();localStorage.setItem(STORAGE.worker,worker.value);localStorage.setItem(STORAGE.unit,unit.value);rememberPermit();}
  async function lookupPermit(silent=false){const p=permit.value.trim().toUpperCase();if(!permitValid(p)||!navigator.onLine)return false;try{const r=await fetch(`/api/mobile/permit?permit_number=${encodeURIComponent(p)}`,{cache:'no-store'});const preserveDraft=hasStageDraft();if(r.status===404){serverFields={};renderApproval(null);renderStageOptions();if(!preserveDraft)renderStageFields();else updateChecklist();return false;}if(!r.ok)throw new Error('lookup');const data=await r.json();applyPermitData(data,preserveDraft);if(!silent)showFlash(true,'Данные НД загружены','Ранее переданные этапы и статус получены с сервера.');return true;}catch(_){if(!silent)showFlash(false,'Нет связи','Не удалось получить данные НД. Можно продолжить — новые данные сохранятся локально.');return false;}}
  function scheduleLookup(){clearTimeout(permitLookupTimer);if(permitValid())permitLookupTimer=setTimeout(()=>lookupPermit(true),550);else{serverFields={};renderApproval(null);renderStageOptions();updateChecklist();}}
  function startApprovalPolling(){clearInterval(approvalTimer);approvalTimer=setInterval(()=>{if(document.visibilityState==='visible'&&navigator.onLine&&permitValid())lookupPermit(true);},8000);}

  async function systemStatus(){if(!navigator.onLine)return;try{const r=await fetch(`/api/mobile/config?app_version=${encodeURIComponent(ANDROID_API_VERSION)}`,{cache:'no-store'});if(!r.ok)return;const cfg=await r.json();const box=$('system-notice');box.hidden=false;box.className=`notice ${cfg.maintenance?'queue-notice':'info-notice'}`;$('system-title').textContent=cfg.maintenance?'Система на обслуживании':'Связь с сервером установлена';$('system-text').textContent=cfg.maintenance?cfg.message:`${cfg.message} PWA ${PWA_VERSION}.`;setTimeout(()=>{if(!cfg.maintenance)box.hidden=true;},4500);}catch(_){} }

  function renderHistory(items){const list=$('history-list');if(!items.length){list.innerHTML='<div class="card"><p class="subtitle">История на этом устройстве пока пуста.</p></div>';return;}list.innerHTML=items.map((x,i)=>{const dt=new Date(x.received_at);const when=Number.isNaN(dt.getTime())?'':dt.toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});const a=x.approval_status==='pending'?'pending':x.approval_status==='approved'?'approved':'';return `<article class="history-card history-clickable" data-history-index="${i}"><div class="history-head"><strong>${escapeHtml(x.permit_number)}</strong><time>${when}</time></div><p>${escapeHtml(x.worker_name||'')}</p><div class="history-meta"><span class="pill">${escapeHtml(x.structural_unit||'—')}</span><span class="pill ${a}">${x.approval_status==='pending'?'Ожидает разрешения':x.approval_status==='approved'?'Разрешено':'Статус записан'}</span></div><div class="history-open-hint">Нажмите, чтобы посмотреть переданные данные ›</div><div class="history-details" hidden><strong>Переданные данные</strong><p>${escapeHtml(x.field_value||'')}</p>${x.comment?`<strong>Комментарии</strong><p>${escapeHtml(x.comment)}</p>`:''}</div></article>`;}).join('');list.querySelectorAll('[data-history-index]').forEach(card=>card.addEventListener('click',()=>{const details=card.querySelector('.history-details'),hint=card.querySelector('.history-open-hint');const opening=details.hidden;list.querySelectorAll('.history-details').forEach(x=>x.hidden=true);list.querySelectorAll('.history-open-hint').forEach(x=>x.hidden=false);details.hidden=!opening;hint.hidden=opening;}));}
  async function loadHistory(){if(navigator.onLine){try{const r=await fetch(`/api/mobile/events?device_id=${encodeURIComponent(deviceId())}&limit=30`,{cache:'no-store'});if(r.ok){renderHistory(await r.json());return;}}catch(_){}}const local=memories().map((m,i)=>({id:i,permit_number:m.permitNumber,worker_name:m.workerName,structural_unit:m.structuralUnit,field_value:'Сохранено на этом устройстве',approval_status:'',received_at:m.updatedAt}));renderHistory(local);}

  async function saveStage(){const events=buildEvents();updateChecklist();if(!events.length){if(noNewEvents){markStageSaved(currentStage().id);baselineFingerprint=stageFingerprint();updateChecklist();showFlash(true,'Уже передано','Заполненные данные этого этапа уже есть на сервере.');return;}showFlash(false,'Проверьте заполнение','Исправьте отмеченные поля и повторите сохранение.');return;}saveButton.disabled=true;enqueue(events);markStageSaved(currentStage().id);rememberPermit();localStorage.setItem(STORAGE.worker,worker.value.trim());localStorage.setItem(STORAGE.unit,unit.value);renderStageOptions();baselineFingerprint=stageFingerprint();updateChecklist();showFlash(true,'Данные сохранены на iPhone',navigator.onLine?'Выполняется отправка на сервер...':'Нет сети. Отправка произойдёт автоматически.');await syncQueue(true);saveButton.disabled=false;}

  function setupNavigation(){document.querySelectorAll('.nav-item').forEach(btn=>btn.addEventListener('click',()=>{const tab=btn.dataset.tab;document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x===btn));document.querySelectorAll('.screen').forEach(s=>s.classList.toggle('active',s.dataset.screen===tab));window.scrollTo({top:0,behavior:'instant'});if(tab==='history')loadHistory();}));}
  function setupInstall(){const standalone=window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone===true;const isIOS=/iphone|ipad|ipod/i.test(navigator.userAgent);const card=$('install-card');if(!standalone&&isIOS&&localStorage.getItem(STORAGE.installHidden)!=='1')card.hidden=false;$('install-close').addEventListener('click',()=>{card.hidden=true;localStorage.setItem(STORAGE.installHidden,'1');});}
  function setupServiceWorker(){if('serviceWorker'in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/app/sw.js',{scope:'/app/'}).catch(()=>{}));}}

  function init(){
    worker.value=stripLatin(localStorage.getItem(STORAGE.worker)||'');unit.value=localStorage.getItem(STORAGE.unit)||'';
    sanitizeTextInput(worker,'worker-error');sanitizeTextInput(permit,'permit-error');
    worker.addEventListener('change',()=>localStorage.setItem(STORAGE.worker,worker.value.trim()));unit.addEventListener('change',()=>{localStorage.setItem(STORAGE.unit,unit.value);updateChecklist();});
    permit.addEventListener('input',()=>{permit.value=stripLatin(permit.value).toUpperCase();scheduleLookup();schedulePermitSuggestions();updateChecklist();});permit.addEventListener('focus',schedulePermitSuggestions);permit.addEventListener('blur',()=>setTimeout(()=>{const menu=$('permit-suggestion-menu');if(menu)menu.hidden=true;},180));permit.addEventListener('change',()=>{permit.value=stripLatin(permit.value).toUpperCase();lookupPermit(true);});
    $('permit-refresh').addEventListener('click',()=>lookupPermit(false));stageSelect.addEventListener('change',renderStageFields);saveButton.addEventListener('click',saveStage);$('retry-queue').addEventListener('click',retryFailed);$('history-refresh').addEventListener('click',loadHistory);
    window.addEventListener('online',()=>{systemStatus();syncQueue(false);if(permitValid())lookupPermit(true);});window.addEventListener('offline',()=>showFlash(true,'Нет сети','РПО продолжит сохранять данные локально.'));
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){systemStatus();syncQueue(false);if(permitValid())lookupPermit(true);}});
    setupNavigation();setupInstall();setupServiceWorker();renderPermitSuggestions();renderStageOptions();renderStageFields();renderQueueNotice();systemStatus();syncQueue(false);startApprovalPolling();
  }

  document.addEventListener('DOMContentLoaded',init);
})();

const $=s=>document.querySelector(s);let selected=null,catalog=null,reviewViolationId='',reviewSeverity='',activeOnly=false;
function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}function fmt(v){if(!v)return'';return new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(v))}function cls(s){if(s==='closed')return'green';if(s==='rejected')return'red';if(['pending_verification','resolution_submitted'].includes(s))return'blue';return'amber'}async function api(url,opts={}){const r=await fetch(url,opts);const d=(r.headers.get('content-type')||'').includes('json')?await r.json():await r.text();if(r.status===401){location.href='/login';throw new Error('Требуется вход')}if(!r.ok)throw new Error(d?.detail||d);return d}
async function load(){
  const p=new URLSearchParams();
  if($('#statusFilter').value)p.set('status',$('#statusFilter').value);
  if($('#severityFilter').value)p.set('severity',$('#severityFilter').value);
  if($('#search').value)p.set('q',$('#search').value);
  if(activeOnly&&!$('#statusFilter').value)p.set('active_only','true');

  let d={items:[]};
  try{
    d=await api('/api/pb-mng/coordinator/stops?'+p);
    $('#queue').innerHTML=d.items.length?d.items.map(x=>`<button class="queue-item ${selected?.id===x.id?'active':''}" data-id="${x.id}"><span class="status ${cls(x.status)}">${esc(x.status_label)}</span><h3>${x.id} · ${esc(x.severity_label||'Не классифицировано')}</h3><p>${esc(x.violation.text||x.description||'Остановка работ')}</p><div class="meta"><span>${esc(x.contractor||x.location)}</span><b>${fmt(x.created_at)}</b></div></button>`).join(''):'<div class="empty">Нет карточек</div>';
    document.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>openStop(b.dataset.id));
    const visibleIds=new Set((d.items||[]).map(x=>x.id));
    if(selected&&!visibleIds.has(selected.id)){selected=null;$('#detail').innerHTML='<div class="empty">Выберите остановку слева</div>';}
  }catch(e){
    $('#queue').innerHTML=`<div class="empty"><b>Не удалось загрузить очередь</b><br><small>${esc(e.message)}</small><br><button class="btn light" style="margin-top:12px" onclick="load()">Повторить</button></div>`;
  }

  try{
    const s=await api('/api/pb-mng/coordinator/stats');
    $('#sActive').textContent=s.active;
    $('#sUnclassified').textContent=s.unclassified;
    $('#sGross').textContent=s.by_severity.gross;
    $('#sSignificant').textContent=s.by_severity.significant;
    const by=s.by_status||{};
    const map={
      stPending:'pending_verification',
      stReturned:'returned_for_revision',
      stAwaitingResolution:'awaiting_resolution',
      stResolutionSubmitted:'resolution_submitted',
      stResolutionRevision:'resolution_revision',
      stPkm:'awaiting_pkm',
      stTraining:'awaiting_training',
      stUnblock:'ready_for_unblock',
      stClosed:'closed',
      stRejected:'rejected'
    };
    Object.entries(map).forEach(([id,status])=>{const el=$('#'+id);if(el)el.textContent=by[status]??0;});
  }catch(e){
    console.warn('PB_MNG stats:',e);
  }

  if(!catalog){
    try{catalog=await api('/api/pb-mng/catalog');}
    catch(e){console.warn('PB_MNG catalog:',e);}
  }

  const requested=new URLSearchParams(location.search).get('stop');
  if(!selected&&requested){
    try{selected=await api('/api/pb-mng/coordinator/stops/'+encodeURIComponent(requested));render();}
    catch(e){console.warn('PB_MNG requested stop:',e);}
  }
  if(!selected&&d.items.length){
    try{selected=await api('/api/pb-mng/coordinator/stops/'+encodeURIComponent(d.items[0].id));render();}
    catch(e){console.warn('PB_MNG first stop:',e);}
  }
  highlightSelected();
}
const STATUS_CAPTIONS={
  pending_verification:'Новые — на верификации',
  returned_for_revision:'Карточки на доработке',
  awaiting_resolution:'Ожидается устранение',
  resolution_submitted:'Проверить устранение',
  resolution_revision:'Устранение на доработке',
  awaiting_pkm:'Ожидается / проверяется ПКМ',
  awaiting_training:'Ожидается обучение',
  ready_for_unblock:'Готово к разблокировке',
  closed:'Закрытые остановки',
  rejected:'Отклонённые остановки'
};
function syncStageUi(){
  const status=$('#statusFilter')?.value||'';
  document.querySelectorAll('[data-status-card]').forEach(b=>b.classList.toggle('active',b.dataset.statusCard===status&&!activeOnly));
  const caption=$('#activeStageCaption');
  const sev=$('#severityFilter')?.value||'';
  const sevCaption={unclassified:'Без классификации',gross:'Грубые нарушения',significant:'Значительные нарушения',minor:'Незначительные нарушения'}[sev];
  if(caption)caption.textContent=activeOnly?(sevCaption?sevCaption+' · активные':'Все активные'):(STATUS_CAPTIONS[status]||sevCaption||'Все этапы');
}
async function applyQueueFilter({status='',severity='',active=false}={}){
  activeOnly=!!active;
  if($('#statusFilter'))$('#statusFilter').value=status;
  if($('#severityFilter'))$('#severityFilter').value=severity;
  selected=null;
  if($('#detail'))$('#detail').innerHTML='<div class="empty">Загрузка карточки…</div>';
  syncStageUi();
  await load();
  $('#queue')?.scrollTo({top:0,behavior:'smooth'});
}
function resetQueueFilters(){
  activeOnly=false;
  if($('#search'))$('#search').value='';
  if($('#statusFilter'))$('#statusFilter').value='';
  if($('#severityFilter'))$('#severityFilter').value='';
  selected=null;
  syncStageUi();
  load();
}
function highlightSelected(){document.querySelectorAll('.queue-item').forEach(b=>b.classList.toggle('active',!!selected&&b.dataset.id===selected.id));}
async function openStop(id){selected=await api('/api/pb-mng/coordinator/stops/'+encodeURIComponent(id));render();highlightSelected();}
let lightboxPhotos=[],lightboxIndex=0;
function photoPhaseTitle(phase){return phase==='resolution'?'Фото после устранения':'Фото нарушения'}
function photoBlock(photos,phase,subtitle=''){const items=(photos||[]).filter(p=>p.phase===phase);const kind=phase==='resolution'?'after':'before';if(!items.length)return `<section class="photo-evidence ${kind}"><div class="photo-evidence-head"><div><h3>${photoPhaseTitle(phase)}</h3><p>${esc(subtitle||'Фотоматериалы пока не представлены')}</p></div><span class="photo-count">0</span></div><div class="photo-empty">Нет фотографий</div></section>`;return `<section class="photo-evidence ${kind}"><div class="photo-evidence-head"><div><h3>${photoPhaseTitle(phase)}</h3><p>${esc(subtitle)}</p></div><span class="photo-count">${items.length}</span></div><div class="photo-evidence-grid">${items.slice(0,4).map((p,i)=>`<button class="photo-thumb" type="button" data-photo-phase="${phase}" data-photo-index="${i}"><img src="${p.url}" loading="lazy" alt="${photoPhaseTitle(phase)} ${i+1}"><span class="photo-thumb-caption">${photoPhaseTitle(phase)} ${i+1} · ${fmt(p.created_at)}</span></button>`).join('')}</div><div class="photo-evidence-footer"><button class="photo-open-all" type="button" data-open-phase="${phase}">Открыть все фотографии (${items.length})</button></div></section>`;}
function bindPhotoGallery(){document.querySelectorAll('[data-photo-phase]').forEach(b=>b.onclick=()=>openPhotoGallery(b.dataset.photoPhase,Number(b.dataset.photoIndex||0)));document.querySelectorAll('[data-open-phase]').forEach(b=>b.onclick=()=>openPhotoGallery(b.dataset.openPhase,0));}
function openPhotoGallery(phase,index=0){if(!selected)return;lightboxPhotos=(selected.photos||[]).filter(p=>p.phase===phase);if(!lightboxPhotos.length)return;lightboxIndex=Math.max(0,Math.min(index,lightboxPhotos.length-1));$('#lightboxTitle').textContent=photoPhaseTitle(phase);$('#photoLightbox').classList.add('open');$('#photoLightbox').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';renderLightbox();}
function renderLightbox(){const p=lightboxPhotos[lightboxIndex];if(!p)return;$('#lightboxImage').src=p.url;$('#lightboxCounter').textContent=`${lightboxIndex+1} из ${lightboxPhotos.length}`;$('#lightboxCaption').textContent=(p.original_name?p.original_name+' · ':'')+fmt(p.created_at);$('#lightboxThumbs').innerHTML=lightboxPhotos.map((x,i)=>`<button type="button" data-lightbox-index="${i}" class="${i===lightboxIndex?'active':''}"><img src="${x.url}" alt="Фото ${i+1}"></button>`).join('');document.querySelectorAll('[data-lightbox-index]').forEach(b=>b.onclick=()=>{lightboxIndex=Number(b.dataset.lightboxIndex);renderLightbox()});$('#lightboxPrev').style.visibility=lightboxPhotos.length>1?'visible':'hidden';$('#lightboxNext').style.visibility=lightboxPhotos.length>1?'visible':'hidden';}
function closePhotoGallery(){$('#photoLightbox').classList.remove('open');$('#photoLightbox').setAttribute('aria-hidden','true');document.body.style.overflow='';$('#lightboxImage').removeAttribute('src');}
if($('#lightboxClose'))$('#lightboxClose').onclick=closePhotoGallery;if($('#photoLightbox'))$('#photoLightbox').onclick=e=>{if(e.target===$('#photoLightbox'))closePhotoGallery()};if($('#lightboxPrev'))$('#lightboxPrev').onclick=()=>{if(!lightboxPhotos.length)return;lightboxIndex=(lightboxIndex-1+lightboxPhotos.length)%lightboxPhotos.length;renderLightbox()};if($('#lightboxNext'))$('#lightboxNext').onclick=()=>{if(!lightboxPhotos.length)return;lightboxIndex=(lightboxIndex+1)%lightboxPhotos.length;renderLightbox()};document.addEventListener('keydown',e=>{if(!$('#photoLightbox').classList.contains('open'))return;if(e.key==='Escape')closePhotoGallery();if(e.key==='ArrowLeft')$('#lightboxPrev').click();if(e.key==='ArrowRight')$('#lightboxNext').click();});

function severityLabel(s){return (catalog?.severity_labels||{gross:'Грубое',significant:'Значительное',minor:'Незначительное'})[s]||s}
function reviewRule(){return (catalog?.violations||[]).find(v=>v.id===reviewViolationId)||null}
function reviewClassifierHtml(x){
  reviewViolationId=x.violation?.id||'';
  reviewSeverity=x.current_severity||'';
  return `<div class="classifier-box">
    <h4>Классификация нарушения</h4>
    <div class="classifier-search-wrap">
      <input class="classifier-search" id="reviewViolationSearch" autocomplete="off" placeholder="Поиск по классификатору: высота, СИЗ, ограждение, НД…">
      <div class="classifier-results hidden" id="reviewViolationResults"></div>
    </div>
    <div class="classifier-selected ${reviewViolationId?'':'empty'}" id="reviewViolationSelected"></div>
    <div class="classification-criteria" id="reviewSeverityArea"></div>
  </div>`;
}
function renderReviewViolationResults(){
  const root=$('#reviewViolationResults'); if(!root)return;
  const q=($('#reviewViolationSearch')?.value||'').trim().toLocaleLowerCase('ru');
  let rows=(catalog?.violations||[]);
  if(q) rows=rows.filter(v=>[v.number,v.text,v.barrier,v.source].join(' ').toLocaleLowerCase('ru').includes(q));
  rows=rows.slice(0,40);
  if(!rows.length){root.innerHTML='<div class="empty" style="padding:14px">Ничего не найдено</div>';root.classList.remove('hidden');return;}
  root.innerHTML=rows.map(v=>`<button type="button" class="classifier-result" data-review-violation="${esc(v.id)}"><b>${esc(v.number+'. '+v.text)}</b><small>${esc([v.source,v.barrier].filter(Boolean).join(' · '))}</small></button>`).join('');
  root.classList.remove('hidden');
  root.querySelectorAll('[data-review-violation]').forEach(b=>b.onclick=()=>selectReviewViolation(b.dataset.reviewViolation));
}
function selectReviewViolation(id){
  reviewViolationId=id;reviewSeverity='';
  if($('#reviewViolationSearch'))$('#reviewViolationSearch').value='';
  if($('#reviewViolationResults'))$('#reviewViolationResults').classList.add('hidden');
  renderReviewViolationSelected();
}
function renderReviewViolationSelected(){
  const selectedBox=$('#reviewViolationSelected'),severityArea=$('#reviewSeverityArea'),rule=reviewRule();
  if(!selectedBox||!severityArea)return;
  if(!rule){
    selectedBox.className='classifier-selected empty';
    selectedBox.innerHTML='Нарушение ещё не классифицировано. Выберите пункт классификатора перед подтверждением.';
    severityArea.innerHTML='';
    return;
  }
  selectedBox.className='classifier-selected';
  selectedBox.innerHTML=`<b>${esc(rule.number+'. '+rule.text)}</b><small>${esc([rule.source,rule.barrier].filter(Boolean).join(' · '))}</small>`;
  const allowed=rule.severities||[];
  if(allowed.length===1){
    reviewSeverity=allowed[0];
    severityArea.innerHTML=`<label>Категория<input value="${esc(severityLabel(reviewSeverity))}" disabled></label>${rule.criteria?.[reviewSeverity]?`<div class="criteria-note">${esc(rule.criteria[reviewSeverity])}</div>`:''}${rule.requires_context?`<label>Основание категории<textarea id="reviewSeverityContext" rows="2" placeholder="Укажите фактические условия"></textarea></label>`:''}`;
  }else{
    if(!allowed.includes(reviewSeverity))reviewSeverity='';
    severityArea.innerHTML=`<label>Категория<select id="reviewSeverity"><option value="">Выберите категорию</option>${allowed.map(s=>`<option value="${esc(s)}" ${reviewSeverity===s?'selected':''}>${esc(severityLabel(s))}</option>`).join('')}</select></label><div class="criteria-note" id="reviewCriteriaNote"></div><label>Основание выбора<textarea id="reviewSeverityContext" rows="2" placeholder="Кратко укажите фактические условия"></textarea></label>`;
    const sel=$('#reviewSeverity'); if(sel)sel.onchange=()=>{reviewSeverity=sel.value;const note=$('#reviewCriteriaNote');if(note)note.textContent=(rule.criteria||{})[reviewSeverity]||'';};
    if(sel)sel.dispatchEvent(new Event('change'));
  }
}
function bindReviewClassifier(){
  const search=$('#reviewViolationSearch');
  if(search){search.onfocus=renderReviewViolationResults;search.oninput=renderReviewViolationResults;}
  document.addEventListener('click',e=>{const root=$('#reviewViolationResults');if(root&&!root.classList.contains('hidden')&&!e.target.closest('.classifier-search-wrap'))root.classList.add('hidden');},{once:true});
  renderReviewViolationSelected();
}
function nextAction(status){
  const map={
    pending_verification:['К','Решение координатора','Проверьте фото, классифицируйте нарушение и примите решение.',''],
    returned_for_revision:['Р','Ожидаем работника','Карточка возвращена работнику на доработку.','worker'],
    awaiting_resolution:['Р','Ожидаем устранение','Работник должен устранить замечание и прислать фото после.','worker'],
    resolution_submitted:['К','Проверка устранения','Проверьте фото после устранения и подтвердите либо верните на доработку.',''],
    resolution_revision:['Р','Ожидаем повторное устранение','Координатор вернул подтверждение устранения на доработку.','worker'],
    awaiting_pkm:['К','Проверка ПКМ','Проверьте план корректирующих мероприятий.',''],
    awaiting_training:['К','Контроль обучения','После прохождения назначенного курса отметьте его выполнение.',''],
    ready_for_unblock:['К','Разблокировка','Все условия выполнены. Проверьте и снимите ограничение пропуска.',''],
    closed:['✓','Процесс завершён','Остановка закрыта, все условия выполнены.','done'],
    rejected:['×','Остановка отклонена','Карточка завершена решением координатора.','done']
  };
  return map[status]||['•','Текущий этап','Проверьте состояние карточки.',''];
}
function nextActionHtml(status){const [icon,title,text,kind]=nextAction(status);return `<div class="next-action ${kind}"><span class="next-action-icon">${icon}</span><div><b>${esc(title)}</b><p>${esc(text)}</p></div></div>`;}
function render(){const x=selected;if(!x)return;const canReview=['pending_verification','returned_for_revision'].includes(x.status),canResolution=x.status==='resolution_submitted',canPkm=x.pkm_required&&x.status==='awaiting_pkm',canCourse=x.course_status==='required'&&x.status==='awaiting_training',canUnblock=x.status==='ready_for_unblock';const measures=(catalog?.measures||[]).map(m=>`<label class="measure"><input type="checkbox" name="measure" value="${esc(m)}" ${m==='Работы остановлены до устранения'?'checked':''}><span>${esc(m)}</span></label>`).join('');const beforePhotos=photoBlock(x.photos,'violation','Материалы, направленные работником при остановке');const afterPhotos=photoBlock(x.photos,'resolution','Подтверждение устранения замечаний');
let decision='';
if(canReview){decision=`<div class="decision-card detail-anchor" id="decisionCard"><div class="decision-head"><div><h3>Решение координатора</h3><p>Сначала классифицируйте нарушение, затем выберите меры и решение.</p></div><span class="status ${cls(x.status)}">${esc(x.status_label)}</span></div>${reviewClassifierHtml(x)}<label>Комментарий<textarea id="reviewNote" rows="2" placeholder="Комментарий; для возврата или отклонения — причина обязательна"></textarea></label><div class="review-grid"><label>Назначить обучение<select id="reviewCourse"><option value="">Не назначать</option>${(catalog?.courses||[]).map(c=>`<option>${esc(c)}</option>`).join('')}</select></label><label>Срок блокировки, дней<input id="blockDays" type="number" min="1" max="365" placeholder="Пусто = до выполнения условий"></label></div><div class="box"><h4>Меры воздействия</h4><div class="measures">${measures}</div></div><div class="review-grid"><div><label class="measure"><input id="pkmRequired" type="checkbox"><span>Требуется ПКМ</span></label><label class="measure"><input id="blockResponsible" type="checkbox"><span>Заблокировать пропуск ответственного</span></label></div></div><div class="action-row decision-actions"><button class="btn green" id="verify">✓ Подтвердить остановку</button><button class="btn light" id="return">↩ На доработку</button><button class="btn red" id="reject">✕ Отклонить</button></div></div>`;}
else if(canResolution){decision=`<div class="decision-card"><div class="decision-head"><div><h3>Проверка устранения</h3><p>Работник направил подтверждение и фотографии после устранения.</p></div></div><div class="action-row decision-actions"><button class="btn green" id="acceptResolution">✓ Устранение подтверждено</button><button class="btn light" id="returnResolution">↩ Вернуть на доработку</button></div></div>`;}
else if(canPkm){decision=`<div class="decision-card"><div class="decision-head"><div><h3>Проверка ПКМ</h3><p>Проверьте план корректирующих мероприятий.</p></div></div><label>Комментарий / сведения по ПКМ<textarea id="pkmText" rows="3">${esc(x.pkm_text||'')}</textarea></label><div class="action-row decision-actions"><button class="btn green" id="acceptPkm">✓ ПКМ принят</button><button class="btn light" id="returnPkm">↩ Вернуть ПКМ</button></div></div>`;}
else if(canCourse){decision=`<div class="decision-card"><div class="decision-head"><div><h3>Обучение</h3><p>Назначен курс: <b>${esc(x.course_name)}</b></p></div></div><div class="action-row decision-actions"><button class="btn green" id="coursePassed">✓ Отметить курс пройденным</button></div></div>`;}
else if(canUnblock){decision=`<div class="decision-card"><div class="decision-head"><div><h3>Все условия выполнены</h3><p>Устранение и назначенные меры подтверждены. Можно снять ограничение.</p></div></div><div class="action-row decision-actions"><button class="btn primary" id="unblock">Снять блокировку и закрыть остановку</button></div></div>`;}
const classification=x.violation?.id?`<div class="box"><h4>Классификация координатора</h4><p>${esc(x.violation.text)}</p><p><b>Барьер:</b> ${esc(x.violation.barrier||'—')}</p><p><b>Категория:</b> ${esc(x.severity_label)}</p>${x.severity_context?`<p><b>Основание:</b> ${esc(x.severity_context)}</p>`:''}</div>`:'';
$('#detail').innerHTML=`<div class="detail-head"><div><span class="status ${cls(x.status)}">${esc(x.status_label)}</span><h2>${x.id}</h2></div><b>${esc(x.severity_label||'Не классифицировано')}</b></div>${nextActionHtml(x.status)}<div class="review-top">${beforePhotos}${decision||'<div class="box"><h4>Текущее состояние</h4><p>'+esc(x.status_label)+'</p></div>'}</div><div class="grid"><span>Дата/время</span><b>${fmt(x.occurred_at)}</b><span>Инициатор</span><b>${esc(x.initiator.name)} · ${esc(x.initiator.unit)}</b><span>Блок / СП</span><b>${esc(x.block)} / ${esc(x.structural_unit)}</b><span>Объект</span><b>${esc(x.field)} · ${esc(x.location)}</b><span>Подрядчик</span><b>${esc(x.contractor)}${x.subcontractor?' / '+esc(x.subcontractor):''}</b><span>Вид работ / НД</span><b>${esc(x.work_type)} ${esc(x.permit_number)}</b><span>Ответственный</span><b>${esc(x.responsible.fio)} · ${esc(x.responsible.pass)}</b></div><div class="box"><h4>Описание обстоятельств работником</h4><p>${esc(x.description||'—')}</p></div>${classification}${(x.photos||[]).some(p=>p.phase==='resolution')?`<div class="photo-compare-title"><h3>Подтверждение устранения</h3><span>Фото после</span></div>${afterPhotos}`:''}${x.verification_note?`<div class="box"><h4>Комментарий координатора</h4><p>${esc(x.verification_note)}</p></div>`:''}${x.measures?.length?`<div class="box"><h4>Назначенные меры</h4><p>${x.measures.map(esc).join(' • ')}</p></div>`:''}<div class="box timeline"><h4>История действий</h4>${(x.actions||[]).map(a=>`<div><b>${fmt(a.at)}</b>${esc(a.actor_name)} · ${esc(a.action)}</div>`).join('')}</div>`;
bindActions();bindPhotoGallery();if(canReview)bindReviewClassifier();}
function bindActions(){if($('#verify'))$('#verify').onclick=()=>review('verify');if($('#return'))$('#return').onclick=()=>review('return_for_revision');if($('#reject'))$('#reject').onclick=()=>review('reject');if($('#acceptResolution'))$('#acceptResolution').onclick=()=>resolution('accept');if($('#returnResolution'))$('#returnResolution').onclick=()=>resolution('return');if($('#acceptPkm'))$('#acceptPkm').onclick=()=>pkm('accept');if($('#returnPkm'))$('#returnPkm').onclick=()=>pkm('return');if($('#coursePassed'))$('#coursePassed').onclick=coursePassed;if($('#unblock'))$('#unblock').onclick=unblock;}
async function review(action){const note=$('#reviewNote')?.value||'';if(['return_for_revision','reject'].includes(action)&&!note.trim()){alert('Укажите причину');return}if(action==='verify'&&!reviewViolationId){alert('Выберите нарушение из классификатора');return}const rule=reviewRule();if(action==='verify'&&rule&&(rule.severities||[]).length>1&&!reviewSeverity){alert('Выберите категорию нарушения');return}const payload={action,note,violation_id:reviewViolationId,severity:reviewSeverity,severity_context:$('#reviewSeverityContext')?.value||'',measures:[...document.querySelectorAll('input[name="measure"]:checked')].map(x=>x.value),course_name:$('#reviewCourse')?.value||'',pkm_required:!!$('#pkmRequired')?.checked,block_responsible:!!$('#blockResponsible')?.checked,block_days:$('#blockDays')?.value?Number($('#blockDays').value):null};selected=await api(`/api/pb-mng/coordinator/stops/${selected.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});render();load();if(!$('#registryPanel').classList.contains('hidden'))loadRegistry()}
async function resolution(action){const note=prompt(action==='return'?'Что необходимо доработать?':'Комментарий (необязательно)')||'';selected=await api(`/api/pb-mng/coordinator/stops/${selected.id}/resolution-review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,note})});render();load()}
async function pkm(action){selected=await api(`/api/pb-mng/coordinator/stops/${selected.id}/pkm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,text:$('#pkmText')?.value||''})});render();load()}
async function coursePassed(){selected=await api(`/api/pb-mng/coordinator/stops/${selected.id}/course-passed`,{method:'POST'});render();load()}
async function unblock(){if(!confirm('Снять блокировку пропуска и закрыть остановку?'))return;selected=await api(`/api/pb-mng/coordinator/stops/${selected.id}/unblock`,{method:'POST'});render();load()}

function showServerTab(name){
  document.querySelectorAll('[data-server-tab]').forEach(b=>b.classList.toggle('active',b.dataset.serverTab===name));
  $('#verificationPanel').classList.toggle('hidden',name!=='verification');
  $('#registryPanel').classList.toggle('hidden',name!=='registry');
  $('#settingsPanel').classList.toggle('hidden',name!=='settings');
  if(name==='registry')loadRegistry();
  if(name==='settings')loadRoutes();
}
async function loadRegistry(){
  const p=new URLSearchParams({limit:'1000'});
  const q=$('#registrySearch')?.value||'',status=$('#registryStatus')?.value||'',severity=$('#registrySeverity')?.value||'',from=$('#registryFrom')?.value||'',to=$('#registryTo')?.value||'';
  if(q)p.set('q',q);if(status)p.set('status',status);if(severity)p.set('severity',severity);if(from)p.set('date_from',from);if(to)p.set('date_to',to);
  const body=$('#registryBody');if(!body)return;
  try{
    const d=await api('/api/pb-mng/coordinator/stops?'+p);
    body.innerHTML=d.items.length?d.items.map(x=>`<tr data-registry-stop="${esc(x.id)}"><td><div class="registry-main">${esc(x.id)}</div><div class="registry-sub">${fmt(x.occurred_at)}</div></td><td><span class="status ${cls(x.status)}">${esc(x.status_label)}</span></td><td>${esc(x.severity_label||'Не классифицировано')}</td><td><div class="registry-main">${esc(x.block||'—')}</div><div class="registry-sub">${esc(x.structural_unit||'')}</div></td><td><div class="registry-main">${esc(x.field||'—')}</div><div class="registry-sub">${esc(x.location||'')}</div></td><td>${esc(x.contractor||'—')}</td><td><div class="registry-main">${esc(x.work_type||'—')}</div><div class="registry-sub">${esc(x.permit_number||'')}</div></td><td><div class="registry-main">${esc(x.violation.text||'Не классифицировано')}</div><div class="registry-sub">${esc(x.description||'')}</div></td><td><div class="registry-main">${esc(x.responsible.fio||'—')}</div><div class="registry-sub">${esc(x.responsible.pass||'')}</div></td><td><div class="registry-main">${esc(x.initiator.name||'—')}</div><div class="registry-sub">${esc(x.initiator.unit||'')}</div></td></tr>`).join(''):'<tr><td colspan="10" class="empty">По выбранным фильтрам остановок нет</td></tr>';
    body.querySelectorAll('[data-registry-stop]').forEach(row=>row.onclick=async()=>{showServerTab('verification');await openStop(row.dataset.registryStop);});
  }catch(e){body.innerHTML=`<tr><td colspan="10" class="empty">Не удалось загрузить реестр: ${esc(e.message)}</td></tr>`;}
}
document.querySelectorAll('[data-server-tab]').forEach(b=>b.onclick=()=>showServerTab(b.dataset.serverTab));
if($('#registryRefresh'))$('#registryRefresh').onclick=loadRegistry;
if($('#registryStatus'))$('#registryStatus').onchange=loadRegistry;
if($('#registrySeverity'))$('#registrySeverity').onchange=loadRegistry;
if($('#registryFrom'))$('#registryFrom').onchange=loadRegistry;
if($('#registryTo'))$('#registryTo').onchange=loadRegistry;
let registryTimer;if($('#registrySearch'))$('#registrySearch').oninput=()=>{clearTimeout(registryTimer);registryTimer=setTimeout(loadRegistry,300)};

async function loadRoutes(){try{const d=await api('/api/pb-mng/coordinator/email-routes');$('#routeList').innerHTML=d.items.map(x=>`<div><span>${esc(x.block||'Все блоки')}</span><span>${esc(x.contractor||'Все подрядчики')}</span><span>${esc(x.role)} · ${esc(x.recipient_name)}</span><b>${esc(x.email)}</b></div>`).join('')||'<p>Дополнительные адресаты пока не настроены.</p>'}catch(e){$('#routeList').innerHTML='<p class="notice">Email-маршрутизация временно недоступна: '+esc(e.message)+'</p>'}}
$('#addRoute').onclick=async()=>{try{await api('/api/pb-mng/coordinator/email-routes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({block:$('#rBlock').value,contractor:$('#rContractor').value,role:$('#rRole').value,recipient_name:$('#rName').value,email:$('#rEmail').value})});$('#rEmail').value='';loadRoutes()}catch(e){alert(e.message)}};
document.querySelectorAll('[data-status-card]').forEach(b=>b.onclick=()=>applyQueueFilter({status:b.dataset.statusCard}));
document.querySelectorAll('[data-severity-filter]').forEach(b=>b.onclick=()=>applyQueueFilter({severity:b.dataset.severityFilter,active:b.dataset.severityFilter==='unclassified'}));
document.querySelectorAll('[data-summary-filter]').forEach(b=>b.onclick=()=>applyQueueFilter({active:true}));
if($('#clearStageFilter'))$('#clearStageFilter').onclick=resetQueueFilters;
if($('#resetFilters'))$('#resetFilters').onclick=resetQueueFilters;
$('#refresh').onclick=load;
$('#statusFilter').onchange=()=>{activeOnly=false;selected=null;syncStageUi();load()};
$('#severityFilter').onchange=()=>{selected=null;syncStageUi();load()};
let timer;$('#search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{selected=null;load()},350)};
async function startCoordinator(){
  activeOnly=true;syncStageUi();
  try{await load();}catch(e){
    console.error('PB_MNG coordinator load failed',e);
    const q=$('#queue'); if(q) q.innerHTML='<div class="empty"><b>Ошибка загрузки кабинета</b><br><small>'+esc(e.message||e)+'</small><br><button class="btn light" style="margin-top:12px" onclick="location.reload()">Перезагрузить</button></div>';
  }
  try{await loadRoutes();}catch(e){console.warn('PB_MNG routes failed',e);}
}
startCoordinator();
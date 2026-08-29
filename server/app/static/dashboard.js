const fmt = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
};
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

const tabMeta = {
  home: ['Панель оператора','Сводка по нарядам-допускам'],
  transmissions: ['Переданные данные','Журнал сообщений и разрешений по этапам'],
  works: ['Работы','Один наряд-допуск — одна строка'],
  analytics: ['Аналитика','Оперативные показатели по работам и этапам'],
  exports: ['Выгрузки','Проверка, редактирование и отправка данных'],
  users: ['Пользователи','Доступ к операторской панели'],
  settings: ['Настройки','Параметры сервера и интеграций'],
};
const filterableTabs = new Set(['transmissions','works','analytics','exports']);
const globalFilter = document.querySelector('#global-filter');
const globalSearch = document.querySelector('#global-search');
const globalUnit = document.querySelector('#global-unit');

function activateTab(name, updateHash=true){
  if(!tabMeta[name]) name='home';
  const current=document.querySelector('[data-tab]:not([hidden])')?.dataset.tab;
  document.querySelectorAll('[data-tab]').forEach(s=>{s.hidden=s.dataset.tab!==name});
  document.querySelectorAll('[data-tab-link]').forEach(a=>a.classList.toggle('active',a.dataset.tabLink===name));
  const title=document.querySelector('#page-title'), subtitle=document.querySelector('#page-subtitle');
  if(title) title.textContent=tabMeta[name][0];
  if(subtitle) subtitle.textContent=tabMeta[name][1];
  if(globalFilter) globalFilter.hidden=!filterableTabs.has(name);
  if(updateHash && location.hash!==`#${name}`) history.replaceState(null,'',`${location.pathname}${location.search}#${name}`);
  if(current!==name) requestAnimationFrame(()=>window.scrollTo({top:0,left:0,behavior:'auto'}));
}
document.querySelectorAll('[data-tab-link]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();activateTab(a.dataset.tabLink)}));
document.querySelectorAll('[data-open-tab]').forEach(b=>b.addEventListener('click',()=>activateTab(b.dataset.openTab)));
window.addEventListener('hashchange',()=>activateTab(location.hash.slice(1)||'home',false));
activateTab(location.hash.slice(1)||'home',false);

function currentFilter(){
  return {q:(globalSearch?.value||'').trim(), unit:(globalUnit?.value||'').trim()};
}
function withFilters(params={}){
  const f=currentFilter();
  const q=new URLSearchParams(params);
  if(f.q) q.set('q',f.q);
  if(f.unit) q.set('unit',f.unit);
  return q;
}
function approvalBadge(status, required=true){
  if(!required) return '<span class="badge neutral">Не требуется</span>';
  if(status==='approved') return '<span class="badge done">Разрешено</span>';
  return '<span class="badge approval-wait">Ожидает</span>';
}
function stageDetails(e, isOpen=false){
  const items=Array.isArray(e.stage_items)?e.stage_items:[];
  const total=Number(e.stage_total)||items.length||1;
  if(!items.length) return '<span class="muted">Этапы пока не заполнены</span>';
  const lines=items.map(item=>{
    const action=item.approval_required&&item.approval_status!=='approved'&&Number(item.event_id)
      ? `<button type="button" class="approve-button small" data-approve-event="${Number(item.event_id)}">Разрешить</button>`:'';
    return `<div class="stage-detail-line"><span><b>${esc(item.label)}</b><small>${esc(item.key)}</small></span><strong>${esc(item.value)}</strong>${item.comment?`<em>${esc(item.comment)}</em>`:''}<span class="stage-approval">${approvalBadge(item.approval_status,item.approval_required)}${action}</span></div>`;
  }).join('');
  return `<details class="stage-details" data-permit="${esc(e.permit_number)}"${isOpen?' open':''}><summary><span>${items.length} из ${total} этапов</span><small>Показать детали</small></summary><div class="stage-detail-list">${lines}</div></details>`;
}

async function refreshWorks(){
  try{
    const q=withFilters({limit:'200'});
    const r=await fetch('/api/operator/events?'+q.toString(),{credentials:'same-origin',cache:'no-store'}); if(!r.ok)return;
    const rows=await r.json();
    const body=document.querySelector('#works-body');
    if(!body)return;
    const canDelete=body.dataset.canDelete==='true';
    const openPermits=new Set(Array.from(body.querySelectorAll('details.stage-details[open]')).map(d=>d.dataset.permit).filter(Boolean));
    body.innerHTML=rows.map(e=>{
      const action=(canDelete&&e.can_delete)?`<button type="button" class="danger-button" data-delete-permit="${Number(e.id)}" data-permit-number="${esc(e.permit_number)}">Удалить</button>`:'—';
      const a=e.approval||{status:'none',label:'Разрешений пока нет'};
      const approval=`<span class="badge ${a.status==='approved'?'done':a.status==='pending'?'approval-wait':'neutral'}">${esc(a.label||'Разрешений пока нет')}</span>${a.pending_count?`<small class="approval-count">${Number(a.pending_count)} ожидает</small>`:''}`;
      return `<tr><td>${esc(fmt(e.updated_at))}</td><td><span class="unit-pill">${esc(e.structural_unit||'—')}</span></td><td><b>${esc(e.permit_number)}</b></td><td><b>${esc(e.worker_name)}</b></td><td><span class="work-state ${esc(e.status_class)}">${esc(e.status)}</span></td><td>${approval}</td><td><div class="progress"><span style="width:${Number(e.progress)||0}%"></span></div><small>${Number(e.stage_count)||0} из ${Number(e.stage_total)||0}</small></td><td class="works-stage-cell">${stageDetails(e,openPermits.has(e.permit_number))}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Не выгружено'}</span></td><td>${action}</td></tr>`;
    }).join('');
  }catch(e){console.error('refreshWorks',e)}
}

async function refreshTransmissions(){
  try{
    const q=withFilters({limit:'300'});
    const r=await fetch('/api/operator/transmissions?'+q.toString(),{credentials:'same-origin',cache:'no-store'}); if(!r.ok)return;
    const rows=await r.json();
    const body=document.querySelector('#transmissions-body');
    if(!body)return;
    body.innerHTML=rows.map(e=>{
      const action=e.approval_required&&e.approval_status!=='approved'?`<button type="button" class="approve-button" data-approve-event="${Number(e.id)}">Разрешить</button>`:'—';
      return `<tr><td>${esc(fmt(e.received_at))}</td><td><span class="unit-pill">${esc(e.structural_unit||'—')}</span></td><td><b>${esc(e.worker_name)}</b></td><td><b>${esc(e.permit_number)}</b></td><td><span class="stage-code">${esc(e.field_key)}</span> ${esc(e.stage_label)}</td><td>${esc(e.field_value)}</td><td class="wrap-cell">${esc(e.comment||'—')}</td><td>${approvalBadge(e.approval_status,e.approval_required)}</td><td>${action}</td></tr>`;
    }).join('');
  }catch(e){console.error('refreshTransmissions',e)}
}

function renderAnalytics(data){
  const values={
    '#analytics-total':data.total,
    '#analytics-active':data.active,
    '#analytics-stopped':data.stopped,
    '#analytics-completed':data.completed,
    '#analytics-extended':data.extended,
    '#analytics-average':data.avg_completion_label||'—',
  };
  Object.entries(values).forEach(([sel,value])=>{const el=document.querySelector(sel);if(el)el.textContent=value??0});
  const activity=document.querySelector('#analytics-activity');
  if(activity) activity.innerHTML=(data.activity_days||[]).map(p=>`<div class="bar-row"><span>${esc(p.label)}</span><div><i style="width:${Number(p.pct)||0}%"></i></div><b>${Number(p.count)||0}</b></div>`).join('')||'<p class="muted">Пока нет данных</p>';
  const stages=document.querySelector('#analytics-stages');
  if(stages) stages.innerHTML=(data.stage_progress||[]).map(p=>`<div class="bar-row"><span title="${esc(p.key)}">${esc(p.label)}</span><div><i style="width:${Number(p.pct)||0}%"></i></div><b>${Number(p.count)||0}</b></div>`).join('')||'<p class="muted">Пока нет данных</p>';
  const workers=document.querySelector('#analytics-workers');
  if(workers) workers.innerHTML=(data.top_workers||[]).map((p,i)=>`<div><span><b>${i+1}</b>${esc(p.name)}</span><strong>${Number(p.count)||0}</strong></div>`).join('')||'<p class="muted">Пока нет данных</p>';
}
async function refreshAnalytics(){
  try{
    const q=withFilters();
    const r=await fetch('/api/operator/analytics?'+q.toString(),{credentials:'same-origin',cache:'no-store'}); if(!r.ok)return;
    renderAnalytics(await r.json());
  }catch(e){console.error('refreshAnalytics',e)}
}

async function refreshFilteredViews(){await Promise.all([refreshWorks(),refreshTransmissions(),refreshAnalytics()]);}
refreshFilteredViews();
setInterval(()=>{refreshWorks();refreshTransmissions()},5000);
let filterTimer=null;
globalSearch?.addEventListener('input',()=>{clearTimeout(filterTimer);filterTimer=setTimeout(refreshFilteredViews,250)});
globalUnit?.addEventListener('change',refreshFilteredViews);
document.querySelector('#global-filter-reset')?.addEventListener('click',()=>{if(globalSearch)globalSearch.value='';if(globalUnit)globalUnit.value='';refreshFilteredViews()});

document.addEventListener('click',async e=>{
  const approve=e.target.closest('[data-approve-event]');
  if(approve){
    const id=Number(approve.dataset.approveEvent); if(!id)return;
    approve.disabled=true; approve.textContent='Разрешаю...';
    try{
      const r=await fetch(`/api/operator/events/${id}/approve`,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json'}});
      let data={};try{data=await r.json()}catch(_){}
      if(!r.ok)throw new Error(data.detail||'Не удалось выдать разрешение');
      await refreshFilteredViews();
    }catch(err){alert(err.message||'Ошибка разрешения');approve.disabled=false;approve.textContent='Разрешить'}
    return;
  }
  const button=e.target.closest('[data-delete-permit]');
  if(!button)return;
  const id=Number(button.dataset.deletePermit);
  const permit=button.dataset.permitNumber||'';
  if(!id||!confirm(`Удалить НД ${permit}? Будут удалены сам НД и все полученные с телефонов события по нему. История уже выполненных выгрузок сохранится.`))return;
  button.disabled=true;
  try{
    const r=await fetch(`/api/operator/permits/${id}`,{method:'DELETE',credentials:'same-origin',headers:{'Accept':'application/json'}});
    let data={}; try{data=await r.json()}catch(_){}
    if(!r.ok)throw new Error(data.detail||'Не удалось удалить запись');
    await refreshFilteredViews();
  }catch(err){alert(err.message||'Ошибка удаления');button.disabled=false;}
});

const pad=n=>String(n).padStart(2,'0');
function localInput(d){return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`}
function setRange(kind){
  const fromEl=document.querySelector('#period-from'), toEl=document.querySelector('#period-to');
  if(!fromEl||!toEl)return;
  const now=new Date(); let start=new Date(now);
  if(kind==='today')start.setHours(0,0,0,0);
  if(kind==='shift')start=new Date(now.getTime()-12*3600e3);
  if(kind==='week')start=new Date(now.getTime()-7*86400e3);
  fromEl.value=localInput(start);toEl.value=localInput(now)
}
document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>setRange(b.dataset.period)));
setRange('shift');

const modal=document.querySelector('#preview-modal');
const previewList=document.querySelector('#preview-list');
let previewRecords=[];
let stageKeys=[];
function closePreview(){ if(!modal)return; modal.hidden=true; document.body.classList.remove('modal-open'); }
document.querySelector('#preview-close')?.addEventListener('click',closePreview);
document.querySelector('#preview-cancel')?.addEventListener('click',closePreview);
modal?.addEventListener('click',e=>{if(e.target===modal)closePreview()});

function renderPreview(records, keys){
  if(!previewList)return;
  const rows=records.map((r,ri)=>{
    const stages=keys.map(key=>{
      const f=r.fields[key]||{label:key,field_value:'',comment:''};
      return `<div class="preview-stage-line"><span class="preview-stage-name"><b>${esc(f.label)}</b><small>${esc(key)}</small></span><input data-ri="${ri}" data-key="${esc(key)}" data-kind="value" value="${esc(f.field_value)}" placeholder="Не заполнено"><input data-ri="${ri}" data-key="${esc(key)}" data-kind="comment" value="${esc(f.comment)}" placeholder="Комментарий"></div>`;
    }).join('');
    const previous=r.previously_exported?`<span class="badge repeat">Ранее выгружено</span>`:`<span class="badge pending">Ещё не выгружалось</span>`;
    return `<tr data-ri="${ri}"><td class="preview-nd"><strong>${esc(r.permit_number)}</strong><small>${esc(r.structural_unit||'—')}</small><small>${esc(r.updated_at_display||fmt(r.updated_at))}</small>${previous}</td><td class="preview-worker"><input data-ri="${ri}" data-kind="worker" value="${esc(r.worker_name)}"></td><td class="preview-stage-cell">${stages}</td></tr>`;
  }).join('');
  previewList.innerHTML=`<div class="preview-table-wrap"><table class="preview-table"><thead><tr><th>НД / подразделение / обновлено</th><th>Работник</th><th>Этапы: значение и комментарий</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function collectPreview(){
  const data=JSON.parse(JSON.stringify(previewRecords));
  if(!previewList)return data;
  previewList.querySelectorAll('[data-kind]').forEach(el=>{
    const ri=Number(el.dataset.ri), kind=el.dataset.kind, key=el.dataset.key;
    if(kind==='worker') data[ri].worker_name=el.value;
    else if(kind==='value') data[ri].fields[key].field_value=el.value;
    else if(kind==='comment') data[ri].fields[key].comment=el.value;
  });
  return data;
}
const exportForm=document.querySelector('#export-form');
exportForm?.addEventListener('submit',async e=>{
  e.preventDefault();
  const from=document.querySelector('#period-from')?.value || '';
  const to=document.querySelector('#period-to')?.value || '';
  const recipient=document.querySelector('#recipient')?.value.trim() || '';
  if(!from||!to||!recipient){alert('Заполните период и email получателя.');return;}
  const button=e.submitter || exportForm.querySelector('button[type="submit"]');
  if(button){button.disabled=true;button.textContent='Загрузка...'}
  try{
    const fromDate=new Date(from), toDate=new Date(to);
    if(Number.isNaN(fromDate.getTime())||Number.isNaN(toDate.getTime()))throw new Error('Проверьте даты периода');
    const q=withFilters({period_from:fromDate.toISOString(),period_to:toDate.toISOString()});
    const r=await fetch('/api/operator/export-preview?'+q.toString(),{credentials:'same-origin',cache:'no-store'});
    let data={}; try{data=await r.json()}catch(_){throw new Error('Сервер вернул некорректный ответ предпросмотра')}
    if(!r.ok) throw new Error(data.detail||'Не удалось сформировать предпросмотр');
    if(!Array.isArray(data.records)||!data.records.length){alert('За выбранный период и текущий фильтр нет нарядов-допусков.');return;}
    previewRecords=data.records; stageKeys=data.stage_keys||[];
    renderPreview(previewRecords,stageKeys);
    document.querySelector('#confirm-period-from').value=data.period_from;
    document.querySelector('#confirm-period-to').value=data.period_to;
    document.querySelector('#confirm-recipient').value=recipient;
    if(!modal)throw new Error('Окно предпросмотра не найдено. Обновите страницу.');
    modal.hidden=false; document.body.classList.add('modal-open');
  }catch(err){ alert(err.message||'Ошибка предпросмотра'); console.error(err); }
  finally{if(button){button.disabled=false;button.textContent='👁 Просмотреть перед отправкой'}}
});
const confirmForm=document.querySelector('#confirm-export-form');
confirmForm?.addEventListener('submit',e=>{
  const send=document.querySelector('#confirm-send');
  if(send?.disabled){e.preventDefault();return;}
  const edited=collectPreview();
  if(edited.some(r=>String(r.worker_name||'').trim().length<3)){e.preventDefault();alert('Проверьте ФИО работника в предпросмотре.');return;}
  document.querySelector('#edited-json').value=JSON.stringify(edited);
  if(send){send.disabled=true;send.textContent='Отправка...';}
});

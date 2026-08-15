const fmt = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
};
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

const tabMeta = {
  home: ['Панель оператора','Сводка по нарядам-допускам'],
  transmissions: ['Переданные данные','Журнал сообщений, поступивших с мобильных устройств'],
  works: ['Работы','Один наряд-допуск — одна строка'],
  analytics: ['Аналитика','Оперативные показатели по работам и этапам'],
  exports: ['Выгрузки','Проверка, редактирование и отправка данных'],
  users: ['Пользователи','Доступ к операторской панели'],
  settings: ['Настройки','Параметры сервера и интеграций'],
};
function activateTab(name, updateHash=true){
  if(!tabMeta[name]) name='home';
  const current=document.querySelector('[data-tab]:not([hidden])')?.dataset.tab;
  document.querySelectorAll('[data-tab]').forEach(s=>{s.hidden=s.dataset.tab!==name});
  document.querySelectorAll('[data-tab-link]').forEach(a=>a.classList.toggle('active',a.dataset.tabLink===name));
  const title=document.querySelector('#page-title'), subtitle=document.querySelector('#page-subtitle');
  if(title) title.textContent=tabMeta[name][0];
  if(subtitle) subtitle.textContent=tabMeta[name][1];
  if(updateHash && location.hash!==`#${name}`) history.replaceState(null,'',`${location.pathname}${location.search}#${name}`);
  if(current!==name) requestAnimationFrame(()=>window.scrollTo({top:0,left:0,behavior:'auto'}));
}
document.querySelectorAll('[data-tab-link]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();activateTab(a.dataset.tabLink)}));
document.querySelectorAll('[data-open-tab]').forEach(b=>b.addEventListener('click',()=>activateTab(b.dataset.openTab)));
window.addEventListener('hashchange',()=>activateTab(location.hash.slice(1)||'home',false));
activateTab(location.hash.slice(1)||'home',false);

function stageDetails(e, isOpen=false){
  const items=Array.isArray(e.stage_items)?e.stage_items:[];
  const total=Number(e.stage_total)||items.length||1;
  if(!items.length) return '<span class="muted">Этапы пока не заполнены</span>';
  const lines=items.map(item=>`<div class="stage-detail-line"><span><b>${esc(item.label)}</b><small>${esc(item.key)}</small></span><strong>${esc(item.value)}</strong>${item.comment?`<em>${esc(item.comment)}</em>`:''}</div>`).join('');
  return `<details class="stage-details" data-permit="${esc(e.permit_number)}"${isOpen?' open':''}><summary><span>${items.length} из ${total} этапов</span><small>Показать детали</small></summary><div class="stage-detail-list">${lines}</div></details>`;
}

async function refreshWorks(){
  try{
    const r=await fetch('/api/operator/events?limit=200',{credentials:'same-origin',cache:'no-store'}); if(!r.ok)return;
    const rows=await r.json();
    const body=document.querySelector('#works-body');
    if(!body)return;
    const openPermits=new Set(
      Array.from(body.querySelectorAll('details.stage-details[open]'))
        .map(details=>details.dataset.permit)
        .filter(Boolean)
    );
    body.innerHTML=rows.map(e=>`<tr><td>${esc(fmt(e.updated_at))}</td><td><b>${esc(e.permit_number)}</b></td><td><b>${esc(e.worker_name)}</b></td><td><span class="work-state ${esc(e.status_class)}">${esc(e.status)}</span></td><td><div class="progress"><span style="width:${Number(e.progress)||0}%"></span></div><small>${Number(e.stage_count)||0} из ${Number(e.stage_total)||0}</small></td><td class="works-stage-cell">${stageDetails(e,openPermits.has(e.permit_number))}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Не выгружено'}</span></td></tr>`).join('');
  }catch(e){console.error('refreshWorks',e)}
}

async function refreshTransmissions(){
  try{
    const r=await fetch('/api/operator/transmissions?limit=300',{credentials:'same-origin',cache:'no-store'}); if(!r.ok)return;
    const rows=await r.json();
    const body=document.querySelector('#transmissions-body');
    if(!body)return;
    body.innerHTML=rows.map(e=>`<tr><td>${esc(fmt(e.received_at))}</td><td><b>${esc(e.worker_name)}</b></td><td><b>${esc(e.permit_number)}</b></td><td><span class="stage-code">${esc(e.field_key)}</span> ${esc(e.stage_label)}</td><td>${esc(e.field_value)}</td><td class="wrap-cell">${esc(e.comment||'—')}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Ожидает'}</span></td></tr>`).join('');
  }catch(e){console.error('refreshTransmissions',e)}
}
refreshWorks();
refreshTransmissions();
setInterval(()=>{refreshWorks();refreshTransmissions()},5000);

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
      return `<div class="preview-stage-line">
        <span class="preview-stage-name"><b>${esc(f.label)}</b><small>${esc(key)}</small></span>
        <input data-ri="${ri}" data-key="${esc(key)}" data-kind="value" value="${esc(f.field_value)}" placeholder="Не заполнено">
        <input data-ri="${ri}" data-key="${esc(key)}" data-kind="comment" value="${esc(f.comment)}" placeholder="Комментарий">
      </div>`;
    }).join('');
    const previous=r.previously_exported?`<span class="badge repeat">Ранее выгружено</span>`:`<span class="badge pending">Ещё не выгружалось</span>`;
    return `<tr data-ri="${ri}">
      <td class="preview-nd"><strong>${esc(r.permit_number)}</strong><small>${esc(r.updated_at_display||fmt(r.updated_at))}</small>${previous}</td>
      <td class="preview-worker"><input data-ri="${ri}" data-kind="worker" value="${esc(r.worker_name)}"></td>
      <td class="preview-stage-cell">${stages}</td>
    </tr>`;
  }).join('');
  previewList.innerHTML=`<div class="preview-table-wrap"><table class="preview-table"><thead><tr><th>НД / обновлено</th><th>Работник</th><th>Этапы: значение и комментарий</th></tr></thead><tbody>${rows}</tbody></table></div>`;
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
    const q=new URLSearchParams({period_from:fromDate.toISOString(),period_to:toDate.toISOString()});
    const r=await fetch('/api/operator/export-preview?'+q.toString(),{credentials:'same-origin',cache:'no-store'});
    let data={};
    try{data=await r.json()}catch(_){throw new Error('Сервер вернул некорректный ответ предпросмотра')}
    if(!r.ok) throw new Error(data.detail||'Не удалось сформировать предпросмотр');
    if(!Array.isArray(data.records)||!data.records.length){alert('За выбранный период нет нарядов-допусков.');return;}
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

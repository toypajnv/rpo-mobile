const fmt = (iso) => new Date(iso).toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

async function refreshEvents(){
  try{
    const r=await fetch('/api/operator/events?limit=100',{credentials:'same-origin'}); if(!r.ok)return;
    const rows=await r.json();
    document.querySelector('#events-body').innerHTML=rows.map(e=>`<tr><td>${fmt(e.updated_at)}</td><td><b>${esc(e.worker_name)}</b></td><td><b>${esc(e.permit_number)}</b></td><td class="summary-cell"><pre>${esc(e.summary)}</pre>${e.comments?`<small class="row-comment">${esc(e.comments)}</small>`:''}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Не выгружено'}</span></td></tr>`).join('');
  }catch(e){}
}
setInterval(refreshEvents,4000);

const pad=n=>String(n).padStart(2,'0');
function localInput(d){return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`}
function setRange(kind){const now=new Date(); let start=new Date(now); if(kind==='today')start.setHours(0,0,0,0); if(kind==='shift')start=new Date(now.getTime()-12*3600e3); if(kind==='week')start=new Date(now.getTime()-7*86400e3); document.querySelector('#period-from').value=localInput(start);document.querySelector('#period-to').value=localInput(now)}
document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>setRange(b.dataset.period))); setRange('shift');

const modal=document.querySelector('#preview-modal');
const previewList=document.querySelector('#preview-list');
let previewRecords=[];
let stageKeys=[];

function closePreview(){ modal.hidden=true; document.body.classList.remove('modal-open'); }
document.querySelector('#preview-close').addEventListener('click',closePreview);
document.querySelector('#preview-cancel').addEventListener('click',closePreview);
modal.addEventListener('click',e=>{if(e.target===modal)closePreview()});

function renderPreview(records, keys){
  previewList.innerHTML=records.map((r,ri)=>{
    const fields=keys.map(key=>{
      const f=r.fields[key]||{label:key,field_value:'',comment:''};
      return `<div class="preview-field">
        <label>${esc(key)} · ${esc(f.label)}<input data-ri="${ri}" data-key="${esc(key)}" data-kind="value" value="${esc(f.field_value)}" placeholder="Не заполнено"></label>
        <label class="comment-label">Комментарий<textarea data-ri="${ri}" data-key="${esc(key)}" data-kind="comment" rows="2" placeholder="Комментарий">${esc(f.comment)}</textarea></label>
      </div>`;
    }).join('');
    return `<article class="permit-preview" data-ri="${ri}"><div class="permit-preview-title"><strong>НД ${esc(r.permit_number)}</strong><span>${fmt(r.updated_at)}</span></div><label>ФИО работника<input data-ri="${ri}" data-kind="worker" value="${esc(r.worker_name)}"></label><div class="preview-fields">${fields}</div></article>`;
  }).join('');
}

function collectPreview(){
  const data=JSON.parse(JSON.stringify(previewRecords));
  previewList.querySelectorAll('[data-kind]').forEach(el=>{
    const ri=Number(el.dataset.ri), kind=el.dataset.kind, key=el.dataset.key;
    if(kind==='worker') data[ri].worker_name=el.value;
    else if(kind==='value') data[ri].fields[key].field_value=el.value;
    else if(kind==='comment') data[ri].fields[key].comment=el.value;
  });
  return data;
}

document.querySelector('#export-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const from=document.querySelector('#period-from').value;
  const to=document.querySelector('#period-to').value;
  const recipient=document.querySelector('#recipient').value.trim();
  if(!from||!to||!recipient)return;
  const button=e.submitter;
  if(button){button.disabled=true;button.textContent='Загрузка...'}
  try{
    const fromIso=new Date(from).toISOString();
    const toIso=new Date(to).toISOString();
    const q=new URLSearchParams({period_from:fromIso,period_to:toIso});
    const r=await fetch('/api/operator/export-preview?'+q.toString(),{credentials:'same-origin'});
    const data=await r.json();
    if(!r.ok) throw new Error(data.detail||'Не удалось сформировать предпросмотр');
    if(!data.records.length){alert('За выбранный период нет невыгруженных нарядов-допусков.');return;}
    previewRecords=data.records; stageKeys=data.stage_keys;
    renderPreview(previewRecords,stageKeys);
    document.querySelector('#confirm-period-from').value=data.period_from;
    document.querySelector('#confirm-period-to').value=data.period_to;
    document.querySelector('#confirm-recipient').value=recipient;
    modal.hidden=false; document.body.classList.add('modal-open');
  }catch(err){ alert(err.message||'Ошибка предпросмотра'); }
  finally{if(button){button.disabled=false;button.textContent='👁 Просмотреть перед отправкой'}}
});

document.querySelector('#confirm-export-form').addEventListener('submit',e=>{
  const send=document.querySelector('#confirm-send');
  if(send.disabled){e.preventDefault();return;}
  const edited=collectPreview();
  if(edited.some(r=>String(r.worker_name||'').trim().length<3)){e.preventDefault();alert('Проверьте ФИО работника в предпросмотре.');return;}
  document.querySelector('#edited-json').value=JSON.stringify(edited);
  send.disabled=true;
  send.textContent='Отправка...';
});

const fmt = (iso) => new Date(iso).toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
async function refreshEvents(){
  try{
    const r=await fetch('/api/operator/events?limit=100',{credentials:'same-origin'}); if(!r.ok)return;
    const rows=await r.json();
    document.querySelector('#events-body').innerHTML=rows.map(e=>`<tr><td>${fmt(e.received_at)}</td><td><b>${esc(e.worker_name)}</b></td><td>${esc(e.permit_number)}</td><td><code>${esc(e.field_key)}</code></td><td>${esc(e.stage_label)}</td><td>${esc(e.field_value)}</td><td><span class="badge ${e.exported?'done':'pending'}">${e.exported?'Выгружено':'Не выгружено'}</span></td></tr>`).join('');
  }catch(e){}
}
setInterval(refreshEvents,4000);
const pad=n=>String(n).padStart(2,'0');
function localInput(d){return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`}
function setRange(kind){const now=new Date(); let start=new Date(now); if(kind==='today')start.setHours(0,0,0,0); if(kind==='shift')start=new Date(now.getTime()-12*3600e3); if(kind==='week')start=new Date(now.getTime()-7*86400e3); document.querySelector('#period-from').value=localInput(start);document.querySelector('#period-to').value=localInput(now)}
document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>setRange(b.dataset.period))); setRange('shift');

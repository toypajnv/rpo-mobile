const $=(s,r=document)=>r.querySelector(s); const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const screens=$$('.screen'); const navBtns=$$('.bottom-nav button'); const toast=$('#toast');
function show(name){screens.forEach(x=>x.classList.toggle('active',x.dataset.screen===name));navBtns.forEach(b=>b.classList.toggle('active',b.dataset.open===name));window.scrollTo({top:0,behavior:'smooth'});}
$$('[data-open]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.open)));
$('#profileBtn').addEventListener('click',()=>show('profile'));
function say(t){toast.textContent=t;toast.classList.add('show');clearTimeout(window.__toast);window.__toast=setTimeout(()=>toast.classList.remove('show'),2400);}
function updateNow(){const d=new Date();$('#nowLabel').textContent=new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(d)}updateNow();

const saved=JSON.parse(localStorage.getItem('pb_mng_profile')||'{}');
if(saved.name){$('#profileName').value=saved.name;$('#profileUnit').value=saved.unit||'';$('#profilePass').value=saved.pass||'';$('#workerLabel').textContent=saved.name;$('#profileBtn').textContent=saved.name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();}
$('#saveProfile').addEventListener('click',()=>{const p={name:$('#profileName').value.trim(),unit:$('#profileUnit').value.trim(),pass:$('#profilePass').value.trim()};localStorage.setItem('pb_mng_profile',JSON.stringify(p));$('#workerLabel').textContent=p.name||'Не указано';$('#profileBtn').textContent=(p.name||'ПБ').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();say('Данные сохранены на устройстве');show('home')});

$('#violation').addEventListener('change',e=>{const opt=e.target.selectedOptions[0];const level=opt?.dataset.level;const box=$('#classification');if(!level){box.className='classification hidden';return}$('#levelText').textContent=level;box.className='classification '+(level==='Грубое'?'gross':level==='Незначительное'?'minor':'');});
$('#photos').addEventListener('change',e=>{const files=[...e.target.files].slice(0,5);$('#photoList').innerHTML='';files.forEach(f=>{const img=document.createElement('img');img.src=URL.createObjectURL(f);$('#photoList').appendChild(img)});$('#photoCount').textContent=files.length+'/5';});
$('#afterPhoto').addEventListener('change',e=>{$('#afterPhotoText').textContent=e.target.files.length?'Фото добавлено ✓':'Обязательно для подтверждения';});

$('#saveDraft').addEventListener('click',()=>{const draft={location:$('#location').value,contractor:$('#contractor').value,workType:$('#workType').value,violation:$('#violation').value,description:$('#description').value,at:new Date().toISOString()};localStorage.setItem('pb_mng_draft',JSON.stringify(draft));say('Черновик сохранён на устройстве');});
$('#stopForm').addEventListener('submit',e=>{e.preventDefault();if(!$('#violation').value){say('Выберите нарушение');return}const record={id:'ОР-2026-'+String(Math.floor(126+Math.random()*700)).padStart(5,'0'),location:$('#location').value,contractor:$('#contractor').value,workType:$('#workType').value,violation:$('#violation').value,level:$('#violation').selectedOptions[0].dataset.level,description:$('#description').value,status:'На проверке координатора',createdAt:new Date().toISOString()};const rows=JSON.parse(localStorage.getItem('pb_mng_demo_stops')||'[]');rows.unshift(record);localStorage.setItem('pb_mng_demo_stops',JSON.stringify(rows));localStorage.removeItem('pb_mng_draft');say('Остановка отправлена на верификацию');setTimeout(()=>show('myStops'),700);});
$('#confirmFix').addEventListener('click',()=>{if(!$('#afterPhoto').files.length){say('Добавьте фото после устранения');return}say('Устранение отправлено координатору');setTimeout(()=>show('myStops'),700);});
const draft=JSON.parse(localStorage.getItem('pb_mng_draft')||'null');if(draft){$('#location').value=draft.location||'';$('#contractor').value=draft.contractor||'';$('#workType').value=draft.workType||'Огневые работы';$('#violation').value=draft.violation||'';$('#description').value=draft.description||'';$('#violation').dispatchEvent(new Event('change'));}

$$('.filter-chips button').forEach(b=>b.addEventListener('click',()=>{$$('.filter-chips button').forEach(x=>x.classList.remove('active'));b.classList.add('active');say('Фильтр: '+b.textContent)}));

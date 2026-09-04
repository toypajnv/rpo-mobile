const CACHE='rpo-pwa-shell-v1.2.2';
const SHELL=['/app/','/app/manifest.webmanifest','/app/icon-180.png','/app/icon-192.png','/app/icon-512.png','/pwa-assets/app.css?v=20260829-2','/pwa-assets/ux.css?v=20260830-1','/pwa-assets/sync-status.js?v=20260831-1','/pwa-assets/app.js?v=20260829-2','/pwa-assets/ux.js?v=20260830-2','/pwa-assets/deny-lock.js?v=20260831-1','/pwa-assets/history-status.js?v=20260901-1'];

self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    // Do not fail the whole installation because one optional asset is temporarily
    // unavailable. The important part is to cache /app/ so iOS can always launch
    // the installed Home Screen app without Safari's black offline error page.
    await Promise.allSettled(SHELL.map(async url=>{
      const response=await fetch(url,{cache:'reload'});
      if(response.ok)await cache.put(url,response.clone());
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});

function offlineShell(){
  return caches.match('/app/').then(hit=>hit||new Response(`<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#073c77"><title>РПО</title><style>body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f4f7fb;color:#10233f;display:grid;min-height:100vh;place-items:center;padding:24px;box-sizing:border-box}.card{max-width:420px;background:#fff;border-radius:22px;padding:26px;box-shadow:0 12px 32px #0b244020}.logo{font-size:34px;font-weight:900;color:#073c77}.state{margin-top:18px;font-size:21px;font-weight:800}.text{margin-top:8px;line-height:1.45;color:#667085}.retry{margin-top:20px;width:100%;border:0;border-radius:14px;background:#0b62c3;color:#fff;padding:14px;font-size:17px;font-weight:800}</style></head><body><main class="card"><div class="logo">РПО</div><div class="state">Нет связи с сервером</div><div class="text">Приложение запущено. Проверьте интернет и нажмите «Повторить». Ранее сохранённые данные на iPhone не удаляются.</div><button class="retry" onclick="location.reload()">Повторить</button></main></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8'}}));
}

self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET')return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin)return;

  if(url.pathname.startsWith('/api/')){
    event.respondWith(fetch(req));
    return;
  }

  if(req.mode==='navigate' && url.pathname.startsWith('/app')){
    event.respondWith((async()=>{
      try{
        const response=await fetch(req);
        if(response.ok){
          const cache=await caches.open(CACHE);
          await cache.put('/app/',response.clone());
        }
        return response;
      }catch(_){
        return offlineShell();
      }
    })());
    return;
  }

  if(url.pathname.startsWith('/pwa-assets/') || url.pathname.startsWith('/app/icon-') || url.pathname==='/app/manifest.webmanifest'){
    event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(resp=>{const copy=resp.clone();caches.open(CACHE).then(cache=>cache.put(req,copy));return resp;})));
  }
});

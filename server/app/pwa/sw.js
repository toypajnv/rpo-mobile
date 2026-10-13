const CACHE='rpo-pwa-shell-v1.3.2-r1';
const SHELL=[
  '/app/', '/app/?home=20260915', '/app/manifest.webmanifest',
  '/app/icon-180.png','/app/icon-192.png','/app/icon-512.png',
  '/pwa-assets/app.css?v=20260829-2','/pwa-assets/ux.css?v=20260830-1',
  '/pwa-assets/sync-status.js?v=20260831-1',
  '/pwa-assets/app.js?v=20261013-1','/pwa-assets/ux.js?v=20261001-1',
  '/pwa-assets/deny-lock.js?v=20260831-1',
  '/pwa-assets/history-status.js?v=20260901-1',
  '/pwa-assets/instruction-assistant.css?v=20260906-1',
  '/pwa-assets/instruction-assistant.js?v=20260906-1'
];
const READY='/app/offline-ready-marker';

self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    try {
      // Installation must be atomic: partial caches previously opened a blank
      // page on iOS when the phone had no connection.
      await Promise.all(SHELL.map(async url=>{
        const response=await fetch(url,{cache:'reload'});
        if(!response.ok)throw new Error('Offline file unavailable: '+url);
        await cache.put(url,response.clone());
      }));
      await cache.put(READY,new Response('ready'));
      await self.skipWaiting();
    } catch(error) {
      await caches.delete(CACHE);
      throw error; // Keep previous, working service worker alive.
    }
  })());
});

self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    if(await cache.match(READY)){
      const keys=await caches.keys();
      await Promise.all(keys.filter(k=>k.startsWith('rpo-pwa-shell-')&&k!==CACHE).map(k=>caches.delete(k)));
    }
    await self.clients.claim();
  })());
});

async function cachedShell(){
  const keys=await caches.keys();
  for(const name of [CACHE,...keys.filter(k=>k.startsWith('rpo-pwa-shell-')&&k!==CACHE)]){
    const cache=await caches.open(name);
    const found=await cache.match('/app/') || await cache.match('/app/?home=20260915');
    if(found)return found;
  }
  return new Response(`<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>РПО · офлайн</title><body style="font:17px sans-serif;padding:28px"><h2>Нет связи с сервером</h2><p>Чтобы использовать РПО без интернета, откройте приложение один раз при устойчивой связи: оно сохранит файлы для дальнейшей работы.</p><button onclick="location.reload()">Повторить</button></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8'}});
}

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;
  if(url.pathname.startsWith('/api/')){
    event.respondWith(fetch(request));
    return;
  }

  if(request.mode==='navigate' && (url.pathname==='/app' || url.pathname.startsWith('/app/'))){
    event.respondWith((async()=>{
      try{
        const response=await fetch(request,{cache:'no-store'});
        if(response.ok){
          const cache=await caches.open(CACHE);
          await cache.put('/app/',response.clone());
          return response;
        }
      }catch(_){}
      return cachedShell();
    })());
    return;
  }

  if(url.pathname.startsWith('/pwa-assets/') || url.pathname.startsWith('/app/icon-') || url.pathname==='/app/manifest.webmanifest'){
    event.respondWith((async()=>{
      const cached=await caches.match(request);
      if(cached)return cached;
      const response=await fetch(request);
      if(response.ok){
        const cache=await caches.open(CACHE);
        await cache.put(request,response.clone());
      }
      return response;
    })());
  }
});

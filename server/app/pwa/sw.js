const CACHE='rpo-pwa-shell-v1.1.0';
const SHELL=['/app/','/app/manifest.webmanifest','/app/icon-180.png','/app/icon-192.png','/app/icon-512.png','/pwa-assets/app.css?v=20260829-2','/pwa-assets/ux.css?v=20260830-1','/pwa-assets/app.js?v=20260829-2','/pwa-assets/ux.js?v=20260830-1'];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});

self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});

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
    event.respondWith(fetch(req).then(resp=>{
      const copy=resp.clone();caches.open(CACHE).then(cache=>cache.put('/app/',copy));return resp;
    }).catch(()=>caches.match('/app/')));
    return;
  }

  if(url.pathname.startsWith('/pwa-assets/') || url.pathname.startsWith('/app/icon-') || url.pathname==='/app/manifest.webmanifest'){
    event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(resp=>{const copy=resp.clone();caches.open(CACHE).then(cache=>cache.put(req,copy));return resp;})));
  }
});

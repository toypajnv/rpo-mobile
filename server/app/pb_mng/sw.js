const CACHE='pb-mng-prototype-20260925-1';const SHELL=['/pb-mng/','/pb-mng/app.css?v=20260925-1','/pb-mng/app.js?v=20260925-1','/pb-mng/manifest.webmanifest','/pb-mng/icon-192.png','/pb-mng/icon-512.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return r}).catch(()=>caches.match(e.request).then(r=>r||caches.match('/pb-mng/'))));});

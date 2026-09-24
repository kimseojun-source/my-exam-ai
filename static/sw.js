// Cache only the public app shell. Private API responses and learning
// documents always stay on the network and never enter Cache Storage.
const CACHE='forest-shell-v39';
const ASSETS=[
 '/',
 '/offline.html',
 '/manifest.webmanifest',
 '/app.css?v=21',
 '/app.js?v=32',
 '/workspace.js?v=3',
 '/workspace.css?v=3',
 '/detail.js?v=6',
 '/install.js?v=1',
 '/icons/icon-192.png',
 '/icons/icon-512.png',
 '/icons/apple-touch-icon.png'
];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET')return;
 const url=new URL(event.request.url);
 if(url.origin!==self.location.origin || url.pathname.startsWith('/api/'))return;
 if(event.request.mode==='navigate'){
  event.respondWith(fetch(event.request).then(response=>{
   if(response.ok&&url.pathname==='/')caches.open(CACHE).then(cache=>cache.put('/',response.clone()));
   return response;
  }).catch(async()=>await caches.match('/')||caches.match('/offline.html')));
  return;
 }
 if(ASSETS.some(asset=>asset!=='/'&&asset===url.pathname+url.search)){
  event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)));
 }
});

(() => {
  'use strict';
  const load = (src) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.defer = true;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
  // Decision controls are injected directly by the server-rendered dashboard HTML.
  // Keep this loader focused on the stable core and UX layers so a loader cache
  // problem cannot hide the operator's «Запретить» action again.
  load('/static/dashboard-core.js?v=20260830-1')
    .then(() => load('/static/dashboard-ux.js?v=20260830-1'))
    .catch((error) => console.error('RPO dashboard loader', error));
})();

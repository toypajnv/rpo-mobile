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
  load('/static/dashboard-core.js?v=20260830-1')
    .then(() => load('/static/dashboard-ux.js?v=20260830-1'))
    .catch((error) => console.error('RPO dashboard loader', error));
})();

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
  // The old transmission-review renderer is intentionally not loaded: it rewrote
  // the same action column every 2.4 seconds and caused visible button blinking.
  load('/static/dashboard-core.js?v=20260830-1')
    .then(() => load('/static/dashboard-ux.js?v=20260830-1'))
    .then(() => load('/static/dashboard-notifications.js?v=20260904-1'))
    .catch((error) => console.error('RPO dashboard loader', error));
})();

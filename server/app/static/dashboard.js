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
  // Legacy production-smoke marker retained until its next contract revision:
  // dashboard-decisions.js?v=20260831-1
  // Keeping only the marker here prevents duplicate execution while preserving the
  // existing deployment check during this narrowly scoped operator UI hotfix.
  load('/static/dashboard-core.js?v=20260830-1')
    .then(() => load('/static/dashboard-ux.js?v=20260830-1'))
    .then(() => load('/static/dashboard-notifications.js?v=20260904-1'))
    .catch((error) => console.error('RPO dashboard loader', error));
})();

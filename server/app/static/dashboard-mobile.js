(() => {
  'use strict';

  const PHONE_SHORT_SIDE_MAX = 540;
  const isCoarsePointer = () => window.matchMedia?.('(pointer: coarse)').matches ?? false;
  const shortSide = () => Math.min(window.screen?.width || innerWidth, window.screen?.height || innerHeight);
  const isPhone = () => isCoarsePointer() && shortSide() <= PHONE_SHORT_SIDE_MAX;

  if (!isPhone()) return;
  document.documentElement.classList.add('mobile-phone');

  const NAV_ITEMS = [
    ['home', '⌂', 'Главная'],
    ['transmissions', '⇧', 'Переданные\nданные'],
    ['works', '▣', 'Работы'],
    ['analytics', '▥', 'Аналитика'],
    ['exports', '⇩', 'Выгрузки'],
  ];

  const tableObservers = new WeakMap();

  function existingTab(name) {
    return document.querySelector(`.sidebar [data-tab-link="${name}"]`);
  }

  function currentTab() {
    const hash = (location.hash || '#home').slice(1);
    return NAV_ITEMS.some(([name]) => name === hash) ? hash : hash;
  }

  function openTab(name) {
    if (typeof window.activateTab === 'function') {
      window.activateTab(name);
    } else {
      const original = existingTab(name);
      if (original) original.click();
      else location.hash = `#${name}`;
    }
    syncActiveTab();
    closeMoreMenu();
  }

  function syncActiveTab() {
    const name = (location.hash || '#home').slice(1) || 'home';
    document.querySelectorAll('.mobile-tabbar [data-mobile-tab]').forEach(link => {
      link.classList.toggle('active', link.dataset.mobileTab === name);
    });
  }

  function closeMoreMenu() {
    const menu = document.querySelector('.mobile-more-menu');
    if (menu) menu.hidden = true;
  }

  function buildHeader() {
    if (document.querySelector('.mobile-dashboard-header')) return;

    const username = document.querySelector('.operator span')?.textContent?.trim() || 'Пользователь';
    const header = document.createElement('div');
    header.className = 'mobile-dashboard-header';
    header.innerHTML = `
      <div class="mobile-dashboard-headline">
        <div class="mobile-brand">
          <span class="mobile-brand-mark">РПО</span>
          <b>РПО Сервер</b>
        </div>
        <div class="mobile-user-area">
          <span class="mobile-online"><i></i>Онлайн</span>
          <span class="mobile-user-name"></span>
          <button type="button" class="mobile-more-button" aria-label="Дополнительное меню" aria-expanded="false">⋯</button>
          <div class="mobile-more-menu" hidden></div>
        </div>
      </div>
      <nav class="mobile-tabbar" aria-label="Основная навигация"></nav>
    `;
    header.querySelector('.mobile-user-name').textContent = username;

    const nav = header.querySelector('.mobile-tabbar');
    NAV_ITEMS.forEach(([name, icon, label]) => {
      if (!existingTab(name)) return;
      const link = document.createElement('a');
      link.href = `#${name}`;
      link.dataset.mobileTab = name;
      link.innerHTML = `<span class="mobile-nav-icon">${icon}</span><span>${label.replace('\n', '<br>')}</span>`;
      link.addEventListener('click', event => {
        event.preventDefault();
        openTab(name);
      });
      nav.appendChild(link);
    });

    const menu = header.querySelector('.mobile-more-menu');
    [['users', '♙ Пользователи'], ['settings', '⚙ Настройки']].forEach(([name, label]) => {
      if (!existingTab(name)) return;
      const link = document.createElement('a');
      link.href = `#${name}`;
      link.textContent = label;
      link.addEventListener('click', event => {
        event.preventDefault();
        openTab(name);
      });
      menu.appendChild(link);
    });

    const logoutForm = document.querySelector('.operator form[action="/logout"]');
    if (logoutForm) {
      const logout = document.createElement('button');
      logout.type = 'button';
      logout.textContent = 'Выйти';
      logout.addEventListener('click', () => logoutForm.requestSubmit ? logoutForm.requestSubmit() : logoutForm.submit());
      menu.appendChild(logout);
    }

    const moreButton = header.querySelector('.mobile-more-button');
    moreButton.addEventListener('click', event => {
      event.stopPropagation();
      menu.hidden = !menu.hidden;
      moreButton.setAttribute('aria-expanded', String(!menu.hidden));
    });
    menu.addEventListener('click', event => event.stopPropagation());
    document.addEventListener('click', closeMoreMenu);

    document.body.prepend(header);
    syncActiveTab();
  }

  function enhanceHome() {
    const home = document.querySelector('#tab-home');
    const stats = home?.querySelector(':scope > .stats');
    const homeGrid = home?.querySelector(':scope > .home-grid');
    if (!home || !stats || !homeGrid || home.querySelector('.mobile-extra-metrics')) return;

    const details = document.createElement('details');
    details.className = 'mobile-extra-metrics';
    details.innerHTML = '<summary>Дополнительные показатели</summary>';
    homeGrid.insertAdjacentElement('afterend', details);
    details.appendChild(stats);
  }

  function decorateTable(table) {
    if (!table) return;
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
    table.querySelectorAll('tbody tr').forEach(row => {
      Array.from(row.children).forEach((cell, index) => {
        if (cell.tagName !== 'TD') return;
        cell.dataset.mobileLabel = headers[index] || '';
      });
    });

    const tbody = table.tBodies?.[0];
    if (tbody && !tableObservers.has(tbody)) {
      const observer = new MutationObserver(() => decorateTable(table));
      observer.observe(tbody, {childList: true});
      tableObservers.set(tbody, observer);
    }
  }

  function decorateTables() {
    document.querySelectorAll('#tab-transmissions table, #tab-works table').forEach(decorateTable);
  }

  function simplifyMobileLabels() {
    const works = document.querySelector('#tab-works .panel-title .panel-note');
    if (works) works.textContent = 'Карточки нарядов-допусков. Нажмите на этапы, чтобы раскрыть подробности.';
    const transmissions = document.querySelector('#tab-transmissions .panel-title .panel-note');
    if (transmissions) transmissions.textContent = 'Каждая передача показана отдельной карточкой — без горизонтальной прокрутки.';
  }

  function markMobileFooter() {
    if (document.querySelector('.mobile-adaptive-note')) return;
    const note = document.createElement('div');
    note.className = 'mobile-adaptive-note';
    note.textContent = '▯ Адаптивная мобильная версия для iOS / Android';
    note.style.cssText = 'text-align:center;color:#7b8ca2;font-size:11px;padding:20px 6px 4px;';
    document.querySelector('.main')?.appendChild(note);
  }

  function init() {
    buildHeader();
    enhanceHome();
    decorateTables();
    simplifyMobileLabels();
    markMobileFooter();
    syncActiveTab();

    window.addEventListener('hashchange', syncActiveTab);
    window.addEventListener('resize', () => {
      if (!isPhone()) location.reload();
    }, {passive: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();

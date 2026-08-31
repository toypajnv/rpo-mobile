(() => {
  'use strict';

  const SAVED_KEY = 'rpo_pwa_saved_v1';
  const QUEUE_KEY = 'rpo_pwa_queue_v1';
  const QUEUE_EVENT = 'rpo:queue-changed';
  const STAGE_BY_FIELD = {
    AT: 'PREPARATION', AU: 'PREPARATION', AV: 'TRANSFER_WORK',
    AY: 'ACTUAL_WORK', BC: 'ACTUAL_WORK', AZ: 'STOP_WORK',
    BA: 'RESUME_WORK', BE: 'EXTEND_WORK', RI: 'REPLACEMENTS',
  };
  const FIELDS_BY_STAGE = {
    PREPARATION: ['AT', 'AU'], TRANSFER_WORK: ['AV'], ACTUAL_WORK: ['AY', 'BC'],
    STOP_WORK: ['AZ'], RESUME_WORK: ['BA'], EXTEND_WORK: ['BE'], REPLACEMENTS: ['RI'],
  };

  const nativeSetItem = Storage.prototype.setItem;
  const nativeRemoveItem = Storage.prototype.removeItem;

  function parseJson(raw, fallback) {
    try {
      const value = JSON.parse(raw || '');
      return value ?? fallback;
    } catch (_) {
      return fallback;
    }
  }

  function itemKey(item) {
    const payload = item?.payload || {};
    return `${String(payload.permit_number || '').trim().toUpperCase()}|${String(payload.field_key || '').trim().toUpperCase()}`;
  }

  function normalizeQueue(items) {
    const list = Array.isArray(items) ? items : [];
    const pendingKeys = new Set(list.filter(item => item?.status === 'pending').map(itemKey));
    return list.filter(item => !(item?.status === 'failed' && pendingKeys.has(itemKey(item))));
  }

  // v1 marked a stage as "saved" before the server accepted it. Drop that legacy
  // cache and block new writes to it. Server-confirmed fields remain the only source
  // for the green "Передано" state.
  try { nativeRemoveItem.call(localStorage, SAVED_KEY); } catch (_) {}

  Storage.prototype.setItem = function(key, value) {
    if (this === localStorage && key === SAVED_KEY) return;
    if (this === localStorage && key === QUEUE_KEY) {
      const normalized = normalizeQueue(parseJson(value, []));
      nativeSetItem.call(this, key, JSON.stringify(normalized));
      setTimeout(() => window.dispatchEvent(new CustomEvent(QUEUE_EVENT)), 0);
      return;
    }
    nativeSetItem.call(this, key, value);
  };

  function queue() {
    return normalizeQueue(parseJson(localStorage.getItem(QUEUE_KEY), []));
  }

  function currentPermit() {
    return String(document.getElementById('permit-number')?.value || '').trim().toUpperCase();
  }

  function relevantQueue() {
    const permit = currentPermit();
    const items = queue();
    return permit ? items.filter(item => String(item?.payload?.permit_number || '').trim().toUpperCase() === permit) : items;
  }

  function stageTitle(item) {
    return String(item?.payload?.stage_label || item?.payload?.field_key || 'Этап').trim();
  }

  function errorText(item) {
    return String(item?.error || 'Сервер не принял запись. Проверьте данные этапа.').trim();
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el && el.textContent !== value) el.textContent = value;
  }

  function updateQueueNotice() {
    const box = document.getElementById('queue-notice');
    const button = document.getElementById('retry-queue');
    if (!box || !button) return;

    const items = relevantQueue();
    const failed = items.filter(item => item?.status === 'failed');
    const pending = items.filter(item => item?.status === 'pending');

    if (failed.length) {
      const first = failed[0];
      box.hidden = false;
      setText('queue-title', 'Ошибка передачи на сервер');
      const more = failed.length > 1 ? ` Ещё ошибок: ${failed.length - 1}.` : '';
      setText('queue-text', `Ошибка: ${stageTitle(first)} — ${errorText(first)}${more}`);
      button.textContent = 'Исправить';
      button.dataset.rpoAction = 'fix';
      return;
    }

    if (pending.length) {
      box.hidden = false;
      setText('queue-title', 'Сохранено на iPhone');
      setText('queue-text', `Ожидает отправки на сервер: ${pending.length}. До подтверждения сервера этап не считается переданным.`);
      button.textContent = 'Повторить';
      button.dataset.rpoAction = 'retry';
      return;
    }

    button.textContent = 'Повторить';
    button.dataset.rpoAction = 'retry';
  }

  function queuedStageStates() {
    const states = new Map();
    for (const item of relevantQueue()) {
      const field = String(item?.payload?.field_key || '').toUpperCase();
      const stage = STAGE_BY_FIELD[field];
      if (!stage) continue;
      const previous = states.get(stage);
      if (item.status === 'failed') states.set(stage, 'failed');
      else if (item.status === 'pending' && previous !== 'failed') states.set(stage, 'pending');
    }
    return states;
  }

  function updateStageRail() {
    const states = queuedStageStates();
    document.querySelectorAll('[data-ux-stage]').forEach(button => {
      const state = states.get(button.dataset.uxStage);
      const status = button.querySelector('small');
      if (!state || !status) return;
      button.classList.remove('done');
      if (state === 'failed') status.textContent = 'Ошибка передачи';
      else status.textContent = 'Ожидает отправки';
    });
  }

  function localDateTime(iso) {
    const d = new Date(iso || '');
    if (Number.isNaN(d.getTime())) return {date: '', time: ''};
    const pad = value => String(value).padStart(2, '0');
    return {
      date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
      time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
    };
  }

  function setInput(id, value) {
    const el = document.getElementById(id);
    if (!el || value == null) return;
    el.value = value;
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }

  function restoreFailedPayload(item) {
    const payload = item?.payload || {};
    const field = String(payload.field_key || '').toUpperCase();
    const stage = STAGE_BY_FIELD[field];
    const select = document.getElementById('stage-select');
    if (!stage || !select) return;

    select.value = stage;
    select.dispatchEvent(new Event('change', {bubbles: true}));

    requestAnimationFrame(() => {
      const dt = localDateTime(payload.event_time);
      if (field === 'AT' || field === 'AY' || field === 'AV' || field === 'AZ' || field === 'BA') {
        setInput('primary-date', dt.date);
        setInput('primary-time', dt.time);
      }
      if (field === 'AU' || field === 'BC') {
        setInput('secondary-date', dt.date);
        setInput('secondary-time', dt.time);
      }
      if (field === 'AZ') setInput('stop-reason', payload.comment || '');
      else if (field === 'BA') setInput('stage-comment', payload.comment || '');
      else if (field === 'BE') {
        const parts = String(payload.field_value || '').split('.');
        if (parts.length === 3) setInput('extension-date', `${parts[2]}-${parts[1]}-${parts[0]}`);
        setInput('stage-comment', payload.comment || '');
      } else if (field !== 'RI') {
        setInput('stage-comment', payload.comment || '');
      }

      const stageFields = document.getElementById('stage-fields');
      stageFields?.scrollIntoView({behavior: 'smooth', block: 'start'});
      showCorrectionMessage(item);
    });
  }

  function showCorrectionMessage(item) {
    const flash = document.getElementById('flash');
    if (!flash) return;
    flash.hidden = false;
    flash.className = 'notice queue-notice';
    setText('flash-icon', '!');
    setText('flash-title', 'Исправьте данные этапа');
    setText('flash-text', errorText(item));
  }

  function handleFixClick(event) {
    const button = event.target.closest?.('#retry-queue');
    if (!button || button.dataset.rpoAction !== 'fix') return;
    const failed = relevantQueue().find(item => item?.status === 'failed');
    if (!failed) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    restoreFailedPayload(failed);
  }

  function refresh() {
    updateQueueNotice();
    updateStageRail();
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', handleFixClick, true);
    refresh();
    setInterval(refresh, 1500);
  });
  window.addEventListener(QUEUE_EVENT, () => setTimeout(refresh, 0));
  window.addEventListener('pageshow', () => setTimeout(refresh, 0));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') setTimeout(refresh, 0);
  });
})();

(() => {
  'use strict';

  const permit = document.getElementById('permit-number');
  const formCard = permit?.closest('.form-card');
  const editButton = document.getElementById('ux-overview-edit');
  if (!permit || !formCard) return;

  function syncEditLabel() {
    const button = document.getElementById('ux-overview-edit');
    if (!button) return;
    button.textContent = formCard.classList.contains('ux-collapsed') ? '✎ Изменить' : '▴ Свернуть';
  }

  function keepEditorOpenWhileTyping() {
    // The UX layer used to treat the minimum valid length (3 symbols) as a signal
    // to collapse the whole permit form. That interrupted entry of normal longer
    // ND numbers on iPhone. Mark the automatic collapse as already handled and
    // keep the editor visible while the permit field has focus.
    formCard.dataset.uxCollapsedOnce = '1';
    formCard.classList.remove('ux-collapsed');
    syncEditLabel();
  }

  permit.addEventListener('focus', keepEditorOpenWhileTyping);
  permit.addEventListener('input', keepEditorOpenWhileTyping);

  editButton?.addEventListener('click', () => setTimeout(syncEditLabel, 0));
  new MutationObserver(syncEditLabel).observe(formCard, {
    attributes: true,
    attributeFilter: ['class'],
  });

  syncEditLabel();
})();

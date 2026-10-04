/* RSF v1.18.204 — dedicated Settings navigation + safe Esc return */
(() => {
  const STORAGE_KEY = 'rsf.settings.returnTo';

  const isSafeOperationalUrl = (value) => {
    if (!value) return false;
    try {
      const url = new URL(value, window.location.origin);
      if (url.origin !== window.location.origin) return false;
      if (!url.pathname.startsWith('/app/')) return false;
      if (url.pathname.startsWith('/app/admin/settings')) return false;
      if (url.pathname === '/app/workflow-diagram') return false;
      return true;
    } catch (_error) {
      return false;
    }
  };

  const storeEntryPoint = () => {
    const target = window.location.pathname + window.location.search + window.location.hash;
    if (!isSafeOperationalUrl(target)) return;
    try { window.sessionStorage.setItem(STORAGE_KEY, target); } catch (_error) {}
  };

  document.addEventListener('click', (event) => {
    const link = event.target.closest?.('[data-settings-entry]');
    if (!link) return;
    storeEntryPoint();
  });

  const experience = document.querySelector('[data-settings-experience]');
  if (!experience) return;

  const fallback = experience.dataset.settingsFallback || '/app/prospects';

  const returnTarget = () => {
    let stored = '';
    try { stored = window.sessionStorage.getItem(STORAGE_KEY) || ''; } catch (_error) {}
    if (isSafeOperationalUrl(stored)) return stored;

    if (document.referrer) {
      try {
        const ref = new URL(document.referrer);
        const local = ref.pathname + ref.search + ref.hash;
        if (isSafeOperationalUrl(local)) return local;
      } catch (_error) {}
    }
    return fallback;
  };

  const leaveSettings = () => {
    const target = returnTarget();
    try { window.sessionStorage.removeItem(STORAGE_KEY); } catch (_error) {}
    window.location.assign(target);
  };

  document.querySelectorAll('[data-settings-exit]').forEach((button) => {
    button.addEventListener('click', leaveSettings);
  });

  document.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || event.key !== 'Escape') return;

    const active = document.activeElement;
    const editing = active && (
      active.matches?.('input, textarea, select') ||
      active.isContentEditable
    );
    if (editing) return;

    const openDialog = document.querySelector('dialog[open], [role="dialog"][open], [role="dialog"]:not([hidden])');
    if (openDialog) return;

    leaveSettings();
  });
})();

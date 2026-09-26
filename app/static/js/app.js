(() => {
  const body = document.body;
  const menu = document.querySelector('[data-menu]');
  const scrim = document.querySelector('[data-scrim]');
  const sidebar = document.getElementById('sidebar');
  const mobileQuery = window.matchMedia('(max-width: 880px)');

  const syncSidebarAccess = () => {
    if (!sidebar) return;
    const mobile = mobileQuery.matches;
    const open = body.classList.contains('menu-open');
    const main = document.getElementById('main-content');
    if (main) main.inert = mobile && open;
    if (mobile && !open) {
      sidebar.setAttribute('aria-hidden', 'true');
      sidebar.inert = true;
    } else {
      sidebar.removeAttribute('aria-hidden');
      sidebar.inert = false;
    }
  };

  const closeMenu = (returnFocus = false) => {
    const wasOpen = body.classList.contains('menu-open');
    body.classList.remove('menu-open');
    if (menu) menu.setAttribute('aria-expanded', 'false');
    syncSidebarAccess();
    if (returnFocus && wasOpen && menu) menu.focus();
  };

  const openMenu = () => {
    body.classList.add('menu-open');
    if (menu) menu.setAttribute('aria-expanded', 'true');
    syncSidebarAccess();
    const firstLink = sidebar?.querySelector('a');
    if (firstLink) window.setTimeout(() => firstLink.focus(), 30);
  };

  if (menu) {
    menu.addEventListener('click', () => {
      if (body.classList.contains('menu-open')) closeMenu(true);
      else openMenu();
    });
  }
  if (scrim) scrim.addEventListener('click', () => closeMenu(true));
  document.querySelector('[data-close-menu]')?.addEventListener('click', () => closeMenu(true));
  sidebar?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      if (mobileQuery.matches) closeMenu(false);
    });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && body.classList.contains('menu-open')) closeMenu(true);
    if (event.key === 'Tab' && mobileQuery.matches && body.classList.contains('menu-open')) {
      const controls = [...sidebar.querySelectorAll('a[href], button:not([disabled])')]
        .filter((control) => control.getClientRects().length > 0);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  });
  mobileQuery.addEventListener?.('change', () => {
    body.classList.remove('menu-open');
    if (menu) menu.setAttribute('aria-expanded', 'false');
    syncSidebarAccess();
  });
  syncSidebarAccess();


  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const clicked = event.submitter;
    const message = clicked?.dataset?.confirm || form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    const checkboxName = form.dataset.confirmIfUnchecked;
    if (checkboxName) {
      const checkbox = form.elements.namedItem(checkboxName);
      if (checkbox instanceof HTMLInputElement && checkbox.type === 'checkbox' && !checkbox.checked) {
        const conditionalMessage = form.dataset.confirmMessage || 'Continue with this change?';
        if (!window.confirm(conditionalMessage)) event.preventDefault();
      }
    }
  });

  document.querySelectorAll('[data-account-disclosure]').forEach((button) => {
    button.addEventListener('click', () => {
      const targetId = button.dataset.target;
      const panel = targetId ? document.getElementById(targetId) : null;
      if (!panel) return;
      const opening = panel.hidden;

      if (opening) {
        document.querySelectorAll('.partner-password-expand:not([hidden])').forEach((openPanel) => {
          openPanel.hidden = true;
          const controller = document.querySelector(`[data-account-disclosure][data-target="${openPanel.id}"]`);
          if (controller) controller.setAttribute('aria-expanded', 'false');
        });
      }

      panel.hidden = !opening;
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
      if (opening) {
        const firstInput = panel.querySelector('input[type="password"]');
        if (firstInput) window.setTimeout(() => firstInput.focus(), 0);
      }
    });
  });

  document.querySelectorAll('[data-password-toggle],[data-toggle-password]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.target);
      if (!(target instanceof HTMLInputElement)) return;
      const reveal = target.type === 'password';
      target.type = reveal ? 'text' : 'password';
      button.textContent = reveal ? 'Hide' : 'Show';
      target.focus();
    });
  });

  document.querySelectorAll('[data-copy-target],[data-copy-input],[data-copy-text]').forEach((button) => {
    button.addEventListener('click', async () => {
      const targetId = button.dataset.copyTarget || button.dataset.target;
      const target = targetId ? document.getElementById(targetId) : null;
      const value = target instanceof HTMLInputElement ? target.value : (target?.textContent || '').trim();
      if (!value) return;
      try {
        await navigator.clipboard.writeText(value);
        const original = button.textContent;
        button.textContent = 'Copied';
        window.setTimeout(() => { button.textContent = original; }, 1400);
      } catch (_error) {
        if (target instanceof HTMLInputElement) {
          target.type = 'text';
          target.focus();
          target.select();
        }
      }
    });
  });


  // Show status-specific lead fields only when they are relevant.
  document.querySelectorAll('[data-lead-status-form]').forEach((form) => {
    const select = form.querySelector('[data-lead-status-select]');
    const fields = [...form.querySelectorAll('[data-status-field]')];
    if (!select || !fields.length) return;
    const syncStatusFields = () => {
      fields.forEach((field) => {
        field.hidden = field.dataset.statusField !== select.value;
      });
    };
    select.addEventListener('change', syncStatusFields);
    syncStatusFields();
  });
})();

/* Private Founder <-> Partner messages and simple voice calls. */
(() => {
  const body = document.body;
  const thread = document.querySelector('[data-message-thread]');
  const unreadBadges = [...document.querySelectorAll('[data-nav-unread]')];
  const clientUnreadBadges = [...document.querySelectorAll('[data-client-unread]')];
  let lastClientNotificationId = Number(sessionStorage.getItem('rsfClientNotificationId') || 0);
  const globalPollUrl = body.dataset.messagePollUrl;
  if (!globalPollUrl) return;

  const csrf = body.dataset.csrf || thread?.dataset.csrf || '';
  const overlay = document.querySelector('[data-call-overlay]');
  const callName = document.querySelector('[data-call-name]');
  const callAvatar = document.querySelector('[data-call-avatar]');
  const callStatus = document.querySelector('[data-call-status]');
  const callDuration = document.querySelector('[data-call-duration]');
  const callError = document.querySelector('[data-call-error]');
  const answerButton = document.querySelector('[data-call-answer]');
  const declineButton = document.querySelector('[data-call-decline]');
  const cancelButton = document.querySelector('[data-call-cancel]');
  const muteButton = document.querySelector('[data-call-mute]');
  const endButton = document.querySelector('[data-call-end]');
  const callActions = document.querySelector('.voice-call-actions');
  const remoteAudio = document.querySelector('[data-call-audio]');
  const startCallButton = document.querySelector('[data-start-call]');

  const list = thread?.querySelector('[data-message-list]');
  const imageViewer = document.querySelector('[data-image-viewer]');
  const imageViewerStage = imageViewer?.querySelector('[data-image-viewer-stage]');
  const imageViewerCanvas = imageViewer?.querySelector('[data-image-viewer-canvas]');
  const imageViewerImg = imageViewer?.querySelector('[data-image-viewer-img]');
  const imageViewerName = imageViewer?.querySelector('[data-image-viewer-name]');
  const imageViewerCount = imageViewer?.querySelector('[data-image-viewer-count]');
  const imageViewerDownload = imageViewer?.querySelector('[data-image-viewer-download]');
  const imageViewerClose = imageViewer?.querySelector('[data-image-viewer-close]');
  const imageViewerPrev = imageViewer?.querySelector('[data-image-viewer-prev]');
  const imageViewerNext = imageViewer?.querySelector('[data-image-viewer-next]');
  const imageViewerZoomIn = imageViewer?.querySelector('[data-image-viewer-zoom-in]');
  const imageViewerZoomOut = imageViewer?.querySelector('[data-image-viewer-zoom-out]');
  const imageViewerFit = imageViewer?.querySelector('[data-image-viewer-fit]');
  const imageViewerZoomValue = imageViewer?.querySelector('[data-image-viewer-zoom-value]');
  let imageViewerItems = [];
  let imageViewerIndex = 0;
  let imageViewerReturnFocus = null;
  let imageViewerBodyScrollY = 0;
  let imageViewerListScrollY = 0;

  const viewerState = {
    zoom: 1,
    minZoom: 0.5,
    maxZoom: 8,
    step: 0.25,
    fitScale: 1,
    panX: 0,
    panY: 0,
    naturalWidth: 0,
    naturalHeight: 0,
    pointers: new Map(),
    dragPointerId: null,
    dragLastX: 0,
    dragLastY: 0,
    pinchStartDistance: 0,
    pinchStartZoom: 1,
    pinchStartCenter: null,
  };

  // Keep the viewer outside the Messages workspace so no parent layout,
  // overflow, transform, or stacking context can make it participate in page flow.
  if (imageViewer && imageViewer.parentElement !== document.body) {
    document.body.appendChild(imageViewer);
  }

  const collectViewerItems = () => Array.from(list?.querySelectorAll('[data-message-image]') || []);
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const viewerViewport = () => {
    const rect = imageViewerCanvas?.getBoundingClientRect();
    return {
      width: Math.max(1, rect?.width || imageViewerStage?.clientWidth || 1),
      height: Math.max(1, rect?.height || imageViewerStage?.clientHeight || 1),
    };
  };
  const absoluteViewerScale = () => viewerState.fitScale * viewerState.zoom;
  const clampViewerPan = () => {
    if (!viewerState.naturalWidth || !viewerState.naturalHeight) {
      viewerState.panX = 0;
      viewerState.panY = 0;
      return;
    }
    const viewport = viewerViewport();
    const scale = absoluteViewerScale();
    const width = viewerState.naturalWidth * scale;
    const height = viewerState.naturalHeight * scale;
    const maxX = Math.max(0, (width - viewport.width) / 2);
    const maxY = Math.max(0, (height - viewport.height) / 2);
    viewerState.panX = clamp(viewerState.panX, -maxX, maxX);
    viewerState.panY = clamp(viewerState.panY, -maxY, maxY);
  };
  const renderViewerTransform = () => {
    if (!imageViewerImg) return;
    clampViewerPan();
    const scale = absoluteViewerScale();
    imageViewerImg.style.transform = `translate(-50%, -50%) translate3d(${viewerState.panX}px, ${viewerState.panY}px, 0) scale(${scale})`;
    const isFit = Math.abs(viewerState.zoom - 1) < 0.001;
    if (imageViewerZoomValue) imageViewerZoomValue.textContent = isFit ? 'Fit' : `${Math.round(viewerState.zoom * 100)}%`;
    if (imageViewerZoomOut) imageViewerZoomOut.disabled = viewerState.zoom <= viewerState.minZoom + 0.001;
    if (imageViewerZoomIn) imageViewerZoomIn.disabled = viewerState.zoom >= viewerState.maxZoom - 0.001;
    const viewport = viewerViewport();
    const pannable = viewerState.naturalWidth * scale > viewport.width + 1 || viewerState.naturalHeight * scale > viewport.height + 1;
    imageViewerCanvas?.classList.toggle('is-pannable', pannable);
    if (!pannable) imageViewerCanvas?.classList.remove('is-panning');
  };
  const calculateViewerFit = () => {
    if (!imageViewerImg || !viewerState.naturalWidth || !viewerState.naturalHeight) return;
    const viewport = viewerViewport();
    const horizontalSafe = window.innerWidth <= 700 ? 20 : 48;
    const verticalSafe = window.innerWidth <= 700 ? 20 : 36;
    const availableWidth = Math.max(1, viewport.width - horizontalSafe);
    const availableHeight = Math.max(1, viewport.height - verticalSafe);
    viewerState.fitScale = Math.min(
      1,
      availableWidth / viewerState.naturalWidth,
      availableHeight / viewerState.naturalHeight,
    );
  };
  const resetViewerTransform = () => {
    viewerState.zoom = 1;
    viewerState.panX = 0;
    viewerState.panY = 0;
    calculateViewerFit();
    renderViewerTransform();
  };
  const setViewerZoom = (nextZoom, originClientX = null, originClientY = null) => {
    const previousZoom = viewerState.zoom;
    const clampedZoom = clamp(nextZoom, viewerState.minZoom, viewerState.maxZoom);
    if (Math.abs(clampedZoom - previousZoom) < 0.0001) return;
    if (originClientX != null && originClientY != null && imageViewerCanvas) {
      const rect = imageViewerCanvas.getBoundingClientRect();
      const pointX = originClientX - (rect.left + rect.width / 2);
      const pointY = originClientY - (rect.top + rect.height / 2);
      const ratio = clampedZoom / previousZoom;
      viewerState.panX = pointX - (pointX - viewerState.panX) * ratio;
      viewerState.panY = pointY - (pointY - viewerState.panY) * ratio;
    } else if (clampedZoom <= 1) {
      viewerState.panX = 0;
      viewerState.panY = 0;
    }
    viewerState.zoom = clampedZoom;
    renderViewerTransform();
  };
  const changeViewerZoom = (direction, x = null, y = null) => setViewerZoom(viewerState.zoom + direction * viewerState.step, x, y);

  const renderImageViewer = () => {
    const item = imageViewerItems[imageViewerIndex];
    if (!item || !imageViewerImg) return;
    const url = item.dataset.imageUrl || '';
    const name = item.dataset.imageName || item.querySelector('img')?.alt || 'Image';
    viewerState.naturalWidth = 0;
    viewerState.naturalHeight = 0;
    viewerState.zoom = 1;
    viewerState.panX = 0;
    viewerState.panY = 0;
    viewerState.fitScale = 1;
    viewerState.pointers.clear();
    imageViewerCanvas?.classList.remove('is-pannable', 'is-panning');
    imageViewerImg.style.transform = 'translate(-50%, -50%)';
    imageViewerImg.src = url;
    imageViewerImg.alt = name;
    if (imageViewerName) imageViewerName.textContent = name;
    if (imageViewerCount) imageViewerCount.textContent = imageViewerItems.length > 1 ? `${imageViewerIndex + 1} of ${imageViewerItems.length}` : '1 of 1';
    if (imageViewerDownload) imageViewerDownload.href = item.dataset.imageDownloadUrl || url;
    if (imageViewerPrev) imageViewerPrev.hidden = imageViewerItems.length < 2;
    if (imageViewerNext) imageViewerNext.hidden = imageViewerItems.length < 2;
    if (imageViewerZoomValue) imageViewerZoomValue.textContent = 'Fit';
  };
  const openImageViewer = (item) => {
    if (!imageViewer || !item) return;
    imageViewerItems = collectViewerItems();
    imageViewerIndex = Math.max(0, imageViewerItems.indexOf(item));
    imageViewerReturnFocus = item;
    imageViewerBodyScrollY = window.scrollY;
    imageViewerListScrollY = list?.scrollTop || 0;
    imageViewer.hidden = false;
    document.documentElement.classList.add('image-viewer-open');
    document.body.classList.add('image-viewer-open');
    renderImageViewer();
    imageViewerClose?.focus();
  };
  const closeImageViewer = () => {
    if (!imageViewer || imageViewer.hidden) return;
    imageViewer.hidden = true;
    document.documentElement.classList.remove('image-viewer-open');
    document.body.classList.remove('image-viewer-open');
    viewerState.pointers.clear();
    imageViewerCanvas?.classList.remove('is-pannable', 'is-panning');
    if (imageViewerImg) {
      imageViewerImg.src = '';
      imageViewerImg.style.transform = '';
    }
    if (list) list.scrollTop = imageViewerListScrollY;
    window.scrollTo({ top: imageViewerBodyScrollY, behavior: 'instant' });
    imageViewerReturnFocus?.focus?.();
    imageViewerReturnFocus = null;
  };
  const moveImageViewer = (direction) => {
    if (imageViewerItems.length < 2) return;
    imageViewerIndex = (imageViewerIndex + direction + imageViewerItems.length) % imageViewerItems.length;
    renderImageViewer();
  };

  imageViewerImg?.addEventListener('load', () => {
    viewerState.naturalWidth = imageViewerImg.naturalWidth || 1;
    viewerState.naturalHeight = imageViewerImg.naturalHeight || 1;
    resetViewerTransform();
  });
  window.addEventListener('resize', () => {
    if (!imageViewer || imageViewer.hidden || !viewerState.naturalWidth) return;
    calculateViewerFit();
    renderViewerTransform();
  });

  list?.addEventListener('click', (event) => {
    const item = event.target.closest('[data-message-image]');
    if (!item) return;
    event.preventDefault();
    openImageViewer(item);
  });
  imageViewerClose?.addEventListener('click', closeImageViewer);
  imageViewerPrev?.addEventListener('click', () => moveImageViewer(-1));
  imageViewerNext?.addEventListener('click', () => moveImageViewer(1));
  imageViewerZoomIn?.addEventListener('click', () => changeViewerZoom(1));
  imageViewerZoomOut?.addEventListener('click', () => changeViewerZoom(-1));
  imageViewerFit?.addEventListener('click', resetViewerTransform);
  imageViewer?.addEventListener('click', (event) => {
    if (event.target === imageViewer) closeImageViewer();
  });
  imageViewerStage?.addEventListener('wheel', (event) => {
    if (!imageViewer || imageViewer.hidden) return;
    event.preventDefault();
    const direction = event.deltaY < 0 ? 1 : -1;
    changeViewerZoom(direction, event.clientX, event.clientY);
  }, { passive: false });
  imageViewerStage?.addEventListener('dblclick', (event) => {
    if (event.target.closest('button,a')) return;
    event.preventDefault();
    if (viewerState.zoom > 1.01) resetViewerTransform();
    else setViewerZoom(2, event.clientX, event.clientY);
  });

  const pointerDistance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const pointerCenter = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
  imageViewerStage?.addEventListener('pointerdown', (event) => {
    if (event.target.closest('button,a')) return;
    viewerState.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    try { imageViewerStage.setPointerCapture(event.pointerId); } catch (_) {}
    if (viewerState.pointers.size === 1) {
      viewerState.dragPointerId = event.pointerId;
      viewerState.dragLastX = event.clientX;
      viewerState.dragLastY = event.clientY;
      if (viewerState.zoom > 1) imageViewerCanvas?.classList.add('is-panning');
    } else if (viewerState.pointers.size === 2) {
      const points = [...viewerState.pointers.values()];
      viewerState.pinchStartDistance = Math.max(1, pointerDistance(points[0], points[1]));
      viewerState.pinchStartZoom = viewerState.zoom;
      viewerState.pinchStartCenter = pointerCenter(points[0], points[1]);
      imageViewerCanvas?.classList.add('is-panning');
    }
  });
  imageViewerStage?.addEventListener('pointermove', (event) => {
    if (!viewerState.pointers.has(event.pointerId)) return;
    const previous = viewerState.pointers.get(event.pointerId);
    viewerState.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (viewerState.pointers.size >= 2) {
      event.preventDefault();
      const points = [...viewerState.pointers.values()].slice(0, 2);
      const distance = Math.max(1, pointerDistance(points[0], points[1]));
      const center = pointerCenter(points[0], points[1]);
      const nextZoom = viewerState.pinchStartZoom * (distance / viewerState.pinchStartDistance);
      setViewerZoom(nextZoom, center.x, center.y);
      return;
    }
    if (viewerState.dragPointerId === event.pointerId && viewerState.zoom > 1) {
      event.preventDefault();
      viewerState.panX += event.clientX - previous.x;
      viewerState.panY += event.clientY - previous.y;
      viewerState.dragLastX = event.clientX;
      viewerState.dragLastY = event.clientY;
      renderViewerTransform();
    }
  });
  const releaseViewerPointer = (event) => {
    viewerState.pointers.delete(event.pointerId);
    if (viewerState.dragPointerId === event.pointerId) viewerState.dragPointerId = null;
    if (viewerState.pointers.size < 2) {
      viewerState.pinchStartDistance = 0;
      viewerState.pinchStartCenter = null;
    }
    if (!viewerState.pointers.size) imageViewerCanvas?.classList.remove('is-panning');
  };
  imageViewerStage?.addEventListener('pointerup', releaseViewerPointer);
  imageViewerStage?.addEventListener('pointercancel', releaseViewerPointer);
  imageViewerStage?.addEventListener('lostpointercapture', releaseViewerPointer);

  document.addEventListener('keydown', (event) => {
    if (!imageViewer || imageViewer.hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeImageViewer();
      return;
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      moveImageViewer(-1);
      return;
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      moveImageViewer(1);
      return;
    }
    if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      changeViewerZoom(1);
      return;
    }
    if (event.key === '-' || event.key === '_') {
      event.preventDefault();
      changeViewerZoom(-1);
      return;
    }
    if (event.key === '0') {
      event.preventDefault();
      resetViewerTransform();
      return;
    }
    if (event.key === 'Tab') {
      const focusable = Array.from(imageViewer.querySelectorAll('button:not([hidden]):not([disabled]),a[href]:not([hidden])'))
        .filter((node) => node.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  const form = thread?.querySelector('[data-message-form]');
  const input = thread?.querySelector('[data-message-input]');
  const fileInput = thread?.querySelector('[data-message-files]');
  const attachButton = thread?.querySelector('[data-attach-button]');
  const attachmentPreview = thread?.querySelector('[data-attachment-preview]');
  const threadError = thread?.querySelector('[data-message-error]');

  let messageAfter = Number(list?.querySelector('[data-message-id]:last-of-type')?.dataset.messageId || 0);
  let callEventAfter = Number(list?.querySelector('[data-call-event-id]:last-of-type')?.dataset.callEventId || 0);
  let pendingFiles = [];
  let currentCall = null;
  let signalAfter = 0;
  let peer = null;
  let localStream = null;
  let pendingOffer = null;
  let pendingCandidates = [];
  let makingAnswer = false;
  let muted = false;
  let closingPeer = false;
  let disconnectTimer = null;
  let connectTimer = null;
  let durationTimer = null;
  let answeringCall = false;
  let callPollBusy = false;
  let globalPollBusy = false;

  // v1.1.28 — audible private-call feedback.
  // Web Audio keeps call tones local to the browser; no media file or public URL is needed.
  let callToneContext = null;
  let callToneMode = null;
  let callToneCycleTimer = null;
  let callToneBurstTimers = [];
  let callToneNodes = [];

  const getCallToneContext = () => {
    if (!callToneContext) {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor) return null;
      callToneContext = new AudioContextCtor();
    }
    return callToneContext;
  };

  const clearCallToneNodes = () => {
    callToneNodes.forEach((node) => {
      try { node.stop?.(); } catch (_error) {}
      try { node.disconnect?.(); } catch (_error) {}
    });
    callToneNodes = [];
  };

  const clearCallToneTimers = () => {
    if (callToneCycleTimer) {
      window.clearTimeout(callToneCycleTimer);
      callToneCycleTimer = null;
    }
    callToneBurstTimers.forEach((timer) => window.clearTimeout(timer));
    callToneBurstTimers = [];
  };

  const stopCallTone = () => {
    callToneMode = null;
    clearCallToneTimers();
    clearCallToneNodes();
  };

  const playCallToneBurst = (frequencies, durationMs, volume = 0.035) => {
    const context = getCallToneContext();
    if (!context || context.state !== 'running') return;
    const now = context.currentTime;
    const duration = Math.max(0.08, durationMs / 1000);
    const master = context.createGain();
    master.gain.setValueAtTime(0.0001, now);
    master.gain.exponentialRampToValueAtTime(volume, now + 0.025);
    master.gain.setValueAtTime(volume, now + Math.max(0.03, duration - 0.05));
    master.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    master.connect(context.destination);
    callToneNodes.push(master);

    frequencies.forEach((frequency) => {
      const oscillator = context.createOscillator();
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(frequency, now);
      oscillator.connect(master);
      oscillator.start(now);
      oscillator.stop(now + duration + 0.02);
      callToneNodes.push(oscillator);
    });

    const cleanupTimer = window.setTimeout(() => {
      try { master.disconnect(); } catch (_error) {}
      callToneNodes = callToneNodes.filter((node) => node !== master);
    }, durationMs + 120);
    callToneBurstTimers.push(cleanupTimer);
  };

  const scheduleCallToneCycle = (mode) => {
    if (callToneMode !== mode) return;
    clearCallToneNodes();
    if (mode === 'outgoing') {
      // Familiar, restrained ringback cadence for the caller.
      playCallToneBurst([440, 480], 1150, 0.032);
      callToneCycleTimer = window.setTimeout(() => scheduleCallToneCycle(mode), 3300);
      return;
    }
    if (mode === 'incoming') {
      // Distinct double-ring pattern for an incoming RSF call.
      playCallToneBurst([660, 880], 420, 0.042);
      const secondRing = window.setTimeout(() => {
        if (callToneMode === mode) playCallToneBurst([660, 880], 420, 0.042);
      }, 650);
      callToneBurstTimers.push(secondRing);
      callToneCycleTimer = window.setTimeout(() => scheduleCallToneCycle(mode), 3000);
    }
  };

  const startCallTone = async (mode) => {
    if (!['incoming', 'outgoing'].includes(mode)) {
      stopCallTone();
      return;
    }
    if (callToneMode === mode && callToneCycleTimer) return;
    stopCallTone();
    callToneMode = mode;
    const context = getCallToneContext();
    if (!context) return;
    try {
      if (context.state === 'suspended') await context.resume();
    } catch (_error) {
      // Browser autoplay policy can require one user interaction.
    }
    if (callToneMode !== mode || context.state !== 'running') return;
    scheduleCallToneCycle(mode);
  };

  const syncCallTone = (mode) => {
    if (mode === 'incoming') {
      startCallTone('incoming');
    } else if (mode === 'calling') {
      startCallTone('outgoing');
    } else {
      stopCallTone();
    }
  };

  const unlockCallAudio = () => {
    const context = getCallToneContext();
    if (!context) return;
    context.resume?.().then(() => {
      if (callToneMode && !callToneCycleTimer) scheduleCallToneCycle(callToneMode);
    }).catch(() => {});
  };
  ['pointerdown', 'keydown', 'touchstart'].forEach((eventName) => {
    document.addEventListener(eventName, unlockCallAudio, { passive: true });
  });

  const tabId = (() => {
    const key = 'rsfVoiceTabId';
    let value = sessionStorage.getItem(key);
    if (!value) {
      value = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      sessionStorage.setItem(key, value);
    }
    return value;
  })();
  const ownerKey = 'rsfVoiceCallOwner';
  const channel = 'BroadcastChannel' in window ? new BroadcastChannel('rsf-voice-call') : null;

  const ownerRecord = () => {
    try { return JSON.parse(localStorage.getItem(ownerKey) || 'null'); } catch (_error) { return null; }
  };
  const isOwner = (callId) => {
    const owner = ownerRecord();
    return Boolean(owner && Number(owner.callId) === Number(callId) && owner.tabId === tabId);
  };
  const ownerIsOtherTab = (callId) => {
    const owner = ownerRecord();
    return Boolean(owner && Number(owner.callId) === Number(callId) && owner.tabId !== tabId && (Date.now() - Number(owner.at || 0)) < 15000);
  };
  const claimCall = (callId) => {
    const owner = { callId: Number(callId), tabId, at: Date.now() };
    localStorage.setItem(ownerKey, JSON.stringify(owner));
    channel?.postMessage({ type: 'claimed', ...owner });
  };
  const refreshClaim = () => {
    if (currentCall && isOwner(currentCall.id)) {
      localStorage.setItem(ownerKey, JSON.stringify({ callId: Number(currentCall.id), tabId, at: Date.now() }));
    }
  };
  const releaseCall = (callId) => {
    if (isOwner(callId)) localStorage.removeItem(ownerKey);
    channel?.postMessage({ type: 'released', callId: Number(callId), tabId });
  };

  channel?.addEventListener('message', (event) => {
    if (event.data?.type === 'claimed' && currentCall && Number(event.data.callId) === Number(currentCall.id) && event.data.tabId !== tabId) {
      hideOverlay();
      if (peer || localStream) resetPeer();
    }
  });
  window.setInterval(refreshClaim, 5000);

  const setUnread = (count) => {
    unreadBadges.forEach((badge) => {
      const value = Number(count || 0);
      badge.textContent = value > 99 ? '99+' : String(value);
      badge.hidden = value < 1;
    });
  };

  const setClientUnread = (count, overdue = 0) => {
    clientUnreadBadges.forEach((badge) => {
      const value = Number(count || 0);
      const overdueValue = Number(overdue || 0);
      badge.textContent = overdueValue > 0 ? `${value > 99 ? '99+' : value}!` : (value > 99 ? '99+' : String(value));
      badge.hidden = value < 1 && overdueValue < 1;
      badge.title = overdueValue > 0 ? `${overdueValue} client response(s) overdue` : `${value} unread client update(s)`;
    });
  };

  const surfaceClientNotification = (item) => {
    if (!item || !item.id) return;
    const id = Number(item.id || 0);
    if (!id || id <= lastClientNotificationId) return;
    lastClientNotificationId = id;
    sessionStorage.setItem('rsfClientNotificationId', String(id));
    if (document.visibilityState === 'visible') {
      const toast = document.createElement('div');
      toast.className = 'client-toast';
      const strong = document.createElement('strong');
      strong.textContent = item.title || 'RSF client update';
      const small = document.createElement('span');
      small.textContent = item.body || '';
      toast.append(strong, small);
      document.body.appendChild(toast);
      window.setTimeout(() => toast.classList.add('show'), 20);
      window.setTimeout(() => { toast.classList.remove('show'); window.setTimeout(() => toast.remove(), 220); }, 6000);
    } else if (window.Notification && Notification.permission === 'granted') {
      try { new Notification(item.title || 'RSF client update', { body: item.body || '' }); } catch (_error) {}
    }
  };

  const showThreadError = (message) => {
    if (!threadError) return;
    threadError.textContent = message || '';
    threadError.hidden = !message;
  };

  const post = async (url, values = {}) => {
    const data = new FormData();
    data.set('csrf_token', csrf);
    Object.entries(values).forEach(([key, value]) => data.set(key, value));
    const response = await fetch(url, {
      method: 'POST',
      body: data,
      headers: { 'X-RSF-Async': '1', Accept: 'application/json' },
      cache: 'no-store'
    });
    let payload = {};
    try { payload = await response.json(); } catch (_error) { /* handled below */ }
    if (!response.ok) throw new Error(payload.error || 'Something went wrong. Try again.');
    return payload;
  };

  const formatTime = (value) => {
    try {
      const date = new Date(value);
      const now = new Date();
      const sameDay = date.toDateString() === now.toDateString();
      if (sameDay) return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date);
      return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date);
    } catch (_error) {
      return value || '';
    }
  };

  const formatBytes = (bytes) => {
    const value = Number(bytes || 0);
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
    return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  };

  const scrollMessages = () => {
    if (list) list.scrollTop = list.scrollHeight;
  };

  const clearDeliveryMarkers = () => {
    list?.querySelectorAll('[data-delivery-status]').forEach((node) => node.remove());
  };

  const setDeliveryStatus = (messageId, status) => {
    if (!list || !messageId || !status) return;
    clearDeliveryMarkers();
    const row = list.querySelector(`[data-message-id="${Number(messageId)}"][data-mine="1"]`);
    const meta = row?.querySelector('.message-meta');
    if (!meta) return;
    const marker = document.createElement('span');
    marker.dataset.deliveryStatus = '';
    marker.textContent = status;
    meta.appendChild(marker);
  };

  const makeAttachmentNode = (attachment) => {
    if (attachment.is_image) {
      const link = document.createElement('button');
      link.type = 'button';
      link.className = 'message-image-link';
      link.dataset.messageImage = '';
      link.dataset.imageUrl = attachment.url;
      link.dataset.imageDownloadUrl = attachment.download_url || attachment.url;
      link.dataset.imageName = attachment.name || 'Image';
      link.setAttribute('aria-label', `Open ${attachment.name || 'image'} in image viewer`);
      const image = document.createElement('img');
      image.src = attachment.url;
      image.alt = attachment.name || 'Shared image';
      image.loading = 'lazy';
      link.appendChild(image);
      return link;
    }
    const link = document.createElement('a');
    link.className = 'message-file';
    link.href = attachment.download_url || attachment.url;
    link.setAttribute('aria-label', `Download ${attachment.name || 'file'}`);
    const name = document.createElement('span');
    name.className = 'message-file-name';
    name.textContent = attachment.name || 'File';
    const action = document.createElement('span');
    action.className = 'message-file-action';
    action.textContent = 'Download';
    link.append(name, action);
    return link;
  };

  const appendMessage = (message) => {
    if (!list || list.querySelector(`[data-message-id="${message.id}"]`)) return;
    list.querySelector('[data-message-empty]')?.remove();
    const row = document.createElement('div');
    row.className = `message-row ${message.mine ? 'mine' : 'theirs'}`;
    row.dataset.messageId = String(message.id);
    row.dataset.mine = message.mine ? '1' : '0';
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${(message.attachments || []).length ? 'has-attachments' : ''}`;
    if (message.body) {
      const text = document.createElement('p');
      text.textContent = message.body;
      bubble.appendChild(text);
    }
    if ((message.attachments || []).length) {
      const attachments = document.createElement('div');
      attachments.className = 'message-attachments';
      message.attachments.forEach((item) => attachments.appendChild(makeAttachmentNode(item)));
      bubble.appendChild(attachments);
    }
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    const time = document.createElement('span');
    time.textContent = formatTime(message.created_at);
    meta.appendChild(time);
    bubble.appendChild(meta);
    row.appendChild(bubble);
    list.appendChild(row);
    messageAfter = Math.max(messageAfter, Number(message.id || 0));
    if (message.mine && message.delivery_status) setDeliveryStatus(message.id, message.delivery_status);
  };

  const appendCallEvent = (event) => {
    if (!list || list.querySelector(`[data-call-event-id="${event.id}"]`)) return;
    list.querySelector('[data-message-empty]')?.remove();
    const row = document.createElement('div');
    row.className = 'call-event';
    row.dataset.callEventId = String(event.id);
    const text = document.createElement('span');
    text.textContent = event.text;
    const meta = document.createElement('small');
    meta.textContent = formatTime(event.created_at);
    row.append(text, meta);
    list.appendChild(row);
    callEventAfter = Math.max(callEventAfter, Number(event.id || 0));
  };

  const revokePendingPreviews = () => {
    pendingFiles.forEach((entry) => {
      if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl);
    });
  };

  const renderPendingFiles = () => {
    if (!attachmentPreview) return;
    attachmentPreview.replaceChildren();
    attachmentPreview.hidden = pendingFiles.length === 0;
    pendingFiles.forEach((entry, index) => {
      const item = document.createElement('div');
      item.className = 'pending-attachment';
      if (entry.file.type.startsWith('image/')) {
        if (!entry.previewUrl) entry.previewUrl = URL.createObjectURL(entry.file);
        const image = document.createElement('img');
        image.src = entry.previewUrl;
        image.alt = '';
        item.appendChild(image);
      } else {
        const fileIcon = document.createElement('span');
        fileIcon.className = 'pending-file-icon';
        fileIcon.textContent = 'File';
        item.appendChild(fileIcon);
      }
      const copy = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = entry.file.name;
      const size = document.createElement('small');
      size.textContent = formatBytes(entry.file.size);
      copy.append(name, size);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'pending-remove';
      remove.setAttribute('aria-label', `Remove ${entry.file.name}`);
      remove.title = 'Remove';
      remove.textContent = '×';
      remove.addEventListener('click', () => {
        if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl);
        pendingFiles.splice(index, 1);
        renderPendingFiles();
      });
      item.append(copy, remove);
      attachmentPreview.appendChild(item);
    });
  };

  const clearPendingFiles = () => {
    revokePendingPreviews();
    pendingFiles = [];
    if (fileInput) fileInput.value = '';
    renderPendingFiles();
  };

  const addFiles = (files) => {
    showThreadError('');
    for (const file of files) {
      if (pendingFiles.length >= 5) {
        showThreadError('Attach up to 5 files at a time.');
        break;
      }
      if (file.size > 15 * 1024 * 1024) {
        showThreadError('Each file must be 15 MB or smaller.');
        continue;
      }
      pendingFiles.push({ file, previewUrl: '' });
    }
    renderPendingFiles();
  };

  attachButton?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => {
    addFiles([...fileInput.files]);
    fileInput.value = '';
  });

  input?.addEventListener('paste', (event) => {
    const imageItems = [...(event.clipboardData?.items || [])].filter((item) => item.kind === 'file' && item.type.startsWith('image/'));
    if (!imageItems.length) return;
    const images = imageItems.map((item, index) => {
      const blob = item.getAsFile();
      if (!blob) return null;
      const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : blob.type === 'image/gif' ? 'gif' : 'png';
      return new File([blob], `Screenshot-${Date.now()}${index ? `-${index + 1}` : ''}.${extension}`, { type: blob.type || `image/${extension}` });
    }).filter(Boolean);
    if (images.length) {
      event.preventDefault();
      addFiles(images);
    }
  });

  const resizeMessageInput = () => {
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  };
  input?.addEventListener('input', resizeMessageInput);

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const bodyText = (input?.value || '').trim();
    if (!bodyText && pendingFiles.length === 0) return;
    showThreadError('');
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const data = new FormData();
      data.set('csrf_token', csrf);
      data.set('body', bodyText);
      pendingFiles.forEach((entry) => data.append('attachments', entry.file, entry.file.name));
      const response = await fetch(thread.dataset.sendUrl, {
        method: 'POST',
        body: data,
        headers: { 'X-RSF-Async': '1', Accept: 'application/json' },
        cache: 'no-store'
      });
      let payload = {};
      try { payload = await response.json(); } catch (_error) { /* handled below */ }
      if (!response.ok) {
        if (response.status === 413) throw new Error('Attachments are too large.');
        throw new Error(payload.error || 'Message could not be sent. Try again.');
      }
      if (payload.message) appendMessage(payload.message);
      if (input) {
        input.value = '';
        resizeMessageInput();
        input.focus();
      }
      clearPendingFiles();
      scrollMessages();
    } catch (error) {
      showThreadError(error.message);
    } finally {
      if (button) button.disabled = false;
    }
  });

  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form?.requestSubmit();
    }
  });

  const hideOverlay = () => {
    stopCallTone();
    if (overlay) overlay.hidden = true;
    if (durationTimer) {
      window.clearInterval(durationTimer);
      durationTimer = null;
    }
    if (connectTimer) {
      window.clearTimeout(connectTimer);
      connectTimer = null;
    }
  };

  const hideAllCallButtons = () => {
    [answerButton, declineButton, cancelButton, muteButton, endButton].forEach((button) => {
      if (button) {
        button.hidden = true;
        button.setAttribute('aria-hidden', 'true');
      }
    });
    if (callActions) callActions.hidden = true;
  };

  const showCallButtons = (...buttons) => {
    const visible = buttons.filter(Boolean);
    visible.forEach((button) => {
      button.hidden = false;
      button.removeAttribute('aria-hidden');
    });
    if (callActions) callActions.hidden = visible.length === 0;
  };

  const setCallError = (message) => {
    if (!callError) return;
    callError.textContent = message || '';
    callError.hidden = !message;
  };

  const formatDuration = (startedAt) => {
    const start = Date.parse(startedAt || '') || Date.now();
    const seconds = Math.max(0, Math.floor((Date.now() - start) / 1000));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return hours > 0
      ? `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
      : `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const startDuration = () => {
    if (!callDuration || !currentCall?.answered_at) return;
    if (durationTimer) window.clearInterval(durationTimer);
    const update = () => { callDuration.textContent = formatDuration(currentCall?.answered_at); };
    update();
    durationTimer = window.setInterval(update, 1000);
  };

  const terminalText = (call) => {
    if (!call) return 'Call ended';
    if (call.status === 'DECLINED') return 'Call declined';
    if (call.status === 'MISSED') return 'Missed call';
    if (call.end_reason === 'failed') return 'Call could not connect';
    if (call.end_reason === 'connection_lost') return 'Internet connection was lost';
    return 'Call ended';
  };

  const renderCall = (mode, error = '') => {
    if (!overlay || !currentCall) return;
    overlay.hidden = false;
    overlay.dataset.callMode = mode;
    syncCallTone(mode);
    hideAllCallButtons();
    setCallError(error);
    if (callName) callName.textContent = currentCall.name || 'Voice call';
    if (callAvatar) {
      const avatarUrl = currentCall.avatar_url || '';
      callAvatar.hidden = !avatarUrl;
      if (avatarUrl) {
        callAvatar.src = avatarUrl;
        callAvatar.alt = `${currentCall.name || 'User'} profile picture`;
      } else {
        callAvatar.removeAttribute('src');
        callAvatar.alt = '';
      }
    }
    if (callDuration) callDuration.hidden = true;

    if (mode === 'incoming') {
      if (callStatus) callStatus.textContent = 'Incoming call';
      showCallButtons(answerButton, declineButton);
      window.setTimeout(() => answerButton?.focus(), 20);
    } else if (mode === 'permission') {
      if (callStatus) callStatus.textContent = 'Allow microphone access...';
    } else if (mode === 'calling') {
      if (callStatus) callStatus.textContent = 'Calling...';
      showCallButtons(cancelButton);
    } else if (mode === 'connecting') {
      if (callStatus) callStatus.textContent = 'Connecting...';
      showCallButtons(endButton);
      if (!connectTimer && isOwner(currentCall.id)) {
        connectTimer = window.setTimeout(() => {
          connectTimer = null;
          if (currentCall?.status === 'ACTIVE' && peer?.connectionState !== 'connected' && isOwner(currentCall.id)) {
            finishCall('failed', 'Call could not connect.');
          }
        }, 20000);
      }
    } else if (mode === 'active') {
      if (connectTimer) {
        window.clearTimeout(connectTimer);
        connectTimer = null;
      }
      if (callStatus) callStatus.textContent = 'In call';
      if (callDuration) callDuration.hidden = false;
      if (muteButton) muteButton.textContent = muted ? 'Unmute' : 'Mute';
      showCallButtons(muteButton, endButton);
      startDuration();
    } else if (mode === 'terminal') {
      if (callStatus) callStatus.textContent = terminalText(currentCall);
    }
  };

  const mediaErrorMessage = (error) => {
    const name = error?.name || '';
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      return 'Microphone access is blocked. Allow it in your browser to call.';
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return 'Your microphone is not available.';
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return 'Your microphone is being used by another app.';
    }
    return 'Your microphone is not available.';
  };

  const ensureMedia = async () => {
    if (localStream) return localStream;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error('Voice calls are not available on this connection.');
    }
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      localStream.getAudioTracks().forEach((track) => {
        track.addEventListener('ended', () => {
          if (!closingPeer && currentCall && ['RINGING', 'ACTIVE'].includes(currentCall.status) && isOwner(currentCall.id)) {
            finishCall('failed', 'Your microphone is not available.');
          }
        });
      });
      return localStream;
    } catch (error) {
      throw new Error(mediaErrorMessage(error));
    }
  };

  const resetPeer = () => {
    stopCallTone();
    closingPeer = true;
    if (disconnectTimer) {
      window.clearTimeout(disconnectTimer);
      disconnectTimer = null;
    }
    if (connectTimer) {
      window.clearTimeout(connectTimer);
      connectTimer = null;
    }
    if (peer) {
      try { peer.close(); } catch (_error) {}
      peer = null;
    }
    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
      localStream = null;
    }
    if (remoteAudio) remoteAudio.srcObject = null;
    pendingOffer = null;
    pendingCandidates = [];
    makingAnswer = false;
    muted = false;
    closingPeer = false;
  };

  const sendSignal = async (kind, payload) => {
    if (!currentCall) return;
    await post(currentCall.signal_url, { kind, payload: JSON.stringify(payload) });
  };

  const applyPendingCandidates = async () => {
    if (!peer?.remoteDescription) return;
    const candidates = pendingCandidates;
    pendingCandidates = [];
    for (const candidate of candidates) {
      try { await peer.addIceCandidate(candidate); } catch (_error) {}
    }
  };

  const ensurePeer = async () => {
    if (peer) return peer;
    await ensureMedia();
    peer = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.cloudflare.com:3478' },
        { urls: 'stun:stun.l.google.com:19302' }
      ]
    });
    localStream.getTracks().forEach((track) => peer.addTrack(track, localStream));
    peer.addEventListener('track', (event) => {
      if (remoteAudio && event.streams?.[0]) {
        remoteAudio.srcObject = event.streams[0];
        remoteAudio.play?.().catch(() => {});
      }
    });
    peer.addEventListener('icecandidate', (event) => {
      if (event.candidate && currentCall && isOwner(currentCall.id)) {
        sendSignal('ICE', event.candidate.toJSON()).catch(() => {});
      }
    });
    peer.addEventListener('connectionstatechange', () => {
      if (!peer || !currentCall || !isOwner(currentCall.id)) return;
      if (peer.connectionState === 'connected') {
        if (disconnectTimer) {
          window.clearTimeout(disconnectTimer);
          disconnectTimer = null;
        }
        renderCall('active');
      } else if (['new', 'connecting'].includes(peer.connectionState) && currentCall.status === 'ACTIVE') {
        renderCall('connecting');
      } else if (peer.connectionState === 'disconnected') {
        renderCall('connecting');
        if (!disconnectTimer) {
          disconnectTimer = window.setTimeout(() => {
            if (peer?.connectionState === 'disconnected') {
              finishCall('connection_lost', 'Internet connection was lost.');
            }
          }, 10000);
        }
      } else if (peer.connectionState === 'failed') {
        finishCall('failed', 'Call could not connect.');
      }
    });
    return peer;
  };

  const answerPendingOffer = async () => {
    if (!pendingOffer || !currentCall || currentCall.status !== 'ACTIVE' || currentCall.started_by_me || !isOwner(currentCall.id) || makingAnswer) return;
    makingAnswer = true;
    try {
      const connection = await ensurePeer();
      if (!connection.currentRemoteDescription) await connection.setRemoteDescription(pendingOffer);
      await applyPendingCandidates();
      const answer = await connection.createAnswer();
      await connection.setLocalDescription(answer);
      await sendSignal('ANSWER', connection.localDescription.toJSON());
    } finally {
      makingAnswer = false;
    }
  };

  const handleSignal = async (signal) => {
    let payload;
    try { payload = JSON.parse(signal.payload_json); } catch (_error) { return; }
    if (signal.kind === 'OFFER') {
      pendingOffer = payload;
      await answerPendingOffer();
    } else if (signal.kind === 'ANSWER' && currentCall?.started_by_me && isOwner(currentCall.id)) {
      const connection = await ensurePeer();
      if (!connection.currentRemoteDescription) {
        await connection.setRemoteDescription(payload);
        await applyPendingCandidates();
      }
    } else if (signal.kind === 'ICE') {
      if (peer?.remoteDescription) {
        try { await peer.addIceCandidate(payload); } catch (_error) {}
      } else {
        pendingCandidates.push(payload);
      }
    }
  };

  const clearCallSoon = (callId) => {
    window.setTimeout(() => {
      if (!currentCall || Number(currentCall.id) !== Number(callId)) return;
      hideOverlay();
      resetPeer();
      releaseCall(callId);
      currentCall = null;
      answeringCall = false;
      signalAfter = 0;
      if (startCallButton) startCallButton.disabled = false;
      pollThread();
    }, 1700);
  };

  const applyServerCall = (call) => {
    if (!call) {
      if (currentCall && !isOwner(currentCall.id)) {
        const oldId = currentCall.id;
        currentCall.status = 'ENDED';
        currentCall.end_reason = 'ended';
        renderCall('terminal');
        clearCallSoon(oldId);
      }
      return;
    }

    if (!currentCall || Number(currentCall.id) !== Number(call.id)) {
      if (peer || localStream) resetPeer();
      currentCall = call;
      signalAfter = 0;
    } else {
      currentCall = { ...currentCall, ...call };
    }

    if (startCallButton) startCallButton.disabled = ['RINGING', 'ACTIVE'].includes(currentCall.status);

    if (['ENDED', 'DECLINED', 'MISSED'].includes(currentCall.status)) {
      const oldId = currentCall.id;
      renderCall('terminal');
      resetPeer();
      clearCallSoon(oldId);
      return;
    }

    if (ownerIsOtherTab(currentCall.id)) {
      hideOverlay();
      return;
    }

    if (currentCall.status === 'RINGING') {
      if (currentCall.started_by_me) {
        if (isOwner(currentCall.id)) renderCall('calling');
        else hideOverlay();
      } else {
        renderCall(answeringCall && isOwner(currentCall.id) ? 'permission' : 'incoming');
      }
    } else if (currentCall.status === 'ACTIVE') {
      if (!isOwner(currentCall.id)) {
        hideOverlay();
      } else if (peer?.connectionState === 'connected') {
        renderCall('active');
      } else {
        renderCall('connecting');
      }
    }
  };

  const pollCall = async () => {
    if (!currentCall || callPollBusy) return;
    const observingIncoming = currentCall.status === 'RINGING' && !currentCall.started_by_me && !ownerIsOtherTab(currentCall.id);
    if (!isOwner(currentCall.id) && !observingIncoming) return;
    callPollBusy = true;
    try {
      const params = new URLSearchParams({ after_signal: String(signalAfter) });
      const response = await fetch(`${currentCall.updates_url}?${params}`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      applyServerCall(data.call);
      for (const signal of (data.signals || [])) {
        signalAfter = Math.max(signalAfter, Number(signal.id || 0));
        await handleSignal(signal);
      }
    } catch (_error) {
      // A later poll retries automatically.
    } finally {
      callPollBusy = false;
    }
  };

  const finishCall = async (reason = 'ended', visibleError = '') => {
    if (!currentCall || !isOwner(currentCall.id)) return;
    const callId = currentCall.id;
    try { await post(currentCall.end_url, { reason }); } catch (_error) { /* clean up locally */ }
    currentCall = { ...currentCall, status: 'ENDED', end_reason: reason };
    if (visibleError) setCallError(visibleError);
    renderCall('terminal', visibleError);
    resetPeer();
    releaseCall(callId);
    clearCallSoon(callId);
  };

  answerButton?.addEventListener('click', async () => {
    if (!currentCall || currentCall.started_by_me || currentCall.status !== 'RINGING') return;
    if (ownerIsOtherTab(currentCall.id)) {
      hideOverlay();
      return;
    }
    claimCall(currentCall.id);
    answeringCall = true;
    renderCall('permission');
    try {
      await new Promise((resolve) => window.setTimeout(resolve, 60));
      if (!isOwner(currentCall.id)) {
        answeringCall = false;
        hideOverlay();
        return;
      }
      await ensureMedia();
      const data = await post(currentCall.accept_url);
      if (data.call) currentCall = { ...currentCall, ...data.call };
      answeringCall = false;
      renderCall('connecting');
      await answerPendingOffer();
      await pollCall();
      await answerPendingOffer();
    } catch (error) {
      answeringCall = false;
      releaseCall(currentCall.id);
      resetPeer();
      renderCall('incoming', error.message);
    }
  });

  declineButton?.addEventListener('click', async () => {
    if (!currentCall || currentCall.started_by_me || currentCall.status !== 'RINGING') return;
    const callId = currentCall.id;
    try { await post(currentCall.decline_url); } catch (_error) {}
    currentCall = { ...currentCall, status: 'DECLINED', end_reason: 'declined' };
    renderCall('terminal');
    resetPeer();
    releaseCall(callId);
    clearCallSoon(callId);
  });

  cancelButton?.addEventListener('click', () => {
    if (!currentCall || currentCall.status !== 'RINGING' || !currentCall.started_by_me) return;
    finishCall('cancelled');
  });
  endButton?.addEventListener('click', () => {
    if (!currentCall || currentCall.status !== 'ACTIVE') return;
    finishCall('ended');
  });
  muteButton?.addEventListener('click', () => {
    if (!currentCall || currentCall.status !== 'ACTIVE' || peer?.connectionState !== 'connected' || !localStream) return;
    muted = !muted;
    localStream.getAudioTracks().forEach((track) => { track.enabled = !muted; });
    renderCall('active');
  });

  startCallButton?.addEventListener('click', async () => {
    if (!thread || currentCall) return;
    startCallButton.disabled = true;
    showThreadError('Allow microphone access to make calls.');
    try {
      await ensureMedia();
      showThreadError('');
      const data = await post(thread.dataset.startCallUrl);
      currentCall = data.call;
      signalAfter = 0;
      claimCall(currentCall.id);
      renderCall('calling');
      const connection = await ensurePeer();
      const offer = await connection.createOffer({ offerToReceiveAudio: true });
      await connection.setLocalDescription(offer);
      await sendSignal('OFFER', connection.localDescription.toJSON());
    } catch (error) {
      if (currentCall && isOwner(currentCall.id)) {
        await finishCall('failed', 'Call could not connect.');
      } else {
        resetPeer();
        showThreadError(error.message);
        startCallButton.disabled = false;
      }
    }
  });

  const pollGlobal = async () => {
    if (globalPollBusy) return;
    globalPollBusy = true;
    try {
      const response = await fetch(globalPollUrl, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      setUnread(data.unread);
      setClientUnread(data.client_unread, data.client_overdue);
      surfaceClientNotification(data.client_notification);
      applyServerCall(data.call);
    } catch (_error) {
      // Keep RSF usable if a background check fails.
    } finally {
      globalPollBusy = false;
    }
  };

  const pollThread = async () => {
    if (!thread || document.visibilityState !== 'visible') return;
    try {
      const params = new URLSearchParams({
        after_message: String(messageAfter),
        after_call_event: String(callEventAfter)
      });
      const response = await fetch(`${thread.dataset.updatesUrl}?${params}`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      const items = [
        ...(data.messages || []).map((item) => ({ kind: 'message', created_at: item.created_at, item })),
        ...(data.call_events || []).map((item) => ({ kind: 'call', created_at: item.created_at, item }))
      ].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
      items.forEach((entry) => entry.kind === 'message' ? appendMessage(entry.item) : appendCallEvent(entry.item));
      if (data.read_receipt?.message_id && data.read_receipt?.status) {
        setDeliveryStatus(data.read_receipt.message_id, data.read_receipt.status);
      }
      if (items.length) scrollMessages();
      setUnread(data.unread);
    } catch (_error) {
      // A later poll retries automatically.
    }
  };

  window.addEventListener('pagehide', () => {
    stopCallTone();
    revokePendingPreviews();
    if (!currentCall || !isOwner(currentCall.id) || !['RINGING', 'ACTIVE'].includes(currentCall.status)) return;
    const data = new FormData();
    data.set('csrf_token', csrf);
    data.set('reason', currentCall.status === 'RINGING' ? 'cancelled' : 'ended');
    navigator.sendBeacon?.(currentCall.end_url, data);
    releaseCall(currentCall.id);
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      pollGlobal();
      pollThread();
      pollCall();
    }
  });


  const credentialShell = document.querySelector('.account-security-shell[data-password-vault-url]');
  if (credentialShell) {
    const revealUrl = credentialShell.dataset.passwordVaultUrl || '';
    const credentialCsrf = credentialShell.dataset.passwordVaultCsrf || csrf || '';

    const loadCredential = async (button) => {
      const target = document.getElementById(button.dataset.target || '');
      if (!(target instanceof HTMLInputElement)) throw new Error('Password field unavailable.');
      if (target.dataset.loaded === '1') return target;

      const body = new URLSearchParams({
        csrf_token: credentialCsrf,
        user_id: button.dataset.userId || ''
      });
      const response = await fetch(revealUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
        body,
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Current password is not available yet.');
      }
      target.value = data.password || '';
      target.dataset.loaded = '1';
      return target;
    };

    credentialShell.addEventListener('click', async (event) => {
      const show = event.target.closest('[data-vault-reveal]');
      if (show) {
        try {
          const input = await loadCredential(show);
          const reveal = input.type === 'password';
          input.type = reveal ? 'text' : 'password';
          show.textContent = reveal ? 'Hide' : 'Show';
        } catch (error) {
          window.alert(error.message);
        }
        return;
      }

      const copy = event.target.closest('[data-vault-copy]');
      if (copy) {
        try {
          const input = await loadCredential(copy);
          await navigator.clipboard.writeText(input.value);
          const previous = copy.textContent;
          copy.textContent = 'Copied';
          window.setTimeout(() => { copy.textContent = previous; }, 1200);
        } catch (error) {
          window.alert(error.message);
        }
      }
    });
  }

  scrollMessages();
  window.setTimeout(pollGlobal, 150);
  window.setTimeout(pollThread, 250);
  window.setInterval(pollGlobal, 2000);
  window.setInterval(pollThread, 2000);
  window.setInterval(pollCall, 1200);
})();

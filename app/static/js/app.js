const RSFConversationTimeline = (() => {
  const activeLoads = new WeakMap();

  const setAction = (element, href) => {
    if (!element) return;
    const locked = element.dataset.actionLocked === 'true';
    if (href && !locked) {
      element.href = href;
      element.removeAttribute('aria-disabled');
      element.removeAttribute('tabindex');
      element.classList.remove('is-disabled');
    } else {
      element.href = '#';
      element.setAttribute('aria-disabled', 'true');
      element.setAttribute('tabindex', '-1');
      element.classList.add('is-disabled');
    }
  };

  const notePayload = (entry, csrfToken, body = null) => {
    const payload = new URLSearchParams({
      csrf_token: csrfToken || '',
      kind: entry.note_kind || ''
    });
    if (entry.note_kind === 'manual') {
      payload.set('note_id', String(entry.note_id || ''));
    } else if (entry.note_kind === 'legacy') {
      payload.set('source_type', entry.source_type || '');
      payload.set('source_id', String(entry.source_id || ''));
    }
    if (body !== null) payload.set('body', body);
    return payload;
  };

  const mutateNote = async (action, entry, csrfToken, body = null) => {
    const response = await fetch(`/app/communications/note-entry/${action}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
      },
      body: notePayload(entry, csrfToken, body).toString(),
      credentials: 'same-origin',
      cache: 'no-store'
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.message || `Note could not be ${action === 'delete' ? 'deleted' : 'updated'}.`);
    }
    return data;
  };

  const iconButton = (label, className, svg) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `conversation-note-action ${className}`;
    button.setAttribute('aria-label', label);
    button.title = label;
    button.innerHTML = svg;
    return button;
  };

  const render = (container, entries, context = {}) => {
    if (!container) return;
    container.replaceChildren();
    if (!entries?.length) {
      const empty = document.createElement('div');
      empty.className = 'conversation-timeline-empty';
      empty.textContent = 'No conversation history yet.';
      container.appendChild(empty);
      return;
    }

    entries.forEach((entry) => {
      const item = document.createElement('article');
      item.className = 'conversation-timeline-item';

      const head = document.createElement('div');
      head.className = 'conversation-timeline-item-head';

      const meta = document.createElement('strong');
      const channel = (entry.channel || '').toUpperCase();
      if (channel === 'NOTE') meta.textContent = 'MANUAL NOTE';
      else if (channel === 'EMAIL') meta.textContent = entry.direction === 'CLIENT' ? 'CLIENT REPLY' : 'EMAIL SENT';
      else if (channel === 'WEBSITE MESSAGE') meta.textContent = 'WEBSITE MESSAGE';
      else if (channel === 'AI SALES CALL') meta.textContent = 'AI SALES CALL';
      else meta.textContent = channel || entry.source || 'COMMUNICATION';

      const headRight = document.createElement('div');
      headRight.className = 'conversation-timeline-item-right';

      const when = document.createElement('time');
      const raw = entry.at || '';
      const date = raw ? new Date(raw) : null;
      when.textContent = date && !Number.isNaN(date.getTime())
        ? new Intl.DateTimeFormat(undefined, {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: 'numeric', minute: '2-digit'
          }).format(date)
        : raw;
      headRight.appendChild(when);

      const body = document.createElement('div');
      body.className = 'conversation-timeline-item-body';

      if (channel === 'AI SALES CALL') {
        body.classList.add('ai-sales-call-entry');
        const facts = document.createElement('div');
        facts.className = 'ai-sales-call-facts';
        const duration = Number(entry.duration_seconds || 0);
        const factValues = [
          ['Attempt', `#${Number(entry.attempt_number || 1)}`],
          ['Duration', duration > 0 ? `${Math.floor(duration / 60)}m ${duration % 60}s` : '—'],
          ['Result', entry.result || 'In progress']
        ];
        factValues.forEach(([label, value]) => {
          const fact = document.createElement('span');
          const strong = document.createElement('strong');
          strong.textContent = label;
          fact.append(strong, document.createTextNode(`: ${value}`));
          facts.appendChild(fact);
        });
        body.appendChild(facts);

        if (entry.recording_url) {
          const recording = document.createElement('a');
          recording.className = 'ai-sales-call-recording';
          recording.href = entry.recording_url;
          recording.target = '_blank';
          recording.rel = 'noopener noreferrer';
          recording.textContent = '▶ Play Recording';
          body.appendChild(recording);
        }
        if (entry.summary) {
          const summary = document.createElement('p');
          const strong = document.createElement('strong');
          strong.textContent = 'Summary: ';
          summary.append(strong, document.createTextNode(entry.summary));
          body.appendChild(summary);
        } else if (entry.body) {
          const summary = document.createElement('p');
          summary.textContent = entry.body;
          body.appendChild(summary);
        }
        if (entry.next_step) {
          const next = document.createElement('p');
          const strong = document.createElement('strong');
          strong.textContent = 'Next Step: ';
          next.append(strong, document.createTextNode(entry.next_step));
          body.appendChild(next);
        }
        if (entry.transcript) {
          const details = document.createElement('details');
          details.className = 'ai-sales-call-transcript';
          const summary = document.createElement('summary');
          summary.textContent = 'Transcript';
          const text = document.createElement('div');
          text.textContent = entry.transcript;
          details.append(summary, text);
          body.appendChild(details);
        }
      } else {
        body.textContent = entry.body || '';
      }

      if (entry.editable) {
        const actions = document.createElement('div');
        actions.className = 'conversation-note-actions';

        const edit = iconButton(
          'Edit note',
          'conversation-note-edit',
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 16.5V20h3.5L18.8 8.7l-3.5-3.5L4 16.5Zm16.7-10.6a1 1 0 0 0 0-1.4l-1.2-1.2a1 1 0 0 0-1.4 0l-1.8 1.8 3.5 3.5 1.9-1.8Z" fill="currentColor"/></svg>'
        );
        const trash = iconButton(
          'Delete note',
          'conversation-note-delete',
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 21a2 2 0 0 1-2-2V7h14v12a2 2 0 0 1-2 2H7Zm2-3h2V10H9v8Zm4 0h2V10h-2v8ZM4 4h5l1-1h4l1 1h5v2H4V4Z" fill="currentColor"/></svg>'
        );

        edit.addEventListener('click', () => {
          if (item.classList.contains('is-editing')) return;
          item.classList.add('is-editing');

          const input = document.createElement('textarea');
          input.className = 'conversation-timeline-edit-input';
          input.maxLength = 3000;
          input.value = entry.body || '';
          body.replaceChildren(input);
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);

          const cancelEdit = () => {
            item.classList.remove('is-editing');
            body.textContent = entry.body || '';
          };

          const saveEdit = async () => {
            const value = input.value.trim();
            if (!value) {
              window.alert('A saved note cannot be empty. Use the trash icon to delete it.');
              return;
            }
            edit.disabled = true;
            trash.disabled = true;
            input.disabled = true;
            try {
              await mutateNote('update', entry, context.csrfToken || '', value);
              if (entry.note_kind === 'legacy') context.onLegacyChanged?.(value);
              await load(
                context.timelineUrl || '',
                container,
                context.callAction,
                context.emailAction,
                context.options || {}
              );
            } catch (error) {
              input.disabled = false;
              edit.disabled = false;
              trash.disabled = false;
              window.alert(error.message || 'Note could not be updated.');
            }
          };

          input.addEventListener('keydown', (event) => {
            if (event.isComposing) return;
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              saveEdit();
            } else if (event.key === 'Escape') {
              event.preventDefault();
              cancelEdit();
            }
          });
        });

        trash.addEventListener('click', async () => {
          if (!window.confirm('Delete this note? This cannot be undone.')) return;
          edit.disabled = true;
          trash.disabled = true;
          try {
            await mutateNote('delete', entry, context.csrfToken || '');
            if (entry.note_kind === 'legacy') context.onLegacyChanged?.('');
            await load(
              context.timelineUrl || '',
              container,
              context.callAction,
              context.emailAction,
              context.options || {}
            );
          } catch (error) {
            edit.disabled = false;
            trash.disabled = false;
            window.alert(error.message || 'Note could not be deleted.');
          }
        });

        actions.append(edit, trash);
        headRight.appendChild(actions);
      }

      head.append(meta, headRight);
      item.append(head, body);
      container.appendChild(item);
    });
  };

  const load = async (url, container, callAction, emailAction, options = {}) => {
    if (!url || !container) return null;
    activeLoads.set(container, { url, callAction, emailAction, options });
    container.dataset.timelineUrl = url;
    container.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'conversation-timeline-empty';
    loading.textContent = 'Loading conversation history...';
    container.appendChild(loading);
    setAction(callAction, '');
    setAction(emailAction, '');

    try {
      const response = await fetch(url, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.message || 'Conversation history could not be loaded.');
      render(container, data.entries || [], {
        timelineUrl: url,
        callAction,
        emailAction,
        csrfToken: options.csrfToken || '',
        onLegacyChanged: options.onLegacyChanged,
        options
      });
      setAction(callAction, data.call_url || '');
      setAction(emailAction, data.email_url || '');
      return data;
    } catch (_error) {
      container.replaceChildren();
      const failed = document.createElement('div');
      failed.className = 'conversation-timeline-empty is-error';
      failed.textContent = 'Conversation history could not be loaded.';
      container.appendChild(failed);
      return null;
    }
  };

  const refresh = async (container) => {
    const state = container ? activeLoads.get(container) : null;
    if (!state) return null;
    return load(state.url, container, state.callAction, state.emailAction, state.options);
  };

  const saveManualNote = async (timelineUrl, body, csrfToken) => {
    const value = (body || '').trim();
    if (!value) throw new Error('Write a manual note first.');
    if (!timelineUrl) throw new Error('Communication record is unavailable.');

    const timeline = new URL(timelineUrl, window.location.origin);
    const payload = new URLSearchParams({
      csrf_token: csrfToken || '',
      body: value
    });
    ['prospect_id', 'inquiry_id', 'deal_id'].forEach((name) => {
      const id = timeline.searchParams.get(name);
      if (id) payload.set(name, id);
    });

    const response = await fetch('/app/communications/manual-note', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
      },
      body: payload.toString(),
      credentials: 'same-origin',
      cache: 'no-store'
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.message || 'Manual note could not be saved.');
    }
    return data;
  };

  return { load, refresh, saveManualNote };
})();

const RSFInlineEmail = (() => {
  const formatWhen = (raw) => {
    const date = raw ? new Date(raw) : null;
    return date && !Number.isNaN(date.getTime())
      ? new Intl.DateTimeFormat(undefined, {
          month: 'short', day: 'numeric', year: 'numeric',
          hour: 'numeric', minute: '2-digit'
        }).format(date)
      : (raw || '');
  };

  const renderThread = (panel, payload) => {
    const thread = panel.querySelector('[data-email-thread]');
    if (!thread) return;
    thread.replaceChildren();
    const messages = payload.messages || [];
    if (!messages.length) {
      const empty = document.createElement('div');
      empty.className = 'conversation-email-empty';
      empty.textContent = 'No emails yet. Write the first outreach email below.';
      thread.appendChild(empty);
      return;
    }
    messages.forEach((message) => {
      const item = document.createElement('article');
      item.className = `conversation-email-message ${message.direction === 'INBOUND' ? 'is-client' : 'is-rsf'}`;
      const head = document.createElement('div');
      head.className = 'conversation-email-message-head';
      const who = document.createElement('strong');
      who.textContent = message.direction === 'INBOUND' ? (payload.client_name || 'Client') : 'Realty Systems Foundry';
      const when = document.createElement('time');
      when.textContent = formatWhen(message.at);
      head.append(who, when);
      const subject = document.createElement('div');
      subject.className = 'conversation-email-message-subject';
      subject.textContent = message.subject || '';
      const body = document.createElement('div');
      body.className = 'conversation-email-message-body';
      body.textContent = message.body || '';
      item.append(head);
      if (message.subject) item.append(subject);
      item.append(body);
      if (message.attachments?.length) {
        const files = document.createElement('div');
        files.className = 'conversation-email-attachments';
        message.attachments.forEach((file) => {
          const link = document.createElement('a');
          link.href = file.url;
          link.textContent = file.name;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          files.appendChild(link);
        });
        item.append(files);
      }
      if (message.direction === 'OUTBOUND' && message.delivery_status) {
        const delivery = document.createElement('small');
        delivery.textContent = message.delivery_status;
        item.append(delivery);
      }
      thread.appendChild(item);
    });
    thread.scrollTop = thread.scrollHeight;
  };

  const load = async (action, focusComposer = false) => {
    if (!action || action.getAttribute('aria-disabled') === 'true' || !action.href || action.href.endsWith('#')) return null;
    const dialog = action.closest('dialog');
    const panel = dialog?.querySelector('[data-email-panel]');
    if (!dialog || !panel) return null;
    panel.hidden = false;
    dialog.classList.add('conversation-email-open');
    const status = panel.querySelector('[data-email-status]');
    if (status) status.textContent = 'Loading…';
    try {
      const response = await fetch(action.href, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.message || 'Email conversation could not be loaded.');
      panel.dataset.threadUrl = action.href;
      panel.dataset.conversationId = String(data.conversation_id || '');
      panel.dataset.sendUrl = data.send_url || '';
      const recipient = panel.querySelector('[data-email-recipient]');
      if (recipient) recipient.textContent = data.recipient || '';
      const subjectWrap = panel.querySelector('[data-email-subject-wrap]');
      const subject = panel.querySelector('[data-email-subject]');
      const body = panel.querySelector('[data-email-body]');
      const send = panel.querySelector('[data-email-send]');
      const hasMessages = Boolean(data.messages?.length);
      if (subjectWrap) subjectWrap.hidden = hasMessages;
      if (subject) {
        subject.value = data.subject || '';
        subject.disabled = hasMessages;
      }
      if (send) {
        send.textContent = hasMessages ? 'Send Reply' : 'Send Email';
        send.disabled = !data.send_ready;
      }
      renderThread(panel, data);
      if (status) status.textContent = data.send_ready ? '' : 'RSF Gmail is not connected yet.';
      if (body) body.disabled = !data.send_ready;
      if (subject) subject.disabled = hasMessages || !data.send_ready;
      if (focusComposer && data.send_ready) window.setTimeout(() => panel.querySelector('[data-email-body]')?.focus(), 0);
      return data;
    } catch (error) {
      if (status) status.textContent = error.message || 'Email conversation could not be loaded.';
      return null;
    }
  };

  const close = (panel) => {
    const dialog = panel?.closest('dialog');
    if (!dialog || !panel) return;
    panel.hidden = true;
    dialog.classList.remove('conversation-email-open');
  };

  document.addEventListener('click', (event) => {
    const action = event.target.closest?.('.conversation-action--email');
    if (action) {
      if (action.getAttribute('aria-disabled') === 'true') return;
      event.preventDefault();
      load(action, true);
      return;
    }
    const closeButton = event.target.closest?.('[data-email-panel-close]');
    if (closeButton) {
      event.preventDefault();
      close(closeButton.closest('[data-email-panel]'));
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target.closest?.('[data-email-form]');
    if (!form) return;
    event.preventDefault();
    const panel = form.closest('[data-email-panel]');
    const dialog = panel?.closest('dialog');
    const action = dialog?.querySelector('.conversation-action--email');
    const body = panel?.querySelector('[data-email-body]');
    const subject = panel?.querySelector('[data-email-subject]');
    const status = panel?.querySelector('[data-email-status]');
    const send = panel?.querySelector('[data-email-send]');
    const value = (body?.value || '').trim();
    if (!value) {
      if (status) status.textContent = 'Write an email first.';
      body?.focus();
      return;
    }
    const payload = new URLSearchParams({
      csrf_token: panel?.dataset.csrfToken || '',
      conversation_id: panel?.dataset.conversationId || '',
      subject: subject?.value || '',
      body: value
    });
    if (send) send.disabled = true;
    if (status) status.textContent = 'Sending…';
    try {
      const response = await fetch(panel?.dataset.sendUrl || '', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        credentials: 'same-origin',
        cache: 'no-store',
        body: payload.toString()
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.message || 'Email could not be sent.');
      if (body) body.value = '';
      if (status) status.textContent = 'Sent.';
      await load(action, false);
      const timeline = dialog?.querySelector('.conversation-timeline');
      if (timeline) await RSFConversationTimeline.refresh(timeline);
      hydrateEmailBadges();
    } catch (error) {
      if (status) status.textContent = error.message || 'Email could not be sent.';
    } finally {
      if (send) send.disabled = false;
    }
  });

  return { load, close };
})();

const hydrateEmailBadges = async () => {
  const buttons = [...document.querySelectorAll('[data-email-conversation-open][data-timeline-url]')];
  const cache = new Map();
  await Promise.all(buttons.map(async (button) => {
    const url = button.dataset.timelineUrl || '';
    if (!url) return;
    if (!cache.has(url)) {
      cache.set(url, fetch(url, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store'
      }).then((response) => response.json().then((data) => ({response, data}))).catch(() => null));
    }
    const result = await cache.get(url);
    const label = button.querySelector('[data-email-conversation-label]');
    if (!result || !result.response.ok || !result.data?.ok) {
      if (label) label.textContent = 'Unavailable';
      button.disabled = true;
      return;
    }
    const data = result.data;
    if (!data.email_url) {
      if (label) label.textContent = 'No email';
      button.disabled = true;
      return;
    }
    button.disabled = false;
    const unread = Number(data.email_unread || 0);
    if (label) label.textContent = unread > 0
      ? `${unread} New ${unread === 1 ? 'Reply' : 'Replies'}`
      : (Number(data.email_message_count || 0) > 0 ? 'Up to date' : 'Ready to email');
  }));
};

document.addEventListener('click', async (event) => {
  const field = event.target.closest?.('[data-email-conversation-open]');
  if (!field || field.disabled) return;
  event.preventDefault();
  const card = field.closest('[data-prospect-row],[data-deal-card],[data-website-inquiry-card]');
  const notesTrigger = card?.querySelector('[data-prospect-notes-expand],[data-deal-notes-expand],[data-website-notes-expand]');
  if (!notesTrigger) return;
  notesTrigger.click();
  for (let attempt = 0; attempt < 25; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 80));
    const dialog = document.querySelector('[data-prospect-notes-viewer][open],[data-deal-notes-viewer][open],[data-website-notes-viewer][open]');
    const emailAction = dialog?.querySelector('.conversation-action--email');
    if (emailAction && emailAction.getAttribute('aria-disabled') !== 'true') {
      emailAction.click();
      return;
    }
  }
});

document.addEventListener('click', async (event) => {
  const action = event.target.closest?.('[data-prospect-call-action]');
  if (!action || action.getAttribute('aria-disabled') === 'true' || !action.href || action.href.endsWith('#')) return;
  event.preventDefault();
  if (action.dataset.callStarting === '1') return;
  action.dataset.callStarting = '1';
  const label = action.querySelector('.conversation-action-label');
  const original = label?.textContent || 'AI Call';
  if (label) label.textContent = 'Starting…';
  try {
    const response = await fetch(action.href, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
      },
      body: new URLSearchParams({ csrf_token: action.dataset.csrfToken || '' }).toString(),
      credentials: 'same-origin',
      cache: 'no-store'
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.message || 'AI sales call could not start.');
    const timeline = action.closest('dialog')?.querySelector('.conversation-timeline');
    if (timeline) await RSFConversationTimeline.refresh(timeline);
  } catch (error) {
    window.alert(error.message || 'AI sales call could not start.');
  } finally {
    delete action.dataset.callStarting;
    if (label) label.textContent = original;
  }
});

window.setTimeout(hydrateEmailBadges, 0);

document.addEventListener('click', (event) => {
  const disabled = event.target.closest?.('.conversation-action-icon[aria-disabled="true"]');
  if (disabled) event.preventDefault();
});

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

  const accountSecurityShell = document.querySelector('.account-security-shell[data-password-vault-url]');
  if (accountSecurityShell) {
    const vaultUrl = accountSecurityShell.dataset.passwordVaultUrl;
    const vaultCsrf = accountSecurityShell.dataset.passwordVaultCsrf;
    const loadVaultPassword = async (button) => {
      const target = document.getElementById(button.dataset.target || '');
      if (!(target instanceof HTMLInputElement)) return null;
      if (target.dataset.loaded === '1') return target.value;
      const body = new URLSearchParams({csrf_token: vaultCsrf || '', user_id: button.dataset.userId || ''});
      const response = await fetch(vaultUrl, {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'}, body, credentials: 'same-origin'});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) { window.alert(payload.error || 'Current password could not be revealed.'); return null; }
      target.value = payload.password; target.dataset.loaded = '1'; return payload.password;
    };
    document.querySelectorAll('[data-vault-reveal]').forEach((button) => {
      button.addEventListener('click', async () => {
        const target = document.getElementById(button.dataset.target || '');
        if (!(target instanceof HTMLInputElement)) return;
        if (target.dataset.loaded !== '1' && await loadVaultPassword(button) === null) return;
        const reveal = target.type === 'password';
        target.type = reveal ? 'text' : 'password';
        button.textContent = reveal ? 'Hide' : 'Show';
      });
    });
    document.querySelectorAll('[data-vault-copy]').forEach((button) => {
      button.addEventListener('click', async () => {
        const target = document.getElementById(button.dataset.target || '');
        if (!(target instanceof HTMLInputElement)) return;
        let value = target.dataset.loaded === '1' ? target.value : await loadVaultPassword(button);
        if (!value) return;
        try { await navigator.clipboard.writeText(value); const original=button.textContent; button.textContent='Copied'; window.setTimeout(()=>{button.textContent=original;},1400); }
        catch (_error) { target.type='text'; target.focus(); target.select(); }
      });
    });
  }

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
      if (!target) return;
      const revealing = target.type === 'password';
      target.type = revealing ? 'text' : 'password';
      button.textContent = revealing ? 'Hide' : 'Show';
      target.focus();
    });
  });

  const copyValue = async (value, button) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch (_error) {
      const area = document.createElement('textarea');
      area.value = value;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    const previous = button.textContent;
    button.textContent = 'Copied';
    window.setTimeout(() => { button.textContent = previous; }, 1400);
  };

  document.querySelectorAll('[data-copy-input]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.target);
      if (target) copyValue(target.value, button);
    });
  });

  document.querySelectorAll('[data-copy-text]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.target);
      if (target) copyValue(target.textContent || '', button);
    });
  });

  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (target) copyValue(target.value || target.textContent || '', button);
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

  scrollMessages();
  window.setTimeout(pollGlobal, 150);
  window.setTimeout(pollThread, 250);
  window.setInterval(pollGlobal, 2000);
  window.setInterval(pollThread, 2000);
  window.setInterval(pollCall, 1200);
})();


(() => {
  document.addEventListener('click', (event) => {
    const toggle = event.target.closest?.('[data-master-deal-toggle]');
    if (!toggle) return;

    const targetId = toggle.getAttribute('aria-controls') || '';
    const body = targetId ? document.getElementById(targetId) : null;
    if (!body) return;

    const opening = body.hidden;
    body.hidden = !opening;
    toggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
    toggle.setAttribute('aria-label', opening ? 'Hide Deal Information' : 'Show Deal Information');
  });
})();

(() => {
  const page = document.querySelector('.prospects-page');
  if (!page) return;

  const trigger = page.querySelector('[data-prospect-add-trigger]');
  const list = page.querySelector('[data-prospect-list]');
  const quick = page.querySelector('[data-prospect-quick-add]');
  const quickForm = page.querySelector('[data-prospect-quick-form]');
  const primaryInput = page.querySelector('[data-prospect-primary-input]');
  const companyInput = page.querySelector('[data-prospect-company-input]');
  const quickMessage = page.querySelector('[data-prospect-quick-message]');
  const toast = page.querySelector('[data-prospect-toast]');
  let toastTimer = null;

  const openTargetProspect = () => {
    if (!window.location.hash) return;
    const target = document.querySelector(window.location.hash);
    if (!target || !target.matches('[data-prospect-row]')) return;
    const details = target.tagName === 'DETAILS' ? target : target.querySelector('details.prospect-card');
    if (details) details.open = true;
  };
  openTargetProspect();
  window.addEventListener('hashchange', openTargetProspect);

  const showToast = (message, isError = false) => {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.toggle('is-error', isError);
    toast.hidden = false;
    toastTimer = window.setTimeout(() => {
      toast.hidden = true;
      toast.classList.remove('is-error');
    }, 1800);
  };

  const hideQuickMessage = () => {
    if (!quickMessage) return;
    quickMessage.hidden = true;
    quickMessage.textContent = '';
  };

  const showQuickMessage = (message) => {
    if (!quickMessage) return;
    quickMessage.textContent = message;
    quickMessage.hidden = false;
  };

  const showDuplicate = (data) => {
    if (!quickMessage) return;
    const duplicate = data.duplicate || {};
    quickMessage.textContent = '';
    const strong = document.createElement('strong');
    strong.textContent = data.message || 'Prospect already exists.';
    quickMessage.appendChild(strong);

    const duplicateDate = duplicate.recorded_date || duplicate.received_date || '';
    if (duplicateDate) {
      const date = new Date(`${duplicateDate}T00:00:00`);
      const readable = Number.isNaN(date.getTime()) ? duplicateDate : new Intl.DateTimeFormat(undefined, { month: 'long', day: 'numeric', year: 'numeric' }).format(date);
      const detail = document.createElement('span');
      detail.textContent = duplicate.source === 'website' ? `Received on ${readable}.` : `Recorded on ${readable}.`;
      quickMessage.appendChild(detail);
    }

    if (duplicate.view_url) {
      const link = document.createElement('a');
      link.href = duplicate.view_url;
      link.textContent = duplicate.source === 'website' ? 'View Website Inquiry' : 'View Prospect';
      quickMessage.appendChild(link);
    }
    quickMessage.hidden = false;
  };

  const ensureEmpty = () => {
    if (!list || list.querySelector('[data-prospect-row]') || list.querySelector('[data-prospect-empty]')) return;
    const empty = document.createElement('div');
    empty.className = 'workspace-empty-state';
    empty.dataset.prospectEmpty = '';
    empty.setAttribute('role', 'status');
    empty.innerHTML = `
      <strong>No prospects yet.</strong>
      <span>Researched Prospects you add will appear here.</span>
    `;
    list.appendChild(empty);
  };

  const closeQuick = () => {
    if (!quick) return;
    quick.hidden = true;
    hideQuickMessage();
  };

  const openQuick = () => {
    if (!quick || !primaryInput) return;
    quick.hidden = false;
    hideQuickMessage();
    window.setTimeout(() => primaryInput.focus(), 0);
  };

  let quickTogglePointerActive = false;

  if (trigger) {
    trigger.addEventListener('pointerdown', () => {
      quickTogglePointerActive = Boolean(quick && !quick.hidden);
    });
    trigger.addEventListener('pointercancel', () => {
      quickTogglePointerActive = false;
    });
    trigger.addEventListener('click', () => {
      if (!quick) {
        quickTogglePointerActive = false;
        window.location.assign('/app/prospects?add=1');
        return;
      }
      if (quickTogglePointerActive) {
        closeQuick();
      } else if (quick.hidden) {
        openQuick();
      } else {
        closeQuick();
      }
      quickTogglePointerActive = false;
    });
  }

  if (quick && quickForm && primaryInput && companyInput && list) {
    const params = new URLSearchParams(window.location.search);
    if (params.get('add') === '1') {
      openQuick();
      params.delete('add');
      const clean = new URL(window.location.href);
      clean.search = params.toString();
      window.history.replaceState({}, '', clean.pathname + (clean.search ? `?${clean.search}` : '') + clean.hash);
    }

    const editableFields = Array.from(quickForm.querySelectorAll('input:not([type="hidden"]), textarea, select'));
    const autoGrowFields = Array.from(quickForm.querySelectorAll('[data-prospect-autogrow]'));
    const resizeQuickTextarea = (field) => {
      if (!field) return;
      field.style.height = '48px';
      field.style.height = `${Math.max(48, field.scrollHeight)}px`;
    };
    autoGrowFields.forEach((field) => {
      resizeQuickTextarea(field);
      field.addEventListener('input', () => resizeQuickTextarea(field));
    });
    window.addEventListener('resize', () => {
      if (!quick.hidden) autoGrowFields.forEach(resizeQuickTextarea);
    });
    let saving = false;
    const hasEnteredData = () => editableFields.some((field) => field.name !== 'status' && field.value.trim() !== '');
    const setDisabled = (disabled) => editableFields.forEach((field) => { field.disabled = disabled; });

    const saveQuick = async () => {
      if (saving || quick.hidden) return;
      const company = companyInput.value.trim().replace(/\s+/g, ' ');

      if (!company) {
        if (!hasEnteredData()) {
          quickForm.reset();
          autoGrowFields.forEach(resizeQuickTextarea);
          closeQuick();
          return;
        }
        showQuickMessage('Company is required.');
        companyInput.focus();
        return;
      }

      companyInput.value = company;
      const body = new URLSearchParams();
      for (const [key, value] of new FormData(quickForm).entries()) body.append(key, String(value));

      saving = true;
      setDisabled(true);
      hideQuickMessage();

      try {
        const response = await fetch(quickForm.action, {
          method: 'POST',
          headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: body.toString(),
          credentials: 'same-origin',
          keepalive: true
        });
        const data = await response.json().catch(() => ({}));

        if (response.ok && data.ok) {
          list.querySelector('[data-prospect-empty]')?.remove();
          quick.insertAdjacentHTML('afterend', data.row_html || '');
          quickForm.reset();
          autoGrowFields.forEach(resizeQuickTextarea);
          closeQuick();
          showToast(data.message || 'Prospect saved.');
          return;
        }

        if (response.status === 409 && (data.error === 'duplicate' || data.error === 'website_duplicate')) {
          showDuplicate(data);
          return;
        }
        showQuickMessage(data.message || 'Prospect could not be saved.');
      } catch (_error) {
        showQuickMessage('Prospect could not be saved. Try again.');
      } finally {
        saving = false;
        setDisabled(false);
        if (!quick.hidden && !quick.contains(document.activeElement)) primaryInput.focus();
      }
    };

    quickForm.addEventListener('submit', (event) => {
      event.preventDefault();
      saveQuick();
    });
    quickForm.addEventListener('input', hideQuickMessage);
    quickForm.addEventListener('change', hideQuickMessage);
    quick.addEventListener('focusout', (event) => {
      const movingToToggle = Boolean(
        trigger
        && (event.relatedTarget === trigger || trigger.contains(event.relatedTarget))
      );
      if (movingToToggle || quickTogglePointerActive) return;
      window.setTimeout(() => {
        if (!saving && !quick.hidden && !quick.contains(document.activeElement)) saveQuick();
      }, 0);
    });
  }

  const csrfForRow = (row) => (
    row.querySelector('input[name="csrf_token"]')?.value
    || quickForm?.querySelector('input[name="csrf_token"]')?.value
    || ''
  );

  const replaceProspectRow = (row, html, keepOpen) => {
    if (!html) return row;
    const template = document.createElement('template');
    template.innerHTML = html.trim();
    const replacement = template.content.firstElementChild;
    if (!replacement) return row;
    row.replaceWith(replacement);
    const details = replacement.querySelector('details.prospect-card');
    if (details && keepOpen) details.open = true;
    return replacement;
  };

  const prospectNotesViewer = page.querySelector('[data-prospect-notes-viewer]');
  const prospectNotesViewerInput = page.querySelector('[data-prospect-notes-viewer-input]');
  const prospectNotesViewerClose = page.querySelector('[data-prospect-notes-viewer-close]');
  const prospectNotesSave = page.querySelector('[data-prospect-notes-save]');
  const prospectConversationTimeline = page.querySelector('[data-prospect-conversation-timeline]');
  const prospectCallAction = page.querySelector('[data-prospect-call-action]');
  const prospectEmailAction = page.querySelector('[data-prospect-email-action]');
  let prospectNotesSource = null;
  let prospectNotesTimelineUrl = '';

  const saveProspectNotes = async (source) => {
    if (!(source instanceof HTMLTextAreaElement)) return;
    const row = source.closest('[data-prospect-row]');
    if (!row) return;

    if (source.dataset.prospectNotesSaving === '1') {
      source.dataset.prospectNotesPending = '1';
      return;
    }

    const previous = source.dataset.prospectNotesStartValue ?? source.value;
    if (source.value === previous) return;

    source.dataset.prospectNotesSaving = '1';
    try {
      do {
        delete source.dataset.prospectNotesPending;
        const valueToSave = source.value;
        const body = new URLSearchParams({
          csrf_token: csrfForRow(row),
          field: 'notes_after_conversation',
          value: valueToSave
        });

        const response = await fetch(row.dataset.prospectUpdateUrl, {
          method: 'POST',
          headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: body.toString(),
          credentials: 'same-origin',
          keepalive: true
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(data.message || 'Notes After Conversation could not be updated.');
        }

        source.dataset.prospectNotesStartValue = valueToSave;
        const linkedDealNotes = row.querySelector('[data-deal-notes-compact]');
        if (linkedDealNotes instanceof HTMLTextAreaElement) {
          linkedDealNotes.value = valueToSave;
          linkedDealNotes.dataset.dealStartValue = valueToSave;
        }
        if (source.value !== valueToSave) source.dataset.prospectNotesPending = '1';
      } while (source.dataset.prospectNotesPending === '1');
    } catch (error) {
      showToast(error.message || 'Notes After Conversation could not be updated. Try again.', true);
    } finally {
      delete source.dataset.prospectNotesSaving;
      delete source.dataset.prospectNotesPending;
    }
  };

  const closeProspectNotesViewer = () => {
    if (prospectNotesViewer?.open) prospectNotesViewer.close();
    prospectNotesSource = null;
    prospectNotesTimelineUrl = '';
    if (prospectNotesViewerInput) prospectNotesViewerInput.value = '';
  };

  page.addEventListener('focusin', (event) => {
    const source = event.target.closest?.('[data-prospect-notes-compact]');
    if (!source) return;
    source.dataset.prospectNotesStartValue = source.value || '';
  });

  page.addEventListener('focusout', (event) => {
    const source = event.target.closest?.('[data-prospect-notes-compact]');
    if (!source) return;
    saveProspectNotes(source);
  });

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-prospect-notes-expand]');
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();

    const notesWrap = trigger.closest('.deal-notes-compact');
    const source = notesWrap?.querySelector('[data-prospect-notes-compact]');
    if (!source) return;

    prospectNotesSource = source;
    source.dataset.prospectNotesStartValue ??= source.value || '';
    prospectNotesTimelineUrl = trigger.dataset.timelineUrl || '';
    if (prospectNotesViewerInput) prospectNotesViewerInput.value = '';
    const prospectNotesRow = prospectNotesSource.closest('[data-prospect-row]');
    const prospectTimelineOptions = {
      csrfToken: csrfForRow(prospectNotesRow),
      onLegacyChanged: (value) => {
        if (!prospectNotesSource) return;
        prospectNotesSource.value = value;
        prospectNotesSource.dataset.prospectNotesStartValue = value;
        const row = prospectNotesSource.closest('[data-prospect-row]');
        const linkedDealNotes = row?.querySelector('[data-deal-notes-compact]');
        if (linkedDealNotes instanceof HTMLTextAreaElement) {
          linkedDealNotes.value = value;
          linkedDealNotes.dataset.dealStartValue = value;
        }
      }
    };
    RSFConversationTimeline.load(
      prospectNotesTimelineUrl,
      prospectConversationTimeline,
      prospectCallAction,
      prospectEmailAction,
      prospectTimelineOptions
    );

    if (prospectNotesViewer && typeof prospectNotesViewer.showModal === 'function') {
      prospectNotesViewer.showModal();
      window.setTimeout(() => prospectNotesViewerInput?.focus(), 0);
      return;
    }

    source.focus();
  });

  prospectNotesSave?.addEventListener('click', async () => {
    if (!prospectNotesViewerInput || !prospectNotesSource) return;
    prospectNotesSave.disabled = true;
    try {
      const row = prospectNotesSource.closest('[data-prospect-row]');
      await RSFConversationTimeline.saveManualNote(
        prospectNotesTimelineUrl,
        prospectNotesViewerInput.value,
        csrfForRow(row)
      );
      prospectNotesViewerInput.value = '';
      await RSFConversationTimeline.load(
        prospectNotesTimelineUrl,
        prospectConversationTimeline,
        prospectCallAction,
        prospectEmailAction,
        {
          csrfToken: csrfForRow(row),
          onLegacyChanged: (value) => {
            if (!prospectNotesSource) return;
            prospectNotesSource.value = value;
            prospectNotesSource.dataset.prospectNotesStartValue = value;
          }
        }
      );
      showToast('Manual note saved.');
      prospectNotesViewerInput.focus();
    } catch (error) {
      showToast(error.message || 'Manual note could not be saved.', true);
    } finally {
      prospectNotesSave.disabled = false;
    }
  });
  prospectNotesViewerInput?.addEventListener('keydown', (event) => {
    if (event.isComposing) return;
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      prospectNotesSave?.click();
    }
  });
  prospectNotesViewerClose?.addEventListener('click', closeProspectNotesViewer);
  prospectNotesViewer?.addEventListener('cancel', () => {
    prospectNotesSource = null;
    prospectNotesTimelineUrl = '';
    if (prospectNotesViewerInput) prospectNotesViewerInput.value = '';
  });
  prospectNotesViewer?.addEventListener('click', (event) => {
    if (event.target === prospectNotesViewer) closeProspectNotesViewer();
  });

  const prospectLongTextViewer = page.querySelector('[data-prospect-longtext-viewer]');
  const prospectLongTextViewerTitle = page.querySelector('[data-prospect-longtext-viewer-title]');
  const prospectLongTextViewerInput = page.querySelector('[data-prospect-longtext-viewer-input]');
  const prospectLongTextViewerClose = page.querySelector('[data-prospect-longtext-viewer-close]');
  let prospectLongTextField = null;
  let prospectLongTextStartValue = '';
  let prospectLongTextSavePromise = null;

  const saveProspectLongText = async () => {
    if (!prospectLongTextField || !prospectLongTextViewerInput) return true;
    if (prospectLongTextSavePromise) return prospectLongTextSavePromise;

    const row = prospectLongTextField.closest('[data-prospect-row]');
    if (!row) return false;

    const fieldName = prospectLongTextField.dataset.prospectField || '';
    if (fieldName !== 'problem' && fieldName !== 'system_wanted') return false;

    const value = prospectLongTextViewerInput.value.trim().slice(0, 2000);
    if (value === prospectLongTextStartValue) return true;

    prospectLongTextSavePromise = (async () => {
      const body = new URLSearchParams({
        csrf_token: csrfForRow(row),
        field: fieldName,
        value
      });

      try {
        const response = await fetch(row.dataset.prospectUpdateUrl, {
          method: 'POST',
          headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: body.toString(),
          credentials: 'same-origin'
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          showToast(data.message || 'Prospect field could not be updated.', true);
          return false;
        }

        prospectLongTextField.dataset.prospectValue = value;
        const preview = prospectLongTextField.querySelector('.prospect-longtext-preview');
        if (preview) preview.textContent = value || '—';
        prospectLongTextStartValue = value;
        showToast(data.message || 'Prospect updated.');
        return true;
      } catch (_error) {
        showToast('Prospect field could not be updated. Try again.', true);
        return false;
      } finally {
        prospectLongTextSavePromise = null;
      }
    })();

    return prospectLongTextSavePromise;
  };

  const closeProspectLongTextViewer = async () => {
    const saved = await saveProspectLongText();
    if (!saved) return;
    if (prospectLongTextViewer?.open) prospectLongTextViewer.close();
    prospectLongTextField = null;
    prospectLongTextStartValue = '';
  };

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-prospect-longtext-expand]');
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();

    const field = trigger.closest('[data-prospect-edit-field]');
    if (!field || !prospectLongTextViewerInput) return;

    prospectLongTextField = field;
    prospectLongTextStartValue = field.dataset.prospectValue || '';
    prospectLongTextViewerInput.value = prospectLongTextStartValue;
    if (prospectLongTextViewerTitle) {
      prospectLongTextViewerTitle.textContent = trigger.dataset.prospectLongtextLabel
        || (field.dataset.prospectField === 'problem' ? 'Problem' : 'System They Want');
    }

    if (prospectLongTextViewer && typeof prospectLongTextViewer.showModal === 'function') {
      prospectLongTextViewer.showModal();
      window.setTimeout(() => prospectLongTextViewerInput.focus(), 0);
      return;
    }

    prospectLongTextViewerInput.focus();
  });

  prospectLongTextViewerInput?.addEventListener('blur', () => {
    saveProspectLongText();
  });
  prospectLongTextViewerClose?.addEventListener('click', () => {
    closeProspectLongTextViewer();
  });
  prospectLongTextViewer?.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeProspectLongTextViewer();
  });
  prospectLongTextViewer?.addEventListener('click', (event) => {
    if (event.target === prospectLongTextViewer) closeProspectLongTextViewer();
  });

  const statusOptions = [
    ['NOT_CONTACTED', 'Not Contacted'],
    ['NO_ANSWER', 'No Answer'],
    ['REJECTED', 'Rejected'],
    ['DEAL', 'Deal'],
    ['DEMO', 'Demo'],
    ['PROPOSAL', 'Proposal'],
    ['DECISION', 'Decision'],
    ['WON', 'Won'],
    ['LOST', 'Lost']
  ];
  const prospectDealStatuses = new Set(['DEAL', 'DEMO', 'PROPOSAL', 'DECISION', 'WON', 'LOST']);
  const prospectPreDealStatuses = new Set(['NOT_CONTACTED', 'NO_ANSWER', 'REJECTED']);
  const prospectStatusLabels = new Map(statusOptions);
  const prospectStatusConfirm = page.querySelector('[data-prospect-status-confirm]');
  const prospectStatusConfirmMessage = page.querySelector('[data-prospect-status-confirm-message]');
  const prospectStatusConfirmYes = page.querySelector('[data-prospect-status-confirm-yes]');
  const prospectStatusConfirmNo = page.querySelector('[data-prospect-status-confirm-no]');
  let pendingProspectStatusDecision = null;

  const settleProspectStatusDecision = (confirmed) => {
    const pending = pendingProspectStatusDecision;
    pendingProspectStatusDecision = null;
    if (prospectStatusConfirm?.open) prospectStatusConfirm.close();
    if (!pending) return;
    if (confirmed) pending.onYes();
    else pending.onNo();
  };

  const requestProspectStatusDecision = (targetStatus, onYes, onNo) => {
    const label = prospectStatusLabels.get(targetStatus) || targetStatus;
    const text = `Are you sure you want to change this Prospect to ${label}? This will remove its linked Deal from the Deals page. Your linked Deal details will stay preserved.`;
    if (prospectStatusConfirmMessage) prospectStatusConfirmMessage.textContent = text;
    pendingProspectStatusDecision = {onYes, onNo};

    if (prospectStatusConfirm && typeof prospectStatusConfirm.showModal === 'function') {
      prospectStatusConfirm.showModal();
      return;
    }

    settleProspectStatusDecision(window.confirm(text));
  };

  prospectStatusConfirmYes?.addEventListener('click', () => settleProspectStatusDecision(true));
  prospectStatusConfirmNo?.addEventListener('click', () => settleProspectStatusDecision(false));
  prospectStatusConfirm?.addEventListener('cancel', (event) => {
    event.preventDefault();
    settleProspectStatusDecision(false);
  });

  const beginProspectEdit = (field) => {
    if (!field || field.dataset.prospectEditing === '1') return;
    const row = field.closest('[data-prospect-row]');
    const display = field.querySelector('[data-prospect-edit-trigger]');
    if (!row || !display) return;

    const fieldName = field.dataset.prospectField || '';
    const editorType = field.dataset.prospectEditor || 'text';
    const originalValue = field.dataset.prospectValue || '';
    let editor;

    if (editorType === 'textarea') {
      editor = document.createElement('textarea');
      editor.rows = 3;
    } else if (editorType === 'status') {
      editor = document.createElement('select');
      statusOptions.forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        editor.appendChild(option);
      });
    } else {
      editor = document.createElement('input');
      editor.type = editorType === 'url' ? 'url' : editorType === 'email' ? 'email' : editorType === 'tel' ? 'tel' : editorType === 'date' ? 'date' : 'text';
    }

    editor.className = 'prospect-inline-editor';
    editor.dataset.prospectEditorActive = '';
    const uppercaseIdentityField = fieldName === 'contact' || fieldName === 'location';
    if (uppercaseIdentityField) editor.classList.add('prospect-uppercase-editor');
    editor.value = uppercaseIdentityField ? originalValue.toUpperCase() : originalValue;
    if (uppercaseIdentityField) {
      editor.addEventListener('input', () => {
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        editor.value = editor.value.toUpperCase();
        if (start !== null && end !== null) editor.setSelectionRange(start, end);
      });
    }
    field.dataset.prospectEditing = '1';
    display.hidden = true;
    field.appendChild(editor);

    let finished = false;
    const restore = () => {
      editor.remove();
      display.hidden = false;
      delete field.dataset.prospectEditing;
    };

    const save = async () => {
      if (finished || field.dataset.prospectStatusConfirming === '1') return;
      const newValue = editor.value;
      if (newValue === originalValue) {
        finished = true;
        restore();
        return;
      }

      const leavingDealPipeline = editorType === 'status'
        && prospectDealStatuses.has(originalValue)
        && prospectPreDealStatuses.has(newValue);

      if (leavingDealPipeline && field.dataset.prospectStatusConfirmed !== '1') {
        field.dataset.prospectStatusConfirming = '1';
        requestProspectStatusDecision(
          newValue,
          () => {
            delete field.dataset.prospectStatusConfirming;
            field.dataset.prospectStatusConfirmed = '1';
            save();
          },
          () => {
            delete field.dataset.prospectStatusConfirming;
            cancel();
          }
        );
        return;
      }

      finished = true;
      editor.disabled = true;
      field.classList.add('is-saving');
      const body = new URLSearchParams({
        csrf_token: csrfForRow(row),
        field: fieldName,
        value: newValue
      });
      if (field.dataset.prospectStatusConfirmed === '1') body.set('confirm_leave_deals', 'yes');

      try {
        const response = await fetch(row.dataset.prospectUpdateUrl, {
          method: 'POST',
          headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: body.toString(),
          credentials: 'same-origin'
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok || !data.ok) {
          restore();
          field.classList.remove('is-saving');
          let message = data.message || 'Prospect could not be updated.';
          if (data.error === 'duplicate' && data.duplicate?.recorded_date) {
            const dateValue = new Date(`${data.duplicate.recorded_date}T00:00:00`);
            const readable = Number.isNaN(dateValue.getTime())
              ? data.duplicate.recorded_date
              : new Intl.DateTimeFormat(undefined, { month: 'long', day: 'numeric', year: 'numeric' }).format(dateValue);
            message += ` Recorded on ${readable}.`;
          }
          showToast(message, true);
          return;
        }

        const keepOpen = Boolean(row.querySelector('details.prospect-card')?.open);
        replaceProspectRow(row, data.row_html, keepOpen);
        showToast(data.message || 'Prospect updated.');
      } catch (_error) {
        restore();
        field.classList.remove('is-saving');
        showToast('Prospect could not be updated. Try again.', true);
      }
    };

    const cancel = () => {
      if (finished) return;
      finished = true;
      restore();
    };

    editor.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        cancel();
        return;
      }
      if (event.key === 'Enter' && editor.tagName !== 'TEXTAREA') {
        event.preventDefault();
        save();
      }
    });
    editor.addEventListener('blur', save);
    if (editorType === 'status' || editorType === 'date') {
      editor.addEventListener('change', save);
    }

    if (editorType === 'status') {
      editor.focus({ preventScroll: true });
      try {
        if (typeof editor.showPicker === 'function') {
          editor.showPicker();
        } else {
          editor.click();
        }
      } catch (_error) {
        editor.focus({ preventScroll: true });
      }
    } else {
      window.setTimeout(() => {
        editor.focus();
        if (editor.select && editorType !== 'date') editor.select();
      }, 0);
    }
  };

  page.querySelectorAll('.prospect-uppercase-input').forEach((field) => {
    field.addEventListener('input', () => {
      const start = field.selectionStart;
      const end = field.selectionEnd;
      field.value = field.value.toUpperCase();
      if (start !== null && end !== null) field.setSelectionRange(start, end);
    });
  });

  const normalizeProspectLink = (rawValue) => {
    const value = String(rawValue || '').trim();
    if (!value) return '';
    const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`;
    try {
      const url = new URL(withScheme);
      if (url.protocol !== 'http:' && url.protocol !== 'https:') return '';
      return url.href;
    } catch (_error) {
      return '';
    }
  };

  const prospectFieldValue = (row, fieldName, useDisplay = false) => {
    const field = row.querySelector(`[data-prospect-edit-field][data-prospect-field="${fieldName}"]`);
    if (!field) return '';
    const activeEditor = field.querySelector('[data-prospect-editor-active]');
    if (activeEditor) return String(activeEditor.value || '').trim();
    if (useDisplay) {
      const display = field.querySelector('[data-prospect-edit-trigger]');
      if (display) return String(display.textContent || '').trim();
    }
    return String(field.dataset.prospectValue || '').trim();
  };

  const writeProspectClipboard = async (value) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const fallback = document.createElement('textarea');
    fallback.value = value;
    fallback.setAttribute('readonly', '');
    fallback.style.position = 'fixed';
    fallback.style.opacity = '0';
    document.body.appendChild(fallback);
    fallback.select();
    const copied = document.execCommand('copy');
    fallback.remove();
    if (!copied) throw new Error('Clipboard unavailable');
  };

  page.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-prospect-open-link]');
    if (!openButton) return;
    event.preventDefault();
    event.stopPropagation();
    if (openButton.disabled) return;

    const field = openButton.closest('[data-prospect-edit-field]');
    const href = normalizeProspectLink(field?.dataset.prospectValue || '');
    if (!href) {
      showToast('This link is not valid yet.', true);
      return;
    }
    window.open(href, '_blank', 'noopener,noreferrer');
  });

  page.addEventListener('click', async (event) => {
    const copyButton = event.target.closest('[data-prospect-copy]');
    if (!copyButton) return;
    event.preventDefault();
    event.stopPropagation();

    const row = copyButton.closest('[data-prospect-row]');
    if (!row) return;

    const notes = String(row.querySelector('[data-prospect-notes-compact]')?.value || '').trim();
    const attempt = String(row.querySelector('[data-prospect-attempt-control]')?.dataset.prospectAttemptValue || '0').trim();

    const emptyAsDash = (value) => value || '—';
    const copyText = [
      `Business Type: ${emptyAsDash(prospectFieldValue(row, 'business_type'))}`,
      `Status: ${emptyAsDash(prospectFieldValue(row, 'status', true))}`,
      `Budget: ${emptyAsDash(prospectFieldValue(row, 'budget'))}`,
      `Post Date: ${emptyAsDash(prospectFieldValue(row, 'post_date', true))}`,
      `Platform They Want: ${emptyAsDash(prospectFieldValue(row, 'platform_wanted'))}`,
      '',
      'Problem:',
      emptyAsDash(prospectFieldValue(row, 'problem')),
      '',
      'System They Want:',
      emptyAsDash(prospectFieldValue(row, 'system_wanted')),
      '',
      'Notes After Conversation:',
      emptyAsDash(notes),
      '',
      `Post Link: ${emptyAsDash(prospectFieldValue(row, 'post_link'))}`,
      `Website: ${emptyAsDash(prospectFieldValue(row, 'website'))}`,
      `Location: ${emptyAsDash(prospectFieldValue(row, 'location'))}`,
      `Company: ${emptyAsDash(prospectFieldValue(row, 'company'))}`,
      `Client Name: ${emptyAsDash(prospectFieldValue(row, 'contact'))}`,
      `Email: ${emptyAsDash(prospectFieldValue(row, 'email'))}`,
      `Phone: ${emptyAsDash(prospectFieldValue(row, 'phone'))}`,
      `Contact Attempt: ${attempt || '0'}`
    ].join('\n');

    try {
      await writeProspectClipboard(copyText);
      showToast('Prospect copied to clipboard.');
    } catch (_error) {
      showToast('Prospect could not be copied. Try again.', true);
    }
  });

  page.addEventListener('click', (event) => {
    const triggerEdit = event.target.closest('[data-prospect-edit-trigger]');
    if (!triggerEdit) return;
    event.preventDefault();
    event.stopPropagation();
    beginProspectEdit(triggerEdit.closest('[data-prospect-edit-field]'));
  });

  page.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-prospect-attempt-delta]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();

    const row = button.closest('[data-prospect-row]');
    const control = button.closest('[data-prospect-attempt-control]');
    if (!row || !control || control.dataset.prospectAttemptSaving === '1') return;

    const delta = Number(button.dataset.prospectAttemptDelta || 0);
    if (delta !== -1 && delta !== 1) return;
    control.dataset.prospectAttemptSaving = '1';
    const buttons = Array.from(control.querySelectorAll('[data-prospect-attempt-delta]'));
    buttons.forEach((item) => { item.disabled = true; });

    const body = new URLSearchParams({
      csrf_token: csrfForRow(row),
      delta: String(delta)
    });

    try {
      const response = await fetch(row.dataset.prospectAttemptUrl, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: body.toString(),
        credentials: 'same-origin'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        showToast(data.message || 'Contact Attempt could not be updated.', true);
        return;
      }
      const value = Math.max(0, Number(data.value || 0));
      control.dataset.prospectAttemptValue = String(value);
      const number = control.querySelector('[data-prospect-attempt-number]');
      if (number) number.textContent = String(value);
    } catch (_error) {
      showToast('Contact Attempt could not be updated. Try again.', true);
    } finally {
      delete control.dataset.prospectAttemptSaving;
      buttons.forEach((item) => {
        const itemDelta = Number(item.dataset.prospectAttemptDelta || 0);
        item.disabled = itemDelta < 0 && Number(control.dataset.prospectAttemptValue || 0) <= 0;
      });
    }
  });

  page.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-prospect-delete-form]');
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector('.prospect-delete-button');
    if (button) button.disabled = true;

    const body = new URLSearchParams();
    for (const [key, value] of new FormData(form).entries()) body.append(key, String(value));

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: body.toString(),
        credentials: 'same-origin'
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok || !data.ok) {
        if (button) button.disabled = false;
        showToast(data.message || 'Prospect could not be deleted.', true);
        return;
      }

      form.closest('[data-prospect-row]')?.remove();
      ensureEmpty();
        showToast(data.message || 'Prospect deleted.');
    } catch (_error) {
      if (button) button.disabled = false;
      showToast('Prospect could not be deleted. Try again.', true);
    }
  });
})();;


(() => {
  const page = document.querySelector('.deals-page, .prospects-page, [data-website-inbox-page]');
  if (!page || !page.querySelector('[data-deal-form]')) return;

  const list = page.querySelector('.deals-list');
  const filterButtons = Array.from(page.querySelectorAll('[data-deal-filter]'));
  const filterEmpty = page.querySelector('[data-deal-filter-empty]');
  let activeDealFilter = 'ALL';

  const applyDealFilter = () => {
    if (!list || !filterButtons.length) return;
    const cards = Array.from(list.querySelectorAll('[data-deal-card]'));
    cards.forEach((card) => {
      card.hidden = activeDealFilter !== 'ALL' && card.dataset.dealStatus !== activeDealFilter;
    });
    filterButtons.forEach((button) => {
      const active = button.dataset.dealFilter === activeDealFilter;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    if (filterEmpty) {
      const hasVisibleCards = cards.some((card) => !card.hidden);
      filterEmpty.hidden = cards.length === 0 || activeDealFilter === 'ALL' || hasVisibleCards;
    }
  };

  if (filterButtons.length && list) {
    filterButtons.forEach((button) => {
      button.addEventListener('click', () => {
        activeDealFilter = button.dataset.dealFilter || 'ALL';
        applyDealFilter();
      });
    });
    applyDealFilter();
  }

  page.addEventListener('click', (event) => {
    const sourceToggle = event.target.closest('[data-deal-source-toggle]');
    if (sourceToggle) {
      const targetId = sourceToggle.getAttribute('aria-controls') || '';
      const sourceBody = targetId ? document.getElementById(targetId) : null;
      if (!sourceBody) return;
      const opening = sourceBody.hidden;
      sourceBody.hidden = !opening;
      sourceToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      const sectionName = sourceToggle.closest('.deal-source-research')
        ? 'Outbound Details'
        : 'Inbound Details';
      sourceToggle.setAttribute('aria-label', opening ? `Hide ${sectionName}` : `Show ${sectionName}`);
      return;
    }

    const documentsToggle = event.target.closest('[data-deal-documents-toggle]');
    if (documentsToggle) {
      const targetId = documentsToggle.getAttribute('aria-controls') || '';
      const fileList = targetId ? document.getElementById(targetId) : null;
      if (!fileList) return;
      const opening = fileList.hidden;
      fileList.hidden = !opening;
      documentsToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      documentsToggle.setAttribute('aria-label', opening ? 'Hide Deal files' : 'Show Deal files');
      return;
    }

    const toggle = event.target.closest('[data-deal-document-upload-toggle]');
    if (!toggle) return;
    const targetId = toggle.getAttribute('aria-controls') || '';
    const uploadForm = targetId ? document.getElementById(targetId) : null;
    if (!uploadForm) return;
    const opening = uploadForm.hidden;
    uploadForm.hidden = !opening;
    toggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
    if (opening) {
      const firstInput = uploadForm.querySelector('input[name="document_type"]');
      if (firstInput) window.setTimeout(() => firstInput.focus(), 0);
    }
  });

  const nextStepFields = Array.from(page.querySelectorAll('[data-deal-next-step]'));
  const resizeNextStep = (field) => {
    if (!field) return;
    field.style.height = '39px';
    field.style.height = `${Math.max(39, field.scrollHeight)}px`;
  };
  nextStepFields.forEach((field) => {
    resizeNextStep(field);
    field.addEventListener('input', () => resizeNextStep(field));
  });
  window.addEventListener('resize', () => {
    nextStepFields.forEach(resizeNextStep);
  });

  const normalizeDealResearchLink = (rawValue) => {
    const value = String(rawValue || '').trim();
    if (!value) return '';
    const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`;
    try {
      const url = new URL(withScheme);
      if (url.protocol !== 'http:' && url.protocol !== 'https:') return '';
      return url.href;
    } catch (_error) {
      return '';
    }
  };

  page.addEventListener('click', (event) => {
    const openButton = event.target.closest('[data-deal-research-open-link]');
    if (!openButton) return;
    event.preventDefault();
    event.stopPropagation();

    const control = openButton.closest('.deal-source-link-control');
    const field = control?.querySelector('[data-deal-research-field]');
    if (!(field instanceof HTMLInputElement)) return;

    const href = normalizeDealResearchLink(field.value || '');
    if (!href) {
      window.alert('This link is not valid yet.');
      return;
    }
    window.open(href, '_blank', 'noopener,noreferrer');
  });

  const saveResearchField = async (field) => {
    if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement)) return;
    const section = field.closest('[data-deal-research-section]');
    if (!section) return;

    const previous = field.dataset.dealResearchStartValue ?? field.value;
    if (field.value === previous || field.dataset.dealResearchSaving === '1') return;

    field.dataset.dealResearchSaving = '1';
    const valueToSave = field.value;
    try {
      const response = await fetch(section.dataset.updateUrl || '', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body: new URLSearchParams({
          csrf_token: section.dataset.csrfToken || '',
          field: field.dataset.dealResearchField || '',
          value: valueToSave
        }).toString(),
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        throw new Error(data.message || 'Research detail could not be saved.');
      }
      field.dataset.dealResearchStartValue = valueToSave;
    } catch (error) {
      field.value = previous;
      window.alert(error.message || 'Research detail could not be saved. Try again.');
    } finally {
      delete field.dataset.dealResearchSaving;
    }
  };

  page.addEventListener('focusin', (event) => {
    const field = event.target.closest?.('[data-deal-research-field]');
    if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement)) return;
    field.dataset.dealResearchStartValue = field.value || '';
  });

  page.addEventListener('focusout', (event) => {
    const field = event.target.closest?.('[data-deal-research-field]');
    if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement)) return;
    saveResearchField(field);
  });

  page.addEventListener('keydown', (event) => {
    const field = event.target.closest?.('[data-deal-research-field]');
    if (!(field instanceof HTMLInputElement) || event.key !== 'Enter') return;
    event.preventDefault();
    field.blur();
  });

  const dealResearchLongTextViewer = page.querySelector('[data-deal-research-longtext-viewer]');
  const dealResearchLongTextViewerTitle = page.querySelector('[data-deal-research-longtext-viewer-title]');
  const dealResearchLongTextViewerInput = page.querySelector('[data-deal-research-longtext-viewer-input]');
  const dealResearchLongTextViewerClose = page.querySelector('[data-deal-research-longtext-viewer-close]');
  let dealResearchLongTextSource = null;
  let dealResearchLongTextStartValue = '';
  let dealResearchLongTextSavePromise = null;

  const saveDealResearchLongText = async () => {
    if (!dealResearchLongTextSource || !dealResearchLongTextViewerInput) return true;
    if (dealResearchLongTextSavePromise) return dealResearchLongTextSavePromise;

    const section = dealResearchLongTextSource.closest('[data-deal-research-section]');
    if (!section) return false;

    const fieldName = dealResearchLongTextSource.dataset.dealResearchFieldName || '';
    if (fieldName !== 'problem' && fieldName !== 'system_wanted') return false;

    const value = dealResearchLongTextViewerInput.value.trim().slice(0, 2000);
    if (value === dealResearchLongTextStartValue) return true;

    dealResearchLongTextSavePromise = (async () => {
      try {
        const response = await fetch(section.dataset.updateUrl || '', {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
          },
          body: new URLSearchParams({
            csrf_token: section.dataset.csrfToken || '',
            field: fieldName,
            value
          }).toString(),
          credentials: 'same-origin',
          cache: 'no-store'
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(data.message || 'Research detail could not be saved.');
        }

        dealResearchLongTextSource.dataset.dealResearchValue = value;
        const preview = dealResearchLongTextSource.querySelector('.deal-research-longtext-preview');
        if (preview) preview.textContent = value || '—';
        dealResearchLongTextStartValue = value;
        return true;
      } catch (error) {
        window.alert(error.message || 'Research detail could not be saved. Try again.');
        return false;
      } finally {
        dealResearchLongTextSavePromise = null;
      }
    })();

    return dealResearchLongTextSavePromise;
  };

  const closeDealResearchLongTextViewer = async () => {
    const saved = await saveDealResearchLongText();
    if (!saved) return;
    if (dealResearchLongTextViewer?.open) dealResearchLongTextViewer.close();
    dealResearchLongTextSource = null;
    dealResearchLongTextStartValue = '';
  };

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-deal-research-longtext-expand]');
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();

    const source = trigger.closest('[data-deal-research-longtext-field]');
    if (!source || !dealResearchLongTextViewerInput) return;

    dealResearchLongTextSource = source;
    dealResearchLongTextStartValue = source.dataset.dealResearchValue || '';
    dealResearchLongTextViewerInput.value = dealResearchLongTextStartValue;
    if (dealResearchLongTextViewerTitle) {
      dealResearchLongTextViewerTitle.textContent = trigger.dataset.dealResearchLongtextLabel
        || (source.dataset.dealResearchFieldName === 'problem' ? 'Problem' : 'System They Want');
    }

    if (dealResearchLongTextViewer && typeof dealResearchLongTextViewer.showModal === 'function') {
      dealResearchLongTextViewer.showModal();
      window.setTimeout(() => dealResearchLongTextViewerInput.focus(), 0);
      return;
    }

    dealResearchLongTextViewerInput.focus();
  });

  dealResearchLongTextViewerInput?.addEventListener('blur', () => {
    saveDealResearchLongText();
  });
  dealResearchLongTextViewerClose?.addEventListener('click', () => {
    closeDealResearchLongTextViewer();
  });
  dealResearchLongTextViewer?.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeDealResearchLongTextViewer();
  });
  dealResearchLongTextViewer?.addEventListener('click', (event) => {
    if (event.target === dealResearchLongTextViewer) closeDealResearchLongTextViewer();
  });

  page.addEventListener('click', async (event) => {
    const button = event.target.closest?.('[data-deal-research-attempt-delta]');
    if (!(button instanceof HTMLButtonElement)) return;
    const section = button.closest('[data-deal-research-section]');
    const control = button.closest('[data-deal-research-attempt-control]');
    const number = control?.querySelector('[data-deal-research-attempt-number]');
    if (!section || !control || !number) return;

    const delta = Number(button.dataset.dealResearchAttemptDelta || 0);
    if (delta !== -1 && delta !== 1) return;
    button.disabled = true;
    try {
      const response = await fetch(section.dataset.attemptUrl || '', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body: new URLSearchParams({
          csrf_token: section.dataset.csrfToken || '',
          delta: String(delta)
        }).toString(),
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        throw new Error(data.message || 'Contact Attempt could not be updated.');
      }
      const value = Math.max(0, Number(data.value || 0));
      control.dataset.attemptValue = String(value);
      number.textContent = String(value);
      const decrease = control.querySelector('[data-deal-research-attempt-delta="-1"]');
      if (decrease instanceof HTMLButtonElement) decrease.disabled = value <= 0;
    } catch (error) {
      window.alert(error.message || 'Contact Attempt could not be updated. Try again.');
    } finally {
      const current = Math.max(0, Number(control.dataset.attemptValue || 0));
      button.disabled = delta < 0 ? current <= 0 : false;
    }
  });

  page.querySelectorAll('input[name="contact_person"], input[name="location"]').forEach((field) => {
    field.value = (field.value || '').toUpperCase();
    field.addEventListener('input', () => {
      const start = field.selectionStart;
      const end = field.selectionEnd;
      field.value = field.value.toUpperCase();
      if (start !== null && end !== null) field.setSelectionRange(start, end);
    });
  });

  const dealAutosaveState = new WeakMap();
  const dealFormForField = (field) => {
    const associatedForm = field?.form;
    if (associatedForm?.matches?.('[data-deal-form]')) return associatedForm;
    return field?.closest?.('[data-deal-form]') || null;
  };
  const autosaveStateFor = (form) => {
    let state = dealAutosaveState.get(form);
    if (!state) {
      state = {saving:false, pending:false};
      dealAutosaveState.set(form, state);
    }
    return state;
  };

  const dealTimezoneState = new WeakMap();
  const dealTimezoneRoots = Array.from(page.querySelectorAll('[data-timezone-combobox]'));

  const timezoneStateFor = (root) => {
    let state = dealTimezoneState.get(root);
    if (!state) {
      state = {matches:[], activeIndex:-1, timer:null, requestId:0};
      dealTimezoneState.set(root, state);
    }
    return state;
  };

  const timezoneFormForRoot = (root) => root?.closest?.('[data-deal-form]') || null;

  const setTimezoneResolution = (root, message, tone = '') => {
    const resolution = root?.parentElement?.querySelector?.('[data-timezone-resolution]');
    if (!resolution) return;
    resolution.classList.remove('is-warning', 'is-error');
    if (tone) resolution.classList.add(tone);
    resolution.textContent = message || '';
  };

  const showResolvedTimezone = (root, timezone) => {
    const resolution = root?.parentElement?.querySelector?.('[data-timezone-resolution]');
    if (!resolution) return;
    resolution.classList.remove('is-warning', 'is-error');
    resolution.replaceChildren();
    if (!timezone) {
      resolution.textContent = 'Type a client location to identify the time zone.';
      return;
    }
    resolution.append(document.createTextNode('Time Zone: '));
    const strong = document.createElement('strong');
    strong.textContent = timezone;
    resolution.appendChild(strong);
  };

  const closeTimezoneDropdown = (root) => {
    const input = root?.querySelector('[data-timezone-input]');
    const dropdown = root?.querySelector('[data-timezone-dropdown]');
    if (!input || !dropdown) return;
    dropdown.hidden = true;
    root.classList.remove('is-open');
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    timezoneStateFor(root).activeIndex = -1;
  };

  const openTimezoneDropdown = (root) => {
    const input = root?.querySelector('[data-timezone-input]');
    const dropdown = root?.querySelector('[data-timezone-dropdown]');
    if (!input || !dropdown) return;
    dropdown.hidden = false;
    root.classList.add('is-open');
    input.setAttribute('aria-expanded', 'true');
  };

  const setActiveTimezoneOption = (root, index) => {
    const dropdown = root?.querySelector('[data-timezone-dropdown]');
    const input = root?.querySelector('[data-timezone-input]');
    if (!dropdown || !input) return;
    const options = Array.from(dropdown.querySelectorAll('[data-timezone-option]'));
    const state = timezoneStateFor(root);
    if (!options.length) {
      state.activeIndex = -1;
      input.removeAttribute('aria-activedescendant');
      return;
    }
    const nextIndex = Math.max(0, Math.min(index, options.length - 1));
    state.activeIndex = nextIndex;
    options.forEach((option, optionIndex) => {
      option.classList.toggle('is-active', optionIndex === nextIndex);
    });
    const active = options[nextIndex];
    if (active?.id) input.setAttribute('aria-activedescendant', active.id);
    active?.scrollIntoView?.({block:'nearest'});
  };

  const renderTimezoneLocationResults = (root, payload = {}) => {
    const dropdown = root?.querySelector('[data-timezone-dropdown]');
    const input = root?.querySelector('[data-timezone-input]');
    if (!dropdown || !input) return;
    const state = timezoneStateFor(root);
    state.matches = Array.isArray(payload.results) ? payload.results : [];
    dropdown.replaceChildren();

    if (payload.message) {
      const message = document.createElement('div');
      message.className = 'deal-timezone-empty';
      message.textContent = payload.message;
      dropdown.appendChild(message);
    }

    state.matches.forEach((result, index) => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'deal-timezone-option';
      option.dataset.timezoneOption = result.timezone || '';
      option.dataset.timezoneLocation = result.location || '';
      option.id = `${dropdown.id}-option-${index}`;
      option.setAttribute('role', 'option');

      const hidden = root.querySelector('[data-timezone-value]');
      option.setAttribute('aria-selected', String((hidden?.value || '') === (result.timezone || '')));

      const primary = document.createElement('span');
      primary.className = 'deal-timezone-option-location';
      primary.textContent = result.location || result.country || result.timezone || 'Location';

      const secondary = document.createElement('span');
      secondary.className = 'deal-timezone-option-meta';
      secondary.textContent = [result.timezone || '', result.offset || ''].filter(Boolean).join(' · ');

      option.append(primary, secondary);
      dropdown.appendChild(option);
    });

    if (!payload.message && !state.matches.length) {
      const empty = document.createElement('div');
      empty.className = 'deal-timezone-empty';
      empty.textContent = 'No matching location found.';
      dropdown.appendChild(empty);
    }

    setActiveTimezoneOption(root, state.matches.length ? 0 : -1);
    openTimezoneDropdown(root);
  };

  const applyTimezoneLocation = (root, result, autosave = true) => {
    const input = root?.querySelector('[data-timezone-input]');
    const hidden = root?.querySelector('[data-timezone-value]');
    if (!input || !hidden || !result?.timezone) return;
    const nextLocation = result.location || input.value || '';
    const nextTimezone = result.timezone;
    const changed = nextLocation !== (root.dataset.selectedLocation || '') || nextTimezone !== (root.dataset.selectedTimezone || '');

    input.value = nextLocation;
    hidden.value = nextTimezone;
    root.dataset.selectedLocation = nextLocation;
    root.dataset.selectedTimezone = nextTimezone;
    input.dataset.dealStartValue = nextLocation;
    hidden.dataset.dealStartValue = nextTimezone;
    showResolvedTimezone(root, nextTimezone);
    closeTimezoneDropdown(root);

    if (autosave && changed) {
      const form = timezoneFormForRoot(root);
      if (form) saveDealFormInBackground(form);
    }
  };

  const searchTimezoneLocations = async (root, query, {persistUnresolved = true} = {}) => {
    const input = root?.querySelector('[data-timezone-input]');
    const hidden = root?.querySelector('[data-timezone-value]');
    const url = root?.dataset.timezoneSearchUrl || '';
    if (!input || !hidden || !url) return;

    const value = String(query || '').trim();
    if (value.length < 2) {
      renderTimezoneLocationResults(root, {
        message: 'Type a city, state/province, or country.',
        results: []
      });
      setTimezoneResolution(root, 'Type a client location to identify the time zone.');
      return;
    }

    const state = timezoneStateFor(root);
    const requestId = ++state.requestId;
    setTimezoneResolution(root, 'Finding the correct time zone…');

    try {
      const response = await fetch(`${url}?q=${encodeURIComponent(value)}`, {
        headers: {Accept:'application/json'},
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const payload = await response.json().catch(() => ({}));
      if (requestId !== timezoneStateFor(root).requestId) return;
      if (!response.ok || !payload.ok) throw new Error(payload.message || 'Location search failed.');

      if (payload.auto_select && Array.isArray(payload.results) && payload.results.length === 1) {
        applyTimezoneLocation(root, payload.results[0], true);
        return;
      }

      renderTimezoneLocationResults(root, payload);
      const tone = payload.status === 'not_found' ? 'is-error' : 'is-warning';
      setTimezoneResolution(root, payload.message || 'Choose the correct location.', tone);

      if (persistUnresolved && !hidden.value) {
        const form = timezoneFormForRoot(root);
        if (form) saveDealFormInBackground(form);
      }
    } catch (_error) {
      if (requestId !== timezoneStateFor(root).requestId) return;
      renderTimezoneLocationResults(root, {
        message: 'Location search is unavailable right now. Try again.',
        results: []
      });
      setTimezoneResolution(root, 'Location search is unavailable right now. Try again.', 'is-error');
    }
  };

  const queueTimezoneLocationSearch = (root, query) => {
    const state = timezoneStateFor(root);
    if (state.timer) window.clearTimeout(state.timer);
    state.timer = window.setTimeout(() => {
      state.timer = null;
      searchTimezoneLocations(root, query);
    }, 280);
  };

  dealTimezoneRoots.forEach((root) => {
    const input = root.querySelector('[data-timezone-input]');
    const hidden = root.querySelector('[data-timezone-value]');
    const toggle = root.querySelector('[data-timezone-toggle]');
    const dropdown = root.querySelector('[data-timezone-dropdown]');
    if (!(input instanceof HTMLInputElement) || !(hidden instanceof HTMLInputElement) || !dropdown) return;

    input.addEventListener('focus', () => {
      if ((input.value || '').trim()) searchTimezoneLocations(root, input.value, {persistUnresolved:false});
    });

    input.addEventListener('blur', () => {
      window.setTimeout(() => {
        if (root.contains(document.activeElement)) return;
        closeTimezoneDropdown(root);
        const changed = (input.value || '') !== (root.dataset.selectedLocation || '')
          || (hidden.value || '') !== (root.dataset.selectedTimezone || '');
        if (!changed) return;
        root.dataset.selectedLocation = input.value || '';
        root.dataset.selectedTimezone = hidden.value || '';
        input.dataset.dealStartValue = input.value || '';
        hidden.dataset.dealStartValue = hidden.value || '';
        const form = timezoneFormForRoot(root);
        if (form) saveDealFormInBackground(form);
      }, 0);
    });

    input.addEventListener('input', () => {
      const current = input.value || '';
      if (current !== (root.dataset.selectedLocation || '')) {
        hidden.value = '';
        root.dataset.selectedTimezone = '';
        const card = root.closest('[data-deal-card]');
        const clientTime = card?.querySelector('[data-client-time-display]');
        const philippinesTime = card?.querySelector('[data-philippines-time-display]');
        if (clientTime) clientTime.textContent = 'Add a more specific client location.';
        if (philippinesTime) philippinesTime.textContent = '—';
        setTimezoneResolution(root, 'Finding the correct time zone…');
      }
      queueTimezoneLocationSearch(root, current);
    });

    input.addEventListener('keydown', (event) => {
      const state = timezoneStateFor(root);
      const isOpen = input.getAttribute('aria-expanded') === 'true';

      if (event.key === 'Escape') {
        if (isOpen) {
          event.preventDefault();
          event.stopPropagation();
          closeTimezoneDropdown(root);
        }
        return;
      }

      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        if (!isOpen) {
          searchTimezoneLocations(root, input.value, {persistUnresolved:false});
          return;
        }
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        const current = state.activeIndex;
        const next = current < 0 ? (delta > 0 ? 0 : state.matches.length - 1) : current + delta;
        setActiveTimezoneOption(root, next);
        return;
      }

      if (event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        if (isOpen && state.activeIndex >= 0 && state.matches[state.activeIndex]) {
          applyTimezoneLocation(root, state.matches[state.activeIndex], true);
        } else if (!isOpen) {
          searchTimezoneLocations(root, input.value, {persistUnresolved:false});
        }
      }
    });

    toggle?.addEventListener('click', () => {
      const isOpen = input.getAttribute('aria-expanded') === 'true';
      if (isOpen) {
        closeTimezoneDropdown(root);
      } else {
        input.focus();
        searchTimezoneLocations(root, input.value, {persistUnresolved:false});
      }
    });

    dropdown.addEventListener('pointerdown', (event) => {
      if (event.target.closest('[data-timezone-option]')) event.preventDefault();
    });
    dropdown.addEventListener('click', (event) => {
      const option = event.target.closest('[data-timezone-option]');
      if (!option) return;
      const state = timezoneStateFor(root);
      const index = Array.from(dropdown.querySelectorAll('[data-timezone-option]')).indexOf(option);
      const result = index >= 0 ? state.matches[index] : null;
      if (result) applyTimezoneLocation(root, result, true);
    });
  });

  document.addEventListener('pointerdown', (event) => {
    dealTimezoneRoots.forEach((root) => {
      if (!root.contains(event.target)) closeTimezoneDropdown(root);
    });
  });

  const updateDealMeetState = (form, data = {}) => {
    const card = form?.closest?.('[data-deal-card]');
    if (!card) return;
    const field = card.querySelector('[data-deal-calendar-meet-field]');
    const clientTimeDisplay = card.querySelector('[data-client-time-display]');
    const philippinesTimeDisplay = card.querySelector('[data-philippines-time-display]');
    const timezoneField = form.querySelector('[data-timezone-value]');
    const timezoneLocationField = form.querySelector('input[name="demo_timezone_location"]');
    const notesTrigger = card.querySelector('[data-deal-notes-expand]');
    const meetUrl = data.google_meet_url || notesTrigger?.dataset.googleMeetUrl || '';
    if (notesTrigger) notesTrigger.dataset.googleMeetUrl = meetUrl;
    if (clientTimeDisplay && typeof data.client_time_display === 'string') {
      clientTimeDisplay.textContent = data.client_time_display;
    }
    if (philippinesTimeDisplay && typeof data.philippines_time_display === 'string') {
      philippinesTimeDisplay.textContent = data.philippines_time_display;
    }
    if (timezoneField && typeof data.demo_timezone === 'string') {
      timezoneField.value = data.demo_timezone;
      timezoneField.dataset.dealStartValue = data.demo_timezone;
      const timezoneRoot = timezoneField.closest('[data-timezone-combobox]');
      if (timezoneRoot) {
        timezoneRoot.dataset.selectedTimezone = data.demo_timezone;
        if (timezoneLocationField && typeof data.demo_timezone_location === 'string') {
          timezoneLocationField.value = data.demo_timezone_location;
          timezoneLocationField.dataset.dealStartValue = data.demo_timezone_location;
          timezoneRoot.dataset.selectedLocation = data.demo_timezone_location;
        }
        if (data.demo_timezone) {
          showResolvedTimezone(timezoneRoot, data.demo_timezone);
        } else {
          const resolution = timezoneRoot.parentElement?.querySelector?.('[data-timezone-resolution]');
          if (!resolution?.classList.contains('is-warning') && !resolution?.classList.contains('is-error')) {
            setTimezoneResolution(
              timezoneRoot,
              data.demo_timezone_location
                ? 'Add a city or state/province to identify the exact time zone.'
                : 'Type a client location to identify the time zone.',
              data.demo_timezone_location ? 'is-warning' : ''
            );
          }
        }
      }
    }

    if (field) {
      let link = field.querySelector('[data-deal-scheduled-meet]');
      let status = field.querySelector('[data-deal-meet-status]');
      if (meetUrl) {
        if (!link) {
          link = document.createElement('a');
          link.dataset.dealScheduledMeet = '';
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = 'Join Meeting';
          status?.replaceWith(link);
        }
        link.href = meetUrl;
      } else if (data.calendar_message && status) {
        status.textContent = data.calendar_message;
      }
      const error = field.querySelector('[data-deal-meet-error]');
      if (error) {
        const message = data.calendar_status === 'error' ? (data.calendar_message || 'Google Calendar sync failed.') : '';
        error.textContent = message;
        error.hidden = !message;
      }
    }

    const openDialog = page.querySelector('[data-deal-notes-viewer][open]');
    if (openDialog && notesSource?.closest?.('[data-deal-card]') === card) {
      const action = openDialog.querySelector('[data-deal-meet-action]');
      if (action) {
        action.href = meetUrl || 'https://meet.google.com/';
        action.title = meetUrl ? 'Join scheduled Google Meet' : 'Open Google Meet';
        action.setAttribute('aria-label', action.title);
      }
    }
  };

  const syncEmbeddedSourceFromDeal = (form, data = {}) => {
    if (form?.dataset.masterDealEmbedded !== '1') return;
    const card = form.closest('[data-deal-card]');
    if (!card) return;

    if (card.hasAttribute('data-prospect-row')) {
      const values = {
        contact: data.contact_person,
        location: data.location,
        email: data.email,
        phone: data.contact_number
      };
      Object.entries(values).forEach(([fieldName, value]) => {
        if (typeof value !== 'string') return;
        const wrap = card.querySelector(`[data-prospect-edit-field][data-prospect-field="${fieldName}"]`);
        if (!wrap) return;
        wrap.dataset.prospectValue = value;
        const trigger = wrap.querySelector('[data-prospect-edit-trigger]');
        if (trigger) trigger.textContent = value || '—';
      });
      if (typeof data.notes_after_conversation === 'string') {
        const sourceNotes = card.querySelector('[data-prospect-notes-compact]');
        if (sourceNotes instanceof HTMLTextAreaElement) {
          sourceNotes.value = data.notes_after_conversation;
          sourceNotes.dataset.prospectNotesStartValue = data.notes_after_conversation;
        }
      }
    }

    if (card.hasAttribute('data-website-inquiry-card')) {
      if (typeof data.contact_person === 'string') {
        const name = card.querySelector('[data-inquiry-client-name]');
        if (name) name.textContent = data.contact_person || '—';
      }
      if (typeof data.email === 'string') {
        const email = card.querySelector('[data-inquiry-email]');
        if (email instanceof HTMLInputElement) email.value = data.email;
        else if (email) email.textContent = data.email || '—';
      }
      if (typeof data.contact_number === 'string') {
        const phone = card.querySelector('[data-inquiry-phone]');
        if (phone instanceof HTMLInputElement) phone.value = data.contact_number;
        else if (phone) phone.textContent = data.contact_number || '—';
      }
      if (typeof data.notes_after_conversation === 'string') {
        const sourceNotes = card.querySelector('[data-website-notes-compact]');
        if (sourceNotes instanceof HTMLTextAreaElement) {
          sourceNotes.value = data.notes_after_conversation;
          sourceNotes.dataset.websiteNotesStartValue = data.notes_after_conversation;
        }
      }
    }
  };

  const saveDealFormInBackground = async (form) => {
    if (!(form instanceof HTMLFormElement)) return;
    const state = autosaveStateFor(form);
    if (state.saving) {
      state.pending = true;
      return;
    }

    state.saving = true;
    try {
      do {
        state.pending = false;
        const body = new URLSearchParams();
        for (const [key, value] of new FormData(form).entries()) body.append(key, String(value));

        const response = await fetch(form.action, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'X-RSF-Async': '1'
          },
          body: body.toString(),
          credentials: 'same-origin',
          cache: 'no-store',
          keepalive: true
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(data.message || 'Deal changes could not be saved.');
        }
        if (data.status) {
          form.dataset.dealCurrentStatus = data.status;
          const card = form.closest('[data-deal-card]');
          if (card) {
            card.dataset.dealStatus = data.status;
            if (card.hasAttribute('data-prospect-row')) card.dataset.prospectStatus = data.status;
            if (card.hasAttribute('data-website-inquiry-card')) card.dataset.websiteInquiryWorkflowStatus = data.status;
          }
          const hiddenStatus = form.querySelector('[data-master-deal-status-hidden]');
          if (hiddenStatus) hiddenStatus.value = data.status;
          applyDealFilter();
        }
        updateDealMeetState(form, data);
        syncEmbeddedSourceFromDeal(form, data);
      } while (state.pending);
    } catch (error) {
      state.pending = false;
      window.alert(error.message || 'Deal changes could not be saved. Try again.');
    } finally {
      state.saving = false;
    }
  };

  const notesViewer = page.querySelector('[data-deal-notes-viewer]');
  const notesViewerInput = page.querySelector('[data-deal-notes-viewer-input]');
  const notesViewerClose = page.querySelector('[data-deal-notes-viewer-close]');
  const dealNotesSave = page.querySelector('[data-deal-notes-save]');
  const dealConversationTimeline = page.querySelector('[data-deal-conversation-timeline]');
  const dealCallAction = page.querySelector('[data-deal-call-action]');
  const dealMeetAction = page.querySelector('[data-deal-meet-action]');
  const dealEmailAction = page.querySelector('[data-deal-email-action]');
  let notesSource = null;
  let dealNotesTimelineUrl = '';

  const saveExpandedNotesIfChanged = () => {
    if (!notesSource) return;
    const previous = notesSource.dataset.dealStartValue ?? notesSource.value;
    if (notesSource.value === previous) return;
    notesSource.dataset.dealStartValue = notesSource.value;
    const form = notesSource.closest('[data-deal-form]');
    if (form) saveDealFormInBackground(form);
  };

  const closeDealNotesViewer = () => {
    if (notesViewer?.open) notesViewer.close();
    notesSource = null;
    dealNotesTimelineUrl = '';
    if (notesViewerInput) notesViewerInput.value = '';
  };

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-deal-notes-expand]');
    if (!trigger) return;
    const notesWrap = trigger.closest('.deal-notes-compact');
    const source = notesWrap?.querySelector('[data-deal-notes-compact]');
    if (!source) return;

    notesSource = source;
    notesSource.dataset.dealStartValue = source.value || '';
    dealNotesTimelineUrl = trigger.dataset.timelineUrl || '';
    if (dealMeetAction) {
      const scheduledMeetUrl = trigger.dataset.googleMeetUrl || '';
      const cardStatus = notesSource.closest('[data-deal-card]')?.dataset.dealStatus || '';
      const dealSide = ['DEAL', 'DEMO', 'PROPOSAL', 'DECISION', 'WON', 'LOST'].includes(cardStatus);
      if (dealSide) {
        dealMeetAction.href = scheduledMeetUrl || 'https://meet.google.com/';
        dealMeetAction.removeAttribute('aria-disabled');
        delete dealMeetAction.dataset.actionLocked;
        dealMeetAction.title = scheduledMeetUrl ? 'Join scheduled Google Meet' : 'Open Google Meet';
      } else {
        dealMeetAction.removeAttribute('href');
        dealMeetAction.setAttribute('aria-disabled', 'true');
        dealMeetAction.dataset.actionLocked = 'true';
        dealMeetAction.title = 'Google Meet — available when this record becomes a Deal';
      }
      dealMeetAction.setAttribute('aria-label', dealMeetAction.title);
    }
    if (notesViewerInput) notesViewerInput.value = '';
    const dealNotesForm = notesSource.closest('[data-deal-form]');
    const dealTimelineOptions = {
      csrfToken: dealNotesForm?.querySelector('input[name="csrf_token"]')?.value || '',
      onLegacyChanged: (value) => {
        if (!notesSource) return;
        notesSource.value = value;
        notesSource.dataset.dealStartValue = value;
        syncEmbeddedSourceFromDeal(dealNotesForm, {notes_after_conversation:value});
      }
    };
    RSFConversationTimeline.load(
      dealNotesTimelineUrl,
      dealConversationTimeline,
      dealCallAction,
      dealEmailAction,
      dealTimelineOptions
    );

    if (notesViewer && typeof notesViewer.showModal === 'function') {
      notesViewer.showModal();
      window.setTimeout(() => notesViewerInput?.focus(), 0);
      return;
    }

    source.focus();
  });

  dealNotesSave?.addEventListener('click', async () => {
    if (!notesViewerInput || !notesSource) return;
    dealNotesSave.disabled = true;
    try {
      const form = notesSource.closest('[data-deal-form]');
      const csrfToken = form?.querySelector('input[name="csrf_token"]')?.value || '';
      await RSFConversationTimeline.saveManualNote(
        dealNotesTimelineUrl,
        notesViewerInput.value,
        csrfToken
      );
      notesViewerInput.value = '';
      await RSFConversationTimeline.load(
        dealNotesTimelineUrl,
        dealConversationTimeline,
        dealCallAction,
        dealEmailAction,
        {
          csrfToken,
          onLegacyChanged: (value) => {
            if (!notesSource) return;
            notesSource.value = value;
            notesSource.dataset.dealStartValue = value;
          }
        }
      );
      notesViewerInput.focus();
    } catch (error) {
      window.alert(error.message || 'Manual note could not be saved.');
    } finally {
      dealNotesSave.disabled = false;
    }
  });
  notesViewerInput?.addEventListener('keydown', (event) => {
    if (event.isComposing) return;
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      dealNotesSave?.click();
    }
  });

  notesViewerClose?.addEventListener('click', closeDealNotesViewer);
  notesViewer?.addEventListener('cancel', () => {
    notesSource = null;
    dealNotesTimelineUrl = '';
    if (notesViewerInput) notesViewerInput.value = '';
  });
  notesViewer?.addEventListener('click', (event) => {
    if (event.target === notesViewer) closeDealNotesViewer();
  });

  const viewer = page.querySelector('[data-deal-document-viewer]');
  const viewerTitle = page.querySelector('[data-deal-document-viewer-title]');
  const viewerFrame = page.querySelector('[data-deal-document-viewer-frame]');
  const viewerDownload = page.querySelector('[data-deal-document-viewer-download]');
  const viewerClose = page.querySelector('[data-deal-document-viewer-close]');

  let viewerZoom = 1;
  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartScrollX = 0;
  let dragStartScrollY = 0;
  let frameWindow = null;
  let frameDocument = null;

  const viewerWindow = () => {
    try {
      return viewerFrame?.contentWindow || null;
    } catch (_error) {
      return null;
    }
  };

  const viewerDocument = () => {
    try {
      return viewerFrame?.contentDocument || null;
    } catch (_error) {
      return null;
    }
  };

  const applyViewerZoom = (nextZoom) => {
    viewerZoom = Math.min(4, Math.max(0.5, Math.round(nextZoom * 10) / 10));
    const doc = viewerDocument();
    if (!doc?.body) return;
    doc.body.style.zoom = String(viewerZoom);
    doc.body.style.transformOrigin = '0 0';
  };

  const handleFrameWheel = (event) => {
    if (!event.ctrlKey) return;
    event.preventDefault();
    applyViewerZoom(viewerZoom + (event.deltaY < 0 ? 0.1 : -0.1));
  };

  const handleFramePointerDown = (event) => {
    if (event.button !== 0) return;
    const targetWindow = viewerWindow();
    if (!targetWindow) return;

    dragging = true;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    dragStartScrollX = targetWindow.scrollX || 0;
    dragStartScrollY = targetWindow.scrollY || 0;

    const doc = viewerDocument();
    if (doc?.documentElement) doc.documentElement.style.cursor = 'grabbing';
    event.preventDefault();
  };

  const handleFramePointerMove = (event) => {
    if (!dragging) return;
    const targetWindow = viewerWindow();
    if (!targetWindow) return;

    const dx = event.clientX - dragStartX;
    const dy = event.clientY - dragStartY;
    targetWindow.scrollTo(dragStartScrollX - dx, dragStartScrollY - dy);
  };

  const stopFrameDrag = () => {
    dragging = false;
    const doc = viewerDocument();
    if (doc?.documentElement) doc.documentElement.style.cursor = 'grab';
  };

  const unbindFrameInteractions = () => {
    if (frameWindow) {
      frameWindow.removeEventListener('wheel', handleFrameWheel);
      frameWindow.removeEventListener('pointermove', handleFramePointerMove);
      frameWindow.removeEventListener('pointerup', stopFrameDrag);
      frameWindow.removeEventListener('pointercancel', stopFrameDrag);
    }
    if (frameDocument) {
      frameDocument.removeEventListener('pointerdown', handleFramePointerDown);
    }
    frameWindow = null;
    frameDocument = null;
  };

  const bindFrameInteractions = () => {
    unbindFrameInteractions();

    const targetWindow = viewerWindow();
    const doc = viewerDocument();
    if (!targetWindow || !doc?.documentElement) return;

    frameWindow = targetWindow;
    frameDocument = doc;
    doc.documentElement.style.cursor = 'grab';

    targetWindow.addEventListener('wheel', handleFrameWheel, {passive:false});
    doc.addEventListener('pointerdown', handleFramePointerDown, {passive:false});
    targetWindow.addEventListener('pointermove', handleFramePointerMove);
    targetWindow.addEventListener('pointerup', stopFrameDrag);
    targetWindow.addEventListener('pointercancel', stopFrameDrag);
    applyViewerZoom(viewerZoom);
  };

  const resetViewerTools = () => {
    viewerZoom = 1;
    dragging = false;
    const doc = viewerDocument();
    if (doc?.body) doc.body.style.zoom = '1';
    if (doc?.documentElement) doc.documentElement.style.cursor = 'grab';
    viewerWindow()?.scrollTo(0, 0);
  };

  const closeDealViewer = () => {
    resetViewerTools();
    unbindFrameInteractions();
    if (viewer?.open) viewer.close();
    viewerFrame?.removeAttribute('src');
  };

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-deal-document-view]');
    if (!trigger) return;
    const previewUrl = trigger.dataset.previewUrl || '';
    const downloadUrl = trigger.dataset.downloadUrl || '';
    const title = trigger.dataset.documentTitle || 'File Preview';
    if (viewerTitle) viewerTitle.textContent = title;
    if (viewerDownload) viewerDownload.href = downloadUrl;
    viewerZoom = 1;
    dragging = false;
    if (viewerFrame) viewerFrame.src = previewUrl;
    if (viewer && typeof viewer.showModal === 'function') viewer.showModal();
    else window.open(previewUrl, '_blank', 'noopener');
  });

  viewerFrame?.addEventListener('load', bindFrameInteractions);

  viewerClose?.addEventListener('click', closeDealViewer);
  viewer?.addEventListener('cancel', () => {
    unbindFrameInteractions();
    window.setTimeout(() => viewerFrame?.removeAttribute('src'), 0);
  });
  viewer?.addEventListener('click', (event) => {
    if (event.target === viewer) closeDealViewer();
  });

  const dialog = page.querySelector('[data-deal-status-confirm]');
  const message = page.querySelector('[data-deal-status-confirm-message]');
  const yes = page.querySelector('[data-deal-status-confirm-yes]');
  const no = page.querySelector('[data-deal-status-confirm-no]');
  const preDealStatuses = new Set(['NOT_CONTACTED', 'NO_ANSWER', 'REJECTED']);
  const labels = {
    NOT_CONTACTED: 'Not Contacted',
    NO_ANSWER: 'No Answer',
    REJECTED: 'Rejected'
  };
  let pendingForm = null;
  const requestDealSubmitWithoutValidation = (form) => {
    if (!(form instanceof HTMLFormElement)) return;
    const previousNoValidate = form.noValidate;
    form.noValidate = true;
    try {
      form.requestSubmit();
    } finally {
      form.noValidate = previousNoValidate;
    }
  };
  const dealAutosaveFields = new Set([
    'demo_date',
    'demo_time',
    'demo_timezone',
    'followup_date',
    'email',
    'price',
    'contact_number',
    'contact_person',
    'location',
    'next_step',
    'notes_after_conversation'
  ]);

  page.addEventListener('focusin', (event) => {
    const field = event.target;
    const form = dealFormForField(field);
    if (!form || !dealAutosaveFields.has(field.name || '')) return;
    field.dataset.dealStartValue = field.value || '';
  });

  page.addEventListener('focusout', (event) => {
    const field = event.target;
    const form = dealFormForField(field);
    if (!form || !dealAutosaveFields.has(field.name || '')) return;

    const previous = field.dataset.dealStartValue ?? field.value;
    if (field.value === previous) return;
    field.dataset.dealStartValue = field.value;
    saveDealFormInBackground(form);
  });

  page.addEventListener('change', (event) => {
    const field = event.target;
    const form = dealFormForField(field);
    if (!form) return;

    if (['demo_date', 'demo_time', 'demo_timezone'].includes(field?.name || '')) {
      field.dataset.dealStartValue = field.value || '';
      saveDealFormInBackground(form);
      return;
    }

    if (field?.name !== 'status') return;
    const status = field.value || '';
    if (status === (form.dataset.dealCurrentStatus || '')) return;
    if (preDealStatuses.has(status)) {
      requestDealSubmitWithoutValidation(form);
      return;
    }
    saveDealFormInBackground(form);
  });

  page.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
    const target = event.target;
    const form = dealFormForField(target);
    if (!form) return;
    if (target instanceof HTMLTextAreaElement && !target.matches('[data-deal-next-step]')) return;
    event.preventDefault();
    form.requestSubmit();
  });

  const resetPendingStatus = () => {
    if (!pendingForm) return;
    const select = pendingForm.elements?.namedItem('status');
    if (select instanceof HTMLSelectElement) select.value = pendingForm.dataset.dealCurrentStatus || select.value;
  };

  const submitConfirmed = () => {
    if (!pendingForm) return;
    const form = pendingForm;
    pendingForm = null;
    const confirmField = form.querySelector('[data-deal-confirm-field]');
    if (confirmField) confirmField.value = 'yes';
    form.dataset.dealBackwardConfirmed = '1';
    if (dialog?.open) dialog.close();
    requestDealSubmitWithoutValidation(form);
  };

  page.addEventListener('submit', (event) => {
    const form = event.target.closest('[data-deal-form]');
    if (!form) return;

    if (form.dataset.masterDealEmbedded === '1') {
      event.preventDefault();
      saveDealFormInBackground(form);
      return;
    }

    if (form.dataset.dealBackwardConfirmed === '1') {
      delete form.dataset.dealBackwardConfirmed;
      return;
    }

    const select = form.elements?.namedItem('status');
    const status = select instanceof HTMLSelectElement ? (select.value || '') : '';
    if (!preDealStatuses.has(status)) return;

    event.preventDefault();
    pendingForm = form;
    const text = `Are you sure you want to change this Deal to ${labels[status] || status}? This will remove it from the Deals page. Your linked Deal details will stay preserved.`;
    if (message) message.textContent = text;

    if (dialog && typeof dialog.showModal === 'function') {
      dialog.showModal();
      return;
    }

    if (window.confirm(text)) submitConfirmed();
    else {
      resetPendingStatus();
      pendingForm = null;
    }
  });

  yes?.addEventListener('click', submitConfirmed);
  no?.addEventListener('click', () => {
    resetPendingStatus();
    pendingForm = null;
    if (dialog?.open) dialog.close();
  });
  dialog?.addEventListener('cancel', () => {
    resetPendingStatus();
    pendingForm = null;
  });
})();


(() => {
  const page = document.querySelector('[data-website-inbox-page]');
  if (!page) return;

  const websiteDealStatuses = new Set(['DEAL', 'DEMO', 'PROPOSAL', 'DECISION', 'WON', 'LOST']);
  const websitePreDealStatuses = new Set(['NOT_CONTACTED', 'NO_ANSWER', 'REJECTED']);
  const websiteStatusLabels = {
    NOT_CONTACTED: 'Not Contacted',
    NO_ANSWER: 'No Answer',
    REJECTED: 'Rejected'
  };
  const websiteStatusConfirm = page.querySelector('[data-website-status-confirm]');
  const websiteStatusConfirmMessage = page.querySelector('[data-website-status-confirm-message]');
  const websiteStatusConfirmYes = page.querySelector('[data-website-status-confirm-yes]');
  const websiteStatusConfirmNo = page.querySelector('[data-website-status-confirm-no]');
  let pendingWebsiteStatusDecision = null;

  const renderWebsiteDealAction = (action, status, dealId) => {
    if (!(action instanceof HTMLElement)) return;
    action.replaceChildren();

    if (websiteDealStatuses.has(status) && dealId) {
      const link = document.createElement('a');
      link.className = 'button secondary';
      link.href = `${action.dataset.dealsUrl || '/app/deals'}#deal-${dealId}`;
      link.textContent = 'View Deal';
      action.appendChild(link);
      return;
    }

    const form = document.createElement('form');
    form.method = 'post';
    form.action = action.dataset.createUrl || '';

    const csrf = document.createElement('input');
    csrf.type = 'hidden';
    csrf.name = 'csrf_token';
    csrf.value = action.dataset.csrfToken || '';

    const button = document.createElement('button');
    button.className = 'button primary';
    button.type = 'submit';
    button.textContent = 'Create Deal';

    form.append(csrf, button);
    action.appendChild(form);
  };

  const viewer = page.querySelector('[data-website-message-viewer]');
  const viewerInput = page.querySelector('[data-website-message-viewer-input]');
  const viewerClose = page.querySelector('[data-website-message-viewer-close]');
  const notesViewer = page.querySelector('[data-website-notes-viewer]');
  const notesViewerInput = page.querySelector('[data-website-notes-viewer-input]');
  const notesViewerClose = page.querySelector('[data-website-notes-viewer-close]');
  const websiteNotesSave = page.querySelector('[data-website-notes-save]');
  const websiteConversationTimeline = page.querySelector('[data-website-conversation-timeline]');
  const websiteCallAction = page.querySelector('[data-website-call-action]');
  const websiteEmailAction = page.querySelector('[data-website-email-action]');
  let notesSource = null;
  let websiteNotesTimelineUrl = '';

  const closeViewer = () => {
    if (viewer?.open) viewer.close();
  };

  const saveWebsiteNotes = async (source) => {
    if (!(source instanceof HTMLTextAreaElement)) return;

    if (source.dataset.websiteNotesSaving === '1') {
      source.dataset.websiteNotesPending = '1';
      return;
    }

    const previous = source.dataset.websiteNotesStartValue ?? source.value;
    if (source.value === previous) return;

    source.dataset.websiteNotesSaving = '1';
    try {
      do {
        delete source.dataset.websiteNotesPending;
        const valueToSave = source.value;
        const response = await fetch(source.dataset.updateUrl || '', {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
          },
          body: new URLSearchParams({
            csrf_token: source.dataset.csrfToken || '',
            value: valueToSave
          }).toString(),
          credentials: 'same-origin',
          cache: 'no-store',
          keepalive: true
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(data.message || 'Notes After Conversation could not be updated.');
        }

        source.dataset.websiteNotesStartValue = valueToSave;
        const card = source.closest('[data-website-inquiry-card]');
        const linkedDealNotes = card?.querySelector('[data-deal-notes-compact]');
        if (linkedDealNotes instanceof HTMLTextAreaElement) {
          linkedDealNotes.value = valueToSave;
          linkedDealNotes.dataset.dealStartValue = valueToSave;
        }
        if (source.value !== valueToSave) source.dataset.websiteNotesPending = '1';
      } while (source.dataset.websiteNotesPending === '1');
    } catch (error) {
      window.alert(error.message || 'Notes After Conversation could not be updated. Try again.');
    } finally {
      delete source.dataset.websiteNotesSaving;
      delete source.dataset.websiteNotesPending;
    }
  };

  const closeWebsiteNotesViewer = () => {
    if (notesViewer?.open) notesViewer.close();
    notesSource = null;
    websiteNotesTimelineUrl = '';
    if (notesViewerInput) notesViewerInput.value = '';
  };

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-website-message-expand]');
    if (!trigger) return;
    const wrap = trigger.closest('.website-inquiry-message-field');
    const source = wrap?.querySelector('[data-website-message-compact]');
    if (!source) return;

    if (viewerInput) viewerInput.value = source.value || '';

    if (viewer && typeof viewer.showModal === 'function') {
      viewer.showModal();
      window.setTimeout(() => viewerClose?.focus(), 0);
      return;
    }

    source.focus();
  });

  page.addEventListener('focusin', (event) => {
    const notes = event.target.closest?.('[data-website-notes-compact]');
    if (notes) {
      notes.dataset.websiteNotesStartValue = notes.value || '';
      return;
    }

    const field = event.target.closest('[data-website-inquiry-status]');
    if (!field) return;
    const currentStatus = field.dataset.websiteInquiryCurrentStatus || field.value || '';
    field.dataset.websiteInquiryCurrentStatus = currentStatus;
    field.dataset.websiteInquiryStartStatus = currentStatus;
  });

  page.addEventListener('focusout', (event) => {
    const notes = event.target.closest?.('[data-website-notes-compact]');
    if (!notes) return;
    saveWebsiteNotes(notes);
  });

  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-website-notes-expand]');
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();

    const wrap = trigger.closest('.deal-notes-compact');
    const source = wrap?.querySelector('[data-website-notes-compact]');
    if (!source) return;

    notesSource = source;
    source.dataset.websiteNotesStartValue ??= source.value || '';
    websiteNotesTimelineUrl = trigger.dataset.timelineUrl || '';
    if (notesViewerInput) notesViewerInput.value = '';
    const websiteTimelineOptions = {
      csrfToken: notesSource.dataset.csrfToken || '',
      onLegacyChanged: (value) => {
        if (!notesSource) return;
        notesSource.value = value;
        notesSource.dataset.websiteNotesStartValue = value;
        const card = notesSource.closest('[data-website-inquiry-card]');
        const linkedDealNotes = card?.querySelector('[data-deal-notes-compact]');
        if (linkedDealNotes instanceof HTMLTextAreaElement) {
          linkedDealNotes.value = value;
          linkedDealNotes.dataset.dealStartValue = value;
        }
      }
    };
    RSFConversationTimeline.load(
      websiteNotesTimelineUrl,
      websiteConversationTimeline,
      websiteCallAction,
      websiteEmailAction,
      websiteTimelineOptions
    );

    if (notesViewer && typeof notesViewer.showModal === 'function') {
      notesViewer.showModal();
      window.setTimeout(() => notesViewerInput?.focus(), 0);
      return;
    }

    source.focus();
  });

  const saveWebsiteInquiryStatus = async (field, previous, status, confirmed = false) => {
    field.disabled = true;
    try {
      const body = new URLSearchParams({
        csrf_token: field.dataset.csrfToken || '',
        status
      });
      if (confirmed) body.set('confirm_leave_deals', 'yes');

      const response = await fetch(field.dataset.updateUrl || '', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body: body.toString(),
        credentials: 'same-origin',
        cache: 'no-store'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        field.value = previous;
        throw new Error(data.message || 'Website Inquiry status could not be updated.');
      }
      const savedStatus = data.status || status;
      field.dataset.websiteInquiryStartStatus = savedStatus;
      field.dataset.websiteInquiryCurrentStatus = savedStatus;
      const card = field.closest('[data-website-inquiry-card]');
      if (card) {
        card.dataset.websiteInquiryWorkflowStatus = savedStatus;
        card.dataset.dealStatus = savedStatus;
        const embeddedForm = card.querySelector('[data-deal-form]');
        const hiddenStatus = embeddedForm?.querySelector('[data-master-deal-status-hidden]');
        if (hiddenStatus) hiddenStatus.value = savedStatus;
        if (embeddedForm) embeddedForm.dataset.dealCurrentStatus = savedStatus;
      }
      const action = card?.querySelector('[data-website-deal-action]');
      if (action) renderWebsiteDealAction(action, savedStatus, data.deal_id || null);

      const crossedWebsiteStageBoundary = (
        (websitePreDealStatuses.has(previous) && websiteDealStatuses.has(savedStatus))
        || (websiteDealStatuses.has(previous) && websitePreDealStatuses.has(savedStatus))
      );
      if (crossedWebsiteStageBoundary) {
        window.location.reload();
        return;
      }


    } catch (error) {
      field.value = previous;
      window.alert(error.message || 'Website Inquiry status could not be updated. Try again.');
    } finally {
      field.disabled = false;
    }
  };

  const settleWebsiteStatusDecision = (confirmed) => {
    const pending = pendingWebsiteStatusDecision;
    pendingWebsiteStatusDecision = null;
    if (websiteStatusConfirm?.open) websiteStatusConfirm.close();
    if (!pending) return;

    const {field, previous, status} = pending;
    field.disabled = false;
    if (confirmed) {
      saveWebsiteInquiryStatus(field, previous, status, true);
    } else {
      field.value = previous;
      field.dataset.websiteInquiryStartStatus = previous;
    }
  };

  websiteStatusConfirmYes?.addEventListener('click', () => settleWebsiteStatusDecision(true));
  websiteStatusConfirmNo?.addEventListener('click', () => settleWebsiteStatusDecision(false));
  websiteStatusConfirm?.addEventListener('cancel', (event) => {
    event.preventDefault();
    settleWebsiteStatusDecision(false);
  });

  page.addEventListener('change', (event) => {
    const field = event.target.closest('[data-website-inquiry-status]');
    if (!(field instanceof HTMLSelectElement)) return;
    const previous = field.dataset.websiteInquiryCurrentStatus || field.dataset.websiteInquiryStartStatus || '';
    const status = field.value || '';
    if (!status || status === previous) return;

    const leavingDealPipeline = websiteDealStatuses.has(previous) && websitePreDealStatuses.has(status);
    if (!leavingDealPipeline) {
      saveWebsiteInquiryStatus(field, previous, status, false);
      return;
    }

    const label = websiteStatusLabels[status] || status;
    const text = `Are you sure you want to change this Website Inquiry to ${label}? This will remove its linked Deal from the Deals page. Your linked Deal details will stay preserved.`;
    if (websiteStatusConfirmMessage) websiteStatusConfirmMessage.textContent = text;
    pendingWebsiteStatusDecision = {field, previous, status};
    field.disabled = true;

    if (websiteStatusConfirm && typeof websiteStatusConfirm.showModal === 'function') {
      websiteStatusConfirm.showModal();
      return;
    }

    settleWebsiteStatusDecision(window.confirm(text));
  });

  viewerClose?.addEventListener('click', closeViewer);
  viewer?.addEventListener('cancel', closeViewer);
  viewer?.addEventListener('click', (event) => {
    if (event.target === viewer) closeViewer();
  });

  websiteNotesSave?.addEventListener('click', async () => {
    if (!notesViewerInput || !notesSource) return;
    websiteNotesSave.disabled = true;
    try {
      await RSFConversationTimeline.saveManualNote(
        websiteNotesTimelineUrl,
        notesViewerInput.value,
        notesSource.dataset.csrfToken || ''
      );
      notesViewerInput.value = '';
      await RSFConversationTimeline.load(
        websiteNotesTimelineUrl,
        websiteConversationTimeline,
        websiteCallAction,
        websiteEmailAction,
        {
          csrfToken: notesSource.dataset.csrfToken || '',
          onLegacyChanged: (value) => {
            if (!notesSource) return;
            notesSource.value = value;
            notesSource.dataset.websiteNotesStartValue = value;
          }
        }
      );
      notesViewerInput.focus();
    } catch (error) {
      window.alert(error.message || 'Manual note could not be saved.');
    } finally {
      websiteNotesSave.disabled = false;
    }
  });
  notesViewerInput?.addEventListener('keydown', (event) => {
    if (event.isComposing) return;
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      websiteNotesSave?.click();
    }
  });
  notesViewerClose?.addEventListener('click', closeWebsiteNotesViewer);
  notesViewer?.addEventListener('cancel', () => {
    notesSource = null;
    websiteNotesTimelineUrl = '';
    if (notesViewerInput) notesViewerInput.value = '';
  });
  notesViewer?.addEventListener('click', (event) => {
    if (event.target === notesViewer) closeWebsiteNotesViewer();
  });
})();


(() => {
  const content = document.querySelector('.main-area .content-wrap');
  const panel = document.querySelector('[data-workspace-visual-panel]');
  if (!content || !panel) return;

  const closeButton = panel.querySelector('[data-workspace-visual-close]');
  const textRange = panel.querySelector('[data-workspace-visual-text]');
  const fieldRange = panel.querySelector('[data-workspace-visual-field]');
  const cardRange = panel.querySelector('[data-workspace-visual-card]');
  const textOutput = panel.querySelector('[data-workspace-visual-text-output]');
  const fieldOutput = panel.querySelector('[data-workspace-visual-field-output]');
  const cardOutput = panel.querySelector('[data-workspace-visual-card-output]');
  const textMaxButton = panel.querySelector('[data-workspace-visual-text-max]');

  if (!(textRange instanceof HTMLInputElement) ||
      !(fieldRange instanceof HTMLInputElement) ||
      !(cardRange instanceof HTMLInputElement)) return;

  const storageKey = 'rsf-workspace-content-display-v1';
  const clamp = (value) => Math.max(0, Math.min(100, Number(value) || 0));
  const mix = (from, to, amount) => {
    const parse = (hex) => [
      parseInt(hex.slice(1, 3), 16),
      parseInt(hex.slice(3, 5), 16),
      parseInt(hex.slice(5, 7), 16)
    ];
    const a = parse(from);
    const b = parse(to);
    const t = clamp(amount) / 100;
    const channels = a.map((value, index) => Math.round(value + (b[index] - value) * t));
    return '#' + channels.map((value) => value.toString(16).padStart(2, '0')).join('');
  };

  const apply = () => {
    const textValue = clamp(textRange.value);
    const fieldValue = clamp(fieldRange.value);
    const cardValue = clamp(cardRange.value);

    textRange.value = String(textValue);
    fieldRange.value = String(fieldValue);
    cardRange.value = String(cardValue);
    if (textOutput) textOutput.textContent = String(textValue);
    if (fieldOutput) fieldOutput.textContent = String(fieldValue);
    if (cardOutput) cardOutput.textContent = String(cardValue);

    content.style.setProperty('--rsf-visual-text-ink', mix('#44564f', '#000000', textValue));
    content.style.setProperty('--rsf-visual-text-muted', mix('#8b9893', '#17251f', textValue));
    content.style.setProperty('--rsf-visual-field-border', mix('#e7eeeb', '#809b90', fieldValue));
    content.style.setProperty('--rsf-visual-card-border', mix('#e1eae6', '#759186', cardValue));
    content.style.setProperty('--rsf-visual-card-shadow-alpha', (0.025 + (cardValue / 100) * 0.155).toFixed(3));

    try {
      window.localStorage.setItem(storageKey, JSON.stringify({
        text: textValue,
        field: fieldValue,
        card: cardValue
      }));
    } catch (_error) {}
  };

  try {
    const saved = JSON.parse(window.localStorage.getItem(storageKey) || 'null');
    if (saved && typeof saved === 'object') {
      textRange.value = String(clamp(saved.text ?? 55));
      fieldRange.value = String(clamp(saved.field ?? 55));
      cardRange.value = String(clamp(saved.card ?? 55));
    }
  } catch (_error) {}

  const setOpen = (open) => {
    panel.classList.toggle('is-open', open);
    panel.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (open) window.setTimeout(() => textRange.focus(), 0);
  };

  [textRange, fieldRange, cardRange].forEach((range) => {
    range.addEventListener('input', apply);
  });

  textMaxButton?.addEventListener('click', () => {
    textRange.value = '100';
    apply();
  });

  closeButton?.addEventListener('click', () => setOpen(false));

  document.addEventListener('keydown', (event) => {
    if (event.repeat || event.metaKey || event.shiftKey || event.ctrlKey) return;
    if (!event.altKey || String(event.key).toLowerCase() !== 'z') return;
    event.preventDefault();
    setOpen(!panel.classList.contains('is-open'));
  });

  apply();
})();


(() => {
  const page = document.querySelector('[data-master-records-page]');
  if (!page) return;

  const rows = Array.from(page.querySelectorAll('[data-master-record-row]'));
  const statusButtons = Array.from(page.querySelectorAll('[data-records-status-filter]'));
  const sourceButtons = Array.from(page.querySelectorAll('[data-records-source-filter]'));
  const searchInput = page.querySelector('[data-records-search]');
  const filterInput = page.querySelector('[data-records-filter-input]');
  const sourceInput = page.querySelector('[data-records-source-input]');
  const empty = page.querySelector('[data-records-empty]');
  const filterEmpty = page.querySelector('[data-records-filter-empty]');
  const selectAll = page.querySelector('[data-records-select-all]');
  const rowChecks = Array.from(page.querySelectorAll('[data-record-row-check]'));
  const selectedCount = page.querySelector('[data-records-selected-count]');
  const deleteTrigger = page.querySelector('[data-records-delete-trigger]');
  const bulkForm = page.querySelector('[data-records-bulk-form]');
  const confirmDialog = page.querySelector('[data-records-delete-confirm]');
  const confirmMessage = page.querySelector('[data-records-delete-confirm-message]');
  const confirmYes = page.querySelector('[data-records-delete-yes]');
  const confirmNo = page.querySelector('[data-records-delete-no]');

  let activeStatus = page.dataset.recordsInitialFilter || 'ALL';
  let activeSource = page.dataset.recordsInitialSource || 'ALL';
  let searchTerm = '';

  const visibleRowChecks = () => rowChecks.filter((check) => {
    const row = check.closest('[data-master-record-row]');
    return row && !row.hidden;
  });

  const visibleDeletableChecks = () => visibleRowChecks().filter((check) => !check.disabled);

  const clearSelection = () => {
    rowChecks.forEach((check) => { check.checked = false; });
    if (selectAll) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    }
  };

  const updateSelection = () => {
    const selected = rowChecks.filter((check) => check.checked && !check.disabled);
    const visibleChecks = visibleRowChecks();
    const visibleDeletable = visibleDeletableChecks();
    const allVisibleSelected = visibleChecks.length > 0
      && visibleChecks.every((check) => !check.disabled && check.checked);

    if (selectedCount) selectedCount.textContent = `Selected ${selected.length}`;
    if (deleteTrigger) deleteTrigger.disabled = selected.length === 0;

    if (selectAll) {
      selectAll.checked = allVisibleSelected;
      selectAll.indeterminate = false;
      selectAll.disabled = visibleDeletable.length === 0;
    }
  };

  const applyFilters = () => {
    rows.forEach((row) => {
      const statusMatch = activeStatus === 'ALL' || row.dataset.recordStatus === activeStatus;
      const sourceMatch = activeSource === 'ALL' || row.dataset.recordSource === activeSource;
      const searchMatch = !searchTerm || (row.dataset.recordSearch || '').includes(searchTerm);
      row.hidden = !(statusMatch && sourceMatch && searchMatch);
    });

    statusButtons.forEach((button) => {
      const active = button.dataset.recordsStatusFilter === activeStatus;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    sourceButtons.forEach((button) => {
      const active = button.dataset.recordsSourceFilter === activeSource;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    if (filterInput) filterInput.value = activeStatus;
    if (sourceInput) sourceInput.value = activeSource;

    const visibleRows = rows.filter((row) => !row.hidden);
    if (empty) empty.hidden = rows.length !== 0;
    if (filterEmpty) filterEmpty.hidden = rows.length === 0 || visibleRows.length !== 0;
    updateSelection();
  };

  statusButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeStatus = button.dataset.recordsStatusFilter || 'ALL';
      clearSelection();
      applyFilters();
    });
  });

  sourceButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeSource = button.dataset.recordsSourceFilter || 'ALL';
      clearSelection();
      applyFilters();
    });
  });

  searchInput?.addEventListener('input', () => {
    searchTerm = String(searchInput.value || '').trim().toLowerCase();
    clearSelection();
    applyFilters();
  });

  selectAll?.addEventListener('change', () => {
    const shouldSelect = selectAll.checked;
    visibleDeletableChecks().forEach((check) => { check.checked = shouldSelect; });
    updateSelection();
  });

  rowChecks.forEach((check) => check.addEventListener('change', updateSelection));

  const closeConfirm = () => {
    if (confirmDialog?.open) confirmDialog.close();
  };

  deleteTrigger?.addEventListener('click', () => {
    const count = rowChecks.filter((check) => check.checked && !check.disabled).length;
    if (!count || !bulkForm) return;

    const text = `Permanently delete ${count} selected inactive master Record${count === 1 ? '' : 's'}? This removes the linked Prospect/Website source data, Deals, Deal documents, and dedicated history for those Records. Shared client conversations still used by other records are preserved. This cannot be undone. Active Deal / Demo / Proposal / Decision Records are protected.`;
    if (confirmMessage) confirmMessage.textContent = text;

    if (confirmDialog && typeof confirmDialog.showModal === 'function') {
      confirmDialog.showModal();
      return;
    }

    if (window.confirm(text)) bulkForm.requestSubmit();
  });

  confirmYes?.addEventListener('click', () => {
    closeConfirm();
    bulkForm?.requestSubmit();
  });
  confirmNo?.addEventListener('click', closeConfirm);
  confirmDialog?.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeConfirm();
  });

  applyFilters();
})();

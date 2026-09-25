(() => {
  const year = document.querySelector('[data-year]');
  if (year) year.textContent = new Date().getFullYear();

  const header = document.querySelector('[data-header]');
  const updateHeader = () => header?.classList.toggle('scrolled', window.scrollY > 12);
  updateHeader();
  window.addEventListener('scroll', updateHeader, { passive: true });

  const toggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');
  const closeNav = () => {
    if (!toggle || !nav) return;
    nav.classList.remove('open');
    document.body.classList.remove('nav-open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open navigation');
  };
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      document.body.classList.toggle('nav-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });
    nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeNav));
    document.addEventListener('click', (event) => {
      if (nav.classList.contains('open') && !nav.contains(event.target) && !toggle.contains(event.target)) closeNav();
    });
  }

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const revealItems = [...document.querySelectorAll('.reveal')];
  if ('IntersectionObserver' in window && !reducedMotion) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -36px 0px' });
    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add('is-visible'));
  }

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', (event) => {
      const id = anchor.getAttribute('href');
      if (!id || id === '#') return;
      const target = document.querySelector(id);
      if (!target) return;
      event.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - 120;
      window.scrollTo({ top, behavior: reducedMotion ? 'auto' : 'smooth' });
      history.replaceState(null, '', id);
    });
  });


  const systemSearch = document.querySelector('[data-system-search]');
  const systemSearchInput = document.querySelector('[data-system-search-input]');
  const systemSearchClear = document.querySelector('[data-system-search-clear]');
  const systemSearchStatus = document.querySelector('[data-system-search-status]');
  const systemSearchEmpty = document.querySelector('[data-system-search-empty]');
  const systemCards = [...document.querySelectorAll('[data-system-card]')];

  if (systemSearch && systemSearchInput && systemCards.length) {
    systemSearch.hidden = false;

    const normalizeSearchText = (value) => (value || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();

    const cardSearchText = new Map(
      systemCards.map((card) => [card, normalizeSearchText(card.dataset.search)])
    );
    const filterTimers = new Map();

    const setCardVisible = (card, visible) => {
      if (filterTimers.has(card)) {
        window.clearTimeout(filterTimers.get(card));
        filterTimers.delete(card);
      }

      card.dataset.searchVisible = visible ? 'true' : 'false';
      if (visible) {
        if (card.hidden) {
          card.hidden = false;
          if (!reducedMotion && card.animate) {
            card.animate(
              [{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'translateY(0)' }],
              { duration: 150, easing: 'ease-out' }
            );
          }
        }
        return;
      }

      if (card.hidden) return;
      if (reducedMotion || !card.animate) {
        card.hidden = true;
        return;
      }

      card.animate(
        [{ opacity: 1 }, { opacity: 0 }],
        { duration: 120, easing: 'ease-in' }
      );
      const timer = window.setTimeout(() => {
        if (card.dataset.searchVisible === 'false') card.hidden = true;
        filterTimers.delete(card);
      }, 125);
      filterTimers.set(card, timer);
    };

    const updateSystemSearch = () => {
      const query = normalizeSearchText(systemSearchInput.value);
      const tokens = query.split(' ').filter(Boolean);
      let matches = 0;

      systemCards.forEach((card) => {
        const haystack = cardSearchText.get(card) || '';
        const visible = tokens.length === 0 || tokens.every((token) => haystack.includes(token));
        if (visible) matches += 1;
        setCardVisible(card, visible);
      });

      if (systemSearchClear) systemSearchClear.hidden = query.length === 0;
      if (systemSearchEmpty) systemSearchEmpty.hidden = matches !== 0;

      if (systemSearchStatus) {
        if (!query) {
          systemSearchStatus.textContent = `${systemCards.length} ${systemCards.length === 1 ? 'system' : 'systems'} available`;
        } else if (matches === 0) {
          systemSearchStatus.textContent = 'No matching systems';
        } else {
          systemSearchStatus.textContent = `${matches} matching ${matches === 1 ? 'system' : 'systems'}`;
        }
      }
    };

    systemSearchInput.addEventListener('input', updateSystemSearch);
    systemSearchInput.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && systemSearchInput.value) {
        event.stopPropagation();
        systemSearchInput.value = '';
        updateSystemSearch();
        systemSearchInput.focus();
      }
    });
    systemSearchClear?.addEventListener('click', () => {
      systemSearchInput.value = '';
      updateSystemSearch();
      systemSearchInput.focus();
    });

    updateSystemSearch();
  }


  const caseJump = document.querySelector('[data-case-jump]');
  const caseSections = [...document.querySelectorAll('[data-case-section]')];
  if (caseJump && caseSections.length) {
    const jumpLinks = [...caseJump.querySelectorAll('a[href^="#"]')];
    const setActiveSection = (id) => {
      jumpLinks.forEach((link) => {
        const active = link.getAttribute('href') === `#${id}`;
        link.classList.toggle('active-section', active);
        if (active) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    };
    setActiveSection(caseSections[0].id);
    if ('IntersectionObserver' in window) {
      const sectionObserver = new IntersectionObserver((entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveSection(visible[0].target.id);
      }, { rootMargin: '-34% 0px -58% 0px', threshold: 0 });
      caseSections.forEach((section) => sectionObserver.observe(section));
    }
  }

  const overlay = document.querySelector('[data-lightbox-overlay]');
  const lightboxImage = document.querySelector('[data-lightbox-image]');
  const lightboxCaption = document.querySelector('[data-lightbox-caption]');
  const lightboxClose = document.querySelector('[data-lightbox-close]');
  let lastFocus = null;

  const closeLightbox = () => {
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  };

  document.querySelectorAll('[data-lightbox]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      if (!overlay || !lightboxImage) return;
      lastFocus = trigger;
      lightboxImage.src = trigger.dataset.lightbox;
      lightboxImage.alt = trigger.dataset.caption || 'Project screen preview';
      if (lightboxCaption) lightboxCaption.textContent = trigger.dataset.caption || '';
      overlay.classList.add('open');
      overlay.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      lightboxClose?.focus();
    });
  });
  lightboxClose?.addEventListener('click', closeLightbox);
  overlay?.addEventListener('click', (event) => {
    if (event.target === overlay) closeLightbox();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeNav();
      closeLightbox();
    }
  });

  const toasts = document.querySelectorAll('.toast');
  if (toasts.length) setTimeout(() => toasts.forEach((toast) => toast.remove()), 6500);
})();

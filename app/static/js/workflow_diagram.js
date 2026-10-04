/* RSF Workflow Diagram v1.18.205 */
(() => {
  const page = document.querySelector('[data-workflow-diagram]');
  if (!page) return;

  const viewport = page.querySelector('[data-workflow-viewport]');
  const board = page.querySelector('[data-workflow-board]');
  const svg = page.querySelector('[data-workflow-svg]');
  const modelNode = page.querySelector('[data-workflow-model]');
  if (!viewport || !board || !svg || !modelNode) return;

  let model;
  try {
    model = JSON.parse(modelNode.textContent || '{}');
  } catch (_error) {
    return;
  }

  const nodes = new Map(
    Array.from(board.querySelectorAll('[data-workflow-node]')).map((node) => [node.dataset.workflowNode, node])
  );
  const inspector = page.querySelector('[data-workflow-inspector]');
  const inspectorEmpty = page.querySelector('[data-workflow-inspector-empty]');
  const inspectorContent = page.querySelector('[data-workflow-inspector-content]');
  const detailEyebrow = page.querySelector('[data-workflow-detail-eyebrow]');
  const detailTitle = page.querySelector('[data-workflow-detail-title]');
  const detailSummary = page.querySelector('[data-workflow-detail-summary]');
  const detailList = page.querySelector('[data-workflow-detail-list]');
  const detailLink = page.querySelector('[data-workflow-detail-link]');
  const zoomOutput = page.querySelector('[data-workflow-zoom]');

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const view = { scale: 1, x: 0, y: 0 };
  let panning = null;
  let autoFit = true;

  const setTransform = () => {
    board.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
    if (zoomOutput) zoomOutput.textContent = `${Math.round(view.scale * 100)}%`;
  };

  const nodePoint = (node, anchor) => {
    const left = node.offsetLeft;
    const top = node.offsetTop;
    const width = node.offsetWidth;
    const height = node.offsetHeight;
    if (anchor === 'left') return { x: left, y: top + height / 2 };
    if (anchor === 'right') return { x: left + width, y: top + height / 2 };
    if (anchor === 'top') return { x: left + width / 2, y: top };
    return { x: left + width / 2, y: top + height };
  };

  const curvePath = (start, end, sourceAnchor, targetAnchor) => {
    const horizontal = ['left', 'right'].includes(sourceAnchor) || ['left', 'right'].includes(targetAnchor);
    if (horizontal) {
      const distance = Math.max(42, Math.abs(end.x - start.x) * 0.40);
      const c1x = start.x + (sourceAnchor === 'left' ? -distance : sourceAnchor === 'right' ? distance : 0);
      const c2x = end.x + (targetAnchor === 'left' ? -distance : targetAnchor === 'right' ? distance : 0);
      return `M ${start.x} ${start.y} C ${c1x} ${start.y}, ${c2x} ${end.y}, ${end.x} ${end.y}`;
    }
    const distance = Math.max(38, Math.abs(end.y - start.y) * 0.42);
    const c1y = start.y + (sourceAnchor === 'top' ? -distance : distance);
    const c2y = end.y + (targetAnchor === 'top' ? -distance : distance);
    return `M ${start.x} ${start.y} C ${start.x} ${c1y}, ${end.x} ${c2y}, ${end.x} ${end.y}`;
  };

  const createSvg = (name, attrs = {}) => {
    const element = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  };

  const drawEdges = () => {
    svg.replaceChildren();
    const defs = createSvg('defs');
    for (const style of ['primary', 'secondary', 'sync', 'conditional', 'action', 'data']) {
      const marker = createSvg('marker', {
        id: `workflow-arrow-${style}`,
        viewBox: '0 0 10 10',
        refX: 9,
        refY: 5,
        markerWidth: 6,
        markerHeight: 6,
        orient: 'auto-start-reverse',
      });
      marker.appendChild(createSvg('path', {
        d: 'M 0 0 L 10 5 L 0 10 z',
        class: `workflow-diagram-arrow workflow-diagram-arrow--${style}`,
      }));
      defs.appendChild(marker);
    }
    svg.appendChild(defs);

    (model.edges || []).forEach((edge) => {
      const source = nodes.get(edge.source);
      const target = nodes.get(edge.target);
      if (!source || !target) return;
      const sourceAnchor = edge.source_anchor || 'right';
      const targetAnchor = edge.target_anchor || 'left';
      const start = nodePoint(source, sourceAnchor);
      const end = nodePoint(target, targetAnchor);
      const style = edge.style || 'primary';
      const path = createSvg('path', {
        d: curvePath(start, end, sourceAnchor, targetAnchor),
        class: `workflow-diagram-edge workflow-diagram-edge--${style}`,
        'marker-end': `url(#workflow-arrow-${style})`,
      });
      svg.appendChild(path);

      if (edge.label) {
        const middle = path.getPointAtLength(path.getTotalLength() / 2);
        const label = createSvg('text', {
          x: middle.x,
          y: middle.y - 5,
          class: 'workflow-diagram-edge-label',
          'text-anchor': 'middle',
        });
        label.textContent = edge.label;
        svg.appendChild(label);
      }
    });
  };

  const getContentBounds = () => {
    const elements = Array.from(board.querySelectorAll('.workflow-diagram-section,[data-workflow-node]'));
    if (!elements.length) {
      return { left: 0, top: 0, right: Number(model.board_width || 1), bottom: Number(model.board_height || 1) };
    }
    let left = Infinity;
    let top = Infinity;
    let right = -Infinity;
    let bottom = -Infinity;
    elements.forEach((element) => {
      left = Math.min(left, element.offsetLeft);
      top = Math.min(top, element.offsetTop);
      right = Math.max(right, element.offsetLeft + element.offsetWidth);
      bottom = Math.max(bottom, element.offsetTop + element.offsetHeight);
    });
    return { left, top, right, bottom };
  };

  const fitBounds = (bounds, padding = 24) => {
    const width = Math.max(1, bounds.right - bounds.left);
    const height = Math.max(1, bounds.bottom - bounds.top);
    const availableWidth = Math.max(1, viewport.clientWidth - padding * 2);
    const availableHeight = Math.max(1, viewport.clientHeight - padding * 2);
    const scale = clamp(Math.min(availableWidth / width, availableHeight / height), 0.58, 1);
    view.scale = scale;
    view.x = (viewport.clientWidth - width * scale) / 2 - bounds.left * scale;
    view.y = (viewport.clientHeight - height * scale) / 2 - bounds.top * scale;
    setTransform();
  };

  const fitView = () => {
    autoFit = true;
    fitBounds(getContentBounds(), 22);
  };

  const zoomAtPoint = (nextScale, pointerX, pointerY) => {
    const scale = clamp(nextScale, 0.46, 1.7);
    const boardX = (pointerX - view.x) / view.scale;
    const boardY = (pointerY - view.y) / view.scale;
    view.scale = scale;
    view.x = pointerX - boardX * scale;
    view.y = pointerY - boardY * scale;
    autoFit = false;
    setTransform();
  };

  const zoomAtCenter = (nextScale) => {
    zoomAtPoint(nextScale, viewport.clientWidth / 2, viewport.clientHeight / 2);
  };

  const clearSelection = () => {
    nodes.forEach((node) => node.classList.remove('is-selected'));
    page.classList.remove('has-workflow-selection');
    inspector?.setAttribute('aria-hidden', 'true');
    if (inspectorEmpty) inspectorEmpty.hidden = false;
    if (inspectorContent) inspectorContent.hidden = true;
  };

  const nodeModel = new Map((model.nodes || []).map((item) => [item.id, item]));
  const selectNode = (id) => {
    const item = nodeModel.get(id);
    if (!item) return;
    nodes.forEach((node) => node.classList.toggle('is-selected', node.dataset.workflowNode === id));
    page.classList.add('has-workflow-selection');
    inspector?.setAttribute('aria-hidden', 'false');
    if (inspectorEmpty) inspectorEmpty.hidden = true;
    if (inspectorContent) inspectorContent.hidden = false;
    if (detailEyebrow) detailEyebrow.textContent = item.eyebrow || 'NODE DETAILS';
    if (detailTitle) detailTitle.textContent = item.label || '';
    if (detailSummary) detailSummary.textContent = item.summary || '';
    if (detailList) {
      detailList.replaceChildren();
      (item.details || []).forEach((detail) => {
        const li = document.createElement('li');
        li.textContent = detail;
        detailList.appendChild(li);
      });
    }
    if (detailLink) {
      if (item.href) {
        detailLink.href = item.href;
        detailLink.hidden = false;
      } else {
        detailLink.hidden = true;
        detailLink.removeAttribute('href');
      }
    }
  };

  nodes.forEach((node, id) => {
    node.addEventListener('click', () => selectNode(id));
  });
  page.querySelector('[data-workflow-detail-close]')?.addEventListener('click', clearSelection);

  viewport.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || event.target.closest('[data-workflow-node]')) return;
    panning = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: view.x,
      originY: view.y,
    };
    autoFit = false;
    viewport.classList.add('is-panning');
    try { viewport.setPointerCapture(event.pointerId); } catch (_error) {}
    event.preventDefault();
  });
  viewport.addEventListener('pointermove', (event) => {
    if (!panning || event.pointerId !== panning.pointerId) return;
    view.x = panning.originX + (event.clientX - panning.startX);
    view.y = panning.originY + (event.clientY - panning.startY);
    setTransform();
  });
  const endPan = (event) => {
    if (!panning || event.pointerId !== panning.pointerId) return;
    try { viewport.releasePointerCapture(event.pointerId); } catch (_error) {}
    panning = null;
    viewport.classList.remove('is-panning');
  };
  viewport.addEventListener('pointerup', endPan);
  viewport.addEventListener('pointercancel', endPan);

  viewport.addEventListener('wheel', (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const rect = viewport.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    zoomAtPoint(view.scale * (event.deltaY < 0 ? 1.08 : 0.92), pointerX, pointerY);
  }, { passive: false });

  page.querySelector('[data-workflow-zoom-in]')?.addEventListener('click', () => zoomAtCenter(view.scale + 0.10));
  page.querySelector('[data-workflow-zoom-out]')?.addEventListener('click', () => zoomAtCenter(view.scale - 0.10));
  page.querySelector('[data-workflow-fit]')?.addEventListener('click', fitView);
  page.querySelector('[data-workflow-reset]')?.addEventListener('click', () => {
    clearSelection();
    fitView();
  });

  const redraw = () => window.requestAnimationFrame(drawEdges);
  const resizeObserver = new ResizeObserver(() => {
    redraw();
    if (autoFit) fitView();
  });
  resizeObserver.observe(viewport);

  const initialLayout = () => {
    drawEdges();
    fitView();
  };
  window.requestAnimationFrame(() => window.requestAnimationFrame(initialLayout));
  if (document.fonts?.ready) {
    document.fonts.ready.then(() => window.requestAnimationFrame(initialLayout)).catch(() => {});
  }
})();

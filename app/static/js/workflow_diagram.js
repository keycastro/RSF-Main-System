/* RSF Workflow Diagram v1.18.203 */
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
      const distance = Math.max(55, Math.abs(end.x - start.x) * 0.45);
      const c1x = start.x + (sourceAnchor === 'left' ? -distance : sourceAnchor === 'right' ? distance : 0);
      const c2x = end.x + (targetAnchor === 'left' ? -distance : targetAnchor === 'right' ? distance : 0);
      return `M ${start.x} ${start.y} C ${c1x} ${start.y}, ${c2x} ${end.y}, ${end.x} ${end.y}`;
    }
    const distance = Math.max(45, Math.abs(end.y - start.y) * 0.45);
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
          y: middle.y - 6,
          class: 'workflow-diagram-edge-label',
          'text-anchor': 'middle',
        });
        label.textContent = edge.label;
        svg.appendChild(label);
      }
    });
  };

  const fitView = () => {
    const boardWidth = Number(model.board_width || board.offsetWidth || 1);
    const boardHeight = Number(model.board_height || board.offsetHeight || 1);
    const availableWidth = Math.max(1, viewport.clientWidth - 34);
    const availableHeight = Math.max(1, viewport.clientHeight - 34);
    view.scale = clamp(Math.min(availableWidth / boardWidth, availableHeight / boardHeight), 0.32, 1);
    view.x = (viewport.clientWidth - boardWidth * view.scale) / 2;
    view.y = (viewport.clientHeight - boardHeight * view.scale) / 2;
    setTransform();
  };

  const zoomAtCenter = (nextScale) => {
    const scale = clamp(nextScale, 0.32, 1.7);
    const centerX = viewport.clientWidth / 2;
    const centerY = viewport.clientHeight / 2;
    const boardX = (centerX - view.x) / view.scale;
    const boardY = (centerY - view.y) / view.scale;
    view.scale = scale;
    view.x = centerX - boardX * scale;
    view.y = centerY - boardY * scale;
    setTransform();
  };

  const nodeModel = new Map((model.nodes || []).map((item) => [item.id, item]));
  const selectNode = (id) => {
    const item = nodeModel.get(id);
    if (!item) return;
    nodes.forEach((node) => node.classList.toggle('is-selected', node.dataset.workflowNode === id));
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

  viewport.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || event.target.closest('[data-workflow-node]')) return;
    panning = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: view.x,
      originY: view.y,
    };
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
    const boardX = (pointerX - view.x) / view.scale;
    const boardY = (pointerY - view.y) / view.scale;
    const scale = clamp(view.scale * (event.deltaY < 0 ? 1.08 : 0.92), 0.32, 1.7);
    view.scale = scale;
    view.x = pointerX - boardX * scale;
    view.y = pointerY - boardY * scale;
    setTransform();
  }, { passive: false });

  page.querySelector('[data-workflow-zoom-in]')?.addEventListener('click', () => zoomAtCenter(view.scale + 0.12));
  page.querySelector('[data-workflow-zoom-out]')?.addEventListener('click', () => zoomAtCenter(view.scale - 0.12));
  page.querySelector('[data-workflow-fit]')?.addEventListener('click', fitView);
  page.querySelector('[data-workflow-reset]')?.addEventListener('click', () => {
    view.scale = 1;
    view.x = 24;
    view.y = 24;
    setTransform();
  });

  const redraw = () => window.requestAnimationFrame(drawEdges);
  window.addEventListener('resize', () => {
    redraw();
    fitView();
  });

  drawEdges();
  fitView();
})();

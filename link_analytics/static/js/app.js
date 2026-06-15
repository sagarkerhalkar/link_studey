(() => {
  'use strict';
  const root = document.documentElement;
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  const applyThemeUI = () => {
    const theme = root.dataset.theme || 'dark';
    document.querySelectorAll('[data-theme-icon]').forEach((el) => { el.textContent = theme === 'dark' ? '☀' : '☾'; });
    document.querySelectorAll('[data-theme-label]').forEach((el) => { el.textContent = theme === 'dark' ? 'Light' : 'Dark'; });
    if (themeMeta) themeMeta.content = theme === 'dark' ? '#07101f' : '#f5f7fb';
  };
  applyThemeUI();
  document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('la-theme', root.dataset.theme);
      applyThemeUI();
    });
  });

  const openSidebar = () => document.body.classList.add('sidebar-open');
  const closeSidebar = () => document.body.classList.remove('sidebar-open');
  document.querySelectorAll('[data-sidebar-open]').forEach((el) => el.addEventListener('click', openSidebar));
  document.querySelectorAll('[data-sidebar-close]').forEach((el) => el.addEventListener('click', closeSidebar));
  window.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSidebar(); });

  document.querySelectorAll('.flash button').forEach((button) => button.addEventListener('click', () => button.parentElement.remove()));
  document.querySelectorAll('form[data-confirm]').forEach((form) => form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));

  const copyValue = async (button) => {
    const value = button.dataset.copy;
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      button.classList.add('copied');
      const original = button.dataset.copyLabel || button.textContent;
      button.dataset.copyLabel = original;
      button.textContent = 'Copied';
      setTimeout(() => { button.textContent = original; button.classList.remove('copied'); }, 1200);
    } catch (_error) {
      window.prompt('Copy this link:', value);
    }
  };
  document.querySelectorAll('[data-copy]').forEach((button) => button.addEventListener('click', () => copyValue(button)));

  const tagField = document.querySelector('[name="custom_tag"]');
  const preview = document.getElementById('short-preview');
  if (tagField && preview) {
    const update = () => { preview.textContent = `${preview.dataset.base}${tagField.value || 'your-tag'}`; };
    tagField.addEventListener('input', update);
    update();
  }

  const revealItems = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.08 });
    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add('visible'));
  }

  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.querySelectorAll('[data-tilt]').forEach((card) => {
      card.addEventListener('pointermove', (event) => {
        if (window.innerWidth < 900) return;
        const rect = card.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width) - 0.5;
        const y = ((event.clientY - rect.top) / rect.height) - 0.5;
        card.style.transform = `perspective(1100px) rotateX(${-y * 2.2}deg) rotateY(${x * 2.8}deg) translateY(-2px)`;
      });
      card.addEventListener('pointerleave', () => { card.style.transform = ''; });
    });
  }
})();

(() => {
  'use strict';
  const number = (value) => Number(value || 0).toLocaleString();
  const text = (value, fallback = 'Unknown') => (value === null || value === undefined || value === '' ? fallback : String(value));
  const humanDate = (value) => {
    if (!value) return 'Unknown';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  };
  const setText = (element, value) => {
    if (!element || element.textContent === value) return;
    element.textContent = value;
    element.classList.remove('live-changed');
    void element.offsetWidth;
    element.classList.add('live-changed');
  };

  const renderBars = (chart, points) => {
    if (!chart) return;
    const items = Array.isArray(points) ? points : [];
    const signature = JSON.stringify(items);
    if (chart.dataset.signature === signature) return;
    chart.dataset.signature = signature;
    chart.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'chart-empty';
      empty.textContent = 'Click data will appear here.';
      chart.appendChild(empty);
      return;
    }
    const max = Math.max(...items.map((point) => Number(point[1]) || 0), 1);
    items.slice(-31).forEach(([label, value]) => {
      const column = document.createElement('div');
      column.className = 'bar-column';
      column.title = `${label}: ${value} clicks`;
      const bar = document.createElement('span');
      bar.style.height = `${Math.max(5, (Number(value) / max) * 100)}%`;
      const caption = document.createElement('small');
      caption.textContent = String(label).slice(5);
      column.append(bar, caption);
      chart.appendChild(column);
    });
  };

  const renderRank = (container, items, total) => {
    if (!container) return;
    const rows = Array.isArray(items) ? items : [];
    const signature = JSON.stringify(rows);
    if (container.dataset.signature === signature) return;
    container.dataset.signature = signature;
    container.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'No data yet.';
      container.appendChild(empty);
      return;
    }
    rows.forEach(([label, value]) => {
      const row = document.createElement('div');
      const header = document.createElement('span');
      const name = document.createElement('b');
      const count = document.createElement('small');
      const bar = document.createElement('i');
      name.textContent = text(label);
      count.textContent = `${number(value)} clicks`;
      bar.style.setProperty('--percent', `${Math.min(100, (Number(value) / Math.max(Number(total), 1)) * 100)}%`);
      header.append(name, count);
      row.append(header, bar);
      container.appendChild(row);
    });
  };

  const confidenceBadge = (value) => {
    const badge = document.createElement('span');
    const label = text(value, 'Hidden');
    badge.className = `confidence confidence-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
    badge.textContent = label;
    return badge;
  };

  const renderDeviceCards = (container, devices) => {
    if (!container) return;
    const items = Array.isArray(devices) ? devices : [];
    const signature = JSON.stringify(items);
    if (container.dataset.signature === signature) return;
    container.dataset.signature = signature;
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'No verified devices yet.';
      container.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const card = document.createElement('article');
      card.className = 'device-audience-card';
      const header = document.createElement('header');
      const titleWrap = document.createElement('div');
      const id = document.createElement('span');
      id.className = 'device-id';
      id.textContent = text(item.device_id);
      const title = document.createElement('h3');
      title.textContent = `${text(item.device_label)}${item.model ? ` · ${item.model}` : ''}`;
      const clicks = document.createElement('strong');
      clicks.textContent = `${number(item.clicks)} clicks`;
      titleWrap.append(id, title);
      header.append(titleWrap, clicks);

      const stats = document.createElement('div');
      stats.className = 'device-card-stats';
      [
        [`${number(item.browser_identities)} browser/app identities`],
        [`${text(item.top_platform)} top platform`],
        [`${text(item.os)} OS`],
      ].forEach(([label]) => {
        const span = document.createElement('span');
        span.textContent = label;
        stats.appendChild(span);
      });

      const platformList = document.createElement('div');
      platformList.className = 'device-platform-list';
      (item.platforms || []).forEach((platform) => {
        const pill = document.createElement('span');
        pill.textContent = `${text(platform.label)} · ${number(platform.clicks)}`;
        platformList.appendChild(pill);
      });

      const footer = document.createElement('footer');
      const confidence = document.createElement('span');
      confidence.textContent = `${text(item.identity_confidence, 'Browser-only')} estimate`;
      const seen = document.createElement('span');
      seen.textContent = `${humanDate(item.first_seen)} → ${humanDate(item.last_seen)}`;
      footer.append(confidence, seen);
      card.append(header, stats, platformList, footer);
      container.appendChild(card);
    });
  };

  const renderRecentCards = (container, visits) => {
    if (!container) return;
    const items = Array.isArray(visits) ? visits : [];
    const signature = JSON.stringify(items);
    if (container.dataset.signature === signature) return;
    container.dataset.signature = signature;
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'No verified clicks yet.';
      container.appendChild(empty);
      return;
    }
    items.slice(0, 50).forEach((visit) => {
      const card = document.createElement('article');
      card.className = 'recent-click-card';

      const primary = document.createElement('div');
      primary.className = 'recent-click-primary';
      primary.appendChild(confidenceBadge(visit.confidence));
      const title = document.createElement('h3');
      title.textContent = text(visit.platform);
      const surface = document.createElement('p');
      surface.textContent = text(visit.surface);
      primary.append(title, surface);

      const device = document.createElement('div');
      const deviceLabel = document.createElement('span');
      deviceLabel.textContent = 'Device';
      const deviceValue = document.createElement('strong');
      deviceValue.textContent = `${text(visit.device_label)}${visit.model ? ` · ${visit.model}` : ''}`;
      const deviceId = document.createElement('small');
      deviceId.textContent = text(visit.device_id);
      device.append(deviceLabel, deviceValue, deviceId);

      const browser = document.createElement('div');
      const browserLabel = document.createElement('span');
      browserLabel.textContent = 'Browser / OS';
      const browserValue = document.createElement('strong');
      browserValue.textContent = `${text(visit.browser)} · ${text(visit.os)}`;
      const location = document.createElement('small');
      location.textContent = text(visit.city || visit.region || visit.country);
      browser.append(browserLabel, browserValue, location);

      const evidence = document.createElement('div');
      evidence.className = 'recent-evidence';
      const evidenceLabel = document.createElement('span');
      evidenceLabel.textContent = 'Why';
      const evidenceValue = document.createElement('strong');
      evidenceValue.textContent = text(visit.evidence);
      const date = document.createElement('small');
      date.textContent = humanDate(visit.date);
      evidence.append(evidenceLabel, evidenceValue, date);

      card.append(primary, device, browser, evidence);
      container.appendChild(card);
    });
  };

  const renderFunnel = (container, analytics) => {
    if (!container) return;
    const all = Math.max(Number(analytics.all_requests || 0), 1);
    container.querySelectorAll('[data-funnel-value]').forEach((element) => {
      const key = element.dataset.funnelValue;
      setText(element, number(analytics[key]));
      const bar = element.parentElement.querySelector('i');
      if (bar) bar.style.setProperty('--funnel-width', `${Math.max(3, Math.min(100, (Number(analytics[key] || 0) / all) * 100))}%`);
    });
  };

  const schedulePoll = (fn, failures) => {
    const base = document.hidden ? 6000 : 1500;
    const delay = Math.min(15000, base * (2 ** Math.min(failures, 3)));
    window.setTimeout(fn, delay);
  };

  const liveRoot = document.querySelector('[data-live-analytics]');
  if (liveRoot) {
    const status = liveRoot.querySelector('[data-live-status]');
    const textKeys = new Set(['top_platform', 'top_device', 'top_country']);
    let running = false;
    let failures = 0;
    const poll = async () => {
      if (running) return schedulePoll(poll, failures);
      running = true;
      try {
        const separator = liveRoot.dataset.liveUrl.includes('?') ? '&' : '?';
        const response = await fetch(`${liveRoot.dataset.liveUrl}${separator}_=${Date.now()}`, {
          headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
          cache: 'no-store',
          credentials: 'same-origin',
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        const analytics = payload.analytics || {};
        liveRoot.querySelectorAll('[data-live-value]').forEach((element) => {
          const key = element.dataset.liveValue;
          let value;
          if (key === 'platform_identification_rate') value = `${Number(analytics[key] || 0).toFixed(1)}%`;
          else if (textKeys.has(key)) value = text(analytics[key], 'No data');
          else value = number(analytics[key]);
          setText(element, value);
        });
        const donut = liveRoot.querySelector('[data-live-donut]');
        if (donut) donut.style.setProperty('--identified', `${Math.max(0, Math.min(100, Number(analytics.platform_identification_rate || 0)))}%`);
        renderFunnel(liveRoot.querySelector('[data-live-funnel]'), analytics);
        renderBars(liveRoot.querySelector('[data-live-chart="daily"]'), analytics.daily);
        ['platforms', 'surfaces', 'devices', 'browsers', 'operating_systems', 'countries'].forEach((key) => {
          renderRank(liveRoot.querySelector(`[data-live-rank="${key}"]`), analytics[key], analytics.human);
        });
        renderDeviceCards(liveRoot.querySelector('[data-live-device-cards]'), analytics.device_rows);
        renderRecentCards(liveRoot.querySelector('[data-live-recent-cards]'), analytics.recent);
        failures = 0;
        if (status) {
          status.textContent = `Live · updated ${new Date().toLocaleTimeString()}`;
          status.classList.remove('live-error');
        }
      } catch (error) {
        failures += 1;
        if (status) {
          status.textContent = `Live update reconnecting · ${error.message}`;
          status.classList.add('live-error');
        }
      } finally {
        running = false;
        schedulePoll(poll, failures);
      }
    };
    poll();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  }

  const dashboardRoot = document.querySelector('[data-live-dashboard]');
  if (dashboardRoot) {
    let running = false;
    let failures = 0;
    const pollDashboard = async () => {
      if (running) return schedulePoll(pollDashboard, failures);
      running = true;
      try {
        const response = await fetch(`${dashboardRoot.dataset.liveUrl}?_=${Date.now()}`, {
          headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
          cache: 'no-store', credentials: 'same-origin',
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        dashboardRoot.querySelectorAll('[data-dashboard-value]').forEach((element) => {
          setText(element, number(payload[element.dataset.dashboardValue]));
        });
        (payload.links || []).forEach((item) => {
          const row = dashboardRoot.querySelector(`[data-dashboard-link="${item.id}"]`);
          if (!row) return;
          row.querySelectorAll('[data-link-value]').forEach((element) => {
            setText(element, number(item[element.dataset.linkValue]));
          });
        });
        failures = 0;
      } catch (_error) {
        failures += 1;
      } finally {
        running = false;
        schedulePoll(pollDashboard, failures);
      }
    };
    pollDashboard();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) pollDashboard(); });
  }
})();

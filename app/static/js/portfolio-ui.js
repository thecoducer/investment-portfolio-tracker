// User profile dropdown toggle
(function() {
  const avatarBtn = document.getElementById('userAvatarBtn');
  const dropdown = document.getElementById('userDropdown');
  if (avatarBtn && dropdown) {
    avatarBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      dropdown.classList.toggle('open');
    });
  }
})();

// Sign-out handler
function handleLogout() {
  window.metronFetch('/api/auth/logout', { method: 'POST' })
    .then(() => { window.location.href = '/'; })
    .catch(() => { window.location.href = '/'; });
}

// Close user dropdown when clicking outside
document.addEventListener('click', function(event) {
  const dropdown = document.getElementById('userDropdown');
  const avatarBtn = document.getElementById('userAvatarBtn');
  if (dropdown && avatarBtn && !avatarBtn.contains(event.target) && !dropdown.contains(event.target)) {
    dropdown.classList.remove('open');
  }
});

// ─── Settings Drawer ──────────────────────────────────────────

function openSettingsDrawer() {
  const drawer = document.getElementById('settingsDrawer');
  const backdrop = document.getElementById('drawerBackdrop');
  if (!drawer) return;
  // Close user dropdown first
  const dd = document.getElementById('userDropdown');
  if (dd) dd.classList.remove('open');

  drawer.classList.add('open');
  backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
  loadDrawerAccounts();
}

function closeSettingsDrawer() {
  const drawer = document.getElementById('settingsDrawer');
  const backdrop = document.getElementById('drawerBackdrop');
  if (!drawer) return;
  drawer.classList.remove('open');
  backdrop.classList.remove('open');
  document.body.style.overflow = '';
}

// Close drawer on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeSettingsDrawer();
});

// Open settings drawer when Enter/Space pressed on login banner
document.addEventListener('keydown', function(e) {
  if ((e.key === 'Enter' || e.key === ' ') && document.activeElement && document.activeElement.id === 'loginBanner') {
    e.preventDefault();
    openSettingsDrawer();
  }
});

// ─── Drawer Zerodha Accounts ──────────────────────────────────

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function renderDrawerAccounts(names, sessionValidity, loginUrls) {
  const listEl = document.getElementById('drawerAccountsList');
  if (!listEl) return;
  if (!names.length) {
    listEl.innerHTML = '<div class="drawer-accounts-empty">No accounts connected yet.</div>';
    return;
  }
  sessionValidity = sessionValidity || {};
  loginUrls = loginUrls || {};
  listEl.innerHTML = names.map(name => {
    const isValid = sessionValidity[name] === true;
    const loginUrl = loginUrls[name] || '';
    let statusHtml = '';
    if (!isValid && loginUrl) {
      statusHtml = '<a class="drawer-account-login" href="' + escapeHtml(loginUrl) + '" target="_blank" rel="noopener" title="Session expired \u2013 click to log in">Login</a>';
    } else if (!isValid) {
      statusHtml = '<span class="drawer-account-expired" title="Session expired">Expired</span>';
    } else {
      statusHtml = '<span class="drawer-account-active" title="Session active">\u2713</span>';
    }
    return '<span class="drawer-account-chip' + (isValid ? '' : ' expired') + '">' +
      '<span>' + escapeHtml(name) + '</span>' +
      statusHtml +
      '<button class="drawer-account-chip-remove" data-name="' + escapeHtml(name) + '" title="Remove ' + escapeHtml(name) + '">\u00d7</button>' +
    '</span>';
  }).join('');
  listEl.querySelectorAll('.drawer-account-chip-remove').forEach(btn => {
    btn.addEventListener('click', () => removeDrawerAccount(btn.dataset.name));
  });
}

function loadDrawerAccounts() {
  const listEl = document.getElementById('drawerAccountsList');
  if (!listEl) return;
  listEl.innerHTML = '<div class="drawer-accounts-loading">Loading\u2026</div>';
  window.metronFetch('/api/settings')
    .then(r => r.ok ? r.json() : Promise.reject())
    .then(data => {
      const names = data.zerodha_accounts || [];
      const validity = data.session_validity || {};
      const loginUrls = data.login_urls || {};
      renderDrawerAccounts(names, validity, loginUrls);
    })
    .catch(() => { listEl.innerHTML = '<div class="drawer-accounts-empty">Failed to load accounts.</div>'; });
}

function removeDrawerAccount(name) {
  if (!confirm('Remove account "' + name + '"? This will delete the stored API credentials.')) return;
  window.metronFetch('/api/settings/zerodha/' + encodeURIComponent(name), { method: 'DELETE' })
    .then(r => r.ok ? loadDrawerAccounts() : Promise.reject())
    .catch(() => alert('Failed to remove account.'));
}

// ─── Drawer Add-Account Form ──────────────────────────────────

(function() {
  const addBtn = document.getElementById('drawerAddAccountBtn');
  const formEl = document.getElementById('drawerAddAccountForm');
  const saveBtn = document.getElementById('drawerSaveAccountBtn');
  const cancelBtn = document.getElementById('drawerCancelAccountBtn');
  const status = document.getElementById('drawerSaveStatus');
  const nameInput = document.getElementById('drawer_account_name');
  const keyInput = document.getElementById('drawer_api_key');
  const secretInput = document.getElementById('drawer_api_secret');
  if (!addBtn || !formEl) return;

  function clearForm() {
    if (nameInput) nameInput.value = '';
    if (keyInput) keyInput.value = '';
    if (secretInput) secretInput.value = '';
    if (status) { status.textContent = ''; status.className = 'drawer-save-status'; }
  }

  addBtn.addEventListener('click', () => {
    formEl.classList.remove('hidden');
    addBtn.style.display = 'none';
    if (nameInput) nameInput.focus();
  });

  cancelBtn.addEventListener('click', () => {
    formEl.classList.add('hidden');
    addBtn.style.display = '';
    clearForm();
  });

  saveBtn.addEventListener('click', async () => {
    const account_name = (nameInput.value || '').trim();
    const api_key = (keyInput.value || '').trim();
    const api_secret = (secretInput.value || '').trim();
    if (!account_name || !api_key || !api_secret) {
      status.textContent = 'All fields are required';
      status.className = 'drawer-save-status error';
      return;
    }
    saveBtn.disabled = true;
    status.textContent = '';
    status.className = 'drawer-save-status';
    try {
      const resp = await window.metronFetch('/api/settings/zerodha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_name, api_key, api_secret }),
      });
      const result = await resp.json();
      if (!resp.ok) {
        status.textContent = result.error || 'Save failed';
        status.classList.add('error');
        return;
      }
      loadDrawerAccounts();
      formEl.classList.add('hidden');
      addBtn.style.display = '';
      clearForm();
    } catch {
      status.textContent = 'Failed to save';
      status.classList.add('error');
    } finally {
      saveBtn.disabled = false;
    }
  });
})();

// ─── Connect Broker Nudge Dismiss ─────────────────────────────

(function() {
  const dismissBtn = document.getElementById('connectNudgeDismiss');
  const nudge = document.getElementById('connectNudge');
  if (!dismissBtn || !nudge) return;

  dismissBtn.addEventListener('click', () => {
    nudge.classList.add('dismissing');
    localStorage.setItem('metron_connect_nudge_dismissed', '1');
    nudge.addEventListener('animationend', () => {
      nudge.style.display = 'none';
    }, { once: true });
  });
})();

// ─── Setup Guide Expand/Collapse ──────────────────────────────

(function() {
  const guide = document.getElementById('setupGuide');
  const toggle = document.getElementById('setupGuideToggle');
  if (!guide || !toggle) return;

  toggle.addEventListener('click', () => {
    const isOpen = guide.classList.toggle('open');
    toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  });
})();

// ─── App Tour ─────────────────────────────────────────────────

(function() {
  const TOUR_KEY = 'metron_tour_done';
  const isFirstVisit = !localStorage.getItem(TOUR_KEY);

  // Hide "NEW" badge if tour was already done
  if (!isFirstVisit) {
    const badge = document.getElementById('tourBadge');
    if (badge) badge.style.display = 'none';
  }

  const STEPS = [
    {
      target: '#combined_summary',
      icon: '�',
      title: 'Your net worth',
      desc: 'Total invested value, current value, and overall P&L — all in one place. Updates automatically when markets are open.',
      position: 'bottom',
    },
    {
      target: '.overview-top-right',
      icon: '🔄',
      title: 'Refresh & status',
      desc: 'Hit the refresh button to fetch the latest data from your broker.<br><br>The <strong>status dot</strong> shows sync state — <span style="color:#f59e0b">●</span> orange while updating, <span style="color:#22c55e">●</span> green when synced. It also shows how long ago data was last refreshed.',
      position: 'bottom-end',
    },
    {
      target: '#indexTickers',
      icon: '📈',
      title: 'Live market indices',
      desc: 'NIFTY 50, SENSEX and other key indices update in real-time during market hours. See the day\'s movement at a glance.',
      position: 'bottom',
    },
    {
      target: '#data-container-summary',
      icon: '📊',
      title: 'Asset breakdown',
      desc: 'Your portfolio split across Stocks, ETFs, Mutual Funds, Gold, Silver, and Fixed Deposits — each card shows invested vs current value and P&L.',
      position: 'bottom',
    },
    {
      target: '#gold_summary',
      icon: '🥇',
      title: 'Expandable gold summary',
      desc: 'Click this card to expand it and see a detailed breakdown of your gold holdings — ETFs, physical gold, and SGBs listed separately with individual P&L.',
      position: 'bottom',
    },
    {
      target: '#stocks-section .crud-add-btn',
      icon: '✏️',
      title: 'Add, edit & delete data',
      desc: 'Use the <strong>+ Add</strong> button on any table to manually enter holdings. Click a row to view details, edit quantities, or delete entries. Every table in the app has these controls.',
      position: 'bottom-start',
    },
    {
      target: '#stocks-section',
      icon: '📋',
      title: 'Your holdings tables',
      desc: 'Stocks, ETFs and mutual funds each have their own table. Click any column header to sort. Click a row to see detailed info including day-wise change and account info.',
      position: 'bottom',
    },
    {
      target: '.nav-menu-btn',
      icon: '🧭',
      title: 'Navigation',
      desc: 'Use the menu to switch between your Portfolio dashboard and the Nifty 50 heatmap.',
      position: 'bottom-start',
    },
    {
      target: '#userAvatarBtn',
      icon: '⚙️',
      title: 'Settings & broker accounts',
      desc: 'Tap your avatar for theme, privacy mode and short numbers. Open <strong>Settings</strong> to connect your broker accounts — sync holdings automatically with a step-by-step setup guide built right in.',
      position: 'bottom-end',
    },
  ];

  let currentStep = 0;
  const overlay = document.getElementById('appTourOverlay');
  const tooltip = document.getElementById('appTourTooltip');
  const content = document.getElementById('appTourContent');
  const progress = document.getElementById('appTourProgress');
  const nextBtn = document.getElementById('appTourNext');
  const skipBtn = document.getElementById('appTourSkip');

  if (!overlay || !tooltip) return;

  function findTarget(selectorStr) {
    const selectors = selectorStr.split(',').map(s => s.trim());
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent !== null) return el;
    }
    // Return first match even if hidden
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }

  // Ensure arrow element exists inside tooltip
  let arrowEl = tooltip.querySelector('.app-tour-arrow');
  if (!arrowEl) {
    arrowEl = document.createElement('div');
    arrowEl.className = 'app-tour-arrow';
    tooltip.appendChild(arrowEl);
  }

  function positionTooltip(rect, position) {
    const gap = 16;
    const tw = tooltip.offsetWidth;
    const th = tooltip.offsetHeight;
    let top, left;
    let arrowSide; // 'top' = arrow sticks out of top edge, 'bottom' = out of bottom

    switch (position) {
      case 'bottom':
      case 'bottom-start':
      case 'bottom-end':
        top = rect.bottom + gap;
        arrowSide = 'top';
        break;
      case 'top':
        top = rect.top - th - gap;
        arrowSide = 'bottom';
        break;
      default:
        top = rect.bottom + gap;
        arrowSide = 'top';
    }

    switch (position) {
      case 'bottom-start':
        left = rect.left;
        break;
      case 'bottom-end':
        left = rect.right - tw;
        break;
      default:
        left = rect.left + rect.width / 2 - tw / 2;
    }

    // Clamp to viewport
    left = Math.max(12, Math.min(left, window.innerWidth - tw - 12));
    top = Math.max(12, Math.min(top, window.innerHeight - th - 12));

    tooltip.style.top = top + 'px';
    tooltip.style.left = left + 'px';
    tooltip.setAttribute('data-arrow', arrowSide);

    // Position arrow horizontally to point at center of target
    const targetCenterX = rect.left + rect.width / 2;
    const arrowLeft = Math.max(18, Math.min(targetCenterX - left - 7, tw - 26));
    arrowEl.style.left = arrowLeft + 'px';
  }

  function renderProgress() {
    progress.innerHTML = STEPS.map((_, i) => {
      let cls = 'app-tour-dot';
      if (i < currentStep) cls += ' done';
      else if (i === currentStep) cls += ' active';
      return '<span class="' + cls + '"></span>';
    }).join('');
  }

  // Smoothly scroll element into view, then invoke callback after scroll settles
  function scrollToElement(el, callback) {
    const rect = el.getBoundingClientRect();
    const inView = rect.top >= 0 && rect.bottom <= window.innerHeight;
    if (inView) {
      callback();
      return;
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Wait for smooth scroll to finish, then fire callback
    let lastY = window.scrollY;
    let settled = 0;
    const check = () => {
      if (Math.abs(window.scrollY - lastY) < 1) {
        settled++;
        if (settled >= 3) { callback(); return; }
      } else {
        settled = 0;
      }
      lastY = window.scrollY;
      requestAnimationFrame(check);
    };
    requestAnimationFrame(check);
  }

  function showStep(index) {
    if (index >= STEPS.length) {
      endTour();
      return;
    }
    currentStep = index;
    const step = STEPS[index];
    const el = findTarget(step.target);
    if (!el || !el.getBoundingClientRect) {
      showStep(index + 1);
      return;
    }

    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) {
      showStep(index + 1);
      return;
    }

    // Hide tooltip during scroll transition
    tooltip.classList.remove('active');

    scrollToElement(el, () => _renderStep(step, el));
  }

  function _renderStep(step, el) {
    const rect = el.getBoundingClientRect();

    content.innerHTML =
      '<span class="tour-tip-icon">' + step.icon + '</span>' +
      '<div class="tour-tip-title">' + step.title + '</div>' +
      '<p class="tour-tip-desc">' + step.desc + '</p>';

    renderProgress();

    nextBtn.textContent = currentStep === STEPS.length - 1 ? 'Done' : 'Next';

    overlay.classList.add('active');

    requestAnimationFrame(() => {
      tooltip.classList.add('active');
      positionTooltip(rect, step.position);
    });
  }

  function endTour() {
    overlay.classList.remove('active');
    tooltip.classList.remove('active');
    localStorage.setItem(TOUR_KEY, '1');
  }

  nextBtn.addEventListener('click', () => showStep(currentStep + 1));
  skipBtn.addEventListener('click', endTour);
  overlay.addEventListener('click', endTour);

  // Expose globally so the menu button can trigger it
  window.startAppTour = function() {
    // Close the user dropdown first
    const dd = document.getElementById('userDropdown');
    if (dd) dd.classList.remove('open');
    // Scroll to top first for a clean start
    window.scrollTo({ top: 0, behavior: 'smooth' });
    currentStep = 0;
    setTimeout(() => showStep(0), 400);
  };

  // Auto-start for first-time visitors — generous delay so UI settles
  if (isFirstVisit) {
    const tourDelay = window.__INITIAL_DATA__ ? 2500 : 4500;
    setTimeout(() => showStep(0), tourDelay);
  }
})();

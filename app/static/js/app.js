// Helpers used by templates
window.IPV2 = {
  // Build a donut chart from a "by-X" breakdown array
  donut(canvasId, dataAttr) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    const raw = el.dataset[dataAttr];
    if (!raw) return;
    const data = JSON.parse(raw);
    new Chart(el.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: data.map(d => d.label),
        datasets: [{
          data: data.map(d => Number(d.value)),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        cutout: '60%',
      },
    });
  },
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[ch]);
}

function initPrivacyMode() {
  const toggles = document.querySelectorAll('[data-privacy-toggle]');
  const values = document.querySelectorAll('.privacy-value');
  if (!toggles.length || !values.length) return;

  const apply = (isPrivate) => {
    document.documentElement.dataset.privacy = isPrivate ? 'on' : 'off';
    toggles.forEach((button) => {
      button.textContent = isPrivate ? '開燈' : '關燈';
      button.setAttribute('aria-pressed', String(isPrivate));
    });
    values.forEach((el) => {
      if (!el.dataset.publicText) el.dataset.publicText = el.textContent.trim();
      el.textContent = isPrivate ? (el.dataset.privateText || '****') : el.dataset.publicText;
    });
  };

  const initial = localStorage.getItem('ipv2.privacy') === 'on';
  apply(initial);
  toggles.forEach((button) => {
    button.addEventListener('click', () => {
      const next = document.documentElement.dataset.privacy !== 'on';
      localStorage.setItem('ipv2.privacy', next ? 'on' : 'off');
      apply(next);
    });
  });
}

async function loadFxRates() {
  const el = document.querySelector('[data-market-widget="fx-rates"]');
  if (!el) return;
  try {
    const res = await fetch('/api/v1/market/fx-rates', { credentials: 'same-origin' });
    if (!res.ok) throw new Error('bad response');
    const data = await res.json();
    const rates = data.rates || [];
    el.innerHTML = `
      <div class="space-y-3">
        ${rates.map((rate) => `
          <div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
            <div>
              <p class="text-xs uppercase tracking-wide text-slate-500">${escapeHtml(rate.base)}/${escapeHtml(rate.quote)}</p>
              <p class="num mt-1 text-2xl font-semibold text-slate-900">${Number(rate.rate).toFixed(rate.base === 'JPY' ? 4 : 3)}</p>
            </div>
            <div class="text-right text-xs text-slate-500">
              <p>計價 ${escapeHtml(rate.as_of_taipei || '-')}</p>
              <p class="text-slate-400">來源 ${escapeHtml(rate.source_pair)}</p>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch {
    el.textContent = '暫時抓不到即時匯率';
  }
}

async function loadPublicSubscriptions() {
  const el = document.querySelector('[data-market-widget="public-subscriptions"]');
  if (!el) return;
  try {
    const res = await fetch('/api/v1/market/public-subscriptions', { credentials: 'same-origin' });
    if (!res.ok) throw new Error('bad response');
    const data = await res.json();
    const items = data.items || [];
    if (!items.length) {
      el.textContent = '目前沒有未來抽籤資料';
      return;
    }
    el.innerHTML = `
      <ul class="divide-y divide-slate-100">
        ${items.map((item) => `
          <li class="py-2">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="font-medium text-slate-900">${escapeHtml(item.symbol)} ${escapeHtml(item.name)}</p>
                <p class="text-xs text-slate-500">${escapeHtml(item.market)} · 申購 ${escapeHtml(item.subscription_period)} · 抽籤 ${escapeHtml(item.draw_date)}</p>
              </div>
              <div class="text-right">
                <p class="num text-sm text-slate-900">${escapeHtml(item.underwriting_price)}</p>
                <p class="text-xs ${Number(String(item.return_pct).replace(/,/g, '')) > 0 ? 'pos' : 'text-slate-500'}">${escapeHtml(item.return_pct)}%</p>
              </div>
            </div>
            <p class="mt-1 text-xs text-slate-400">${escapeHtml(item.status)} · 撥券 ${escapeHtml(item.delivery_date)}</p>
          </li>
        `).join('')}
      </ul>
    `;
  } catch {
    el.textContent = '暫時抓不到公開申購清單';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initPrivacyMode();
  loadFxRates();
  loadPublicSubscriptions();
});

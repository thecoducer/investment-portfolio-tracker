/* Portfolio Tracker - Market Index Ticker */

class IndexTicker {
  constructor() {
    this.refreshInterval = 15_000;
    this.timer = null;
    this.previousValues = {};
  }

  async init() {
    await this.fetchAndRender();
    this.startAutoRefresh();
  }

  startAutoRefresh() {
    if (this.timer) clearInterval(this.timer);
    this.timer = setInterval(() => this.fetchAndRender(), this.refreshInterval);
  }

  stopAutoRefresh() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
  }

  async fetchAndRender() {
    try {
      const res = await fetch('/market_indices');
      if (!res.ok) return;
      const data = await res.json();
      if (data.nifty50) this.renderIndex('nifty', data.nifty50);
      if (data.sensex)  this.renderIndex('sensex', data.sensex);
    } catch (e) {
      console.warn('Index ticker fetch failed:', e);
    }
  }

  renderIndex(prefix, data) {
    if (!data || data.value === 0) return;

    const valueEl  = document.getElementById(`${prefix}Value`);
    const changeEl = document.getElementById(`${prefix}Change`);

    if (valueEl) {
      const formatted = this._formatNumber(data.value);
      const prev = this.previousValues[prefix];
      if (prev !== undefined && prev !== data.value) {
        valueEl.classList.remove('flash-green', 'flash-red');
        void valueEl.offsetWidth;
        valueEl.classList.add(data.value > prev ? 'flash-green' : 'flash-red');
      }
      valueEl.textContent = formatted;
      this.previousValues[prefix] = data.value;
    }

    if (changeEl) {
      const sign  = data.change > 0 ? '+' : '';
      const arrow = data.change > 0 ? '▲' : data.change < 0 ? '▼' : '';
      const cls   = data.change > 0 ? 'positive' : data.change < 0 ? 'negative' : 'neutral';
      changeEl.innerHTML =
        `<span class="change-arrow">${arrow}</span>${sign}${data.change.toFixed(2)} (${sign}${data.pChange.toFixed(2)}%)`;
      changeEl.className = `index-change ${cls}`;
    }
  }

  _formatNumber(num) {
    return new Intl.NumberFormat('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  }
}

export default IndexTicker;

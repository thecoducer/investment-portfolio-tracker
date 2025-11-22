/* Portfolio Tracker - Table Rendering Module */

import { Formatter, Calculator } from './utils.js';

class TableRenderer {
  constructor() {
    this.searchQuery = '';
  }

  setSearchQuery(query) {
    this.searchQuery = query.toLowerCase();
  }

  _getUpdateClass(isUpdating) {
    return isUpdating ? 'updating-field' : '';
  }

  _applyUpdatingClass(element, isUpdating) {
    if (isUpdating) {
      element.classList.add('updating-field');
    } else {
      element.classList.remove('updating-field');
    }
  }

  /**
   * Build a styled table cell with optional class.
   * @param {string} content - Cell content
   * @param {string} cssClass - Optional CSS class
   * @returns {string} HTML string for table cell
   */
  _buildCell(content, cssClass = '') {
    const classAttr = cssClass ? ` class="${cssClass}"` : '';
    return `<td${classAttr}>${content}</td>`;
  }

  /**
   * Build a styled P/L cell with color.
   * @param {number} value - P/L value
   * @param {string} cssClass - Optional CSS class
   * @returns {string} HTML string for P/L cell
   */
  _buildPLCell(value, cssClass = '') {
    const formatted = Formatter.formatNumber(value);
    const color = Formatter.colorPL(value);
    return `<td><span class="${cssClass}" style="color:${color};font-weight:600">${formatted}</span></td>`;
  }

  /**
   * Build a cell with value and percentage.
   * @param {number} value - Main value
   * @param {number} percentage - Percentage to display
   * @param {string} cssClass - Optional CSS class
   * @returns {string} HTML string
   */
  _buildValueWithPctCell(value, percentage, cssClass = '') {
    const formatted = Formatter.formatNumber(value);
    const color = Formatter.colorPL(value);
    const pctText = `${Formatter.formatSign(value)}${percentage.toFixed(2)}%`;
    return `<td class="${cssClass}">${formatted} <span class="pl_pct_small" style="color:${color}">${pctText}</span></td>`;
  }

  renderStocksTable(holdings, status) {
    const tbody = document.getElementById('tbody');
    const ltpRunning = status.ltp_fetch_state === 'updating' || status.state === 'updating';
    const refreshRunning = status.state === 'updating';

    tbody.innerHTML = '';
    let totalInvested = 0;
    let totalCurrent = 0;

    holdings.forEach(holding => {
      const text = (holding.tradingsymbol + holding.account).toLowerCase();
      if (!text.includes(this.searchQuery)) return;

      const metrics = Calculator.calculateStockMetrics(holding);
      totalInvested += metrics.invested;
      totalCurrent += metrics.current;

      tbody.innerHTML += this._buildStockRow(holding, metrics, {
        qtyClass: this._getUpdateClass(refreshRunning),
        avgClass: this._getUpdateClass(refreshRunning),
        investedClass: this._getUpdateClass(refreshRunning),
        ltpClass: this._getUpdateClass(ltpRunning),
        plClass: this._getUpdateClass(ltpRunning),
        dayChangeClass: this._getUpdateClass(ltpRunning),
        currentClass: this._getUpdateClass(ltpRunning)
      });
    });

    this._updateStockSummary({
      totalInvested,
      totalCurrent,
      totalPL: totalCurrent - totalInvested,
      totalPLPct: totalInvested ? ((totalCurrent - totalInvested) / totalInvested * 100) : 0
    }, ltpRunning);

    this._updateStatusDisplay(status);
  }

  renderMFTable(mfHoldings, status) {
    const tbody = document.getElementById('mf_tbody');
    const ltpRunning = status.ltp_fetch_state === 'updating' || status.state === 'updating';
    const refreshRunning = status.state === 'updating';

    tbody.innerHTML = '';
    let mfTotalInvested = 0;
    let mfTotalCurrent = 0;

    mfHoldings.forEach(mf => {
      const fundName = mf.fund || mf.tradingsymbol;
      const text = (fundName + mf.account).toLowerCase();
      if (!text.includes(this.searchQuery)) return;

      const metrics = Calculator.calculateMFMetrics(mf);
      mfTotalInvested += metrics.invested;
      mfTotalCurrent += metrics.current;

      tbody.innerHTML += this._buildMFRow(fundName, mf, metrics, {
        qtyClass: this._getUpdateClass(refreshRunning),
        avgClass: this._getUpdateClass(refreshRunning),
        investedClass: this._getUpdateClass(refreshRunning),
        navClass: this._getUpdateClass(ltpRunning),
        currentClass: this._getUpdateClass(ltpRunning),
        plClass: this._getUpdateClass(ltpRunning)
      });
    });

    this._updateMFSummary({
      totalInvested: mfTotalInvested,
      totalCurrent: mfTotalCurrent,
      totalPL: mfTotalCurrent - mfTotalInvested,
      totalPLPct: mfTotalInvested ? ((mfTotalCurrent - mfTotalInvested) / mfTotalInvested * 100) : 0
    }, ltpRunning);
  }

  renderSIPsTable(sips, status) {
    const tbody = document.getElementById('sips_tbody');
    const refreshRunning = status.state === 'updating';
    const dataClass = this._getUpdateClass(refreshRunning);

    tbody.innerHTML = '';
    let totalMonthlyAmount = 0;

    sips.forEach(sip => {
      const fundName = (sip.fund || sip.tradingsymbol).toUpperCase();
      const text = (fundName + sip.account).toLowerCase();
      if (!text.includes(this.searchQuery)) return;

      const dataClass = refreshRunning ? 'updating-field' : '';

      tbody.innerHTML += this._buildSIPRow(fundName, sip, dataClass);
      
      // Calculate total monthly amount for active SIPs
      if (sip.status === 'ACTIVE' && sip.instalment_amount) {
        const frequency = sip.frequency || 'monthly';
        const amount = sip.instalment_amount;
        
        // Convert to monthly equivalent
        if (frequency.toLowerCase() === 'monthly') {
          totalMonthlyAmount += amount;
        } else if (frequency.toLowerCase() === 'weekly') {
          totalMonthlyAmount += amount * 4.33; // Average weeks per month
        } else if (frequency.toLowerCase() === 'quarterly') {
          totalMonthlyAmount += amount / 3;
        }
      }
    });
    
    // Update total amount display
    this._updateSIPTotal(totalMonthlyAmount, refreshRunning);
  }

  _updateSIPTotal(totalAmount, refreshRunning) {
    const totalEl = document.getElementById('sip_total_amount');
    if (totalEl) {
      totalEl.innerText = totalAmount.toLocaleString(undefined, { 
        minimumFractionDigits: 0, 
        maximumFractionDigits: 0 
      });
      this._applyUpdatingClass(totalEl, refreshRunning);
    }
  }

  _buildStockRow(holding, metrics, classes) {
    const { qty, avg, invested, ltp, dayChange, pl, current, plPct, dayChangePct } = metrics;
    const color = Formatter.colorPL(dayChange);
    
    return `<tr style="background-color:${Formatter.rowColor(pl)}">
${this._buildCell(holding.tradingsymbol)}
${this._buildCell(qty.toLocaleString(), classes.qtyClass)}
${this._buildCell(avg.toLocaleString(), classes.avgClass)}
${this._buildCell(Formatter.formatNumber(invested), classes.investedClass)}
${this._buildCell(ltp.toLocaleString(), classes.ltpClass)}
${this._buildPLCell(pl, classes.plClass)}
<td class="${classes.dayChangeClass}"><span style="color:${color};font-weight:600">${Formatter.formatNumber(dayChange)}</span> <span class="pl_pct_small" style="color:${color}">${dayChangePct.toFixed(2)}%</span></td>
${this._buildValueWithPctCell(current, plPct, classes.currentClass)}
${this._buildCell(holding.exchange)}
${this._buildCell(holding.account)}
</tr>`;
  }

  _buildMFRow(fundName, mf, metrics, classes) {
    const { qty, avg, invested, nav, current, pl, plPct } = metrics;
    
    // Format NAV date in relative format
    let navDateText = '';
    if (mf.last_price_date) {
      const formattedDate = Formatter.formatRelativeDate(mf.last_price_date, true);
      if (formattedDate) {
        navDateText = ` <span class="pl_pct_small">${formattedDate.toLowerCase()}</span>`;
      }
    }
    
    return `<tr style="background-color:${Formatter.rowColor(pl)}">
${this._buildCell(fundName)}
${this._buildCell(qty.toLocaleString(), classes.qtyClass)}
${this._buildCell(avg.toLocaleString(), classes.avgClass)}
${this._buildCell(Formatter.formatNumber(invested), classes.investedClass)}
${this._buildCell(nav.toLocaleString() + navDateText, classes.navClass)}
${this._buildPLCell(pl, classes.plClass)}
${this._buildValueWithPctCell(current, plPct, classes.currentClass)}
${this._buildCell(mf.account)}
</tr>`;
  }

  _buildSIPRow(fundName, sip, dataClass) {
    // Format frequency
    const frequency = sip.frequency || '-';
    
    // Format installments - handle -1 as perpetual/unlimited
    let installments = '-';
    if (sip.instalments && sip.instalments !== -1) {
      const completed = sip.completed_instalments || 0;
      installments = `${completed}/${sip.instalments}`;
    } else if (sip.completed_instalments && sip.completed_instalments > 0) {
      // For perpetual SIPs, just show completed count
      installments = `${sip.completed_instalments}`;
    }
    
    // Format status with color
    const status = sip.status || 'UNKNOWN';
    let statusColor = '#666';
    if (status === 'ACTIVE') statusColor = '#28a745';
    else if (status === 'PAUSED') statusColor = '#ffc107';
    else if (status === 'CANCELLED') statusColor = '#dc3545';
    
    // Format next due date
    let nextDueText = '-';
    if (sip.next_instalment && status === 'ACTIVE') {
      const formattedDate = Formatter.formatRelativeDate(sip.next_instalment, false);
      nextDueText = formattedDate || sip.next_instalment;
    }
    
    return `<tr>
<td class="${dataClass}">${fundName}</td>
<td class="${dataClass}">${(sip.instalment_amount || 0).toLocaleString()}</td>
<td class="${dataClass}">${frequency}</td>
<td class="${dataClass}">${installments}</td>
<td class="${dataClass}"><span style="color:${statusColor};font-weight:600">${status}</span></td>
<td class="${dataClass}">${nextDueText}</td>
<td class="${dataClass}">${sip.account}</td>
</tr>`;
  }

  _updateStockSummary(totals, ltpRunning) {
    const currentValueEl = document.getElementById('current_value');
    const totalPlEl = document.getElementById('total_pl');
    const totalPlPctEl = document.getElementById('total_pl_pct');

    document.getElementById('total_invested').innerText = Formatter.formatNumber(totals.totalInvested);
    currentValueEl.innerText = Formatter.formatNumber(totals.totalCurrent);
    totalPlEl.innerText = Formatter.formatSign(totals.totalPL) + Formatter.formatNumber(totals.totalPL);
    totalPlEl.style.color = Formatter.colorPL(totals.totalPL);
    totalPlPctEl.innerText = Formatter.formatSign(totals.totalPL) + totals.totalPLPct.toFixed(2) + '%';
    totalPlPctEl.style.color = Formatter.colorPL(totals.totalPL);

    [currentValueEl, totalPlEl, totalPlPctEl].forEach(el => this._applyUpdatingClass(el, ltpRunning));
  }

  _updateMFSummary(totals, ltpRunning) {
    const mfCurrentValueEl = document.getElementById('mf_current_value');
    const mfTotalPlEl = document.getElementById('mf_total_pl');
    const mfTotalPlPctEl = document.getElementById('mf_total_pl_pct');

    document.getElementById('mf_total_invested').innerText = Formatter.formatNumber(totals.totalInvested);
    mfCurrentValueEl.innerText = Formatter.formatNumber(totals.totalCurrent);
    mfTotalPlEl.innerText = Formatter.formatSign(totals.totalPL) + Formatter.formatNumber(totals.totalPL);
    mfTotalPlEl.style.color = Formatter.colorPL(totals.totalPL);
    mfTotalPlPctEl.innerText = Formatter.formatSign(totals.totalPL) + totals.totalPLPct.toFixed(2) + '%';
    mfTotalPlPctEl.style.color = Formatter.colorPL(totals.totalPL);

    [mfCurrentValueEl, mfTotalPlEl, mfTotalPlPctEl].forEach(el => this._applyUpdatingClass(el, ltpRunning));
  }

  _updateStatusDisplay(status) {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');

    const isUpdating = status.state === 'updating' || status.ltp_fetch_state === 'updating';
    statusTag.className = isUpdating ? 'updating' : 'updated';
    statusText.innerText = isUpdating 
      ? 'updating' 
      : ('updated' + (status.holdings_last_updated ? ` • ${status.holdings_last_updated}` : ''));
  }
}

export default TableRenderer;

/* Portfolio Tracker - Table Rendering Module */

import { Formatter, Calculator } from './utils.js';

class TableRenderer {
  constructor() {
    this.searchQuery = '';
  }

  setSearchQuery(query) {
    this.searchQuery = query.toLowerCase();
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

      const qtyClass = refreshRunning ? 'updating-field' : '';
      const avgClass = refreshRunning ? 'updating-field' : '';
      const investedClass = refreshRunning ? 'updating-field' : '';
      const ltpClass = ltpRunning ? 'updating-field' : '';
      const plClass = ltpRunning ? 'updating-field' : '';
      const dayChangeClass = ltpRunning ? 'updating-field' : '';
      const currentClass = ltpRunning ? 'updating-field' : '';

      tbody.innerHTML += this._buildStockRow(holding, metrics, {
        qtyClass,
        avgClass,
        investedClass,
        ltpClass,
        plClass,
        dayChangeClass,
        currentClass
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

      const qtyClass = refreshRunning ? 'updating-field' : '';
      const avgClass = refreshRunning ? 'updating-field' : '';
      const investedClass = refreshRunning ? 'updating-field' : '';
      const navClass = ltpRunning ? 'updating-field' : '';
      const currentClass = ltpRunning ? 'updating-field' : '';
      const plClass = ltpRunning ? 'updating-field' : '';

      tbody.innerHTML += this._buildMFRow(fundName, mf, metrics, {
        qtyClass,
        avgClass,
        investedClass,
        navClass,
        currentClass,
        plClass
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
      totalEl.innerText = '₹' + totalAmount.toLocaleString(undefined, { 
        minimumFractionDigits: 0, 
        maximumFractionDigits: 0 
      });
      if (refreshRunning) {
        totalEl.classList.add('updating-field');
      } else {
        totalEl.classList.remove('updating-field');
      }
    }
  }

  _buildStockRow(holding, metrics, classes) {
    return `<tr style="background-color:${Formatter.rowColor(metrics.pl)}">
<td>${holding.tradingsymbol}</td>
<td class="${classes.qtyClass}">${metrics.qty.toLocaleString()}</td>
<td class="${classes.avgClass}">${metrics.avg.toLocaleString()}</td>
<td class="${classes.investedClass}">${Formatter.formatNumber(metrics.invested)}</td>
<td class="${classes.ltpClass}">${metrics.ltp.toLocaleString()}</td>
<td><span class="${classes.plClass}" style="color:${Formatter.colorPL(metrics.pl)};font-weight:600">${Formatter.formatNumber(metrics.pl)}</span></td>
<td class="${classes.dayChangeClass}"><span style="color:${Formatter.colorPL(metrics.dayChange)};font-weight:600">${Formatter.formatNumber(metrics.dayChange)}</span> <span class="pl_pct_small" style="color:${Formatter.colorPL(metrics.dayChange)}">${metrics.dayChangePct.toFixed(2)}%</span></td>
<td class="${classes.currentClass}">${Formatter.formatNumber(metrics.current)} <span class="pl_pct_small" style="color:${Formatter.colorPL(metrics.pl)}">${metrics.plPct.toFixed(2)}%</span></td>
<td>${holding.exchange}</td>
<td>${holding.account}</td>
</tr>`;
  }

  _buildMFRow(fundName, mf, metrics, classes) {
    // Format NAV date in relative format
    let navDateText = '';
    if (mf.last_price_date) {
      const formattedDate = Formatter.formatRelativeDate(mf.last_price_date, true);
      if (formattedDate) {
        navDateText = ` <span class="pl_pct_small">${formattedDate.toLowerCase()}</span>`;
      }
    }
    
    return `<tr style="background-color:${Formatter.rowColor(metrics.pl)}">
<td>${fundName}</td>
<td class="${classes.qtyClass}">${metrics.qty.toLocaleString()}</td>
<td class="${classes.avgClass}">${metrics.avg.toLocaleString()}</td>
<td class="${classes.investedClass}">${Formatter.formatNumber(metrics.invested)}</td>
<td class="${classes.navClass}">${metrics.nav.toLocaleString()}${navDateText}</td>
<td><span class="${classes.plClass}" style="color:${Formatter.colorPL(metrics.pl)};font-weight:600">${Formatter.formatNumber(metrics.pl)}</span></td>
<td class="${classes.currentClass}">${Formatter.formatNumber(metrics.current)} <span class="pl_pct_small" style="color:${Formatter.colorPL(metrics.pl)}">${metrics.plPct.toFixed(2)}%</span></td>
<td>${mf.account}</td>
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
<td class="${dataClass}">₹${(sip.instalment_amount || 0).toLocaleString()}</td>
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

    this._toggleUpdatingClass([currentValueEl, totalPlEl, totalPlPctEl], ltpRunning);
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

    this._toggleUpdatingClass([mfCurrentValueEl, mfTotalPlEl, mfTotalPlPctEl], ltpRunning);
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

  _toggleUpdatingClass(elements, isUpdating) {
    elements.forEach(el => {
      if (isUpdating) {
        el.classList.add('updating-field');
      } else {
        el.classList.remove('updating-field');
      }
    });
  }
}

export default TableRenderer;

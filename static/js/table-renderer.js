/* Portfolio Tracker - Table Rendering Module */

import { Formatter, Calculator } from './utils.js';
import PaginationManager from './pagination.js';

class TableRenderer {
  constructor() {
    this.searchQuery = '';
    this.stocksPagination = new PaginationManager(25, 1);
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
    const formatted = Formatter.formatCurrency(value);
    const color = Formatter.colorPL(value);
    return `<td><span class="${cssClass}" style="color:${color};font-weight:600">${formatted}</span></td>`;
  }

  /**
   * Build a cell with value and percentage with color coding.
   * @param {number|string} value - Main value (numeric or formatted string)
   * @param {number} percentage - Percentage to display
   * @param {string} cssClass - Optional CSS class
   * @returns {string} HTML string
   */
  _buildValueWithPctCell(value, percentage, cssClass = '') {
    const formatted = (typeof value === 'number') ? Formatter.formatNumber(value) : value;
    const color = Formatter.colorPL(percentage);
    const pctText = Formatter.formatPercentage(percentage);
    return `<td class="${cssClass}">${formatted} <span class="pl_pct_small" style="color:${color}">${pctText}</span></td>`;
  }

  /**
   * Build a cell with change value and percentage.
   * @param {number} changeValue - Change value
   * @param {number} changePercent - Change percentage
   * @param {string} cssClass - Optional CSS class
   * @returns {string} HTML string
   */
  _buildChangeCell(changeValue, changePercent, cssClass = '') {
    const color = Formatter.colorPL(changeValue);
    const formattedValue = Formatter.formatCurrency(changeValue);
    const formattedPct = Formatter.formatPercentage(changePercent);
    return `<td class="${cssClass}"><span style="color:${color};font-weight:600">${formattedValue}</span> <span class="pl_pct_small" style="color:${color}">${formattedPct}</span></td>`;
  }

  renderStocksTable(holdings, status) {
    const tbody = document.getElementById('tbody');
    const section = document.getElementById('stocks-section');
    const loadingRow = document.getElementById('stocks_table_loading');
    if (loadingRow) loadingRow.style.display = 'none';
    const isUpdating = status.portfolio_state === 'updating';

    let totalInvested = 0;
    let totalCurrent = 0;
    let filteredHoldings = [];

    // Filter and calculate totals
    holdings.forEach(holding => {
      const text = (holding.tradingsymbol + holding.account).toLowerCase();
      if (text.includes(this.searchQuery)) {
        filteredHoldings.push(holding);
        const metrics = Calculator.calculateStockMetrics(holding);
        totalInvested += metrics.invested;
        totalCurrent += metrics.current;
      }
    });

    // Use pagination manager
    const paginationInfo = this.stocksPagination.paginate(filteredHoldings);
    const { pageData } = paginationInfo;

    tbody.innerHTML = '';
    pageData.forEach(holding => {
      const metrics = Calculator.calculateStockMetrics(holding);
      tbody.innerHTML += this._buildStockRow(holding, metrics, {
        symbolClass: this._getUpdateClass(isUpdating),
        qtyClass: this._getUpdateClass(isUpdating),
        avgClass: this._getUpdateClass(isUpdating),
        investedClass: this._getUpdateClass(isUpdating),
        ltpClass: this._getUpdateClass(isUpdating),
        plClass: this._getUpdateClass(isUpdating),
        dayChangeClass: this._getUpdateClass(isUpdating),
        currentClass: this._getUpdateClass(isUpdating),
        exchangeClass: this._getUpdateClass(isUpdating),
        accountClass: this._getUpdateClass(isUpdating)
      });
    });

    section.style.display = filteredHoldings.length === 0 ? 'none' : 'block';
    
    // Update pagination UI
    PaginationManager.updatePaginationUI(
      paginationInfo,
      'stocks_pagination_info',
      'stocks_pagination_buttons',
      'goToStocksPage',
      'stocks'
    );

    return {
      invested: totalInvested,
      current: totalCurrent,
      pl: totalCurrent - totalInvested,
      plPct: totalInvested ? ((totalCurrent - totalInvested) / totalInvested * 100) : 0
    };
  }

  renderMFTable(mfHoldings, status) {
    const tbody = document.getElementById('mf_tbody');
    const section = document.getElementById('mf-section');
    const loadingRow = document.getElementById('mf_table_loading');
    if (loadingRow) loadingRow.style.display = 'none';
    const isUpdating = status.portfolio_state === 'updating';

    tbody.innerHTML = '';
    let mfTotalInvested = 0;
    let mfTotalCurrent = 0;
    let visibleCount = 0;

    mfHoldings.forEach(mf => {
      const fundName = mf.fund || mf.tradingsymbol;
      const text = (fundName + mf.account).toLowerCase();
      if (!text.includes(this.searchQuery)) return;

      visibleCount++;
      const metrics = Calculator.calculateMFMetrics(mf);
      mfTotalInvested += metrics.invested;
      mfTotalCurrent += metrics.current;

      tbody.innerHTML += this._buildMFRow(fundName, mf, metrics, {
        fundClass: this._getUpdateClass(isUpdating),
        qtyClass: this._getUpdateClass(isUpdating),
        avgClass: this._getUpdateClass(isUpdating),
        investedClass: this._getUpdateClass(isUpdating),
        navClass: this._getUpdateClass(isUpdating),
        currentClass: this._getUpdateClass(isUpdating),
        plClass: this._getUpdateClass(isUpdating),
        accountClass: this._getUpdateClass(isUpdating)
      });
    });

    section.style.display = visibleCount === 0 ? 'none' : 'block';

    return {
      invested: mfTotalInvested,
      current: mfTotalCurrent,
      pl: mfTotalCurrent - mfTotalInvested,
      plPct: mfTotalInvested ? ((mfTotalCurrent - mfTotalInvested) / mfTotalInvested * 100) : 0
    };
  }

  renderSIPsTable(sips, status) {
    const tbody = document.getElementById('sips_tbody');
    const section = document.getElementById('sips-section');
    const loadingRow = document.getElementById('sips_table_loading');
    if (loadingRow) loadingRow.style.display = 'none';
    const isUpdating = status.portfolio_state === 'updating';
    const dataClass = this._getUpdateClass(isUpdating);

    tbody.innerHTML = '';
    let totalMonthlyAmount = 0;
    let visibleCount = 0;

    sips.forEach(sip => {
      const fundName = (sip.fund || sip.tradingsymbol).toUpperCase();
      const text = (fundName + sip.account).toLowerCase();
      if (!text.includes(this.searchQuery)) return;

      visibleCount++;
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
    
    // Hide section if no visible rows
    section.style.display = visibleCount === 0 ? 'none' : 'block';
    
    // Add total row at the end of the table
    tbody.innerHTML += this._buildSIPTotalRow(totalMonthlyAmount, dataClass);
  }

  _buildSIPTotalRow(totalAmount, dataClass) {
    const formattedAmount = Formatter.formatCurrency(totalAmount);

    return `<tr style="border-top: 2px solid #e9e9e7; font-weight: 600;">
<td class="${dataClass}">Total Monthly SIP Amount:</td>
<td class="${dataClass}">${formattedAmount}</td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>`;
  }

  _buildStockRow(holding, metrics, classes) {
    const { qty, avg, invested, ltp, dayChange, pl, current, plPct, dayChangePct } = metrics;
    
    return `<tr style="background-color:${Formatter.rowColor(pl)}">
  ${this._buildCell(holding.tradingsymbol, classes.symbolClass)}
  ${this._buildCell(qty.toLocaleString(), classes.qtyClass)}
  ${this._buildCell(Formatter.formatCurrency(avg), classes.avgClass)}
  ${this._buildCell(Formatter.formatCurrency(invested), classes.investedClass)}
  ${this._buildValueWithPctCell(Formatter.formatCurrency(current), plPct, classes.currentClass)}
  ${this._buildCell(Formatter.formatCurrency(ltp), classes.ltpClass)}
  ${this._buildPLCell(pl, classes.plClass)}
  ${this._buildChangeCell(dayChange, dayChangePct, classes.dayChangeClass)}
  ${this._buildCell(holding.exchange, classes.exchangeClass)}
  ${this._buildCell(holding.account, classes.accountClass)}
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
  ${this._buildCell(fundName, classes.fundClass)}
  ${this._buildCell(qty.toLocaleString(), classes.qtyClass)}
  ${this._buildCell(Formatter.formatCurrency(avg), classes.avgClass)}
  ${this._buildCell(Formatter.formatCurrency(invested), classes.investedClass)}
  ${this._buildValueWithPctCell(Formatter.formatCurrency(current), plPct, classes.currentClass)}
  ${this._buildCell(Formatter.formatCurrency(nav) + navDateText, classes.navClass)}
  ${this._buildPLCell(pl, classes.plClass)}
  ${this._buildCell(mf.account, classes.accountClass)}
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
<td class="${dataClass}">${Formatter.formatCurrency(sip.instalment_amount || 0)}</td>
<td class="${dataClass}">${frequency}</td>
<td class="${dataClass}">${installments}</td>
<td class="${dataClass}"><span style="color:${statusColor};font-weight:600">${status}</span></td>
<td class="${dataClass}">${nextDueText}</td>
<td class="${dataClass}">${sip.account}</td>
</tr>`;
  }

  _updateStocksPagination(currentPage, totalPages, totalItems, startIndex, endIndex) {
    // Deprecated - now handled by PaginationManager.updatePaginationUI in renderStocksTable
  }

  _buildPaginationButtons(currentPage, totalPages, clickFunctionName) {
    // Deprecated - use PaginationManager.buildPaginationButtons instead
    return PaginationManager.buildPaginationButtons(currentPage, totalPages, clickFunctionName);
  }

  changeStocksPageSize(size) {
    this.stocksPagination.changePageSize(size);
  }

  goToStocksPage(page) {
    this.stocksPagination.goToPage(page);
  }

}

export default TableRenderer;

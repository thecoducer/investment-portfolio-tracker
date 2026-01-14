/* Portfolio Tracker - Table Rendering Module */

import { Formatter, Calculator, isGoldInstrument, isSilverInstrument } from './utils.js';
import PaginationManager from './pagination.js';

class TableRenderer {
  constructor() {
    this.searchQuery = '';
    this.stocksPagination = new PaginationManager(25, 1);
    this.mfPagination = new PaginationManager(25, 1);
    this.physicalGoldPagination = new PaginationManager(10, 1);
    this.fixedDepositsPagination = new PaginationManager(10, 1);
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
    const formatted = (typeof value === 'number') ? Formatter.formatNumberWithLocale(value, 1) : value;
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
    const isUpdating = status.portfolio_state === 'updating';

    let totalInvested = 0;
    let totalCurrent = 0;
    let goldInvested = 0;
    let goldCurrent = 0;
    let silverInvested = 0;
    let silverCurrent = 0;
    let filteredHoldings = [];

    // Filter and calculate totals (Gold and Silver shown in table but not in Stocks summary)
    holdings.forEach(holding => {
      const symbol = holding.tradingsymbol || '';
      const text = (symbol + holding.account).toLowerCase();
      const isGold = isGoldInstrument(symbol);
      const isSilver = isSilverInstrument(symbol);
      
      if (text.includes(this.searchQuery)) {
        filteredHoldings.push(holding);  // Add all holdings to display
        const metrics = Calculator.calculateStockMetrics(holding);
        
        if (isGold) {
          // Accumulate Gold totals separately (not in Stocks summary)
          goldInvested += metrics.invested;
          goldCurrent += metrics.current;
        } else if (isSilver) {
          // Accumulate Silver totals separately (not in Stocks summary)
          silverInvested += metrics.invested;
          silverCurrent += metrics.current;
        } else {
          // Only non-Gold/Silver holdings count toward Stocks summary
          totalInvested += metrics.invested;
          totalCurrent += metrics.current;
        }
      }
    });

    // Use pagination manager
    const paginationData = this.stocksPagination.paginate(filteredHoldings);
    const { pageData } = paginationData;

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

    // Show/hide table and empty state
    const table = section.querySelector('table');
    const emptyState = document.getElementById('stocks_empty_state');
    const paginationInfoEl = document.getElementById('stocks_pagination_info');
    const paginationButtonsEl = document.getElementById('stocks_pagination_buttons');
    const controlsContainer = section.querySelector('.controls-container');
    
    if (filteredHoldings.length === 0) {
      table.style.display = 'none';
      emptyState.style.display = 'block';
      if (paginationInfoEl) paginationInfoEl.style.display = 'none';
      if (paginationButtonsEl) paginationButtonsEl.style.display = 'none';
      if (controlsContainer) controlsContainer.style.display = 'none';
    } else {
      table.style.display = 'table';
      emptyState.style.display = 'none';
      if (paginationInfoEl) paginationInfoEl.style.display = 'block';
      if (paginationButtonsEl) paginationButtonsEl.style.display = 'flex';
      if (controlsContainer) controlsContainer.style.display = 'flex';
    }
    
    // Update pagination UI
    PaginationManager.updatePaginationUI(
      paginationData,
      'stocks_pagination_info',
      'stocks_pagination_buttons',
      'goToStocksPage',
      'stocks'
    );

    // Return separate totals for stocks, gold, and silver
    const stockTotals = {
      invested: totalInvested,
      current: totalCurrent,
      pl: totalCurrent - totalInvested,
      plPct: totalInvested ? ((totalCurrent - totalInvested) / totalInvested * 100) : 0
    };
    
    const goldTotals = {
      invested: goldInvested,
      current: goldCurrent,
      pl: goldCurrent - goldInvested,
      plPct: goldInvested ? ((goldCurrent - goldInvested) / goldInvested * 100) : 0
    };
    
    const silverTotals = {
      invested: silverInvested,
      current: silverCurrent,
      pl: silverCurrent - silverInvested,
      plPct: silverInvested ? ((silverCurrent - silverInvested) / silverInvested * 100) : 0
    };

    return { stockTotals, goldTotals, silverTotals };
  }

  renderMFTable(mfHoldings, status) {
    const tbody = document.getElementById('mf_tbody');
    const section = document.getElementById('mf-section');
    const isUpdating = status.portfolio_state === 'updating';

    tbody.innerHTML = '';
    let mfTotalInvested = 0;
    let mfTotalCurrent = 0;
    let filteredHoldings = [];

    mfHoldings.forEach(mf => {
      const fundName = mf.fund || mf.tradingsymbol;
      const text = (fundName + mf.account).toLowerCase();
      if (!text.includes(this.searchQuery)) return;

      filteredHoldings.push(mf);
      const metrics = Calculator.calculateMFMetrics(mf);
      mfTotalInvested += metrics.invested;
      mfTotalCurrent += metrics.current;
    });

    // Use pagination manager
    const paginationData = this.mfPagination.paginate(filteredHoldings);
    const { pageData } = paginationData;

    pageData.forEach(mf => {
      const fundName = mf.fund || mf.tradingsymbol;
      const metrics = Calculator.calculateMFMetrics(mf);
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

    // Show/hide table and empty state
    const table = section.querySelector('table');
    const emptyState = document.getElementById('mf_empty_state');
    const controlsContainer = section.querySelector('.controls-container');
    const paginationInfoEl = document.getElementById('mf_pagination_info');
    const paginationButtonsEl = document.getElementById('mf_pagination_buttons');
    
    if (filteredHoldings.length === 0) {
      table.style.display = 'none';
      emptyState.style.display = 'block';
      if (controlsContainer) controlsContainer.style.display = 'none';
      if (paginationInfoEl) paginationInfoEl.style.display = 'none';
      if (paginationButtonsEl) paginationButtonsEl.style.display = 'none';
    } else {
      table.style.display = 'table';
      emptyState.style.display = 'none';
      if (controlsContainer) controlsContainer.style.display = 'flex';
      if (paginationInfoEl) paginationInfoEl.style.display = 'block';
      if (paginationButtonsEl) paginationButtonsEl.style.display = 'flex';
    }

    // Update pagination UI
    PaginationManager.updatePaginationUI(
      paginationData,
      'mf_pagination_info',
      'mf_pagination_buttons',
      'goToMFPage',
      'funds'
    );

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
    
    // Show/hide table and empty state
    const table = section.querySelector('table');
    const emptyState = document.getElementById('sips_empty_state');
    
    if (visibleCount === 0) {
      table.style.display = 'none';
      emptyState.style.display = 'block';
    } else {
      table.style.display = 'table';
      emptyState.style.display = 'none';
    }
    
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
    const frequency = sip.frequency || '-';
    
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

  changeStocksPageSize(size) {
    this.stocksPagination.changePageSize(size);
  }

  goToStocksPage(page) {
    this.stocksPagination.goToPage(page);
  }

  changeMFPageSize(size) {
    this.mfPagination.changePageSize(size);
  }

  goToMFPage(page) {
    this.mfPagination.goToPage(page);
  }

  /**
   * Render physical gold holdings table with pagination
   */
  renderPhysicalGoldTable(holdings) {
    const tbody = document.getElementById('physical_gold_table_body');
    const section = document.getElementById('physical-gold-section');
    
    if (!tbody) return { invested: 0 };

    tbody.innerHTML = '';

    const table = section ? section.querySelector('table') : null;
    const emptyState = document.getElementById('physical_gold_empty_state');
    const controlsContainer = section ? section.querySelector('.controls-container') : null;
    const paginationInfo = document.getElementById('physical_gold_pagination_info');
    const paginationButtons = document.getElementById('physical_gold_pagination_buttons');

    if (!holdings || holdings.length === 0) {
      if (table) table.style.display = 'none';
      if (emptyState) emptyState.style.display = 'block';
      if (controlsContainer) controlsContainer.style.display = 'none';
      if (paginationInfo) paginationInfo.style.display = 'none';
      if (paginationButtons) paginationButtons.style.display = 'none';
      return { invested: 0 };
    }

    if (table) table.style.display = 'table';
    if (emptyState) emptyState.style.display = 'none';
    if (controlsContainer) controlsContainer.style.display = 'flex';
    if (paginationInfo) paginationInfo.style.display = 'block';
    if (paginationButtons) paginationButtons.style.display = 'flex';

    let totalPhysicalGoldInvested = 0;
    let totalPhysicalGoldCurrent = 0;
    let totalPhysicalGoldPL = 0;
    
    holdings.forEach((holding) => {
      const weight = holding.weight_gms || 0;
      const ibjaRate = holding.bought_ibja_rate_per_gm || 0;
      const latestPrice = holding.latest_ibja_price_per_gm || ibjaRate;
      totalPhysicalGoldInvested += weight * ibjaRate;
      totalPhysicalGoldCurrent += weight * latestPrice;
      totalPhysicalGoldPL += holding.pl || 0;
    });

    const paginationData = this.physicalGoldPagination.paginate(holdings);
    const { pageData } = paginationData;

    pageData.forEach((holding) => {
      tbody.innerHTML += this._buildPhysicalGoldRow(holding);
    });

    this._renderPhysicalGoldPagination(paginationData);
    
    const plPct = totalPhysicalGoldInvested ? (totalPhysicalGoldPL / totalPhysicalGoldInvested * 100) : 0;
    
    return { 
      invested: totalPhysicalGoldInvested,
      current: totalPhysicalGoldCurrent,
      pl: totalPhysicalGoldPL,
      plPct: plPct
    };
  }

  _buildPhysicalGoldRow(holding) {
    const weight = holding.weight_gms ? holding.weight_gms.toFixed(3) : '0.000';
    const ibjaRate = Formatter.formatCurrency(holding.bought_ibja_rate_per_gm || 0);
    
    let latestPrice = '-';
    if (holding.latest_ibja_price_per_gm) {
      latestPrice = Formatter.formatCurrency(holding.latest_ibja_price_per_gm);
    }
    
    const pl = holding.pl || 0;
    const plPct = holding.pl_pct || 0;
    
    let plDisplay = '-';
    let plColor = '#999';
    
    if (holding.pl !== undefined) {
      plDisplay = Formatter.formatCurrency(Math.abs(pl));
      if (pl < 0) {
        plDisplay = '-' + plDisplay;
      }
      plColor = Formatter.colorPL(pl);
      const pctText = Formatter.formatPercentage(plPct);
      plDisplay = `${plDisplay} <span class="pl_pct_small" style="color:${plColor}">${pctText}</span>`;
    }

    return `<tr style="background-color:${Formatter.rowColor(pl)}">
      <td>${holding.date || '-'}</td>
      <td>${holding.type || '-'}</td>
      <td>${holding.retail_outlet || '-'}</td>
      <td style="font-weight:600;color:#d4af37">${holding.purity || '-'}</td>
      <td>${weight}</td>
      <td>${ibjaRate}</td>
      <td>${latestPrice}</td>
      <td style="color:${plColor};font-weight:600">${plDisplay}</td>
    </tr>`;
  }

  _renderPhysicalGoldPagination(paginationData) {
    const paginationInfo = document.getElementById('physical_gold_pagination_info');
    const paginationButtons = document.getElementById('physical_gold_pagination_buttons');

    if (!paginationInfo || !paginationButtons) return;

    PaginationManager.updatePaginationUI(
      paginationData,
      'physical_gold_pagination_info',
      'physical_gold_pagination_buttons',
      'goToPhysicalGoldPage',
      'holdings'
    );
  }

  changePhysicalGoldPageSize(size) {
    this.physicalGoldPagination.changePageSize(size);
  }

  goToPhysicalGoldPage(page) {
    this.physicalGoldPagination.goToPage(page);
  }

  /**
   * Render fixed deposits table with pagination
   */
  renderFixedDepositsTable(deposits) {
    const tbody = document.getElementById('fixed_deposits_table_body');
    const section = document.getElementById('fixed-deposits-section');
    
    if (!tbody) return { invested: 0, maturity: 0, returns: 0, returnsPct: 0 };

    tbody.innerHTML = '';

    const table = section ? section.querySelector('table') : null;
    const emptyState = document.getElementById('fixed_deposits_empty_state');
    const controlsContainer = section ? section.querySelector('.controls-container') : null;
    const paginationInfo = document.getElementById('fixed_deposits_pagination_info');
    const paginationButtons = document.getElementById('fixed_deposits_pagination_buttons');

    if (!deposits || deposits.length === 0) {
      if (table) table.style.display = 'none';
      if (emptyState) emptyState.style.display = 'block';
      if (controlsContainer) controlsContainer.style.display = 'none';
      if (paginationInfo) paginationInfo.style.display = 'none';
      if (paginationButtons) paginationButtons.style.display = 'none';
      return { invested: 0, maturity: 0, returns: 0, returnsPct: 0 };
    }

    if (table) table.style.display = 'table';
    if (emptyState) emptyState.style.display = 'none';
    if (controlsContainer) controlsContainer.style.display = 'flex';
    if (paginationInfo) paginationInfo.style.display = 'block';
    if (paginationButtons) paginationButtons.style.display = 'flex';

    // Calculate totals
    let totalInvested = 0;
    let totalCurrentValue = 0;
    
    deposits.forEach((deposit) => {
      totalInvested += deposit.original_amount || 0;
      totalCurrentValue += deposit.current_value || 0;
    });
    
    const totalReturns = totalCurrentValue - totalInvested;
    const returnsPct = totalInvested > 0 ? (totalReturns / totalInvested * 100) : 0;

    const paginationData = this.fixedDepositsPagination.paginate(deposits);
    const { pageData } = paginationData;

    pageData.forEach((deposit) => {
      tbody.innerHTML += this._buildFixedDepositRow(deposit);
    });

    this._renderFixedDepositsPagination(paginationData);
    
    return {
      invested: totalInvested,
      maturity: totalCurrentValue,
      returns: totalReturns,
      returnsPct: returnsPct
    };
  }

  _buildFixedDepositRow(deposit) {
    const originalAmount = Formatter.formatCurrency(deposit.original_amount || 0);
    const reinvestedAmount = Formatter.formatCurrency(deposit.reinvested_amount)
    const currentValue = Formatter.formatCurrency(deposit.current_value || 0);
    const interestRate = deposit.interest_rate ? `${deposit.interest_rate.toFixed(2)}%` : '-';

    return `<tr>
      <td>${deposit.original_investment_date || '-'}</td>
      <td>${deposit.reinvested_date || '-'}</td>
      <td>${deposit.bank_name || '-'}</td>
      <td>${originalAmount}</td>
      <td>${reinvestedAmount}</td>
      <td style="color:#3498db;font-weight:600">${interestRate}</td>
      <td>${deposit.maturity_date || '-'}</td>
      <td>${currentValue}</td>
      <td>${deposit.account || '-'}</td>
    </tr>`;
  }

  _renderFixedDepositsPagination(paginationData) {
    const paginationInfo = document.getElementById('fixed_deposits_pagination_info');
    const paginationButtons = document.getElementById('fixed_deposits_pagination_buttons');

    if (!paginationInfo || !paginationButtons) return;

    PaginationManager.updatePaginationUI(
      paginationData,
      'fixed_deposits_pagination_info',
      'fixed_deposits_pagination_buttons',
      'goToFixedDepositsPage',
      'deposits'
    );
  }

  changeFixedDepositsPageSize(size) {
    this.fixedDepositsPagination.changePageSize(size);
  }

  goToFixedDepositsPage(page) {
    this.fixedDepositsPagination.goToPage(page);
  }

}

export default TableRenderer;

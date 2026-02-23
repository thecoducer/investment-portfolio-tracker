/* Portfolio Tracker - Main Application Controller */

import DataManager from './data-manager.js';
import TableRenderer from './table-renderer.js';
import SummaryManager from './summary-manager.js';
import SortManager from './sort-manager.js';
import ThemeManager from './theme-manager.js';
import PrivacyManager from './visibility-manager.js';
import SSEConnectionManager from './sse-manager.js';
import PaginationManager from './pagination.js';
import { Formatter, Calculator } from './utils.js';

class PortfolioApp {
  constructor() {
    this.dataManager = new DataManager();
    this.tableRenderer = new TableRenderer();
    this.summaryManager = new SummaryManager();
    this.sortManager = new SortManager();
    this.themeManager = new ThemeManager();
    this.privacyManager = new PrivacyManager();
    this.sseManager = new SSEConnectionManager();
    this.needsLogin = false;
    this.lastStatus = null;
    this.searchTimeout = null;
    // _wasUpdating and _wasWaitingForLogin intentionally left undefined
    // to detect first status update on page load
  }

  async init() {
    Formatter.initCompactFormat();
    this._updateCompactFormatIcon();
    this.themeManager.init();
    this.privacyManager.init();
    this._setupEventListeners();
    
    this._hideLoadingIndicators();
    
    this._renderEmptyStates();
    
    // Connect SSE without fetching initial data
    // Data will be fetched only on manual refresh or when auto-refresh completes
    this.connectEventSource();
  }

  _hideLoadingIndicators() {
    const loadingIds = [
      'combined_summary_loading',
      'stocks_summary_loading',
      'mf_summary_loading'
    ];
    
    loadingIds.forEach(id => {
      const element = document.getElementById(id);
      if (element) element.style.display = 'none';
    });
  }

  _renderEmptyStates() {
    this.tableRenderer.renderStocksTable([], { portfolio_state: 'idle' });
    this.tableRenderer.renderMFTable([], { portfolio_state: 'idle' });
    this.tableRenderer.renderSIPsTable([], { portfolio_state: 'idle' });
    this.tableRenderer.renderPhysicalGoldTable([]);
    this.tableRenderer.renderFixedDepositsTable([]);
    this.tableRenderer.renderFDSummaryTable([]);
  }

  _isStatusUpdating(status) {
    // Portfolio page: check portfolio, physical gold, and fixed deposits (not Nifty50 background fetch)
    return status.portfolio_state === 'updating' || 
           status.physical_gold_state === 'updating' ||
           status.fixed_deposits_state === 'updating';
  }

  /**
   * Calculate combined gold totals (ETFs + Physical Gold)
   * @param {Object} goldETFTotals - Gold ETF totals from stocks
   * @param {Object} physicalGoldTotals - Physical gold totals
   * @returns {Object} Combined totals with invested, current, pl, plPct
   */
  _calculateCombinedGoldTotals(goldETFTotals, physicalGoldTotals) {
    const totalInvested = goldETFTotals.invested + physicalGoldTotals.invested;
    const totalCurrent = goldETFTotals.current + physicalGoldTotals.current;
    const totalPL = goldETFTotals.pl + physicalGoldTotals.pl;
    const totalPLPct = totalInvested ? (totalPL / totalInvested * 100) : 0;
    
    return {
      invested: totalInvested,
      current: totalCurrent,
      pl: totalPL,
      plPct: totalPLPct
    };
  }

  _updateCompactFormatIcon() {
    const icon = document.getElementById('compact_toggle_icon');
    if (icon) {
      icon.textContent = Formatter.isCompactFormat ? '🔤' : '🔢';
    }
  }

  _setupEventListeners() {
    const searchInput = document.getElementById('search');
    searchInput.addEventListener('input', () => {
      if (this.searchTimeout) clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => this.handleSearch(), 150);
    });

    window.toggleTheme = () => this.themeManager.toggle();
    window.togglePrivacy = () => this.privacyManager.toggle();
    window.toggleCompactFormat = () => {
      Formatter.toggleCompactFormat();
      this._updateCompactFormatIcon();
      this.handleSearch();
    };
    window.triggerRefresh = () => this.handleRefresh();
    window.sortStocksTable = (sortBy) => this.handleStocksSort(sortBy);
    window.sortMFTable = (sortBy) => this.handleMFSort(sortBy);
    window.sortPhysicalGoldTable = (sortBy) => this.handlePhysicalGoldSort(sortBy);
    window.sortFixedDepositsTable = (sortBy) => this.handleFixedDepositsSort(sortBy);
    window.changeStocksPageSize = (size) => {
      this.tableRenderer.changeStocksPageSize(size);
      this.updateData();
    };
    window.goToStocksPage = (page) => {
      this.tableRenderer.goToStocksPage(page);
      this.updateData();
    };
    window.changeMFPageSize = (size) => {
      this.tableRenderer.changeMFPageSize(parseInt(size));
      this.updateData();
    };
    window.goToMFPage = (page) => {
      this.tableRenderer.goToMFPage(page);
      this.updateData();
    };
    window.changePhysicalGoldPageSize = (size) => {
      this.tableRenderer.changePhysicalGoldPageSize(parseInt(size));
      this.updateData();
    };
    window.goToPhysicalGoldPage = (page) => {
      this.tableRenderer.goToPhysicalGoldPage(page);
      this.updateData();
    };
    window.changeFixedDepositsPageSize = (size) => {
      this.tableRenderer.changeFixedDepositsPageSize(parseInt(size));
      this.updateData();
    };
    window.goToFixedDepositsPage = (page) => {
      this.tableRenderer.goToFixedDepositsPage(page);
      this.updateData();
    };
    window.sortFDSummaryTable = (sortBy) => this.handleFDSummarySort(sortBy);
    window.changeFDSummaryPageSize = (size) => {
      this.tableRenderer.changeFDSummaryPageSize(parseInt(size));
      this.updateData();
    };
    window.goToFDSummaryPage = (page) => {
      this.tableRenderer.goToFDSummaryPage(page);
      this.updateData();
    };
  }

  connectEventSource() {
    this.sseManager.onMessage((status) => this.handleStatusUpdate(status));
    this.sseManager.connect();
  }

  handleStatusUpdate(status) {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    const isUpdating = this._isStatusUpdating(status);
    const waitingForLogin = status.waiting_for_login === true;

    this.lastStatus = status;

    const physicalGoldWasUpdating = this._physicalGoldWasUpdating || false;
    const physicalGoldIsUpdating = status.physical_gold_state === 'updating';
    const physicalGoldJustCompleted = physicalGoldWasUpdating && !physicalGoldIsUpdating && status.physical_gold_state === 'updated';
    this._physicalGoldWasUpdating = physicalGoldIsUpdating;

    const fixedDepositsWasUpdating = this._fixedDepositsWasUpdating || false;
    const fixedDepositsIsUpdating = status.fixed_deposits_state === 'updating';
    const fixedDepositsJustCompleted = fixedDepositsWasUpdating && !fixedDepositsIsUpdating && status.fixed_deposits_state === 'updated';
    this._fixedDepositsWasUpdating = fixedDepositsIsUpdating;

    const sessionValidity = status.session_validity || {};
    const anyAccountInvalid = Object.keys(sessionValidity).length > 0 && 
                              Object.values(sessionValidity).some(valid => !valid);
    this.needsLogin = anyAccountInvalid && !isUpdating && !waitingForLogin;

    const isNotLoaded = status.portfolio_state === null;
    statusTag.classList.toggle('updating', isUpdating || waitingForLogin);
    statusTag.classList.toggle('updated', !isUpdating && !waitingForLogin && !isNotLoaded);
    statusTag.classList.toggle('not-loaded', isNotLoaded);
    statusTag.classList.toggle('market_closed', status.market_open === false);
    statusTag.classList.toggle('needs-login', this.needsLogin);

    if (waitingForLogin) {
      statusText.innerText = 'waiting for login';
    } else if (isUpdating) {
      statusText.innerText = 'updating';
    } else if (status.portfolio_state === null) {
      statusText.innerText = 'not loaded';
    } else {
      statusText.innerText = 'updated' + (status.portfolio_last_updated ? ` • ${status.portfolio_last_updated}` : '');
    }

    this._updateRefreshButton(isUpdating || waitingForLogin, this.needsLogin);

    const hasData = this.dataManager.getStocks().length > 0 ||
                    this.dataManager.getMFHoldings().length > 0 ||
                    this.dataManager.getSIPs().length > 0;

    this._renderTablesAndSummary(hasData, status, isUpdating || waitingForLogin);

    // Fetch data when:
    // 1. First time receiving status with portfolio already updated (initial page load)
    // 2. State changed from 'updating' to 'updated' (normal refresh complete)
    // 3. Login just completed (was waiting, now not waiting)
    // 4. Physical gold or fixed deposits just completed fetching
    const isFirstStatusUpdate = this._wasUpdating === undefined;
    const portfolioAlreadyUpdated = status.portfolio_state === 'updated' && !isUpdating;
    const justCompletedLogin = this._wasWaitingForLogin && !waitingForLogin && !isUpdating;
    const shouldFetchData = (isFirstStatusUpdate && portfolioAlreadyUpdated) ||
                           (!isUpdating && this._wasUpdating) ||
                           justCompletedLogin ||
                           physicalGoldJustCompleted ||
                           fixedDepositsJustCompleted;

    if (shouldFetchData) {
      this.updateData();
    }

    this._wasUpdating = isUpdating;
    this._wasWaitingForLogin = waitingForLogin;
  }

  _renderTablesAndSummary(hasData, status, isUpdating) {
    const sortedPhysicalGold = this.sortManager.sortPhysicalGold(
      this.dataManager.getPhysicalGold(),
      this.sortManager.getPhysicalGoldSortOrder()
    );
    const physicalGoldTotals = this.tableRenderer.renderPhysicalGoldTable(sortedPhysicalGold);

    const sortedFixedDeposits = this.sortManager.sortFixedDeposits(
      this.dataManager.getFixedDeposits(),
      this.sortManager.getFixedDepositsSortOrder()
    );
    const fdTotals = this.tableRenderer.renderFixedDepositsTable(sortedFixedDeposits);

    if (hasData) {
      const sortedHoldings = this.sortManager.sortStocks(
        this.dataManager.getStocks(),
        this.sortManager.getStocksSortOrder()
      );
      const sortedMFHoldings = this.sortManager.sortMF(
        this.dataManager.getMFHoldings(),
        this.sortManager.getMFSortOrder()
      );

      const { stockTotals, goldTotals, silverTotals } = this.tableRenderer.renderStocksTable(sortedHoldings, status);
      const mfTotals = this.tableRenderer.renderMFTable(sortedMFHoldings, status);
      this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);
      
      const combinedGoldTotals = this._calculateCombinedGoldTotals(goldTotals, physicalGoldTotals);
      
      this.summaryManager.updateAllSummaries(stockTotals, combinedGoldTotals, silverTotals, mfTotals, fdTotals, isUpdating);
    } else {
      const combinedGoldTotals = this._calculateCombinedGoldTotals(
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        physicalGoldTotals
      );
      this.summaryManager.updateAllSummaries(
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        combinedGoldTotals,
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        fdTotals,
        isUpdating
      );
    }
  }

  /**
   * Sort all data, render all tables, and update summary cards.
   * Centralizes the repeated sort→render→summarize pattern.
   * @param {Object} status - Current status object
   * @param {Object} [opts] - Options
   * @param {boolean} [opts.renderSIPs=false] - Whether to also render the SIPs table
   * @param {boolean} [opts.isUpdating=false] - Whether data is currently updating
   * @param {Array|null} [opts.fdSummaryData=null] - If provided, render FD summary table with this data
   */
  _renderAllAndUpdateSummaries(status, { renderSIPs = false, isUpdating = false, fdSummaryData = null } = {}) {
    const sortedHoldings = this.sortManager.sortStocks(
      this.dataManager.getStocks(),
      this.sortManager.getStocksSortOrder()
    );
    const sortedMFHoldings = this.sortManager.sortMF(
      this.dataManager.getMFHoldings(),
      this.sortManager.getMFSortOrder()
    );
    const sortedPhysicalGold = this.sortManager.sortPhysicalGold(
      this.dataManager.getPhysicalGold(),
      this.sortManager.getPhysicalGoldSortOrder()
    );
    const sortedFixedDeposits = this.sortManager.sortFixedDeposits(
      this.dataManager.getFixedDeposits(),
      this.sortManager.getFixedDepositsSortOrder()
    );

    const { stockTotals, goldTotals, silverTotals } = this.tableRenderer.renderStocksTable(sortedHoldings, status);
    const mfTotals = this.tableRenderer.renderMFTable(sortedMFHoldings, status);
    if (renderSIPs) {
      this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);
    }
    const physicalGoldTotals = this.tableRenderer.renderPhysicalGoldTable(sortedPhysicalGold);
    const fdTotals = this.tableRenderer.renderFixedDepositsTable(sortedFixedDeposits);

    if (fdSummaryData && fdSummaryData.length > 0) {
      this.tableRenderer.renderFDSummaryTable(fdSummaryData);
    }

    const combinedGoldTotals = this._calculateCombinedGoldTotals(goldTotals, physicalGoldTotals);

    this.summaryManager.updateAllSummaries(stockTotals, combinedGoldTotals, silverTotals, mfTotals, fdTotals, isUpdating);
  }

  handleSearch() {
    const searchQuery = document.getElementById('search').value;
    this.tableRenderer.setSearchQuery(searchQuery);
    this._renderAllAndUpdateSummaries(this.lastStatus || {}, { renderSIPs: true });
  }

  async updateData() {
    try {
      const { stocks, mfHoldings, sips, physicalGold, fixedDeposits, fdSummary, status } = await this.dataManager.fetchAllData();

      this._hideLoadingIndicators();

      const searchQuery = document.getElementById('search').value;
      const forceUpdate = searchQuery !== '';
      
      this.dataManager.updateStocks(stocks, forceUpdate);
      this.dataManager.updateMFHoldings(mfHoldings, forceUpdate);
      this.dataManager.updateSIPs(sips, forceUpdate);
      this.dataManager.updatePhysicalGold(physicalGold, forceUpdate);
      this.dataManager.updateFixedDeposits(fixedDeposits, forceUpdate);
      this.dataManager.updateFDSummary(fdSummary, forceUpdate);

      this.tableRenderer.setSearchQuery(searchQuery);

      this._renderAllAndUpdateSummaries(status, {
        renderSIPs: true,
        isUpdating: this._isStatusUpdating(status),
        fdSummaryData: this.dataManager.getFDSummary()
      });
    } catch (error) {
      console.error('Error updating data:', error);
    }
  }

  handleStocksSort(sortBy) {
    this.sortManager.setStocksSortOrder(sortBy);
    this._renderAllAndUpdateSummaries(this.lastStatus || {});
  }

  handleMFSort(sortBy) {
    this.sortManager.setMFSortOrder(sortBy);
    this._renderAllAndUpdateSummaries(this.lastStatus || {});
  }

  handlePhysicalGoldSort(sortBy) {
    this.sortManager.setPhysicalGoldSortOrder(sortBy);
    this._renderAllAndUpdateSummaries(this.lastStatus || {});
  }

  handleFixedDepositsSort(sortBy) {
    this.sortManager.setFixedDepositsSortOrder(sortBy);
    const sortedFixedDeposits = this.sortManager.sortFixedDeposits(
      this.dataManager.getFixedDeposits(),
      this.sortManager.getFixedDepositsSortOrder()
    );
    this.tableRenderer.renderFixedDepositsTable(sortedFixedDeposits);
    this.tableRenderer.renderFDSummaryTable(sortedFixedDeposits);
  }

  handleFDSummarySort(sortBy) {
    this.sortManager.setFDSummarySortOrder(sortBy);
    const fixedDeposits = this.dataManager.getFixedDeposits();
    const tbody = document.getElementById('fd_summary_table_body');
    if (!tbody) return;

    // Get current summary data from table
    const groupedData = this.tableRenderer._groupFDByBankAndAccount(fixedDeposits);
    const summaryArray = Object.values(groupedData);
    
    // Sort and re-render
    const sortedSummary = this.sortManager.sortFDSummary(summaryArray, sortBy);
    
    // Update pagination and re-render
    this.tableRenderer.fdSummaryPagination.goToPage(1);
    const paginationData = this.tableRenderer.fdSummaryPagination.paginate(sortedSummary);
    
    let rowsHTML = '';
    paginationData.pageData.forEach((summary) => {
      rowsHTML += this.tableRenderer._buildFDSummaryRow(summary);
    });
    tbody.innerHTML = rowsHTML;

    PaginationManager.updatePaginationUI(
      paginationData,
      'fd_summary_pagination_info',
      'fd_summary_pagination_buttons',
      'goToFDSummaryPage',
      'summaries'
    );
  }

  async handleRefresh() {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    
    statusTag.className = 'updating';
    statusText.innerText = 'updating';
    this._updateRefreshButton(true);

    try {
      await this.dataManager.triggerRefresh();
    } catch (error) {
      alert('Error triggering refresh: ' + error.message);
    }
  }

  _updateRefreshButton(isUpdating, needsLogin = false) {
    const btnText = document.getElementById('refresh_btn_text');
    if (isUpdating) {
      btnText.innerHTML = '<span class="spinner"></span>';
    } else {
      btnText.textContent = needsLogin ? 'Login' : 'Refresh';
    }
  }

  disconnect() {
    this.sseManager.disconnect();
  }
}

// Global function to toggle group expansion
window.toggleGroupExpand = function(event, groupId) {
  event.stopPropagation();
  const toggleBtn = event.target;
  const breakdownRows = document.querySelectorAll(`.breakdown-row.${groupId}`);
  const isExpanded = toggleBtn.classList.contains('expanded');
  
  // Access the global app instance to track expanded state
  if (window.portfolioApp && window.portfolioApp.tableRenderer) {
    if (isExpanded) {
      breakdownRows.forEach(row => {
        row.style.display = 'none';
      });
      toggleBtn.classList.remove('expanded');
      toggleBtn.textContent = '▶';
      window.portfolioApp.tableRenderer.markGroupCollapsed(groupId);
    } else {
      breakdownRows.forEach(row => {
        row.style.display = 'table-row';
      });
      toggleBtn.classList.add('expanded');
      toggleBtn.textContent = '▼';
      window.portfolioApp.tableRenderer.markGroupExpanded(groupId);
    }
  }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new PortfolioApp();
  window.portfolioApp = app; // Expose app globally for toggle function
  app.init();
});

export default PortfolioApp;

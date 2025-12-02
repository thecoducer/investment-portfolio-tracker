/* Portfolio Tracker - Main Application Controller */

import DataManager from './data-manager.js';
import TableRenderer from './table-renderer.js';
import SummaryManager from './summary-manager.js';
import SortManager from './sort-manager.js';
import ThemeManager from './theme-manager.js';
import PrivacyManager from './visibility-manager.js';
import SSEConnectionManager from './sse-manager.js';
import { Formatter, Calculator } from './utils.js';

class PortfolioApp {
  constructor() {
    this.dataManager = new DataManager();
    this.tableRenderer = new TableRenderer();
    this.summaryManager = new SummaryManager();
    this.sortManager = new SortManager();
    this.themeManager = new ThemeManager();
    this.privacyManager = new PrivacyManager();
    this.updateInterval = null;
    this.sseManager = new SSEConnectionManager();
    this.needsLogin = false;
    this._wasUpdating = false;
    this._wasWaitingForLogin = false;
    this.searchTimeout = null;
  }

  async init() {
    Formatter.initCompactFormat();
    this._updateCompactFormatIcon();
    this.themeManager.init();
    this.privacyManager.init();
    this._setupEventListeners();
    // Show loading placeholders
    document.getElementById('combined_summary_loading').style.display = '';
    document.getElementById('stocks_summary_loading').style.display = '';
    document.getElementById('mf_summary_loading').style.display = '';
    document.getElementById('stocks_table_loading').style.display = '';
    document.getElementById('mf_table_loading').style.display = '';
    document.getElementById('sips_table_loading').style.display = '';
    this.connectEventSource();
  }

  _isStatusUpdating(status) {
    return status.portfolio_state === 'updating';
  }

  _updateCompactFormatIcon() {
    const icon = document.getElementById('compact_toggle_icon');
    if (icon) {
      icon.textContent = Formatter.isCompactFormat ? '🔤' : '🔢';
    }
  }

  _setupEventListeners() {
    // Search functionality with debouncing
    document.getElementById('search').addEventListener('input', () => {
      // Clear previous timeout
      if (this.searchTimeout) {
        clearTimeout(this.searchTimeout);
      }
      // Set new timeout - execute search after 150ms of no typing
      this.searchTimeout = setTimeout(() => {
        this.handleSearch();
      }, 150);
    });

    // Theme toggle
    window.toggleTheme = () => this.themeManager.toggle();

    // Privacy toggle
    window.togglePrivacy = () => this.privacyManager.toggle();

    // Compact format toggle
    window.toggleCompactFormat = () => {
      Formatter.toggleCompactFormat();
      this._updateCompactFormatIcon();
      // Re-render with current search filter to respect filtered data
      this.handleSearch();
    };

    // Refresh button
    window.triggerRefresh = () => this.handleRefresh();

    // Sort handlers
    window.sortStocksTable = (sortBy) => this.handleStocksSort(sortBy);
    window.sortMFTable = (sortBy) => this.handleMFSort(sortBy);

    // Stocks pagination handlers
    window.changeStocksPageSize = (size) => {
      this.tableRenderer.changeStocksPageSize(size);
      this.updateData();
    };
    window.goToStocksPage = (page) => {
      this.tableRenderer.goToStocksPage(page);
      this.updateData();
    };
  }

  connectEventSource() {
    // Set up SSE connection with handlers
    this.sseManager.onMessage((status) => this.handleStatusUpdate(status));
    this.sseManager.connect();
  }

  handleStatusUpdate(status) {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    const isUpdating = this._isStatusUpdating(status);
    const waitingForLogin = status.waiting_for_login === true;

    // Store status for later use
    this.lastStatus = status;

    // Check if any account needs login (at least one invalid session)
    const sessionValidity = status.session_validity || {};
    const anyAccountInvalid = Object.keys(sessionValidity).length > 0 && 
                              Object.values(sessionValidity).some(valid => !valid);
    this.needsLogin = anyAccountInvalid && !isUpdating && !waitingForLogin;

    // Update status class
    statusTag.classList.toggle('updating', isUpdating || waitingForLogin);
    statusTag.classList.toggle('updated', !isUpdating && !waitingForLogin);
    statusTag.classList.toggle('market_closed', status.market_open === false);
    statusTag.classList.toggle('needs-login', this.needsLogin);

    // Update status text based on state
    if (waitingForLogin) {
      statusText.innerText = 'waiting for login';
    } else if (isUpdating) {
      statusText.innerText = 'updating';
    } else {
      statusText.innerText = 'updated' + (status.portfolio_last_updated ? ` • ${status.portfolio_last_updated}` : '');
    }

    this._updateRefreshButton(isUpdating || waitingForLogin, this.needsLogin);

    const hasData = this.dataManager.getHoldings().length > 0 ||
                    this.dataManager.getMFHoldings().length > 0 ||
                    this.dataManager.getSIPs().length > 0;

    this._renderTablesAndSummary(hasData, status, isUpdating || waitingForLogin);

    // Fetch data when:
    // 1. State changed from 'updating' to 'updated' (normal refresh complete)
    // 2. State is 'updated' but we have no data yet (first load after server restart)
    // 3. Login just completed (was waiting, now not waiting)
    const justCompletedLogin = this._wasWaitingForLogin && !waitingForLogin && !isUpdating;
    const shouldFetchData = (!isUpdating && this._wasUpdating) ||
                           (!isUpdating && !hasData) ||
                           justCompletedLogin;

    if (shouldFetchData) {
      this.updateData();
    }

    this._wasUpdating = isUpdating;
    this._wasWaitingForLogin = waitingForLogin;
  }

  _renderTablesAndSummary(hasData, status, isUpdating) {
    if (hasData) {
      // Re-render tables and get totals with current sort order
      const sortedHoldings = this.sortManager.sortStocks(
        this.dataManager.getHoldings(),
        this.sortManager.getStocksSortOrder()
      );
      const sortedMFHoldings = this.sortManager.sortMF(
        this.dataManager.getMFHoldings(),
        this.sortManager.getMFSortOrder()
      );

      const stockTotals = this.tableRenderer.renderStocksTable(sortedHoldings, status);
      const mfTotals = this.tableRenderer.renderMFTable(sortedMFHoldings, status);
      this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);
      this.summaryManager.updateAllSummaries(stockTotals, mfTotals, isUpdating);
    } else {
      // First load - show zeros
      this.summaryManager.updateAllSummaries(
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        isUpdating
      );
    }
  }

  handleSearch() {
    const searchQuery = document.getElementById('search').value;
    this.tableRenderer.setSearchQuery(searchQuery);

    // Re-render with current data, no fetch
    const holdings = this.dataManager.getHoldings();
    const mfHoldings = this.dataManager.getMFHoldings();
    const sips = this.dataManager.getSIPs();
    // Use last status if available, or empty object
    const status = this.lastStatus || {};

    const sortedHoldings = this.sortManager.sortStocks(holdings, this.sortManager.getStocksSortOrder());
    const sortedMFHoldings = this.sortManager.sortMF(mfHoldings, this.sortManager.getMFSortOrder());

    const stockTotals = this.tableRenderer.renderStocksTable(sortedHoldings, status);
    const mfTotals = this.tableRenderer.renderMFTable(sortedMFHoldings, status);
    this.tableRenderer.renderSIPsTable(sips, status);
    this.summaryManager.updateAllSummaries(stockTotals, mfTotals, false);
  }

  async updateData() {
    try {
      const { holdings, mfHoldings, sips, status } = await this.dataManager.fetchAllData();

      // Hide loading placeholders
      const combinedLoading = document.getElementById('combined_summary_loading');
      if(combinedLoading) combinedLoading.style.display = 'none';
      
      const stocksSummaryLoading = document.getElementById('stocks_summary_loading');
      if(stocksSummaryLoading) stocksSummaryLoading.style.display = 'none';
      
      const mfSummaryLoading = document.getElementById('mf_summary_loading');
      if(mfSummaryLoading) mfSummaryLoading.style.display = 'none';
      
      const stocksTableLoading = document.getElementById('stocks_table_loading');
      if(stocksTableLoading) stocksTableLoading.style.display = 'none';
      
      const mfTableLoading = document.getElementById('mf_table_loading');
      if(mfTableLoading) mfTableLoading.style.display = 'none';
      
      const sipsTableLoading = document.getElementById('sips_table_loading');
      if(sipsTableLoading) sipsTableLoading.style.display = 'none';

      // Update data manager state
      const searchQuery = document.getElementById('search').value;
      const forceUpdate = searchQuery !== '';
      
      this.dataManager.updateHoldings(holdings, forceUpdate);
      this.dataManager.updateMFHoldings(mfHoldings, forceUpdate);
      this.dataManager.updateSIPs(sips, forceUpdate);

      // Update search query in renderer
      this.tableRenderer.setSearchQuery(searchQuery);

      // Apply current sort orders
      const sortedHoldings = this.sortManager.sortStocks(
        this.dataManager.getHoldings(),
        this.sortManager.getStocksSortOrder()
      );
      const sortedMFHoldings = this.sortManager.sortMF(
        this.dataManager.getMFHoldings(),
        this.sortManager.getMFSortOrder()
      );

      // Render tables and get totals
      const stockTotals = this.tableRenderer.renderStocksTable(sortedHoldings, status);
      const mfTotals = this.tableRenderer.renderMFTable(sortedMFHoldings, status);
      this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);

      // Update all summary cards with totals from rendered tables
      // isUpdating is already calculated from status
      const isUpdating = this._isStatusUpdating(status);
      this.summaryManager.updateAllSummaries(stockTotals, mfTotals, isUpdating);

    } catch (error) {
      console.error('Error updating data:', error);
    }
  }

  handleStocksSort(sortBy) {
    this.sortManager.setStocksSortOrder(sortBy);
    const holdings = this.dataManager.getHoldings();
    const status = this.lastStatus || {};
    const sortedHoldings = this.sortManager.sortStocks(holdings, this.sortManager.getStocksSortOrder());
    this.tableRenderer.renderStocksTable(sortedHoldings, status);
  }

  handleMFSort(sortBy) {
    this.sortManager.setMFSortOrder(sortBy);
    const mfHoldings = this.dataManager.getMFHoldings();
    const status = this.lastStatus || {};
    const sortedMFHoldings = this.sortManager.sortMF(mfHoldings, this.sortManager.getMFSortOrder());
    this.tableRenderer.renderMFTable(sortedMFHoldings, status);
  }

  async handleRefresh() {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    
    statusTag.className = '';
    void statusTag.offsetWidth;
    statusTag.className = 'updating';
    
    this._updateRefreshButton(true);
    statusText.innerText = 'updating';

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

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new PortfolioApp();
  app.init();
});

export default PortfolioApp;

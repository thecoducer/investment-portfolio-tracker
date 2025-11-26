/* Portfolio Tracker - Main Application Controller */

import DataManager from './data-manager.js';
import TableRenderer from './table-renderer.js';
import SummaryManager from './summary-manager.js';
import SortManager from './sort-manager.js';
import ThemeManager from './theme-manager.js';
import PrivacyManager from './visibility-manager.js';

class PortfolioApp {
  constructor() {
    this.dataManager = new DataManager();
    this.tableRenderer = new TableRenderer();
    this.summaryManager = new SummaryManager();
    this.sortManager = new SortManager();
    this.themeManager = new ThemeManager();
    this.privacyManager = new PrivacyManager();
    this.updateInterval = null;
    this.eventSource = null;
  }

  async init() {
    this.themeManager.init();
    this.privacyManager.init();
    this._setupEventListeners();
    // Show loading placeholders
    document.getElementById('combined_summary_loading').style.display = '';
    document.getElementById('portfolio_summary_loading').style.display = '';
    document.getElementById('mf_summary_loading').style.display = '';
    document.getElementById('stocks_table_loading').style.display = '';
    document.getElementById('mf_table_loading').style.display = '';
    document.getElementById('sips_table_loading').style.display = '';
    this.connectEventSource();
  }

  _isStatusUpdating(status) {
    return status.state === 'updating' || status.ltp_fetch_state === 'updating';
  }

  _setupEventListeners() {
    // Search functionality
    document.getElementById('search').addEventListener('input', () => {
      this.handleSearch();
    });

    // Theme toggle
    window.toggleTheme = () => this.themeManager.toggle();

    // Privacy toggle
    window.togglePrivacy = () => this.privacyManager.toggle();

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
    // Close existing connection if any
    if (this.eventSource) {
      this.eventSource.close();
    }

    // Connect to SSE endpoint
    this.eventSource = new EventSource('/events');

    this.eventSource.onmessage = (event) => {
      try {
        const status = JSON.parse(event.data);
        this.handleStatusUpdate(status);
      } catch (error) {
        console.error('Error parsing SSE message:', error);
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      // Try to reconnect after 5 seconds
      setTimeout(() => {
        if (this.eventSource.readyState === EventSource.CLOSED) {
          console.log('Reconnecting to SSE...');
          this.connectEventSource();
        }
      }, 5000);
    };

    this.eventSource.onopen = () => {
      console.log('SSE connection established');
    };
  }

  handleStatusUpdate(status) {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    const isUpdating = this._isStatusUpdating(status);
    
    // Update status class
    statusTag.classList.toggle('updating', isUpdating);
    statusTag.classList.toggle('updated', !isUpdating);
    statusTag.classList.toggle('market_closed', status.market_open === false);
    
    statusText.innerText = isUpdating 
      ? 'updating' 
      : ('updated' + (status.holdings_last_updated ? ` • ${status.holdings_last_updated}` : ''));

    this._updateRefreshButton(status.state === 'updating');
    
    const hasData = this.dataManager.getHoldings().length > 0 || 
                    this.dataManager.getMFHoldings().length > 0 || 
                    this.dataManager.getSIPs().length > 0;
    
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
      // First load - show zeros with animation
      this.summaryManager.updateAllSummaries(
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        { invested: 0, current: 0, pl: 0, plPct: 0 },
        isUpdating
      );
    }

    // Fetch data when:
    // 1. State changed from 'updating' to 'updated' (normal refresh complete)
    // 2. State is 'updated' but we have no data yet (first load after server restart)
    const shouldFetchData = (!isUpdating && this._wasUpdating) || 
                           (!isUpdating && !hasData);
    
    if (shouldFetchData) {
      this.updateData();
    }
    
    this._wasUpdating = isUpdating;
  }

  handleSearch() {
    const searchQuery = document.getElementById('search').value;
    this.tableRenderer.setSearchQuery(searchQuery);
    
    // Re-render with current data
    const holdings = this.dataManager.getHoldings();
    const mfHoldings = this.dataManager.getMFHoldings();
    const sips = this.dataManager.getSIPs();
    
    // Need current status - fetch it
    this.updateData();
  }

  async updateData() {
    try {
      const { holdings, mfHoldings, sips, status } = await this.dataManager.fetchAllData();
      // Hide loading placeholders
      document.getElementById('combined_summary_loading').style.display = 'none';
      document.getElementById('portfolio_summary_loading').style.display = 'none';
      document.getElementById('mf_summary_loading').style.display = 'none';
      document.getElementById('stocks_table_loading').style.display = 'none';
      document.getElementById('mf_table_loading').style.display = 'none';
      document.getElementById('sips_table_loading').style.display = 'none';

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
    this.updateData();
  }

  handleMFSort(sortBy) {
    this.sortManager.setMFSortOrder(sortBy);
    this.updateData();
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

  _updateRefreshButton(isUpdating) {
    const btnText = document.getElementById('refresh_btn_text');
    btnText.innerHTML = isUpdating ? '<span class="spinner"></span>' : 'Refresh';
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new PortfolioApp();
  app.init();
});

export default PortfolioApp;

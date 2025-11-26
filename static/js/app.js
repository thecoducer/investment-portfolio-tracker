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
    // Initialize theme and privacy
    this.themeManager.init();
    this.privacyManager.init();

    // Set up event listeners
    this._setupEventListeners();

    // Show loading state
    this._showLoadingState();

    // Don't fetch data immediately - wait for SSE to indicate backend is ready
    // This prevents showing empty dashboard when data endpoints haven't been populated yet

    // Connect to SSE for real-time updates
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

    // Theme toggle (assuming button will call this via global function)
    window.toggleTheme = () => this.themeManager.toggle();

    // Privacy toggle
    window.togglePrivacy = () => this.privacyManager.toggle();

    // Refresh button (assuming button will call this via global function)
    window.triggerRefresh = () => this.handleRefresh();

    // Sort handlers
    window.sortStocksTable = (sortBy) => this.handleStocksSort(sortBy);
    window.sortMFTable = (sortBy) => this.handleMFSort(sortBy);
  }

  _showLoadingState() {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    statusTag.className = 'updating';
    statusText.innerText = 'updating';
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
    // Update status display
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    const isUpdating = this._isStatusUpdating(status);
    
    // Force animation restart by removing and re-adding class
    const currentClass = statusTag.className;
    const newClass = isUpdating ? 'updating' : 'updated';
    
    if (currentClass !== newClass) {
      statusTag.className = '';
      // Force reflow to restart animation
      void statusTag.offsetWidth;
      statusTag.className = newClass;
    }
    
    statusText.innerText = isUpdating 
      ? 'updating' 
      : ('updated' + (status.holdings_last_updated ? ` • ${status.holdings_last_updated}` : ''));

    // Update refresh button
    this._updateRefreshButton(status.state === 'updating');
    
    // Check if we have any data loaded
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
    
    // Force animation restart
    statusTag.className = '';
    void statusTag.offsetWidth;
    statusTag.className = 'updating';
    
    this._updateRefreshButton(true);
    statusText.innerText = 'updating';

    try {
      // Trigger refresh on server
      await this.dataManager.triggerRefresh();

      // SSE will handle the status updates and trigger data refresh when complete

    } catch (error) {
      alert('Error triggering refresh: ' + error.message);
      btnText.innerText = 'Refresh';
    }
  }

  _updateRefreshButton(isUpdating) {
    const btnText = document.getElementById('refresh_btn_text');
    if (isUpdating) {
      btnText.innerHTML = '<span class="spinner"></span>';
    } else {
      btnText.innerText = 'Refresh';
    }
  }

  startPeriodicUpdates(intervalMs) {
    // No longer needed - SSE handles real-time updates
    console.log('Periodic polling disabled - using SSE for real-time updates');
  }

  stopPeriodicUpdates() {
    // No longer needed
  }

  disconnect() {
    // Clean up SSE connection
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

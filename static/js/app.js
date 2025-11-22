/* Portfolio Tracker - Main Application Controller */

import DataManager from './data-manager.js';
import TableRenderer from './table-renderer.js';
import SummaryManager from './summary-manager.js';
import ThemeManager from './theme-manager.js';
import PrivacyManager from './visibility-manager.js';

class PortfolioApp {
  constructor() {
    this.dataManager = new DataManager();
    this.tableRenderer = new TableRenderer();
    this.summaryManager = new SummaryManager();
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

    // Fetch initial data
    await this.updateData();

    // Connect to SSE for real-time updates
    this.connectEventSource();
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
  }

  _showLoadingState() {
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    statusTag.className = 'updating';
    statusText.innerText = 'loading';
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
    const isUpdating = status.state === 'updating' || status.ltp_fetch_state === 'updating';
    
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
    const btnText = document.getElementById('refresh_btn_text');
    if (status.state === 'updating') {
      btnText.innerHTML = '<span class="spinner"></span>';
    } else {
      btnText.innerText = 'Refresh';
    }

    // Update summary
    const ltpUpdating = status.ltp_fetch_state === 'updating';
    const refreshRunning = status.state === 'updating';
    this.summaryManager.updateCombinedSummary(ltpUpdating, refreshRunning);

    // Re-render tables with current data to apply/remove updating animations
    const hasData = this.dataManager.getHoldings().length > 0 || 
                    this.dataManager.getMFHoldings().length > 0 || 
                    this.dataManager.getSIPs().length > 0;
    
    if (hasData) {
      this.tableRenderer.renderStocksTable(this.dataManager.getHoldings(), status);
      this.tableRenderer.renderMFTable(this.dataManager.getMFHoldings(), status);
      this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);
    }

    // If state changed to 'updated', refresh the data
    if (!isUpdating && this._wasUpdating) {
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

      // Render tables
      this.tableRenderer.renderStocksTable(this.dataManager.getHoldings(), status);
      this.tableRenderer.renderMFTable(this.dataManager.getMFHoldings(), status);
      this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);

      // Update combined summary after table rendering (to reflect filtered totals)
      this.summaryManager.updateCombinedSummary(
        status.ltp_fetch_state === 'updating',
        status.state === 'updating'
      );

    } catch (error) {
      console.error('Error updating data:', error);
    }
  }

  async handleRefresh() {
    const btnText = document.getElementById('refresh_btn_text');
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    
    // Force animation restart
    statusTag.className = '';
    void statusTag.offsetWidth;
    statusTag.className = 'updating';
    
    btnText.innerHTML = '<span class="spinner"></span>';
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

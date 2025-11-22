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
  }

  async init() {
    // Initialize theme and privacy
    this.themeManager.init();
    this.privacyManager.init();

    // Set up event listeners
    this._setupEventListeners();

    // Show loading state
    this._showLoadingState();

    // Start periodic updates (will handle initial data fetch)
    this.startPeriodicUpdates(2000);

    // Fetch initial data without blocking
    this.updateData();
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

      // Update combined summary
      const ltpUpdating = status.ltp_fetch_state === 'updating';
      const refreshRunning = status.state === 'updating';
      this.summaryManager.updateCombinedSummary(ltpUpdating, refreshRunning);

    } catch (error) {
      console.error('Error updating data:', error);
    }
  }

  async handleRefresh() {
    const btnText = document.getElementById('refresh_btn_text');
    const statusTag = document.getElementById('status_tag');
    const statusText = document.getElementById('status_text');
    
    btnText.innerHTML = '<span class="spinner"></span>';
    statusTag.className = 'updating';
    statusText.innerText = 'updating';

    try {
      // Trigger refresh on server
      await this.dataManager.triggerRefresh();

      // Poll and update UI until refresh completes
      let status;
      do {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Fetch all data including status
        const { holdings, mfHoldings, sips, status: currentStatus } = await this.dataManager.fetchAllData();
        status = currentStatus;
        
        // Update status display during polling
        const isUpdating = status.state === 'updating' || status.ltp_fetch_state === 'updating';
        statusTag.className = isUpdating ? 'updating' : 'updated';
        statusText.innerText = isUpdating 
          ? 'updating' 
          : ('updated' + (status.holdings_last_updated ? ` • ${status.holdings_last_updated}` : ''));
        
        // Update data manager and render tables with current status
        this.dataManager.updateHoldings(holdings, true);
        this.dataManager.updateMFHoldings(mfHoldings, true);
        this.dataManager.updateSIPs(sips, true);
        
        const searchQuery = document.getElementById('search').value;
        this.tableRenderer.setSearchQuery(searchQuery);
        this.tableRenderer.renderStocksTable(this.dataManager.getHoldings(), status);
        this.tableRenderer.renderMFTable(this.dataManager.getMFHoldings(), status);
        this.tableRenderer.renderSIPsTable(this.dataManager.getSIPs(), status);
        
        const ltpUpdating = status.ltp_fetch_state === 'updating' || status.state === 'updating';
        const refreshRunning = status.state === 'updating';
        this.summaryManager.updateCombinedSummary(ltpUpdating, refreshRunning);
      } while (status.state === 'updating');

      // Final update after completion
      await this.updateData();

    } catch (error) {
      alert('Error triggering refresh: ' + error.message);
      await this.updateData();
    } finally {
      btnText.innerText = 'Refresh';
    }
  }

  startPeriodicUpdates(intervalMs) {
    this.updateInterval = setInterval(() => {
      this.updateData();
    }, intervalMs);
  }

  stopPeriodicUpdates() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
    }
  }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new PortfolioApp();
  app.init();
});

export default PortfolioApp;

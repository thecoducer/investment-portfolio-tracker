// Nifty 50 Page Application
class Nifty50App {
  constructor() {
    this.nifty50Data = [];
    this.nifty50SortOrder = 'default';
    this.nifty50PageSize = 25;
    this.nifty50CurrentPage = 1;
    this.eventSource = null;
    this._wasUpdating = false;
    this._lastNifty50Timestamp = 0;  // Track last Nifty 50 update timestamp
  }

  async init() {
    this.setupTheme();
    this.connectEventSource();
    await this.loadInitialData();
  }

  setupTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    document.body.classList.toggle('dark-theme', theme === 'dark');
    
    const themeIcon = document.getElementById('theme_toggle_icon');
    if (themeIcon) {
      themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  }

  connectEventSource() {
    if (this.eventSource) {
      this.eventSource.close();
    }

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
    
    // Update status classes
    statusTag.classList.toggle('updating', isUpdating);
    statusTag.classList.toggle('updated', !isUpdating);
    statusTag.classList.toggle('market_closed', status.market_open === false);
    
    statusText.innerText = isUpdating 
      ? 'updating' 
      : ('updated' + (status.holdings_last_updated ? ` • ${status.holdings_last_updated}` : ''));

    this._updateRefreshButton(status.state === 'updating');
    
    // Re-render table with current status if we have data
    if (this.nifty50Data && this.nifty50Data.length > 0) {
      this.renderNifty50Table(status);
    }

    // Fetch new data when:
    // 1. Status changed from 'updating' to 'updated' (refresh completed)
    // 2. Status is 'updated' but we have no data yet (initial load)
    // 3. Nifty 50 timestamp has changed (new data available)
    // Important: Use > instead of !== to handle any timestamp updates (including same values from rapid refreshes)
    const nifty50Updated = status.nifty50_last_updated && 
                          status.nifty50_last_updated > 0 &&
                          status.nifty50_last_updated !== this._lastNifty50Timestamp;
    
    const statusTransitioned = !isUpdating && this._wasUpdating;
    const noData = !isUpdating && this.nifty50Data.length === 0;
    
    const shouldFetchData = statusTransitioned || noData || nifty50Updated;
    
    if (shouldFetchData) {
      this._lastNifty50Timestamp = status.nifty50_last_updated;
      this.updateNifty50();
    }
    
    this._wasUpdating = isUpdating;
  }

  _isStatusUpdating(status) {
    return status.state === 'updating';
  }

  _updateRefreshButton(isUpdating) {
    const refreshBtn = document.getElementById('refresh_btn');
    const refreshBtnText = document.getElementById('refresh_btn_text');
    
    if (refreshBtn && refreshBtnText) {
      if (isUpdating) {
        refreshBtn.classList.add('loading');
        refreshBtn.disabled = true;
        refreshBtnText.innerHTML = '<span class="spinner"></span>';
      } else {
        refreshBtn.classList.remove('loading');
        refreshBtn.disabled = false;
        refreshBtnText.textContent = 'Refresh';
      }
    }
  }

  async loadInitialData() {
    await this.updateNifty50();
  }

  async updateNifty50(status = null) {
    try {
      const response = await fetch('/nifty50_data');
      if (!response.ok) throw new Error('Failed to fetch Nifty 50 data');
      
      const nifty50Data = await response.json();
      this.nifty50Data = nifty50Data;
      this.renderNifty50Table(status);
    } catch (error) {
      console.error('Error fetching Nifty 50 data:', error);
    }
  }

  sortNifty50Data(data, sortOrder) {
    const sorted = [...data];
    
    switch (sortOrder) {
      case 'change_desc':
        return sorted.sort((a, b) => b.pChange - a.pChange);
      case 'change_asc':
        return sorted.sort((a, b) => a.pChange - b.pChange);
      case 'ltp_desc':
        return sorted.sort((a, b) => b.ltp - a.ltp);
      case 'ltp_asc':
        return sorted.sort((a, b) => a.ltp - b.ltp);
      case 'symbol_asc':
        return sorted.sort((a, b) => a.symbol.localeCompare(b.symbol));
      case 'symbol_desc':
        return sorted.sort((a, b) => b.symbol.localeCompare(a.symbol));
      case 'name_asc':
        return sorted.sort((a, b) => a.name.localeCompare(b.name));
      case 'name_desc':
        return sorted.sort((a, b) => b.name.localeCompare(a.name));
      default:
        return sorted;
    }
  }

  renderNifty50Table(status = null) {
    const tbody = document.getElementById('nifty50_tbody');
    if (!tbody) return;
    const loadingRow = document.getElementById('nifty50_table_loading');
    if (loadingRow) loadingRow.style.display = 'none';

    const isUpdating = status ? this._isStatusUpdating(status) : false;
    const updateClass = isUpdating ? 'updating-field' : '';

    const sortedData = this.sortNifty50Data(this.nifty50Data, this.nifty50SortOrder);
    
    const totalItems = sortedData.length;
    const pageSize = this.nifty50PageSize === 100 ? totalItems : this.nifty50PageSize;
    const totalPages = Math.ceil(totalItems / pageSize);
    const currentPage = Math.min(this.nifty50CurrentPage, totalPages);
    
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, totalItems);
    const pageData = sortedData.slice(startIndex, endIndex);

    tbody.innerHTML = pageData.map(stock => {
      const changeClass = stock.change >= 0 ? 'positive' : 'negative';
      const changeSign = stock.change >= 0 ? '+' : '';
      
      return `
        <tr>
          <td class="${updateClass}"><strong>${stock.symbol}</strong></td>
          <td class="${updateClass}">${stock.name}</td>
          <td class="${updateClass}">${this._formatNiftyNumber(stock.ltp)}</td>
          <td class="${changeClass} ${updateClass}">
            ${changeSign}${this._formatNiftyNumber(stock.change)}
            <span class="pl_pct_small">${changeSign}${stock.pChange.toFixed(2)}%</span>
          </td>
          <td class="${updateClass}">${this._formatNiftyNumber(stock.open)}</td>
          <td class="${updateClass}">${this._formatNiftyNumber(stock.high)}</td>
          <td class="${updateClass}">${this._formatNiftyNumber(stock.low)}</td>
          <td class="${updateClass}">${this._formatNiftyNumber(stock.close)}</td>
        </tr>
      `.trim();
    }).join('');
    
    this.updateNifty50Pagination(currentPage, totalPages, totalItems, startIndex, endIndex);
  }

  _formatNiftyNumber(n) {
    return Number(n).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  updateNifty50Pagination(currentPage, totalPages, totalItems, startIndex, endIndex) {
    const infoDiv = document.getElementById('nifty50_pagination_info');
    const buttonsDiv = document.getElementById('nifty50_pagination_buttons');
    
    if (!infoDiv || !buttonsDiv) return;

    if (totalItems > 0) {
      infoDiv.textContent = `Showing ${startIndex + 1}-${endIndex} of ${totalItems} stocks`;
    } else {
      infoDiv.innerHTML = '<span class="spinner"></span> Loading data...';
    }

    if (totalPages <= 1) {
      buttonsDiv.innerHTML = '';
      return;
    }

    let buttonsHTML = '';
    
    buttonsHTML += `
      <button onclick="window.goToNifty50Page(1)" ${currentPage === 1 ? 'disabled' : ''}>First</button>
      <button onclick="window.goToNifty50Page(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>
    `;

    const maxPageButtons = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxPageButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxPageButtons - 1);
    
    if (endPage - startPage < maxPageButtons - 1) {
      startPage = Math.max(1, endPage - maxPageButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      const activeClass = i === currentPage ? 'active' : '';
      buttonsHTML += `<button class="${activeClass}" onclick="window.goToNifty50Page(${i})">${i}</button>`;
    }

    buttonsHTML += `
      <button onclick="window.goToNifty50Page(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>Next</button>
      <button onclick="window.goToNifty50Page(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''}>Last</button>
    `;

    buttonsDiv.innerHTML = buttonsHTML;
  }

  sortNifty50Table(sortOrder) {
    this.nifty50SortOrder = sortOrder;
    this.nifty50CurrentPage = 1;
    this.renderNifty50Table();
  }

  changeNifty50PageSize(size) {
    this.nifty50PageSize = parseInt(size);
    this.nifty50CurrentPage = 1;
    this.renderNifty50Table();
  }

  goToNifty50Page(page) {
    this.nifty50CurrentPage = page;
    this.renderNifty50Table();
  }

  cleanup() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

// Global functions
window.toggleTheme = function() {
  const isDark = document.body.classList.toggle('dark-theme');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
  
  const themeIcon = document.getElementById('theme_toggle_icon');
  if (themeIcon) {
    themeIcon.textContent = isDark ? '☀️' : '🌙';
  }
};

window.triggerRefresh = async function() {
  const refreshBtn = document.getElementById('refresh_btn');
  if (refreshBtn.disabled) return;

  try {
    const response = await fetch('/refresh', { method: 'POST' });
    if (!response.ok) {
      console.error('Refresh failed:', response.status);
    }
  } catch (error) {
    console.error('Error triggering refresh:', error);
  }
};

window.sortNifty50Table = function(sortOrder) {
  if (window.nifty50App) {
    window.nifty50App.sortNifty50Table(sortOrder);
  }
};

window.changeNifty50PageSize = function(size) {
  if (window.nifty50App) {
    window.nifty50App.changeNifty50PageSize(size);
  }
};

window.goToNifty50Page = function(page) {
  if (window.nifty50App) {
    window.nifty50App.goToNifty50Page(page);
  }
};

// Initialize app
window.nifty50App = new Nifty50App();
window.nifty50App.init();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (window.nifty50App) {
    window.nifty50App.cleanup();
  }
});

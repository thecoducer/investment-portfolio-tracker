/* Portfolio Tracker - Sort Manager Module */

import { Calculator } from './utils.js';

class SortManager {
  constructor() {
    this.stocksSortOrder = 'default';
    this.mfSortOrder = 'default';
  }

  /**
   * Sort stocks array based on selected criteria
   * @param {Array} holdings - Stock holdings array
   * @param {string} sortBy - Sort criteria
   * @returns {Array} Sorted array
   */
  sortStocks(holdings, sortBy = 'default') {
    if (sortBy === 'default' || !holdings || holdings.length === 0) {
      return holdings;
    }

    const sorted = [...holdings];

    switch (sortBy) {
      case 'pl_pct_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return bMetrics.plPct - aMetrics.plPct;
        });
        break;
      
      case 'pl_pct_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return aMetrics.plPct - bMetrics.plPct;
        });
        break;
      
      case 'pl_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return bMetrics.pl - aMetrics.pl;
        });
        break;
      
      case 'pl_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return aMetrics.pl - bMetrics.pl;
        });
        break;
      
      case 'invested_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return bMetrics.invested - aMetrics.invested;
        });
        break;
      
      case 'invested_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return aMetrics.invested - bMetrics.invested;
        });
        break;
      
      case 'current_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return bMetrics.current - aMetrics.current;
        });
        break;
      
      case 'current_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return aMetrics.current - bMetrics.current;
        });
        break;
      
      case 'day_change_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return bMetrics.dayChange - aMetrics.dayChange;
        });
        break;
      
      case 'day_change_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateStockMetrics(a);
          const bMetrics = Calculator.calculateStockMetrics(b);
          return aMetrics.dayChange - bMetrics.dayChange;
        });
        break;
      
      case 'symbol_asc':
        sorted.sort((a, b) => {
          return (a.tradingsymbol || '').localeCompare(b.tradingsymbol || '');
        });
        break;
      
      case 'symbol_desc':
        sorted.sort((a, b) => {
          return (b.tradingsymbol || '').localeCompare(a.tradingsymbol || '');
        });
        break;
      
      default:
        return holdings;
    }

    return sorted;
  }

  /**
   * Sort mutual funds array based on selected criteria
   * @param {Array} mfHoldings - MF holdings array
   * @param {string} sortBy - Sort criteria
   * @returns {Array} Sorted array
   */
  sortMF(mfHoldings, sortBy = 'default') {
    if (sortBy === 'default' || !mfHoldings || mfHoldings.length === 0) {
      return mfHoldings;
    }

    const sorted = [...mfHoldings];

    switch (sortBy) {
      case 'pl_pct_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return bMetrics.plPct - aMetrics.plPct;
        });
        break;
      
      case 'pl_pct_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return aMetrics.plPct - bMetrics.plPct;
        });
        break;
      
      case 'pl_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return bMetrics.pl - aMetrics.pl;
        });
        break;
      
      case 'pl_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return aMetrics.pl - bMetrics.pl;
        });
        break;
      
      case 'invested_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return bMetrics.invested - aMetrics.invested;
        });
        break;
      
      case 'invested_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return aMetrics.invested - bMetrics.invested;
        });
        break;
      
      case 'current_desc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return bMetrics.current - aMetrics.current;
        });
        break;
      
      case 'current_asc':
        sorted.sort((a, b) => {
          const aMetrics = Calculator.calculateMFMetrics(a);
          const bMetrics = Calculator.calculateMFMetrics(b);
          return aMetrics.current - bMetrics.current;
        });
        break;
      
      case 'name_asc':
        sorted.sort((a, b) => {
          const aName = a.fund || a.tradingsymbol || '';
          const bName = b.fund || b.tradingsymbol || '';
          return aName.localeCompare(bName);
        });
        break;
      
      case 'name_desc':
        sorted.sort((a, b) => {
          const aName = a.fund || a.tradingsymbol || '';
          const bName = b.fund || b.tradingsymbol || '';
          return bName.localeCompare(aName);
        });
        break;
      
      default:
        return mfHoldings;
    }

    return sorted;
  }

  setStocksSortOrder(sortBy) {
    this.stocksSortOrder = sortBy;
  }

  setMFSortOrder(sortBy) {
    this.mfSortOrder = sortBy;
  }

  getStocksSortOrder() {
    return this.stocksSortOrder;
  }

  getMFSortOrder() {
    return this.mfSortOrder;
  }
}

export default SortManager;

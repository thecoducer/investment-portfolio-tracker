/* Portfolio Tracker - Sort Manager Module */

import { Calculator } from './utils.js';

class SortManager {
  constructor() {
    this.stocksSortOrder = 'default';
    this.mfSortOrder = 'default';
    this.physicalGoldSortOrder = 'default';
    this.fixedDepositsSortOrder = 'default';
  }

  /**
   * Generic comparator for numeric sorting
   * @param {function} getValue - Function to extract value from item
   * @param {boolean} descending - Sort direction
   * @returns {function} Comparator function
   */
  _numericComparator(getValue, descending = true) {
    return (a, b) => {
      const aVal = getValue(a);
      const bVal = getValue(b);
      return descending ? bVal - aVal : aVal - bVal;
    };
  }

  /**
   * Generic comparator for date string sorting
   * @param {function} getValue - Function to extract date string from item
   * @param {boolean} descending - Sort direction (true = newest first)
   * @returns {function} Comparator function
   */
  _dateComparator(getValue, descending = true) {
    return (a, b) => {
      const aVal = getValue(a);
      const bVal = getValue(b);
      
      // Parse dates (format: "Month Day, Year")
      const aDate = aVal ? new Date(aVal) : new Date(0);
      const bDate = bVal ? new Date(bVal) : new Date(0);
      
      return descending ? bDate - aDate : aDate - bDate;
    };
  }

  /**
   * Generic comparator for string sorting
   * @param {function} getValue - Function to extract value from item
   * @param {boolean} descending - Sort direction
   * @returns {function} Comparator function
   */
  _stringComparator(getValue, descending = false) {
    return (a, b) => {
      const aVal = getValue(a) || '';
      const bVal = getValue(b) || '';
      return descending ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
    };
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
    
    // Map sort criteria to comparator functions
    const comparators = {
      'pl_pct_desc': this._numericComparator(h => Calculator.calculateStockMetrics(h).plPct, true),
      'pl_pct_asc': this._numericComparator(h => Calculator.calculateStockMetrics(h).plPct, false),
      'pl_desc': this._numericComparator(h => Calculator.calculateStockMetrics(h).pl, true),
      'pl_asc': this._numericComparator(h => Calculator.calculateStockMetrics(h).pl, false),
      'invested_desc': this._numericComparator(h => Calculator.calculateStockMetrics(h).invested, true),
      'invested_asc': this._numericComparator(h => Calculator.calculateStockMetrics(h).invested, false),
      'current_desc': this._numericComparator(h => Calculator.calculateStockMetrics(h).current, true),
      'current_asc': this._numericComparator(h => Calculator.calculateStockMetrics(h).current, false),
      'day_change_desc': this._numericComparator(h => Calculator.calculateStockMetrics(h).dayChange, true),
      'day_change_asc': this._numericComparator(h => Calculator.calculateStockMetrics(h).dayChange, false),
      'symbol_asc': this._stringComparator(h => h.tradingsymbol, false),
      'symbol_desc': this._stringComparator(h => h.tradingsymbol, true)
    };

    const comparator = comparators[sortBy];
    return comparator ? sorted.sort(comparator) : holdings;
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

    // Map sort criteria to comparator functions
    const comparators = {
      'pl_pct_desc': this._numericComparator(h => Calculator.calculateMFMetrics(h).plPct, true),
      'pl_pct_asc': this._numericComparator(h => Calculator.calculateMFMetrics(h).plPct, false),
      'pl_desc': this._numericComparator(h => Calculator.calculateMFMetrics(h).pl, true),
      'pl_asc': this._numericComparator(h => Calculator.calculateMFMetrics(h).pl, false),
      'invested_desc': this._numericComparator(h => Calculator.calculateMFMetrics(h).invested, true),
      'invested_asc': this._numericComparator(h => Calculator.calculateMFMetrics(h).invested, false),
      'current_desc': this._numericComparator(h => Calculator.calculateMFMetrics(h).current, true),
      'current_asc': this._numericComparator(h => Calculator.calculateMFMetrics(h).current, false),
      'name_asc': this._stringComparator(h => h.fund || h.tradingsymbol, false),
      'name_desc': this._stringComparator(h => h.fund || h.tradingsymbol, true)
    };

    const comparator = comparators[sortBy];
    return comparator ? sorted.sort(comparator) : mfHoldings;
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

  /**
   * Sort physical gold array based on selected criteria
   * @param {Array} holdings - Physical gold holdings array
   * @param {string} sortBy - Sort criteria
   * @returns {Array} Sorted array
   */
  sortPhysicalGold(holdings, sortBy = 'default') {
    if (sortBy === 'default' || !holdings || holdings.length === 0) {
      return holdings;
    }

    const sorted = [...holdings];

    // Map sort criteria to comparator functions
    const comparators = {
      'date_desc': this._numericComparator(h => new Date(h.date || 0).getTime(), true),
      'date_asc': this._numericComparator(h => new Date(h.date || 0).getTime(), false),
      'weight_desc': this._numericComparator(h => h.weight_gms || 0, true),
      'weight_asc': this._numericComparator(h => h.weight_gms || 0, false),
      'type_asc': this._stringComparator(h => h.type, false),
      'type_desc': this._stringComparator(h => h.type, true)
    };

    const comparator = comparators[sortBy];
    return comparator ? sorted.sort(comparator) : holdings;
  }

  setPhysicalGoldSortOrder(sortBy) {
    this.physicalGoldSortOrder = sortBy;
  }

  getPhysicalGoldSortOrder() {
    return this.physicalGoldSortOrder;
  }

  /**
   * Sort fixed deposits array based on selected criteria
   * @param {Array} deposits - Fixed deposits array
   * @param {string} sortBy - Sort criteria
   * @returns {Array} Sorted array
   */
  sortFixedDeposits(deposits, sortBy = 'default') {
    if (sortBy === 'default' || !deposits || deposits.length === 0) {
      return deposits;
    }

    const sorted = [...deposits];

    // Map sort criteria to comparator functions
    const comparators = {
      'date_desc': this._dateComparator(d => d.deposited_on, true),
      'date_asc': this._dateComparator(d => d.deposited_on, false),
      'amount_desc': this._numericComparator(d => d.amount || 0, true),
      'amount_asc': this._numericComparator(d => d.amount || 0, false),
      'bank_asc': this._stringComparator(d => d.bank_name, false),
      'bank_desc': this._stringComparator(d => d.bank_name, true),
      'maturity_desc': this._dateComparator(d => d.maturity_date, true),
      'maturity_asc': this._dateComparator(d => d.maturity_date, false)
    };

    const comparator = comparators[sortBy];
    return comparator ? sorted.sort(comparator) : deposits;
  }

  setFixedDepositsSortOrder(sortBy) {
    this.fixedDepositsSortOrder = sortBy;
  }

  getFixedDepositsSortOrder() {
    return this.fixedDepositsSortOrder;
  }
}

export default SortManager;

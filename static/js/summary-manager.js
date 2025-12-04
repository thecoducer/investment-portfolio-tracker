/* Portfolio Tracker - Summary Module */

import { Formatter } from './utils.js';

// Element ID constants
const ELEMENT_IDS = {
  STOCK: {
    INVESTED: 'total_invested',
    CURRENT: 'current_value',
    PL: 'total_pl',
    PL_PCT: 'total_pl_pct'
  },
  GOLD: {
    INVESTED: 'gold_total_invested',
    CURRENT: 'gold_current_value',
    PL: 'gold_total_pl',
    PL_PCT: 'gold_total_pl_pct'
  },
  SILVER: {
    INVESTED: 'silver_total_invested',
    CURRENT: 'silver_current_value',
    PL: 'silver_total_pl',
    PL_PCT: 'silver_total_pl_pct'
  },
  MF: {
    INVESTED: 'mf_total_invested',
    CURRENT: 'mf_current_value',
    PL: 'mf_total_pl',
    PL_PCT: 'mf_total_pl_pct'
  },
  COMBINED: {
    INVESTED: 'combined_total_invested',
    CURRENT: 'combined_current_value',
    PL: 'combined_total_pl',
    PL_PCT: 'combined_total_pl_pct'
  }
};

class SummaryManager {
  /**
   * Update all summary cards with provided totals
   * @param {Object} stockTotals - { invested, current, pl, plPct }
   * @param {Object} goldTotals - { invested, current, pl, plPct }
   * @param {Object} silverTotals - { invested, current, pl, plPct }
   * @param {Object} mfTotals - { invested, current, pl, plPct }
   * @param {boolean} isUpdating - Whether refresh/update is in progress
   */
  updateAllSummaries(stockTotals, goldTotals, silverTotals, mfTotals, isUpdating = false) {
    // Hide loading placeholders
    const combinedLoading = document.getElementById('combined_summary_loading');
    if (combinedLoading) combinedLoading.style.display = 'none';
    const stocksLoading = document.getElementById('stocks_summary_loading');
    if (stocksLoading) stocksLoading.style.display = 'none';
    const goldLoading = document.getElementById('gold_summary_loading');
    if (goldLoading) goldLoading.style.display = 'none';
    const silverLoading = document.getElementById('silver_summary_loading');
    if (silverLoading) silverLoading.style.display = 'none';
    const mfLoading = document.getElementById('mf_summary_loading');
    if (mfLoading) mfLoading.style.display = 'none';

    // Provide default values if undefined
    const stock = stockTotals || { invested: 0, current: 0, pl: 0, plPct: 0 };
    const gold = goldTotals || { invested: 0, current: 0, pl: 0, plPct: 0 };
    const silver = silverTotals || { invested: 0, current: 0, pl: 0, plPct: 0 };
    const mf = mfTotals || { invested: 0, current: 0, pl: 0, plPct: 0 };

    // Calculate combined totals
    const combinedInvested = stock.invested + gold.invested + silver.invested + mf.invested;
    const combinedCurrent = stock.current + gold.current + silver.current + mf.current;
    const combinedPL = combinedCurrent - combinedInvested;
    const combinedPLPct = combinedInvested ? (combinedPL / combinedInvested * 100) : 0;

    // Calculate allocation percentages
    const stockAllocation = combinedInvested ? (stock.invested / combinedInvested * 100) : 0;
    const goldAllocation = combinedInvested ? (gold.invested / combinedInvested * 100) : 0;
    const silverAllocation = combinedInvested ? (silver.invested / combinedInvested * 100) : 0;
    const mfAllocation = combinedInvested ? (mf.invested / combinedInvested * 100) : 0;

    // Update allocation percentages
    this._updateAllocationPercentage('stocks_allocation_pct', stockAllocation);
    this._updateAllocationPercentage('gold_allocation_pct', goldAllocation);
    this._updateAllocationPercentage('silver_allocation_pct', silverAllocation);
    this._updateAllocationPercentage('mf_allocation_pct', mfAllocation);

    // Update all cards
    this._updateStockCard(stock);
    this._updateGoldCard(gold);
    this._updateSilverCard(silver);
    this._updateMFCard(mf);
    this._updateCombinedCard({
      invested: combinedInvested,
      current: combinedCurrent,
      pl: combinedPL,
      plPct: combinedPLPct
    });
  }

  _updateAllocationPercentage(elementId, percentage) {
    const el = document.getElementById(elementId);
    if (el) {
      el.innerText = percentage.toFixed(1) + '% ';
      
      // Set progress bar on parent card
      const card = el.closest('.card');
      if (card) {
        card.style.setProperty('--allocation-width', `${percentage}%`);
        
        // Set color based on card type
        let color = '#8b7765'; // default brown
        if (elementId === 'stocks_allocation_pct') {
          color = '#7c5cdb'; // purple
        } else if (elementId === 'mf_allocation_pct') {
          color = '#5ca0db'; // blue
        } else if (elementId === 'gold_allocation_pct') {
          color = '#d4af37'; // gold
        } else if (elementId === 'silver_allocation_pct') {
          color = '#c0c0c0'; // silver
        }
        card.style.setProperty('--allocation-color', color);
      }
    }
  }

  _updateStockCard(totals) {
    this._updateCard(
      ELEMENT_IDS.STOCK.INVESTED,
      ELEMENT_IDS.STOCK.CURRENT,
      ELEMENT_IDS.STOCK.PL,
      ELEMENT_IDS.STOCK.PL_PCT,
      totals
    );
  }

  _updateGoldCard(totals) {
    this._updateCard(
      ELEMENT_IDS.GOLD.INVESTED,
      ELEMENT_IDS.GOLD.CURRENT,
      ELEMENT_IDS.GOLD.PL,
      ELEMENT_IDS.GOLD.PL_PCT,
      totals
    );
  }

  _updateSilverCard(totals) {
    this._updateCard(
      ELEMENT_IDS.SILVER.INVESTED,
      ELEMENT_IDS.SILVER.CURRENT,
      ELEMENT_IDS.SILVER.PL,
      ELEMENT_IDS.SILVER.PL_PCT,
      totals
    );
  }

  _updateMFCard(totals) {
    this._updateCard(
      ELEMENT_IDS.MF.INVESTED,
      ELEMENT_IDS.MF.CURRENT,
      ELEMENT_IDS.MF.PL,
      ELEMENT_IDS.MF.PL_PCT,
      totals
    );
  }

  _updateCombinedCard(totals) {
    this._updateCard(
      ELEMENT_IDS.COMBINED.INVESTED,
      ELEMENT_IDS.COMBINED.CURRENT,
      ELEMENT_IDS.COMBINED.PL,
      ELEMENT_IDS.COMBINED.PL_PCT,
      totals
    );
  }

  _updateCard(investedId, currentId, plId, plPctId, totals) {
    const investedEl = document.getElementById(investedId);
    const currentEl = document.getElementById(currentId);
    const plEl = document.getElementById(plId);
    const plPctEl = document.getElementById(plPctId);

    // Safeguard against NaN values
    const invested = isNaN(totals.invested) ? 0 : totals.invested;
    const current = isNaN(totals.current) ? 0 : totals.current;
    const pl = isNaN(totals.pl) ? 0 : totals.pl;
    const plPct = isNaN(totals.plPct) ? 0 : totals.plPct;

    // Format invested, current, and P/L using summary currency formatter (respects compact toggle)
    investedEl.innerText = Formatter.formatCurrencyForSummary(invested);
    currentEl.innerText = Formatter.formatCurrencyForSummary(current);
    // Show '-' before currency for negative P/L
    if (pl < 0) {
      plEl.innerText = '-' + Formatter.formatCurrencyForSummary(Math.abs(pl));
    } else {
      plEl.innerText = Formatter.formatCurrencyForSummary(pl);
    }
    plEl.style.color = Formatter.colorPL(pl);
    // Show only one sign before percent value, use absolute value
    if (pl < 0) {
      plPctEl.innerText = '-' + Math.abs(plPct).toFixed(2) + '%';
    } else if (pl > 0) {
      plPctEl.innerText = '+' + Math.abs(plPct).toFixed(2) + '%';
    } else {
      plPctEl.innerText = '0.00%';
    }
    plPctEl.style.color = Formatter.colorPL(pl);
  }
}

export default SummaryManager;

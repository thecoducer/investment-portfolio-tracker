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
   * Update all three summary cards with provided totals
   * @param {Object} stockTotals - { invested, current, pl, plPct }
   * @param {Object} mfTotals - { invested, current, pl, plPct }
   * @param {boolean} isUpdating - Whether refresh/update is in progress
   */
  updateAllSummaries(stockTotals, mfTotals, isUpdating = false) {
    // Hide loading placeholders
    const combinedLoading = document.getElementById('combined_summary_loading');
    if (combinedLoading) combinedLoading.style.display = 'none';
    const stocksLoading = document.getElementById('stocks_summary_loading');
    if (stocksLoading) stocksLoading.style.display = 'none';
    const mfLoading = document.getElementById('mf_summary_loading');
    if (mfLoading) mfLoading.style.display = 'none';

    // Provide default values if undefined
    const stock = stockTotals || { invested: 0, current: 0, pl: 0, plPct: 0 };
    const mf = mfTotals || { invested: 0, current: 0, pl: 0, plPct: 0 };

    // Calculate combined totals
    const combinedInvested = stock.invested + mf.invested;
    const combinedCurrent = stock.current + mf.current;
    const combinedPL = combinedCurrent - combinedInvested;
    const combinedPLPct = combinedInvested ? (combinedPL / combinedInvested * 100) : 0;

    // Update all three cards
    this._updateStockCard(stock);
    this._updateMFCard(mf);
    this._updateCombinedCard({
      invested: combinedInvested,
      current: combinedCurrent,
      pl: combinedPL,
      plPct: combinedPLPct
    });

    // No card animations
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

    // Format invested, current, and P/L using centralized currency formatter
    investedEl.innerText = Formatter.formatCurrency(totals.invested);
    currentEl.innerText = Formatter.formatCurrency(totals.current);
    // Show '-' before currency for negative P/L
    if (totals.pl < 0) {
      plEl.innerText = '-' + Formatter.formatCurrency(Math.abs(totals.pl));
    } else {
      plEl.innerText = Formatter.formatCurrency(totals.pl);
    }
    plEl.style.color = Formatter.colorPL(totals.pl);
    // Show only one sign before percent value, use absolute value
    if (totals.pl < 0) {
      plPctEl.innerText = '-' + Math.abs(totals.plPct).toFixed(2) + '%';
    } else if (totals.pl > 0) {
      plPctEl.innerText = '+' + Math.abs(totals.plPct).toFixed(2) + '%';
    } else {
      plPctEl.innerText = '0.00%';
    }
    plPctEl.style.color = Formatter.colorPL(totals.pl);
  }

  // _applyAnimations removed: no animation logic
}

export default SummaryManager;

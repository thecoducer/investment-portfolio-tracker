/* Portfolio Tracker - Summary Module */

import { Formatter, Calculator } from './utils.js';

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
    const stocksLoading = document.getElementById('portfolio_summary_loading');
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

    // Apply animations to all cards
    this._applyAnimations(isUpdating);
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

    investedEl.innerText = Formatter.formatNumber(totals.invested);
    currentEl.innerText = Formatter.formatNumber(totals.current);
    plEl.innerText = Formatter.formatSign(totals.pl) + Formatter.formatNumber(totals.pl);
    plEl.style.color = Formatter.colorPL(totals.pl);
    plPctEl.innerText = Formatter.formatSign(totals.pl) + totals.plPct.toFixed(2) + '%';
    plPctEl.style.color = Formatter.colorPL(totals.pl);
  }

  _applyAnimations(isUpdating) {
    // Get all elements from all three cards
    const allElements = [
      // Combined card
      document.getElementById(ELEMENT_IDS.COMBINED.INVESTED),
      document.getElementById(ELEMENT_IDS.COMBINED.CURRENT),
      document.getElementById(ELEMENT_IDS.COMBINED.PL),
      document.getElementById(ELEMENT_IDS.COMBINED.PL_PCT),
      // Stock card
      document.getElementById(ELEMENT_IDS.STOCK.INVESTED),
      document.getElementById(ELEMENT_IDS.STOCK.CURRENT),
      document.getElementById(ELEMENT_IDS.STOCK.PL),
      document.getElementById(ELEMENT_IDS.STOCK.PL_PCT),
      // MF card
      document.getElementById(ELEMENT_IDS.MF.INVESTED),
      document.getElementById(ELEMENT_IDS.MF.CURRENT),
      document.getElementById(ELEMENT_IDS.MF.PL),
      document.getElementById(ELEMENT_IDS.MF.PL_PCT)
    ];
    
    allElements.forEach(el => {
      if (isUpdating) {
        el.classList.add('updating-field');
      } else {
        el.classList.remove('updating-field');
      }
    });
  }
}

export default SummaryManager;

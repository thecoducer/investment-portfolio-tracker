/* Portfolio Tracker - Summary Module */

import { Formatter, Calculator } from './utils.js';

class SummaryManager {
  /**
   * Update all three summary cards with provided totals
   * @param {Object} stockTotals - { invested, current, pl, plPct }
   * @param {Object} mfTotals - { invested, current, pl, plPct }
   * @param {boolean} isUpdating - Whether refresh/update is in progress
   */
  updateAllSummaries(stockTotals, mfTotals, isUpdating = false) {
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
    const totalInvestedEl = document.getElementById('total_invested');
    const currentValueEl = document.getElementById('current_value');
    const totalPlEl = document.getElementById('total_pl');
    const totalPlPctEl = document.getElementById('total_pl_pct');

    totalInvestedEl.innerText = Formatter.formatNumber(totals.invested);
    currentValueEl.innerText = Formatter.formatNumber(totals.current);
    totalPlEl.innerText = Formatter.formatSign(totals.pl) + Formatter.formatNumber(totals.pl);
    totalPlEl.style.color = Formatter.colorPL(totals.pl);
    totalPlPctEl.innerText = Formatter.formatSign(totals.pl) + totals.plPct.toFixed(2) + '%';
    totalPlPctEl.style.color = Formatter.colorPL(totals.pl);
  }

  _updateMFCard(totals) {
    const mfTotalInvestedEl = document.getElementById('mf_total_invested');
    const mfCurrentValueEl = document.getElementById('mf_current_value');
    const mfTotalPlEl = document.getElementById('mf_total_pl');
    const mfTotalPlPctEl = document.getElementById('mf_total_pl_pct');

    mfTotalInvestedEl.innerText = Formatter.formatNumber(totals.invested);
    mfCurrentValueEl.innerText = Formatter.formatNumber(totals.current);
    mfTotalPlEl.innerText = Formatter.formatSign(totals.pl) + Formatter.formatNumber(totals.pl);
    mfTotalPlEl.style.color = Formatter.colorPL(totals.pl);
    mfTotalPlPctEl.innerText = Formatter.formatSign(totals.pl) + totals.plPct.toFixed(2) + '%';
    mfTotalPlPctEl.style.color = Formatter.colorPL(totals.pl);
  }

  _updateCombinedCard(totals) {
    const combinedTotalInvestedEl = document.getElementById('combined_total_invested');
    const combinedCurrentValueEl = document.getElementById('combined_current_value');
    const combinedTotalPlEl = document.getElementById('combined_total_pl');
    const combinedTotalPlPctEl = document.getElementById('combined_total_pl_pct');

    combinedTotalInvestedEl.innerText = Formatter.formatNumber(totals.invested);
    combinedCurrentValueEl.innerText = Formatter.formatNumber(totals.current);
    combinedTotalPlEl.innerText = Formatter.formatSign(totals.pl) + Formatter.formatNumber(totals.pl);
    combinedTotalPlEl.style.color = Formatter.colorPL(totals.pl);
    combinedTotalPlPctEl.innerText = Formatter.formatSign(totals.pl) + totals.plPct.toFixed(2) + '%';
    combinedTotalPlPctEl.style.color = Formatter.colorPL(totals.pl);
  }

  _applyAnimations(isUpdating) {
    // Get all elements from all three cards
    const allElements = [
      // Combined card
      document.getElementById('combined_total_invested'),
      document.getElementById('combined_current_value'),
      document.getElementById('combined_total_pl'),
      document.getElementById('combined_total_pl_pct'),
      // Stock card
      document.getElementById('total_invested'),
      document.getElementById('current_value'),
      document.getElementById('total_pl'),
      document.getElementById('total_pl_pct'),
      // MF card
      document.getElementById('mf_total_invested'),
      document.getElementById('mf_current_value'),
      document.getElementById('mf_total_pl'),
      document.getElementById('mf_total_pl_pct')
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

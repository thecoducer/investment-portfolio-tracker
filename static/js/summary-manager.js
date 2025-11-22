/* Portfolio Tracker - Summary Module */

import { Formatter, Calculator } from './utils.js';

class SummaryManager {
  updateCombinedSummary(ltpUpdating = false, refreshRunning = false) {
    const stockInvested = this._parseValue('total_invested');
    const stockCurrent = this._parseValue('current_value');
    const mfInvested = this._parseValue('mf_total_invested');
    const mfCurrent = this._parseValue('mf_current_value');

    const combinedInvested = stockInvested + mfInvested;
    const combinedCurrent = stockCurrent + mfCurrent;
    const combinedPL = combinedCurrent - combinedInvested;
    const combinedPLPct = combinedInvested ? (combinedPL / combinedInvested * 100) : 0;

    this._updateCombinedDisplay({
      invested: combinedInvested,
      current: combinedCurrent,
      pl: combinedPL,
      plPct: combinedPLPct
    }, ltpUpdating, refreshRunning);
  }

  _parseValue(elementId) {
    const text = document.getElementById(elementId).innerText;
    return parseFloat(text.replace(/,/g, '') || 0);
  }

  _updateCombinedDisplay(totals, ltpUpdating, refreshRunning) {
    const combinedTotalInvestedEl = document.getElementById('combined_total_invested');
    const stockInvestedEl = document.getElementById('total_invested');
    const mfInvestedEl = document.getElementById('mf_total_invested');
    const combinedCurrentValueEl = document.getElementById('combined_current_value');
    const combinedTotalPlEl = document.getElementById('combined_total_pl');
    const combinedTotalPlPctEl = document.getElementById('combined_total_pl_pct');

    combinedTotalInvestedEl.innerText = Formatter.formatNumber(totals.invested);
    combinedCurrentValueEl.innerText = Formatter.formatNumber(totals.current);
    combinedTotalPlEl.innerText = Formatter.formatSign(totals.pl) + Formatter.formatNumber(totals.pl);
    combinedTotalPlEl.style.color = Formatter.colorPL(totals.pl);
    combinedTotalPlPctEl.innerText = Formatter.formatSign(totals.pl) + totals.plPct.toFixed(2) + '%';
    combinedTotalPlPctEl.style.color = Formatter.colorPL(totals.pl);

    // Apply animation to all fields during refresh (no separate LTP updates anymore)
    const isUpdating = refreshRunning || ltpUpdating;
    const allElements = [
      combinedTotalInvestedEl, stockInvestedEl, mfInvestedEl,
      combinedCurrentValueEl, combinedTotalPlEl, combinedTotalPlPctEl
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

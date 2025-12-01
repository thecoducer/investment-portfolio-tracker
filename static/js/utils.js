/* Portfolio Tracker - Formatting and Calculation Utilities */

class Formatter {
  static formatNumber(n) {
    return n.toLocaleString(undefined, { 
      minimumFractionDigits: 1, 
      maximumFractionDigits: 1 
    });
  }

  /**
   * Format a number using Indian numbering system with specified fraction digits.
   * @param {number} n - Number to format
   * @param {number} digits - Fraction digits (default: 2)
   * @param {string} locale - Locale to use (default: 'en-IN')
   * @returns {string} Formatted number
   */
  static formatNumberWithLocale(n, digits = 2, locale = 'en-IN') {
    return Number(n).toLocaleString(locale, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  /**
   * Format a number as Indian Rupee currency using Intl.NumberFormat.
   * Defaults to 1 fraction digits for clean currency presentation.
   * @param {number} n
   * @param {number} digits
   */
  static formatCurrency(n, digits = 1) {
    try {
      return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      }).format(n);
    } catch (e) {
      // Fallback: simple rupee prefix with thousands separator
      const fixed = Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
      return `₹${fixed}`;
    }
  }

  static colorPL(pl) {
    if (pl > 0) return '#10b981';
    if (pl < 0) return '#ef4444';
    return '#6b7280';
  }

  static rowColor(pl) {
    if (pl > 0) return 'rgba(16,185,129,0.04)';
    if (pl < 0) return 'rgba(239,68,68,0.04)';
    return 'transparent';
  }

  static formatSign(value) {
    if (value > 0) return '+';
    if (value < 0) return '-';
    return '';
  }

  /**
   * Format percentage with sign and specified decimal places.
   * @param {number} percentage - Percentage value
   * @param {number} decimals - Decimal places (default: 2)
   * @returns {string} Formatted percentage string
   */
  static formatPercentage(percentage, decimals = 2) {
    const sign = this.formatSign(percentage);
    return `${sign}${Math.abs(percentage).toFixed(decimals)}%`;
  }

  /**
   * Format a date string to relative format (today, yesterday, X days ago, or date)
   * @param {string} dateStr - Date string to format
   * @param {boolean} isPastDate - If true, shows "X days ago", if false shows "In X days"
   * @returns {string} Formatted date string
   */
  static formatRelativeDate(dateStr, isPastDate = true) {
    if (!dateStr) return '';
    
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return '';
      
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const compareDate = new Date(date);
      compareDate.setHours(0, 0, 0, 0);
      
      const diffTime = isPastDate 
        ? today.getTime() - compareDate.getTime()
        : compareDate.getTime() - today.getTime();
      const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) {
        return 'Today';
      } else if (diffDays === 1) {
        return isPastDate ? 'Yesterday' : 'Tomorrow';
      } else if (diffDays > 1 && diffDays <= 7) {
        return isPastDate ? `${diffDays} days ago` : `In ${diffDays} days`;
      } else {
        return date.toLocaleDateString('en-GB', { 
          day: 'numeric', 
          month: 'short',
          year: diffDays > 365 ? 'numeric' : undefined
        });
      }
    } catch (e) {
      return dateStr;
    }
  }
}

class Calculator {
  /**
   * Calculate basic investment metrics: current value, P/L, and P/L percentage.
   * @param {number} invested - Total amount invested
   * @param {number} currentValue - Current market value
   * @returns {object} P/L and P/L percentage
   */
  static _calculatePL(invested, currentValue) {
    const pl = currentValue - invested;
    const plPct = invested ? (pl / invested * 100) : 0;
    return { pl, plPct };
  }

  /**
   * Calculate stock holding metrics.
   * @param {object} holding - Stock holding data
   * @returns {object} All calculated metrics for display
   */
  static calculateStockMetrics(holding) {
    const qty = holding.quantity || 0;
    const avg = holding.average_price || 0;
    const invested = holding.invested || 0;
    const ltp = holding.last_price || 0;
    const dayChange = holding.day_change || 0;

    const current = ltp * qty;
    const { pl, plPct } = this._calculatePL(invested, current);
    const dayChangePct = ltp ? (dayChange / ltp * 100) : 0;

    return {
      qty,
      avg,
      invested,
      ltp,
      dayChange,
      pl,
      current,
      plPct,
      dayChangePct
    };
  }

  /**
   * Calculate mutual fund holding metrics.
   * @param {object} mfHolding - MF holding data
   * @returns {object} All calculated metrics for display
   */
  static calculateMFMetrics(mfHolding) {
    const qty = mfHolding.quantity || 0;
    const avg = mfHolding.average_price || 0;
    const invested = mfHolding.invested || 0;
    const nav = mfHolding.last_price || 0;

    const current = qty * nav;
    const { pl, plPct } = this._calculatePL(invested, current);

    return {
      qty,
      avg,
      invested,
      nav,
      current,
      pl,
      plPct
    };
  }

  static calculateTotalMetrics(holdings, calculator) {
    let totalInvested = 0;
    let totalCurrent = 0;

    holdings.forEach(holding => {
      const metrics = calculator(holding);
      totalInvested += metrics.invested;
      totalCurrent += metrics.current;
    });

    const totalPL = totalCurrent - totalInvested;
    const totalPLPct = totalInvested ? (totalPL / totalInvested * 100) : 0;

    return {
      totalInvested,
      totalCurrent,
      totalPL,
      totalPLPct
    };
  }
}

export { Formatter, Calculator };

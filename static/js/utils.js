/* Portfolio Tracker - Formatting and Calculation Utilities */

class Formatter {
  static formatNumber(n) {
    return n.toLocaleString(undefined, { 
      minimumFractionDigits: 1, 
      maximumFractionDigits: 1 
    });
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
    return value >= 0 ? '+' : '';
  }
}

class Calculator {
  static calculateStockMetrics(holding) {
    const qty = holding.quantity || 0;
    const avg = holding.average_price || 0;
    const invested = holding.invested || 0;
    const ltp = holding.last_price || 0;
    const dayChange = holding.day_change || 0;

    const pl = ltp * qty - invested;
    const current = invested + pl;
    const plPct = invested ? (pl / invested * 100) : 0;
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

  static calculateMFMetrics(mfHolding) {
    const qty = mfHolding.quantity || 0;
    const avg = mfHolding.average_price || 0;
    const invested = mfHolding.invested || 0;
    const nav = mfHolding.last_price || 0;

    const current = qty * nav;
    const pl = current - invested;
    const plPct = invested ? (pl / invested * 100) : 0;

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

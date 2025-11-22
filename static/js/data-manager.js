/* Portfolio Tracker - Data Management Module */

class DataManager {
  constructor() {
    this.latestHoldings = [];
    this.latestMFHoldings = [];
    this.latestSIPs = [];
    this.lastRenderedJSON = "";
    this.lastRenderedMFJSON = "";
    this.lastRenderedSIPsJSON = "";
  }

  async fetchHoldings() {
    const response = await fetch('/holdings_data');
    return await response.json();
  }

  async fetchMFHoldings() {
    const response = await fetch('/mf_holdings_data');
    return await response.json();
  }

  async fetchSIPs() {
    const response = await fetch('/sips_data');
    return await response.json();
  }

  async fetchStatus() {
    const response = await fetch('/status');
    return await response.json();
  }

  async fetchAllData() {
    const [holdings, mfHoldings, sips, status] = await Promise.all([
      this.fetchHoldings(),
      this.fetchMFHoldings(),
      this.fetchSIPs(),
      this.fetchStatus()
    ]);
    return { holdings, mfHoldings, sips, status };
  }

  updateHoldings(holdings, forceUpdate = false) {
    const holdingsJSON = JSON.stringify(holdings);
    if (holdingsJSON !== this.lastRenderedJSON || forceUpdate) {
      this.latestHoldings = holdings;
      this.lastRenderedJSON = holdingsJSON;
      return true;
    }
    return false;
  }

  updateMFHoldings(mfHoldings, forceUpdate = false) {
    const mfHoldingsJSON = JSON.stringify(mfHoldings);
    if (mfHoldingsJSON !== this.lastRenderedMFJSON || forceUpdate) {
      this.latestMFHoldings = mfHoldings;
      this.lastRenderedMFJSON = mfHoldingsJSON;
      return true;
    }
    return false;
  }

  updateSIPs(sips, forceUpdate = false) {
    const sipsJSON = JSON.stringify(sips);
    if (sipsJSON !== this.lastRenderedSIPsJSON || forceUpdate) {
      this.latestSIPs = sips;
      this.lastRenderedSIPsJSON = sipsJSON;
      return true;
    }
    return false;
  }

  getHoldings() {
    return this.latestHoldings;
  }

  getMFHoldings() {
    return this.latestMFHoldings;
  }

  getSIPs() {
    return this.latestSIPs;
  }

  async triggerRefresh() {
    const response = await fetch('/refresh', { method: 'POST' });
    if (response.status !== 202) {
      const data = await response.json();
      throw new Error(data.error || 'Unknown error');
    }
    return await response.json();
  }

  async waitForRefreshComplete() {
    let status;
    do {
      await new Promise(resolve => setTimeout(resolve, 1000));
      status = await this.fetchStatus();
    } while (status.state === 'updating');
    return status;
  }
}

export default DataManager;

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

  async _fetchEndpoint(endpoint) {
    const response = await fetch(endpoint);
    return await response.json();
  }

  async fetchHoldings() {
    return this._fetchEndpoint('/holdings_data');
  }

  async fetchMFHoldings() {
    return this._fetchEndpoint('/mf_holdings_data');
  }

  async fetchSIPs() {
    return this._fetchEndpoint('/sips_data');
  }

  async fetchStatus() {
    return this._fetchEndpoint('/status');
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

  _updateData(data, currentData, lastJSON, forceUpdate) {
    const dataJSON = JSON.stringify(data);
    if (dataJSON !== lastJSON || forceUpdate) {
      return { updated: true, newData: data, newJSON: dataJSON };
    }
    return { updated: false, newData: currentData, newJSON: lastJSON };
  }

  updateHoldings(holdings, forceUpdate = false) {
    const result = this._updateData(holdings, this.latestHoldings, this.lastRenderedJSON, forceUpdate);
    if (result.updated) {
      this.latestHoldings = result.newData;
      this.lastRenderedJSON = result.newJSON;
    }
    return result.updated;
  }

  updateMFHoldings(mfHoldings, forceUpdate = false) {
    const result = this._updateData(mfHoldings, this.latestMFHoldings, this.lastRenderedMFJSON, forceUpdate);
    if (result.updated) {
      this.latestMFHoldings = result.newData;
      this.lastRenderedMFJSON = result.newJSON;
    }
    return result.updated;
  }

  updateSIPs(sips, forceUpdate = false) {
    const result = this._updateData(sips, this.latestSIPs, this.lastRenderedSIPsJSON, forceUpdate);
    if (result.updated) {
      this.latestSIPs = result.newData;
      this.lastRenderedSIPsJSON = result.newJSON;
    }
    return result.updated;
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

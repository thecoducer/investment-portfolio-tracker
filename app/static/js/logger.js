/* Metron - Production Logger
 *
 * Minimal console output for production:
 *  - debug()  → console.debug  (hidden in DevTools unless "Verbose" level is on)
 *  - info()   → console.debug  (same as debug, hidden by default)
 *  - warn()   → console.warn   (always visible — use for actionable events)
 *  - error()  → console.error  (always visible — real errors only)
 *  - time()/timeEnd() → lightweight timing helpers
 *
 * All messages are prefixed with a tag, e.g. [Data], [PIN], [Auth].
 * Timestamps are added automatically.
 *
 * Usage:
 *   import { Log } from './logger.js';
 *   Log.debug('Data', 'Fetch started');
 *   Log.warn('Auth', 'Session expired');
 *   Log.time('Data', 'allDataFetch');
 *   // ... fetch ...
 *   Log.timeEnd('Data', 'allDataFetch');
 */

const _timers = new Map();

function _ts() {
  return new Date().toISOString();
}

const Log = Object.freeze({
  /**
   * Verbose debug — hidden in production DevTools by default.
   * @param {string} tag  Category tag (e.g. 'Data', 'PIN')
   * @param {...any} args  Message parts
   */
  debug(tag, ...args) {
    console.debug(`${_ts()} [${tag}]`, ...args);
  },

  /**
   * Informational — same visibility as debug (hidden by default).
   */
  info(tag, ...args) {
    console.debug(`${_ts()} [${tag}]`, ...args);
  },

  /**
   * Warning — always visible in DevTools console.
   * Use for events the user or developer should notice.
   */
  warn(tag, ...args) {
    console.warn(`${_ts()} [${tag}]`, ...args);
  },

  /**
   * Error — always visible. Use for real failures only.
   */
  error(tag, ...args) {
    console.error(`${_ts()} [${tag}]`, ...args);
  },

  /**
   * Start a named timer.  Call timeEnd() with the same key to log elapsed ms.
   * @param {string} tag   Category tag
   * @param {string} label Timer label (unique per tag)
   */
  time(tag, label) {
    _timers.set(`${tag}:${label}`, performance.now());
  },

  /**
   * End a named timer and log the elapsed duration (debug level).
   * @param {string} tag   Category tag
   * @param {string} label Timer label (must match a previous time() call)
   */
  timeEnd(tag, label) {
    const key = `${tag}:${label}`;
    const start = _timers.get(key);
    if (start !== undefined) {
      const ms = (performance.now() - start).toFixed(1);
      _timers.delete(key);
      console.debug(`${_ts()} [${tag}] ${label}: ${ms}ms`);
    }
  },
});

export { Log };

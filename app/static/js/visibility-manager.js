/* Portfolio Tracker - Visibility Management Module */

class PrivacyManager {
  constructor() {
    this.privacyIcon = document.getElementById('privacy_toggle_icon');
    this.isPrivacyMode = false;
  }

  init() {
    const savedPrivacy = localStorage.getItem('privacyMode') || 'off';
    this.applyPrivacyMode(savedPrivacy === 'on');
  }

  toggle() {
    this.isPrivacyMode = !this.isPrivacyMode;
    this.applyPrivacyMode(this.isPrivacyMode);
    localStorage.setItem('privacyMode', this.isPrivacyMode ? 'on' : 'off');
  }

  applyPrivacyMode(enabled) {
    this.isPrivacyMode = enabled;
    const body = document.body;
    
    if (enabled) {
      body.classList.add('privacy-mode');
      this.privacyIcon.textContent = '🔒';
    } else {
      body.classList.remove('privacy-mode');
      this.privacyIcon.textContent = '👁️';
    }
  }

  getPrivacyMode() {
    return this.isPrivacyMode;
  }
}

export default PrivacyManager;

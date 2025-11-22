/* Portfolio Tracker - Theme Management Module */

class ThemeManager {
  constructor() {
    this.themeIcon = document.getElementById('theme_toggle_icon');
  }

  init() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    this.applyTheme(savedTheme);
  }

  toggle() {
    const body = document.body;
    const newTheme = body.classList.contains('dark-theme') ? 'light' : 'dark';
    this.applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  }

  applyTheme(theme) {
    const body = document.body;
    
    if (theme === 'dark') {
      body.classList.add('dark-theme');
      this.themeIcon.textContent = '☀️';
    } else {
      body.classList.remove('dark-theme');
      this.themeIcon.textContent = '🌙';
    }
  }
}

export default ThemeManager;

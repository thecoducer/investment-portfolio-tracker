// Shared navigation utilities (loaded by both portfolio and nifty50 pages)

// Close user dropdown when clicking outside
document.addEventListener('click', function(event) {
  var dropdown = document.getElementById('userDropdown');
  var avatarBtn = document.getElementById('userAvatarBtn');
  if (dropdown && avatarBtn && !avatarBtn.contains(event.target) && !dropdown.contains(event.target)) {
    dropdown.classList.remove('open');
  }
  // Close nav dropdown when clicking outside
  var navDropdown = document.getElementById('navDropdown');
  var hamburgerBtn = document.getElementById('hamburgerBtn');
  if (navDropdown && hamburgerBtn && !hamburgerBtn.contains(event.target) && !navDropdown.contains(event.target)) {
    navDropdown.classList.remove('open');
    hamburgerBtn.classList.remove('open');
    hamburgerBtn.setAttribute('aria-expanded', 'false');
  }
});

// User avatar dropdown toggle
(function() {
  var avatarBtn = document.getElementById('userAvatarBtn');
  var dropdown = document.getElementById('userDropdown');
  if (avatarBtn && dropdown) {
    avatarBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      dropdown.classList.toggle('open');
    });
  }
})();

// Hamburger navigation menu toggle
(function() {
  var hamburgerBtn = document.getElementById('hamburgerBtn');
  var navDropdown = document.getElementById('navDropdown');
  if (hamburgerBtn && navDropdown) {
    hamburgerBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      var isOpen = navDropdown.classList.toggle('open');
      hamburgerBtn.classList.toggle('open');
      hamburgerBtn.setAttribute('aria-expanded', String(isOpen));
    });
  }
})();

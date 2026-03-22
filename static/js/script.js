/* FindMyParking — JavaScript */

// ── Mobile menu toggle ──
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    if (menu) menu.classList.toggle('hidden');
}

function getStoredTheme() {
    try {
        return localStorage.getItem('fmp-theme');
    } catch (e) {
        return null;
    }
}

function setStoredTheme(theme) {
    try {
        localStorage.setItem('fmp-theme', theme);
    } catch (e) {
        // Ignore persistence failures (private mode/storage blocked)
    }
}

function applyTheme(theme) {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    setStoredTheme(theme);

    if (document.body) {
        document.body.classList.toggle('dark-mode', theme === 'dark');
    }

    const isDark = theme === 'dark';
    const desktopIcon = document.getElementById('theme-toggle-icon');
    const desktopText = document.getElementById('theme-toggle-text');
    const mobileIcon = document.getElementById('mobile-theme-toggle-icon');
    const mobileText = document.getElementById('mobile-theme-toggle-text');

    if (desktopIcon) desktopIcon.textContent = isDark ? '☀️' : '🌙';
    if (desktopText) desktopText.textContent = isDark ? 'Light' : 'Dark';
    if (mobileIcon) mobileIcon.textContent = isDark ? '☀️' : '🌙';
    if (mobileText) mobileText.textContent = isDark ? 'Light Mode' : 'Dark Mode';
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'dark' ? 'light' : 'dark');
}

// ── Password show/hide ──
function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    btn.innerHTML = isHidden
        ? '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21"/></svg>'
        : '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>';
}

// ── Confirmation modal ──
let confirmCallback = null;

function showConfirmModal(title, message, form) {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    document.getElementById('confirm-modal').classList.remove('hidden');
    confirmCallback = () => { closeConfirmModal(); form.submit(); };
    document.getElementById('confirm-action-btn').onclick = confirmCallback;
    return false; // prevent immediate form submit
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.add('hidden');
    confirmCallback = null;
}

// Close modal on backdrop click
document.addEventListener('click', function (e) {
    const modal = document.getElementById('confirm-modal');
    if (modal && e.target === modal) closeConfirmModal();
});

// ── Client-side search filtering ──
document.addEventListener('DOMContentLoaded', function () {
    if (!window.__fmpThemeManaged) {
        const themeToggle = document.getElementById('theme-toggle');
        const mobileThemeToggle = document.getElementById('mobile-theme-toggle');
        const currentTheme = getStoredTheme() || document.documentElement.getAttribute('data-theme') || 'light';
        applyTheme(currentTheme);

        if (themeToggle) themeToggle.addEventListener('click', toggleTheme);
        if (mobileThemeToggle) mobileThemeToggle.addEventListener('click', toggleTheme);
    }

    const premiumPanels = document.querySelectorAll('.premium-panel');
    if (premiumPanels.length) {
        premiumPanels.forEach(panel => panel.classList.add('reveal'));
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        premiumPanels.forEach(panel => observer.observe(panel));
    }

    document.querySelectorAll('.ultra-media img').forEach((img) => {
        if (img.complete) {
            var mediaParent = img.closest('.ultra-media');
            if (mediaParent) mediaParent.classList.add('loaded');
        } else {
            img.addEventListener('load', () => {
                var loadedParent = img.closest('.ultra-media');
                if (loadedParent) loadedParent.classList.add('loaded');
            });
        }
    });

    const revealSections = document.querySelectorAll('.reveal-seq');
    if (revealSections.length) {
        const sectionObserver = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                const children = Array.from(entry.target.children);
                children.forEach((child) => {
                    child.classList.add('is-visible');
                });
                sectionObserver.unobserve(entry.target);
            });
        }, { threshold: 0.1 });

        revealSections.forEach((section) => sectionObserver.observe(section));
    }
    // NOTE: Search filtering is handled by map integration (filterParkingSpots)
    // Do not duplicate search logic here - it conflicts with map-based filtering

    // ── Auto-dismiss toasts after 5s ──
    document.querySelectorAll('.toast-msg').forEach(msg => {
        setTimeout(() => {
            msg.style.transition = 'all .3s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateX(100px)';
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });

    // ── Close user dropdown on outside click or Escape key ──
    document.addEventListener('click', function (e) {
        const dd = document.getElementById('user-dropdown');
        const ddBtn = document.querySelector('[onclick*="user-dropdown"]');
        const ddWrap = dd ? dd.closest('.relative') : null;
        if (dd && ddWrap && !ddWrap.contains(e.target)) {
            dd.classList.add('hidden');
            if (ddBtn) ddBtn.setAttribute('aria-expanded', 'false');
        }
    });

    // ── Escape key handler for dropdown ──
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const dd = document.getElementById('user-dropdown');
            const ddBtn = document.querySelector('[onclick*="user-dropdown"]');
            if (dd && !dd.classList.contains('hidden')) {
                dd.classList.add('hidden');
                if (ddBtn) {
                    ddBtn.setAttribute('aria-expanded', 'false');
                    ddBtn.focus();
                }
            }
        }
    });

    // ── Navbar shadow on scroll ──
    const nav = document.getElementById('main-nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 10) {
                nav.classList.add('shadow-sm');
            } else {
                nav.classList.remove('shadow-sm');
            }
        });
    }
});

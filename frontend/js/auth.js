/**
 * Authentication and Session Management for Blood SOS
 */

class Auth {
    static isLoggedIn() {
        return !!ApiClient.getToken();
    }

    static getUser() {
        return ApiClient.getUser();
    }

    static async login(email, password) {
        const response = await ApiClient.post('/auth/login', { email, password });
        ApiClient.setToken(response.access_token);
        ApiClient.setUser({
            id: response.user_id,
            role: response.role,
            full_name: response.full_name,
            email: response.email
        });
        return response;
    }

    static async register(userData) {
        const response = await ApiClient.post('/auth/register', userData);
        ApiClient.setToken(response.access_token);
        ApiClient.setUser({
            id: response.user_id,
            role: response.role,
            full_name: response.full_name,
            email: response.email
        });
        return response;
    }

    static logout() {
        ApiClient.removeToken();
        showToast('Logged out successfully', 'info');
        setTimeout(() => {
            window.location.href = '/login.html';
        }, 500);
    }

    static requireAuth(allowedRoles = []) {
        if (!this.isLoggedIn()) {
            window.location.href = `/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
            return null;
        }

        const user = this.getUser();
        if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
            // Redirect to appropriate dashboard based on actual role
            if (user.role === 'admin') window.location.href = '/admin-dashboard.html';
            else if (user.role === 'donor') window.location.href = '/donor-dashboard.html';
            else if (user.role === 'patient') window.location.href = '/patient-dashboard.html';
            else window.location.href = '/index.html';
            return null;
        }
        return user;
    }

    static updateNavigation() {
        const navActions = document.getElementById('nav-actions');
        if (!navActions) return;

        if (this.isLoggedIn()) {
            const user = this.getUser();
            let dashboardHref = '/patient-dashboard.html';
            if (user.role === 'donor') dashboardHref = '/donor-dashboard.html';
            if (user.role === 'admin') dashboardHref = '/admin-dashboard.html';

            navActions.innerHTML = `
                <!-- Notification Bell -->
                <div class="notification-menu">
                    <button class="notification-bell" id="notification-bell-btn" title="Notifications">
                        🔔
                        <span class="notification-badge" id="notification-unread-count" style="display: none;">0</span>
                    </button>
                    <div class="notification-dropdown" id="notification-dropdown">
                        <div class="notification-header">
                            <span style="font-weight: 700; font-size: 0.95rem;">Notifications</span>
                            <button class="btn btn-sm btn-secondary" id="mark-all-read-btn">Mark All Read</button>
                        </div>
                        <ul class="notification-list" id="notification-items-container">
                            <li style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                                Loading alerts...
                            </li>
                        </ul>
                    </div>
                </div>

                <!-- Dashboard Link -->
                <a href="${dashboardHref}" class="btn btn-secondary btn-sm">
                    Dashboard
                </a>

                <!-- User Profile / Logout Menu -->
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary);">${user.full_name.split(' ')[0]}</span>
                    <button onclick="Auth.logout()" class="btn btn-outline-red btn-sm" title="Log out">
                        Exit
                    </button>
                </div>
            `;

            // Initialize notification listeners
            if (window.NotificationsManager) {
                window.NotificationsManager.init();
            }
        } else {
            navActions.innerHTML = `
                <a href="/login.html" class="btn btn-secondary btn-sm">Log In</a>
                <a href="/register.html" class="btn btn-primary btn-sm">Sign Up</a>
            `;
        }
    }
}

// Global auto-run when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    Auth.updateNavigation();
});

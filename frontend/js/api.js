/**
 * Centralized API client for Blood SOS
 */

const API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? `${window.location.origin}/api`
    : '/api';

class ApiClient {
    static getToken() {
        return localStorage.getItem('bloodsos_token');
    }

    static setToken(token) {
        localStorage.setItem('bloodsos_token', token);
    }

    static removeToken() {
        localStorage.removeItem('bloodsos_token');
        localStorage.removeItem('bloodsos_user');
    }

    static getUser() {
        const u = localStorage.getItem('bloodsos_user');
        return u ? JSON.parse(u) : null;
    }

    static setUser(user) {
        localStorage.setItem('bloodsos_user', JSON.stringify(user));
    }

    static async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (response.status === 401) {
                // Unauthorized - clear token and redirect if on protected page
                this.removeToken();
                const path = window.location.pathname;
                if (!path.includes('login.html') && !path.includes('register.html') && path !== '/' && !path.endsWith('index.html')) {
                    window.location.href = '/login.html?expired=true';
                }
            }

            const data = await response.json().catch(() => null);

            if (!response.ok) {
                const errorMsg = data && (data.detail || data.message) ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : 'Request failed';
                throw new Error(errorMsg);
            }

            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    static get(endpoint, params = null) {
        let url = endpoint;
        if (params) {
            const query = new URLSearchParams();
            Object.entries(params).forEach(([key, val]) => {
                if (val !== undefined && val !== null && val !== '') {
                    query.append(key, val);
                }
            });
            const qs = query.toString();
            if (qs) url += `?${qs}`;
        }
        return this.request(url, { method: 'GET' });
    }

    static post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    static put(endpoint, body) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    }

    static patch(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(body)
        });
    }

    static del(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}

// Toast notification helper
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';

    toast.innerHTML = `
        <span style="font-size: 1.1rem;">${icon}</span>
        <div style="flex: 1; font-size: 0.88rem; font-weight: 500;">${message}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

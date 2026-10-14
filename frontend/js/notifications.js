/**
 * In-app Notification System for Blood SOS
 */

class NotificationsManager {
    static init() {
        const bellBtn = document.getElementById('notification-bell-btn');
        const dropdown = document.getElementById('notification-dropdown');
        const markAllBtn = document.getElementById('mark-all-read-btn');

        if (!bellBtn || !dropdown) return;

        bellBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isShowing = dropdown.classList.contains('show');
            if (!isShowing) {
                this.loadNotifications();
                dropdown.classList.add('show');
            } else {
                dropdown.classList.remove('show');
            }
        });

        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target) && e.target !== bellBtn) {
                dropdown.classList.remove('show');
            }
        });

        if (markAllBtn) {
            markAllBtn.addEventListener('click', async () => {
                try {
                    await ApiClient.post('/notifications/mark-all-read', {});
                    this.loadNotifications();
                    showToast('All notifications marked read', 'info');
                } catch (err) {
                    console.error('Failed to mark all read:', err);
                }
            });
        }

        // Initial check for unread badge
        this.checkUnreadCount();
        
        // Periodic poll every 30 seconds
        setInterval(() => this.checkUnreadCount(), 30000);
    }

    static async checkUnreadCount() {
        if (!Auth.isLoggedIn()) return;
        try {
            const notifications = await ApiClient.get('/notifications');
            const unread = notifications.filter(n => !n.is_read).length;
            const badge = document.getElementById('notification-unread-count');
            if (badge) {
                if (unread > 0) {
                    badge.innerText = unread > 9 ? '9+' : unread;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        } catch (e) {
            // Quiet fail
        }
    }

    static async loadNotifications() {
        const container = document.getElementById('notification-items-container');
        if (!container) return;

        try {
            const list = await ApiClient.get('/notifications');
            if (!list || list.length === 0) {
                container.innerHTML = `
                    <li style="padding: 2rem 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                        No notifications yet.
                    </li>
                `;
                return;
            }

            container.innerHTML = list.map(item => `
                <li class="notification-item ${item.is_read ? '' : 'unread'}" onclick="NotificationsManager.markItemRead('${item.id}', '${item.related_request_id || ''}')">
                    <div class="notification-item-title">${item.title}</div>
                    <div class="notification-item-desc">${item.message}</div>
                    <div class="notification-item-time">${new Date(item.created_at).toLocaleString()}</div>
                </li>
            `).join('');

            // Update badge count
            const unread = list.filter(n => !n.is_read).length;
            const badge = document.getElementById('notification-unread-count');
            if (badge) {
                if (unread > 0) {
                    badge.innerText = unread > 9 ? '9+' : unread;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        } catch (err) {
            container.innerHTML = `
                <li style="padding: 1.5rem; text-align: center; color: var(--accent-red); font-size: 0.85rem;">
                    Failed to load notifications.
                </li>
            `;
        }
    }

    static async markItemRead(notificationId, relatedRequestId) {
        try {
            await ApiClient.patch(`/notifications/${notificationId}/read`);
            this.loadNotifications();
            if (relatedRequestId) {
                // If it relates to a request, navigate to requests page
                window.location.href = `/requests.html?id=${relatedRequestId}`;
            }
        } catch (e) {
            console.error('Failed to mark read:', e);
        }
    }
}

window.NotificationsManager = NotificationsManager;

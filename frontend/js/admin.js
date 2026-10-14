/**
 * Administrator Dashboard & Analytics Controller for Blood SOS
 */

let charts = {};

document.addEventListener('DOMContentLoaded', async () => {
    const user = Auth.requireAuth(['admin']);
    if (!user) return;

    loadDashboardStats();
    loadAnalyticsCharts();
    loadAdminUsers();
    loadAdminRequests();
    loadPendingDonations();
    setupAdminFilters();
});

async function loadDashboardStats() {
    try {
        const stats = await ApiClient.get('/admin/dashboard');
        
        document.getElementById('stat-total-users').innerText = stats.total_users;
        document.getElementById('stat-available-donors').innerText = `${stats.available_donors} / ${stats.total_donors}`;
        document.getElementById('stat-critical-requests').innerText = stats.critical_active_requests;
        document.getElementById('stat-fulfilled-requests').innerText = stats.fulfilled_requests;
        document.getElementById('stat-verified-donations').innerText = stats.verified_donations;
        document.getElementById('stat-total-points').innerText = stats.total_points_awarded;
    } catch (e) {
        console.error('Failed to load dashboard stats', e);
    }
}

async function loadAnalyticsCharts() {
    try {
        const data = await ApiClient.get('/admin/analytics');

        // 1. Requests by Blood Group Bar Chart
        const ctxBg = document.getElementById('chart-blood-group');
        if (ctxBg) {
            if (charts.bg) charts.bg.destroy();
            charts.bg = new Chart(ctxBg, {
                type: 'bar',
                data: {
                    labels: Object.keys(data.requests_by_blood_group),
                    datasets: [{
                        label: 'Requests',
                        data: Object.values(data.requests_by_blood_group),
                        backgroundColor: 'rgba(239, 68, 68, 0.7)',
                        borderColor: '#ef4444',
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { grid: { display: false } }
                    }
                }
            });
        }

        // 2. Requests by Status Doughnut Chart
        const ctxStatus = document.getElementById('chart-status');
        if (ctxStatus) {
            if (charts.status) charts.status.destroy();
            charts.status = new Chart(ctxStatus, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(data.requests_by_status).map(s => s.replace(/_/g, ' ')),
                    datasets: [{
                        data: Object.values(data.requests_by_status),
                        backgroundColor: [
                            '#ef4444', '#f59e0b', '#06b6d4', '#10b981', '#64748b', '#8b5cf6'
                        ],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } }
                }
            });
        }

        // 3. Donor Availability Pie Chart
        const ctxAvail = document.getElementById('chart-availability');
        if (ctxAvail) {
            if (charts.avail) charts.avail.destroy();
            charts.avail = new Chart(ctxAvail, {
                type: 'pie',
                data: {
                    labels: Object.keys(data.donor_availability_distribution).map(s => s.replace(/_/g, ' ')),
                    datasets: [{
                        data: Object.values(data.donor_availability_distribution),
                        backgroundColor: ['#10b981', '#64748b', '#f59e0b', '#ef4444'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } }
                }
            });
        }
    } catch (e) {
        console.error('Failed to load analytics charts', e);
    }
}

async function loadAdminUsers(filterParams = {}) {
    const container = document.getElementById('admin-users-table-body');
    if (!container) return;

    try {
        const users = await ApiClient.get('/admin/users', filterParams);
        if (!users || users.length === 0) {
            container.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No matching users found.</td></tr>`;
            return;
        }

        container.innerHTML = users.map(u => {
            const isSuspended = u.account_status === 'suspended';
            return `
                <tr>
                    <td>
                        <strong>${u.full_name}</strong>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${u.email}</div>
                    </td>
                    <td><span class="badge ${u.role === 'admin' ? 'badge-critical' : (u.role === 'donor' ? 'badge-available' : 'badge-normal')}">${u.role}</span></td>
                    <td><span class="blood-pill">${u.blood_group || 'N/A'}</span></td>
                    <td>${u.city || 'N/A'}</td>
                    <td>
                        <span class="badge ${isSuspended ? 'badge-critical' : 'badge-available'}">
                            ${u.account_status.toUpperCase()}
                        </span>
                    </td>
                    <td>
                        ${u.role === 'donor' ? `
                            <button class="btn btn-sm ${u.is_verified ? 'btn-secondary' : 'btn-cyan'}" onclick="toggleUserVerification('${u.id}', ${!u.is_verified})">
                                ${u.is_verified ? 'Verified ✓' : 'Verify Donor'}
                            </button>
                        ` : '-'}
                    </td>
                    <td>
                        ${u.role !== 'admin' ? `
                            <button class="btn btn-sm ${isSuspended ? 'btn-primary' : 'btn-outline-red'}" onclick="toggleAccountSuspension('${u.id}', '${isSuspended ? 'active' : 'suspended'}')">
                                ${isSuspended ? 'Reactivate' : 'Suspend'}
                            </button>
                        ` : '<span style="color: var(--text-muted); font-size: 0.78rem;">Protected</span>'}
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = `<tr><td colspan="7" style="color: var(--accent-red); padding: 1rem;">Failed to load users: ${e.message}</td></tr>`;
    }
}

async function toggleAccountSuspension(userId, newStatus) {
    if (!confirm(`Are you sure you want to set this account status to ${newStatus}?`)) return;
    try {
        await ApiClient.patch(`/admin/users/${userId}/status`, { account_status: newStatus });
        showToast(`Account updated to ${newStatus}`, 'success');
        loadAdminUsers();
        loadDashboardStats();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function toggleUserVerification(userId, isVerified) {
    try {
        await ApiClient.patch(`/admin/users/${userId}/status`, { is_verified: isVerified });
        showToast(isVerified ? 'Donor marked verified!' : 'Donor verification removed', 'info');
        loadAdminUsers();
        loadDashboardStats();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadAdminRequests() {
    const container = document.getElementById('admin-requests-table-body');
    if (!container) return;

    try {
        const requests = await ApiClient.get('/admin/requests');
        if (!requests || requests.length === 0) {
            container.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No requests logged.</td></tr>`;
            return;
        }

        container.innerHTML = requests.map(r => `
            <tr>
                <td><strong>${r.hospital_name}</strong><div style="font-size: 0.75rem; color: var(--text-muted);">${r.city}, ${r.state}</div></td>
                <td>${r.requester_name}</td>
                <td><span class="blood-pill">${r.blood_group}</span> (${r.units_required}u)</td>
                <td><span class="badge badge-${r.urgency}">${r.urgency}</span></td>
                <td><span class="badge badge-normal">${r.status}</span></td>
                <td>${new Date(r.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } catch (e) {
        container.innerHTML = `<tr><td colspan="6" style="color: var(--accent-red); padding: 1rem;">Failed to load requests: ${e.message}</td></tr>`;
    }
}

async function loadPendingDonations() {
    const container = document.getElementById('admin-donations-table-body');
    if (!container) return;

    try {
        const donations = await ApiClient.get('/admin/donations');
        if (!donations || donations.length === 0) {
            container.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No donation records submitted.</td></tr>`;
            return;
        }

        container.innerHTML = donations.map(d => {
            const isPending = d.donation_status === 'completed_pending_verification';
            return `
                <tr>
                    <td><strong>${d.donor_name}</strong></td>
                    <td><span class="blood-pill">${d.donor_blood_group}</span></td>
                    <td>${d.hospital_name || 'Blood Bank'}</td>
                    <td>${d.donation_date}</td>
                    <td>
                        <span class="badge ${d.donation_status === 'verified' ? 'badge-fulfilled' : (isPending ? 'badge-high' : 'badge-unavailable')}">
                            ${d.donation_status.replace(/_/g, ' ').toUpperCase()}
                        </span>
                    </td>
                    <td>
                        ${isPending ? `
                            <button class="btn btn-sm btn-primary" onclick="verifyDonation('${d.id}', 'verify')">Verify (+100 Pts)</button>
                            <button class="btn btn-sm btn-outline-red" onclick="verifyDonation('${d.id}', 'reject')">Reject</button>
                        ` : `
                            <span style="color: var(--text-muted); font-size: 0.8rem;">Points: ${d.points_awarded || 0}</span>
                        `}
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = `<tr><td colspan="6" style="color: var(--accent-red); padding: 1rem;">Failed to load donations: ${e.message}</td></tr>`;
    }
}

async function verifyDonation(donationId, action) {
    try {
        await ApiClient.patch(`/admin/donations/${donationId}/verify`, { action });
        showToast(action === 'verify' ? 'Donation verified & +100 points awarded to donor!' : 'Donation record rejected.', 'success');
        loadPendingDonations();
        loadDashboardStats();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function setupAdminFilters() {
    const searchInput = document.getElementById('user-search-input');
    const roleSelect = document.getElementById('user-role-filter');

    const applyFilter = () => {
        const search = searchInput ? searchInput.value : '';
        const role = roleSelect ? roleSelect.value : '';
        loadAdminUsers({ search, role });
    };

    if (searchInput) searchInput.addEventListener('input', applyFilter);
    if (roleSelect) roleSelect.addEventListener('change', applyFilter);
}

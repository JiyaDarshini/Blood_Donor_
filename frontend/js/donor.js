/**
 * Donor Dashboard Logic for Blood SOS
 */

document.addEventListener('DOMContentLoaded', async () => {
    const user = Auth.requireAuth(['donor', 'admin']);
    if (!user) return;

    setupAvailabilityToggle();
    setupDonationForm();
    Promise.allSettled([
        loadDonorProfile(),
        loadInvitations(),
        loadRewardsAndBadges()
    ]);
});

async function loadDonorProfile() {
    try {
        const me = await ApiClient.get('/auth/me');
        const nameEl = document.getElementById('donor-name-display');
        const bloodEl = document.getElementById('donor-blood-display');
        const statusEl = document.getElementById('donor-verified-badge');
        const toggle = document.getElementById('availability-switch');

        if (nameEl) nameEl.innerText = me.user.full_name;
        if (bloodEl && me.profile) bloodEl.innerText = me.profile.blood_group || 'O+';
        
        if (statusEl && me.profile) {
            if (me.profile.is_verified) {
                statusEl.innerHTML = '<span class="badge badge-verified">Verified Donor</span>';
            } else {
                statusEl.innerHTML = '<span class="badge badge-unavailable">Pending Verification</span>';
            }
        }

        if (toggle && me.profile) {
            toggle.checked = me.profile.availability_status === 'available';
            updateAvailabilityLabel(toggle.checked);
        }
    } catch (e) {
        console.error('Failed to load profile', e);
    }
}

function updateAvailabilityLabel(isAvailable) {
    const label = document.getElementById('availability-text');
    if (label) {
        label.innerText = isAvailable ? 'Available for SOS Calls' : 'Currently Unavailable';
        label.style.color = isAvailable ? 'var(--accent-emerald)' : 'var(--text-muted)';
    }
}

function setupAvailabilityToggle() {
    const toggle = document.getElementById('availability-switch');
    if (!toggle) return;

    toggle.addEventListener('change', async (e) => {
        const newStatus = toggle.checked ? 'available' : 'unavailable';
        updateAvailabilityLabel(toggle.checked);

        try {
            await ApiClient.patch('/donors/me/availability', {
                availability_status: newStatus
            });
            showToast(`Status updated to: ${newStatus.toUpperCase()}`, 'success');
        } catch (err) {
            showToast('Failed to update availability: ' + err.message, 'error');
            toggle.checked = !toggle.checked;
            updateAvailabilityLabel(toggle.checked);
        }
    });
}

async function loadInvitations() {
    const container = document.getElementById('donor-invitations-container');
    if (!container) return;

    try {
        const invitations = await ApiClient.get('/invitations/me');
        if (!invitations || invitations.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 2.5rem 1.5rem; color: var(--text-muted); font-size: 0.9rem;">
                    No pending SOS requests in your area at the moment. Keep your availability active to save lives!
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 1rem;">
                ${invitations.map(inv => {
                    const req = inv.request_details;
                    if (!req) return '';
                    const isPending = inv.status === 'pending';
                    const isAccepted = inv.status === 'accepted';

                    return `
                        <div class="card ${isPending ? 'card-glow-red' : ''}" style="padding: 1.25rem;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.75rem;">
                                <div>
                                    <span class="badge badge-${req.urgency}">${req.urgency.toUpperCase()}</span>
                                    <h4 style="font-size: 1.15rem; font-weight: 700; margin-top: 0.35rem; color: var(--text-primary);">
                                        ${req.hospital_name}
                                    </h4>
                                    <div style="font-size: 0.82rem; color: var(--text-muted);">${req.city}, ${req.state}</div>
                                </div>
                                <div style="text-align: right;">
                                    <span class="blood-pill">${req.blood_group}</span>
                                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.25rem;">${req.units_required} unit(s)</div>
                                </div>
                            </div>

                            <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 1rem;">
                                ${req.description || 'Emergency blood donation needed. Please assist if eligible.'}
                            </p>

                            ${isAccepted ? `
                                <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem;">
                                    <strong>Contact Revealed:</strong> Requester: ${req.requester_name} | Phone: <a href="tel:${req.requester_phone}" style="color: var(--accent-emerald); font-weight: 700;">${req.requester_phone}</a>
                                </div>
                            ` : ''}

                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                                <div style="font-size: 0.78rem; color: var(--text-muted);">
                                    Invited on: ${new Date(inv.invited_at).toLocaleDateString()}
                                </div>
                                <div style="display: flex; gap: 0.5rem;">
                                    ${isPending ? `
                                        <button class="btn btn-outline-red btn-sm" onclick="respondInvitation('${inv.id}', 'declined')">Decline</button>
                                        <button class="btn btn-primary btn-sm" onclick="respondInvitation('${inv.id}', 'accepted')">Accept SOS</button>
                                    ` : `
                                        <span class="badge ${isAccepted ? 'badge-fulfilled' : 'badge-unavailable'}">
                                            ${inv.status.toUpperCase()}
                                        </span>
                                    `}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    } catch (e) {
        container.innerHTML = `<div style="color: var(--accent-red); padding: 1rem;">Error loading invitations: ${e.message}</div>`;
    }
}

async function respondInvitation(invitationId, responseChoice) {
    try {
        await ApiClient.post(`/invitations/${invitationId}/respond`, { response: responseChoice });
        showToast(responseChoice === 'accepted' ? 'Thank you! You accepted the emergency request.' : 'Declined request.', 'info');
        loadInvitations();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadRewardsAndBadges() {
    try {
        const data = await ApiClient.get('/rewards/me');
        const pointsEl = document.getElementById('wallet-points-display');
        const donationsEl = document.getElementById('wallet-donations-display');
        const milestoneEl = document.getElementById('wallet-milestone-text');
        const milestoneBar = document.getElementById('wallet-milestone-bar');
        const badgesContainer = document.getElementById('wallet-badges-container');
        const ledgerContainer = document.getElementById('wallet-ledger-container');

        if (pointsEl) pointsEl.innerText = data.total_points;
        if (donationsEl) donationsEl.innerText = `${data.total_verified_donations} Verified Donation(s)`;
        if (milestoneEl) milestoneEl.innerText = `Next: ${data.next_milestone} (${data.points_to_next_milestone} pts needed)`;
        
        if (milestoneBar) {
            const pct = Math.min(100, Math.max(10, (data.total_points % 500) / 5));
            milestoneBar.style.width = `${pct}%`;
        }

        if (badgesContainer) {
            if (data.badges.length === 0) {
                badgesContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">Complete your first verified donation to unlock achievement badges!</span>`;
            } else {
                badgesContainer.innerHTML = data.badges.map(b => `
                    <div class="badge-item">
                        <span>🎖️</span>
                        <span>${b}</span>
                    </div>
                `).join('');
            }
        }

        if (ledgerContainer) {
            if (!data.transactions || data.transactions.length === 0) {
                ledgerContainer.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No reward transactions logged yet.</td></tr>`;
            } else {
                ledgerContainer.innerHTML = data.transactions.map(t => `
                    <tr>
                        <td style="font-weight: 700; color: var(--accent-emerald);">+${t.points} Pts</td>
                        <td>${t.description}</td>
                        <td><span class="badge badge-normal">${t.transaction_type}</span></td>
                        <td style="color: var(--text-muted); font-size: 0.82rem;">${new Date(t.created_at).toLocaleDateString()}</td>
                    </tr>
                `).join('');
            }
        }
    } catch (e) {
        console.error('Failed to load rewards', e);
    }
}

function setupDonationForm() {
    const form = document.getElementById('log-donation-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const dateVal = document.getElementById('donation-date').value;
        const hospitalVal = document.getElementById('donation-hospital').value;
        const unitsVal = parseInt(document.getElementById('donation-units').value);
        const notesVal = document.getElementById('donation-notes').value;

        try {
            await ApiClient.post('/donations', {
                donation_date: dateVal,
                hospital_name: hospitalVal,
                units_donated: unitsVal,
                notes: notesVal
            });
            showToast('Donation record submitted! Points will be awarded upon admin verification.', 'success');
            closeDonationModal();
            form.reset();
            loadRewardsAndBadges();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });
}

function openDonationModal() {
    const modal = document.getElementById('donation-modal');
    if (modal) modal.classList.add('show');
}

function closeDonationModal() {
    const modal = document.getElementById('donation-modal');
    if (modal) modal.classList.remove('show');
}

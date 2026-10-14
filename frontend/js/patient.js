/**
 * Patient / Requester Dashboard Logic for Blood SOS
 */

document.addEventListener('DOMContentLoaded', async () => {
    const user = Auth.requireAuth(['patient', 'admin']);
    if (!user) return;

    loadPatientProfile();
    loadPatientRequests();
    setupSosModal();
});

async function loadPatientProfile() {
    try {
        const me = await ApiClient.get('/auth/me');
        const nameEl = document.getElementById('patient-name-display');
        if (nameEl) nameEl.innerText = me.user.full_name;
    } catch (e) {
        console.error('Failed to load patient info', e);
    }
}

async function loadPatientRequests() {
    const container = document.getElementById('patient-requests-container');
    if (!container) return;

    try {
        const requests = await ApiClient.get('/requests?only_mine=true');
        if (!requests || requests.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem 1.5rem; background: var(--bg-card); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle);">
                    <div style="font-size: 2.5rem; margin-bottom: 0.8rem;">🚨</div>
                    <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;">No Active Blood Requests</h3>
                    <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto 1.5rem; font-size: 0.9rem;">
                        If you or someone under your care requires blood urgently, click the Emergency SOS button above to broadcast an instant alert to compatible donors.
                    </p>
                    <button class="btn btn-sos btn-sm" onclick="openSosModal()">Create Emergency Request</button>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Hospital & City</th>
                            <th>Blood Group</th>
                            <th>Units</th>
                            <th>Urgency</th>
                            <th>Status</th>
                            <th>Matched Donors</th>
                            <th>Created</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${requests.map(r => `
                            <tr>
                                <td>
                                    <strong>${r.hospital_name}</strong>
                                    <div style="font-size: 0.78rem; color: var(--text-muted);">${r.city}, ${r.state}</div>
                                </td>
                                <td><span class="blood-pill">${r.blood_group}</span></td>
                                <td><strong>${r.units_required}</strong></td>
                                <td><span class="badge badge-${r.urgency}">${r.urgency}</span></td>
                                <td><span class="badge ${getStatusBadgeClass(r.status)}">${formatStatus(r.status)}</span></td>
                                <td>
                                    <span style="font-weight: 700; color: ${r.accepted_donors_count > 0 ? 'var(--accent-emerald)' : 'var(--text-secondary)'};">
                                        ${r.accepted_donors_count} Accepted / ${r.matched_donors_count} Notified
                                    </span>
                                </td>
                                <td style="font-size: 0.82rem; color: var(--text-muted);">${new Date(r.created_at).toLocaleDateString()}</td>
                                <td>
                                    <button class="btn btn-secondary btn-sm" onclick="viewRequestDetails('${r.id}')">View</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div style="color: var(--accent-red); padding: 1.5rem;">Error loading requests: ${err.message}</div>`;
    }
}

function getStatusBadgeClass(status) {
    if (status === 'fulfilled') return 'badge-fulfilled';
    if (status === 'critical') return 'badge-critical';
    if (status === 'searching') return 'badge-normal';
    if (status === 'responses_received') return 'badge-available';
    return 'badge-unavailable';
}

function formatStatus(status) {
    return status.replace(/_/g, ' ').toUpperCase();
}

function setupSosModal() {
    const geoBtn = document.getElementById('auto-locate-btn');
    if (geoBtn) {
        geoBtn.addEventListener('click', () => {
            if ('geolocation' in navigator) {
                geoBtn.innerText = 'Locating GPS...';
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        const latInput = document.getElementById('sos-latitude');
                        const lonInput = document.getElementById('sos-longitude');
                        if (latInput) latInput.value = pos.coords.latitude.toFixed(6);
                        if (lonInput) lonInput.value = pos.coords.longitude.toFixed(6);
                        geoBtn.innerText = 'GPS Acquired';
                        showToast('Location coordinates captured successfully', 'success');
                    },
                    (err) => {
                        geoBtn.innerText = 'Use Current Location';
                        showToast('GPS permission denied or unavailable. You can enter City/State manually.', 'info');
                    }
                );
            } else {
                showToast('Geolocation not supported by your browser', 'error');
            }
        });
    }

    const form = document.getElementById('sos-request-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('sos-submit-btn');
            submitBtn.disabled = true;
            submitBtn.innerText = 'Broadcasting SOS...';

            const payload = {
                blood_group: document.getElementById('sos-blood-group').value,
                units_required: parseInt(document.getElementById('sos-units').value),
                urgency: document.getElementById('sos-urgency').value,
                hospital_name: document.getElementById('sos-hospital-name').value,
                hospital_address: document.getElementById('sos-hospital-address').value,
                city: document.getElementById('sos-city').value,
                state: document.getElementById('sos-state').value,
                description: document.getElementById('sos-description').value,
                recipient_name: document.getElementById('sos-recipient-name').value,
                preferred_contact_method: document.getElementById('sos-contact-method').value
            };

            const lat = document.getElementById('sos-latitude').value;
            const lon = document.getElementById('sos-longitude').value;
            if (lat && lon) {
                payload.latitude = parseFloat(lat);
                payload.longitude = parseFloat(lon);
            }

            try {
                const res = await ApiClient.post('/requests', payload);
                showToast(`🚨 SOS Broadcasted! Notified ${res.matched_donors_count} compatible donors!`, 'success');
                closeSosModal();
                form.reset();
                loadPatientRequests();
            } catch (err) {
                showToast(err.message, 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerText = 'Broadcast Emergency SOS';
            }
        });
    }
}

function openSosModal() {
    const modal = document.getElementById('sos-modal');
    if (modal) modal.classList.add('show');
}

function closeSosModal() {
    const modal = document.getElementById('sos-modal');
    if (modal) modal.classList.remove('show');
}

async function viewRequestDetails(requestId) {
    try {
        const req = await ApiClient.get(`/requests/${requestId}`);
        const modal = document.getElementById('details-modal');
        const content = document.getElementById('details-modal-content');

        content.innerHTML = `
            <div style="margin-bottom: 1.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span class="badge badge-${req.urgency}">${req.urgency.toUpperCase()} URGENCY</span>
                    <span class="badge ${getStatusBadgeClass(req.status)}">${formatStatus(req.status)}</span>
                </div>
                <h3 style="font-size: 1.4rem; font-weight: 800; color: var(--text-primary); margin-bottom: 0.3rem;">
                    ${req.hospital_name}
                </h3>
                <p style="color: var(--text-muted); font-size: 0.9rem;">${req.hospital_address}, ${req.city}, ${req.state}</p>
            </div>

            <!-- Stepper Progress Tracker -->
            <div class="request-tracker">
                <div class="step-node ${['submitted', 'searching', 'responses_received', 'assistance_arranged', 'fulfilled'].includes(req.status) ? 'completed' : ''}">
                    <div class="step-circle">1</div>
                    <div class="step-label">Submitted</div>
                </div>
                <div class="step-node ${['searching', 'responses_received', 'assistance_arranged', 'fulfilled'].includes(req.status) ? 'completed' : (req.status === 'searching' ? 'active' : '')}">
                    <div class="step-circle">2</div>
                    <div class="step-label">Searching Donors</div>
                </div>
                <div class="step-node ${['responses_received', 'assistance_arranged', 'fulfilled'].includes(req.status) ? 'completed' : (req.status === 'responses_received' ? 'active' : '')}">
                    <div class="step-circle">3</div>
                    <div class="step-label">Donor Responses</div>
                </div>
                <div class="step-node ${req.status === 'fulfilled' ? 'completed' : ''}">
                    <div class="step-circle">4</div>
                    <div class="step-label">Fulfilled</div>
                </div>
            </div>

            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 1.25rem; margin-bottom: 1.5rem;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-size: 0.9rem;">
                    <div><span style="color: var(--text-muted);">Required Blood Group:</span> <span class="blood-pill" style="margin-left: 0.4rem;">${req.blood_group}</span></div>
                    <div><span style="color: var(--text-muted);">Units Needed:</span> <strong>${req.units_required} unit(s)</strong></div>
                    <div><span style="color: var(--text-muted);">Recipient:</span> <strong>${req.recipient_name || 'Patient'}</strong></div>
                    <div><span style="color: var(--text-muted);">Donors Responded:</span> <strong style="color: var(--accent-emerald);">${req.accepted_donors_count} Accepted</strong></div>
                </div>
                ${req.description ? `<p style="margin-top: 1rem; color: var(--text-secondary); font-size: 0.88rem; border-top: 1px solid var(--border-subtle); padding-top: 0.75rem;">${req.description}</p>` : ''}
            </div>

            <div style="display: flex; gap: 0.75rem; justify-content: flex-end; flex-wrap: wrap;">
                ${req.status !== 'fulfilled' && req.status !== 'cancelled' ? `
                    <button class="btn btn-outline-red btn-sm" onclick="cancelPatientRequest('${req.id}')">Cancel Request</button>
                    <button class="btn btn-cyan btn-sm" onclick="markRequestFulfilled('${req.id}')">Mark as Fulfilled</button>
                ` : ''}
                <a href="/map.html?lat=${req.latitude || ''}&lon=${req.longitude || ''}&blood=${req.blood_group}" class="btn btn-primary btn-sm">Find on Live Map</a>
            </div>
        `;

        modal.classList.add('show');
    } catch (err) {
        showToast('Failed to load details: ' + err.message, 'error');
    }
}

function closeDetailsModal() {
    const modal = document.getElementById('details-modal');
    if (modal) modal.classList.remove('show');
}

async function cancelPatientRequest(requestId) {
    if (!confirm('Are you sure you want to cancel this emergency blood request?')) return;
    try {
        await ApiClient.post(`/requests/${requestId}/cancel`, {});
        showToast('Request cancelled successfully', 'info');
        closeDetailsModal();
        loadPatientRequests();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function markRequestFulfilled(requestId) {
    if (!confirm('Has the blood requirement been completely satisfied?')) return;
    try {
        await ApiClient.patch(`/requests/${requestId}/status`, { status: 'fulfilled' });
        showToast('Request marked as fulfilled. Thank you!', 'success');
        closeDetailsModal();
        loadPatientRequests();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

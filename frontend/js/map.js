/**
 * Leaflet.js Map Controller for Blood SOS
 */

let mapInstance = null;
let donorMarkersLayer = null;
let requestMarkersLayer = null;
let currentCenter = { lat: 30.2672, lon: -97.7431 }; // Default Austin, TX

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupMapControls();
});

function initMap() {
    const mapElement = document.getElementById('map-view');
    if (!mapElement) return;

    // Check URL params for focus
    const urlParams = new URLSearchParams(window.location.search);
    const pLat = parseFloat(urlParams.get('lat'));
    const pLon = parseFloat(urlParams.get('lon'));
    if (!isNaN(pLat) && !isNaN(pLon)) {
        currentCenter = { lat: pLat, lon: pLon };
    }

    mapInstance = L.map('map-view').setView([currentCenter.lat, currentCenter.lon], 12);

    // Official OpenStreetMap tile layer
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(mapInstance);

    donorMarkersLayer = L.layerGroup().addTo(mapInstance);
    requestMarkersLayer = L.layerGroup().addTo(mapInstance);

    // Initial load
    fetchMapData();
}

async function fetchMapData() {
    if (!mapInstance) return;

    const bloodGroupFilter = document.getElementById('map-blood-filter')?.value || '';
    const radiusFilter = parseFloat(document.getElementById('map-radius-slider')?.value || '35');

    // Run donors and requests fetches in parallel
    try {
        const [donors, requests] = await Promise.all([
            ApiClient.get('/donors/nearby', {
                lat: currentCenter.lat,
                lon: currentCenter.lon,
                compatible_for: bloodGroupFilter,
                radius_km: radiusFilter
            }).catch(e => {
                console.error('Error fetching nearby donors:', e);
                return [];
            }),
            ApiClient.get('/requests').catch(e => {
                console.error('Error fetching requests for map:', e);
                return [];
            })
        ]);

        donorMarkersLayer.clearLayers();
        requestMarkersLayer.clearLayers();

        // 1. Render Donors
        const donorCountEl = document.getElementById('map-donor-count');
        if (donorCountEl) donorCountEl.innerText = `${donors.length} Donors Found`;

        donors.forEach(donor => {
            if (!donor.latitude || !donor.longitude) return;

            // Donor Marker (Cyan/Emerald Drop)
            const icon = L.divIcon({
                className: 'custom-donor-pin',
                html: `
                    <div style="background: rgba(6, 182, 212, 0.9); border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 10px; color: black; box-shadow: 0 0 12px rgba(6, 182, 212, 0.8);">
                        ${donor.blood_group}
                    </div>
                `,
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });

            const marker = L.marker([donor.latitude, donor.longitude], { icon });
            marker.bindPopup(`
                <div style="color: #070b14; min-width: 180px;">
                    <div style="font-size: 1.1rem; font-weight: 800; color: #0284c7; margin-bottom: 0.2rem;">
                        ${donor.blood_group} Donor
                    </div>
                    <div style="font-size: 0.85rem; font-weight: 600;">${donor.full_name}</div>
                    <div style="font-size: 0.78rem; color: #475569;">${donor.city}, ${donor.state}</div>
                    <div style="font-size: 0.8rem; margin-top: 0.4rem;">
                        <strong>Distance:</strong> ${donor.distance_km || '~'} km away
                    </div>
                    <div style="font-size: 0.75rem; color: #16a34a; font-weight: 700; margin-top: 0.2rem;">
                        ● Available to Donate
                    </div>
                </div>
            `);
            donorMarkersLayer.addLayer(marker);
        });

        // 2. Render Active Requests
        requests.forEach(req => {
            if (!req.latitude || !req.longitude) return;
            if (req.status === 'fulfilled' || req.status === 'cancelled') return;

            // Red Emergency Marker
            const reqIcon = L.divIcon({
                className: 'custom-request-pin',
                html: `
                    <div style="background: #ef4444; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 11px; color: white; box-shadow: 0 0 16px rgba(239, 68, 68, 0.9);">
                        SOS
                    </div>
                `,
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            });

            const marker = L.marker([req.latitude, req.longitude], { icon: reqIcon });
            marker.bindPopup(`
                <div style="color: #070b14; min-width: 220px;">
                    <span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">
                        ${req.urgency} SOS
                    </span>
                    <h4 style="font-size: 1.05rem; font-weight: 800; margin: 0.4rem 0 0.1rem; color: #991b1b;">
                        ${req.hospital_name}
                    </h4>
                    <div style="font-size: 0.8rem; color: #475569;">${req.hospital_address}, ${req.city}</div>
                    <div style="margin: 0.5rem 0; font-size: 0.85rem;">
                        <strong>Blood Group:</strong> <span style="color: #ef4444; font-weight: 800;">${req.blood_group}</span> (${req.units_required} units)
                    </div>
                    <a href="https://www.google.com/maps/dir/?api=1&destination=${req.latitude},${req.longitude}" target="_blank" rel="noopener noreferrer" style="display: block; text-align: center; background: #0284c7; color: white; padding: 0.4rem 0.8rem; border-radius: 4px; text-decoration: none; font-size: 0.8rem; font-weight: 600; margin-top: 0.6rem;">
                        Get Directions 📍
                    </a>
                </div>
            `);
            requestMarkersLayer.addLayer(marker);
        });
    } catch (e) {
        console.error('Error fetching map data:', e);
    }
}

function setupMapControls() {
    const locateBtn = document.getElementById('map-locate-btn');
    if (locateBtn) {
        locateBtn.addEventListener('click', () => {
            if ('geolocation' in navigator) {
                locateBtn.innerText = 'Locating...';
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        currentCenter = {
                            lat: pos.coords.latitude,
                            lon: pos.coords.longitude
                        };
                        mapInstance.setView([currentCenter.lat, currentCenter.lon], 13);
                        locateBtn.innerText = '📍 My Location';
                        fetchMapData();
                        showToast('Map centered to your current position', 'info');
                    },
                    (err) => {
                        locateBtn.innerText = '📍 Center Location';
                        showToast('GPS permission denied or unavailable.', 'error');
                    }
                );
            }
        });
    }

    const bloodFilter = document.getElementById('map-blood-filter');
    if (bloodFilter) {
        bloodFilter.addEventListener('change', fetchMapData);
    }

    const radiusSlider = document.getElementById('map-radius-slider');
    const radiusDisplay = document.getElementById('map-radius-display');
    let sliderDebounceTimer = null;
    if (radiusSlider && radiusDisplay) {
        radiusSlider.addEventListener('input', (e) => {
            radiusDisplay.innerText = `${e.target.value} km`;
            clearTimeout(sliderDebounceTimer);
            sliderDebounceTimer = setTimeout(() => {
                fetchMapData();
            }, 200);
        });
    }

    // OpenStreetMap Location Search (Nominatim)
    const searchBtn = document.getElementById('map-search-btn');
    const searchInput = document.getElementById('map-search-input');

    const handleSearch = async () => {
        const query = searchInput?.value?.trim();
        if (!query) return;

        searchBtn.disabled = true;
        searchBtn.innerText = 'Searching...';

        try {
            const resp = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
            const data = await resp.json();

            if (data && data.length > 0) {
                const first = data[0];
                currentCenter = {
                    lat: parseFloat(first.lat),
                    lon: parseFloat(first.lon)
                };
                mapInstance.setView([currentCenter.lat, currentCenter.lon], 13);
                fetchMapData();
                showToast(`Jumped to: ${first.display_name.split(',')[0]}`, 'success');
            } else {
                showToast('Location not found on OpenStreetMap.', 'warning');
            }
        } catch (err) {
            console.error('OSM Geocoding error:', err);
            showToast('Unable to search location at this moment.', 'error');
        } finally {
            searchBtn.disabled = false;
            searchBtn.innerText = 'Search';
        }
    };

    if (searchBtn) {
        searchBtn.addEventListener('click', handleSearch);
    }
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSearch();
            }
        });
    }
}


/**
 * System Control API Client
 * 
 * Provides functions for system lifecycle control endpoints.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Get current system state
 * @returns {Promise<{state: string, message: string, started_at: string|null, fault_type: string|null}>}
 */
export async function getSystemState() {
    const response = await fetch(`${API_BASE}/system/state`);
    if (!response.ok) {
        throw new Error('Failed to get system state');
    }
    return response.json();
}

/**
 * Start system calibration
 * @param {string} assetId - Asset to calibrate
 * @returns {Promise<{status: string, message: string, state: string}>}
 */
export async function calibrateSystem(assetId = 'Motor-01') {
    const response = await fetch(`${API_BASE}/system/calibrate?asset_id=${assetId}`, {
        method: 'POST',
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Calibration failed');
    }
    return response.json();
}

/**
 * Start fault injection
 * @param {string} assetId - Asset to inject fault
 * @param {string} faultType - Type of fault (SPIKE, DRIFT, DEFAULT)
 * @returns {Promise<{status: string, message: string, state: string}>}
 */
export async function injectFault(assetId = 'Motor-01', faultType = 'DEFAULT') {
    const response = await fetch(
        `${API_BASE}/system/inject-fault?asset_id=${assetId}&fault_type=${faultType}`,
        { method: 'POST' }
    );
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Fault injection failed');
    }
    return response.json();
}

/**
 * Reset system to healthy monitoring
 * @param {string} assetId - Asset to reset
 * @returns {Promise<{status: string, message: string, state: string}>}
 */
export async function resetSystem(assetId = 'Motor-01') {
    const response = await fetch(`${API_BASE}/system/reset?asset_id=${assetId}`, {
        method: 'POST',
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Reset failed');
    }
    return response.json();
}

/**
 * Stop session and return to IDLE state
 * @returns {Promise<{status: string, message: string, state: string}>}
 */
export async function stopSession() {
    const response = await fetch(`${API_BASE}/system/stop`, {
        method: 'POST',
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Stop failed');
    }
    return response.json();
}

/**
 * API Client - Backend Communication
 * 
 * Frontend is a PURE RENDERER - it does NOT calculate scores.
 * All data comes from the backend.
 */

// API base URL - can be overridden via environment
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Fetch current health status for an asset
 */
export async function fetchHealthStatus(assetId = 'Motor-01') {
    try {
        const response = await fetch(`${API_BASE}/api/v1/status/${assetId}`)
        if (!response.ok) {
            if (response.status === 404) {
                return null // No data yet
            }
            throw new Error(`API Error: ${response.status}`)
        }
        return response.json()
    } catch (error) {
        console.warn('Failed to fetch health status:', error.message)
        return null
    }
}

/**
 * Fetch sensor data history for charting
 */
export async function fetchDataHistory(assetId = 'Motor-01', limit = 100) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/data/history/${assetId}?limit=${limit}`)
        if (!response.ok) {
            return { data: [], count: 0 }
        }
        return response.json()
    } catch (error) {
        console.warn('Failed to fetch data history:', error.message)
        return { data: [], count: 0 }
    }
}

/**
 * Trigger baseline building
 */
export async function buildBaseline(assetId = 'Motor-01') {
    const response = await fetch(`${API_BASE}/api/v1/baseline/build?asset_id=${assetId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to build baseline')
    }
    return response.json()
}

/**
 * Get report download URL
 */
export function getReportUrl(assetId = 'Motor-01', format = 'pdf') {
    return `${API_BASE}/api/v1/report/${assetId}?format=${format}`
}

/**
 * Check API health
 */
export async function checkApiHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`)
        return response.ok
    } catch {
        return false
    }
}

export default {
    fetchHealthStatus,
    fetchDataHistory,
    buildBaseline,
    getReportUrl,
    checkApiHealth,
    API_BASE
}

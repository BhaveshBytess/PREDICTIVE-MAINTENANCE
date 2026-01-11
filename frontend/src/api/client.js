/**
 * API Client - Wrapper for backend communication
 * Frontend is a PURE RENDERER - it does NOT calculate scores
 */

const API_BASE = '/api'

/**
 * Fetch dashboard data from backend
 */
export async function fetchDashboardData() {
    const response = await fetch(`${API_BASE}/dashboard`)
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`)
    }
    return response.json()
}

/**
 * Fetch health report for an asset
 */
export async function fetchHealthReport(assetId) {
    const response = await fetch(`${API_BASE}/health/${assetId}`)
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`)
    }
    return response.json()
}

/**
 * Fetch recent sensor events for chart
 */
export async function fetchRecentEvents(assetId, limit = 60) {
    const response = await fetch(`${API_BASE}/events/${assetId}?limit=${limit}`)
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`)
    }
    return response.json()
}

export default {
    fetchDashboardData,
    fetchHealthReport,
    fetchRecentEvents
}

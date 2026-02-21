/**
 * API Client - Backend Communication
 * 
 * Frontend is a PURE RENDERER - it does NOT calculate scores.
 * All data comes from the backend.
 */

import { API_URL } from '../config'

// API base URL from centralized config
const API_BASE = API_URL

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
            return { sensor_data: [], events: [], count: 0 }
        }
        return response.json()
    } catch (error) {
        console.warn('Failed to fetch data history:', error.message)
        return { sensor_data: [], events: [], count: 0 }
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
 * Check API health - uses root endpoint instead of /health to avoid InfluxDB dependency
 */
export async function checkApiHealth() {
    try {
        const response = await fetch(`${API_BASE}/`)
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

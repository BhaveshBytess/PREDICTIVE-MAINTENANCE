import { useState, useEffect } from 'react'
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceArea,
    ReferenceLine
} from 'recharts'
import styles from './SignalChart.module.css'
import { API_URL } from '../../config'

// Generate mock data for demo - using real ISO timestamps (no synthetic Date.now())
// NOTE: This is only used when no real data is available
const generateMockData = () => {
    const data = []
    // Use a fixed base time for demo consistency
    const baseTime = new Date('2026-02-15T12:00:00Z')

    for (let i = 60; i >= 0; i--) {
        const timestamp = new Date(baseTime.getTime() - i * 60000).toISOString()
        const baseValue = 15 + Math.sin(i / 5) * 3
        const noise = (Math.random() - 0.5) * 2
        const value = baseValue + noise

        // Add anomaly spike at certain points
        const is_anomaly = i === 25 || i === 40

        data.push({
            timestamp: timestamp, // ISO string - matches backend format
            value: is_anomaly ? value + 8 : value,
            is_anomaly: is_anomaly
        })
    }

    return data
}

/**
 * Calculate anomaly regions by coalescing consecutive anomaly points.
 * Now uses Unix timestamps for proper time-based rendering.
 * 
 * @param {Array} data - Chart data with { timestamp, value, anomaly } objects
 * @returns {Array} Regions with { x1, x2 } timestamps for ReferenceArea
 */
function calculateAnomalyRegions(data) {
    const regions = []
    let regionStart = null

    for (let i = 0; i < data.length; i++) {
        const point = data[i]

        if (point.anomaly) {
            // Start a new region if not already in one
            if (regionStart === null) {
                regionStart = point.timestamp
            }
        } else {
            // End the current region if we were in one
            if (regionStart !== null) {
                const prevPoint = data[i - 1]
                regions.push({
                    x1: regionStart,
                    x2: prevPoint.timestamp
                })
                regionStart = null
            }
        }
    }

    // Handle case where anomaly extends to end of data
    if (regionStart !== null) {
        const lastPoint = data[data.length - 1]
        regions.push({
            x1: regionStart,
            x2: lastPoint.timestamp
        })
    }

    return regions
}

/**
 * Severity color mapping for maintenance log markers
 */
const severityColors = {
    CRITICAL: '#ef4444',  // Red
    HIGH: '#f97316',      // Orange  
    MEDIUM: '#eab308',    // Yellow
    LOW: '#22c55e'        // Green
}

/**
 * Custom tooltip for maintenance log markers
 */
const MaintenanceTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    
    const data = payload[0]?.payload
    if (!data?.maintenanceLog) return null
    
    const log = data.maintenanceLog
    const color = severityColors[log.severity] || '#6b7280'
    
    return (
        <div className={styles.maintenanceTooltip}>
            <div className={styles.tooltipHeader} style={{ borderLeftColor: color }}>
                <span className={styles.tooltipIcon}>🔧</span>
                <span className={styles.tooltipType}>
                    {log.event_type.replace(/_/g, ' ')}
                </span>
            </div>
            <div className={styles.tooltipBody}>
                <p className={styles.tooltipDescription}>{log.description}</p>
                <div className={styles.tooltipMeta}>
                    <span className={styles.tooltipSeverity} style={{ color }}>
                        {log.severity}
                    </span>
                    <span className={styles.tooltipTime}>
                        {new Date(log.timestamp).toLocaleString()}
                    </span>
                </div>
            </div>
        </div>
    )
}

// PHASE 1A: anomalyIndices prop is DEPRECATED - anomalies are now per-point via is_anomaly field
function SignalChart({ data, anomalyIndices = [], title, refreshTrigger = 0, selectedTimestamp = null }) {
    const [maintenanceLogs, setMaintenanceLogs] = useState([])
    const [logsLoading, setLogsLoading] = useState(false)

    // Fetch maintenance logs on mount and when refreshTrigger changes
    useEffect(() => {
        async function fetchMaintenanceLogs() {
            try {
                setLogsLoading(true)
                const response = await fetch(`${API_URL}/api/logs?hours=24&limit=20`)
                
                if (!response.ok) {
                    console.warn('Failed to fetch maintenance logs:', response.status)
                    return
                }
                
                const result = await response.json()
                setMaintenanceLogs(result.logs || [])
                console.log(`📋 Loaded ${result.count} maintenance logs for chart overlay`)
            } catch (error) {
                console.warn('Error fetching maintenance logs:', error)
            } finally {
                setLogsLoading(false)
            }
        }
        
        fetchMaintenanceLogs()
        
        // Refresh logs every 60 seconds
        const interval = setInterval(fetchMaintenanceLogs, 60000)
        return () => clearInterval(interval)
    }, [refreshTrigger]) // Re-fetch when refreshTrigger changes

    // PHASE 1C: No mock data fallback - chart stays empty until real data arrives
    const chartData = data?.length > 0 ? data : []

    // PHASE 1A: Convert ISO timestamp strings to milliseconds ONCE
    // NO synthetic time generation - use REAL timestamps only
    const dataWithTimestamps = chartData.map((d) => {
        // Convert ISO string timestamp to Unix milliseconds
        const timestampMs = new Date(d.timestamp).getTime()
        
        // Validate timestamp - must be a valid number
        if (isNaN(timestampMs)) {
            console.warn('Invalid timestamp in data point:', d.timestamp)
        }
        
        return {
            ...d,
            timestamp: timestampMs,  // Numeric for Recharts X-axis
            anomaly: d.is_anomaly ?? false  // Use per-point anomaly flag
        }
    })

    /* ── Directive A: Fixed 60s sliding window (right-anchored) ── */
    const now = Date.now()
    const windowStart = now - 60000

    // Only render data within the visible 60s window
    const visibleData = dataWithTimestamps.filter(
        d => d.timestamp >= windowStart && d.timestamp <= now
    )

    /* ── Directive B: Need ≥ 2 points to draw a line segment ── */
    const hasEnoughPoints = visibleData.length >= 2

    // Calculate coalesced anomaly regions from visible data
    const anomalyRegions = calculateAnomalyRegions(visibleData)

    // Maintenance markers within visible 60s window
    const maintenanceMarkers = maintenanceLogs
        .map(log => {
            const logTimestamp = new Date(log.timestamp).getTime()
            if (logTimestamp >= windowStart && logTimestamp <= now) {
                return {
                    ...log,
                    timestamp: logTimestamp,
                    color: severityColors[log.severity] || '#6b7280'
                }
            }
            return null
        })
        .filter(Boolean)

    // Format timestamp for X-axis ticks (HH:mm:ss)
    const formatTimestamp = (ts) => {
        return new Date(ts).toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        })
    }

    return (
        <div className={`glass-card ${styles.container}`}>
            <h3 className={styles.title}>{title}</h3>

            <div className={styles.chartWrapper}>
                <ResponsiveContainer width="100%" height={450}>
                    <LineChart data={visibleData} margin={{ top: 20, right: 60, left: 0, bottom: 20 }}>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(255,255,255,0.1)"
                            vertical={false}
                        />

                        {/* Directive A: Fixed 60s sliding window, right-anchored */}
                        <XAxis
                            dataKey="timestamp"
                            type="number"
                            domain={[windowStart, now]}
                            scale="time"
                            tickFormatter={formatTimestamp}
                            stroke="#6b7280"
                            tick={{ fill: '#9ca3af', fontSize: 10 }}
                            tickLine={false}
                            interval="preserveStartEnd"
                            animationDuration={0}
                            allowDataOverflow
                        />

                        {/* Directive C: Fixed Y-axis domains */}
                        <YAxis
                            yAxisId="voltage"
                            orientation="left"
                            domain={[0, 300]}
                            stroke="#3b82f6"
                            tick={{ fill: '#3b82f6', fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            label={{ value: 'V', position: 'insideTopLeft', fill: '#3b82f6', fontSize: 11, offset: 10 }}
                            animationDuration={0}
                        />
                        <YAxis
                            yAxisId="vibration"
                            orientation="right"
                            domain={[0, 2]}
                            stroke="#10b981"
                            tick={{ fill: '#10b981', fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            label={{ value: 'g', position: 'insideTopRight', fill: '#10b981', fontSize: 11, offset: 10 }}
                            animationDuration={0}
                        />
                        <YAxis yAxisId="current" domain={[0, 40]} hide animationDuration={0} />

                        <Tooltip
                            contentStyle={{
                                background: 'rgba(17, 24, 39, 0.95)',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '8px',
                                color: '#f9fafb'
                            }}
                            labelStyle={{ color: '#9ca3af' }}
                            labelFormatter={formatTimestamp}
                            formatter={(value, name) => {
                                const units = { voltage: 'V', current: 'A', vibration: 'g' }
                                const labels = { voltage: 'Voltage', current: 'Current', vibration: 'Vibration' }
                                return [`${Number(value).toFixed(2)} ${units[name] || ''}`, labels[name] || name]
                            }}
                        />

                        {/* Anomaly shading */}
                        {anomalyRegions.map((region, idx) => (
                            <ReferenceArea
                                key={`anomaly-region-${idx}`}
                                yAxisId="voltage"
                                x1={region.x1}
                                x2={region.x2}
                                fill="#ef4444"
                                fillOpacity={0.2}
                                stroke="#ef4444"
                                strokeOpacity={0.5}
                                strokeWidth={1}
                                isAnimationActive={false}
                            />
                        ))}

                        {/* Maintenance markers */}
                        {maintenanceMarkers.map((marker, idx) => (
                            <ReferenceLine
                                key={`maintenance-${marker.event_id || idx}`}
                                yAxisId="voltage"
                                x={marker.timestamp}
                                stroke={marker.color}
                                strokeWidth={2}
                                strokeDasharray="4 4"
                                isAnimationActive={false}
                                label={{
                                    value: '🔧',
                                    position: 'top',
                                    fill: marker.color,
                                    fontSize: 16
                                }}
                            />
                        ))}

                        {/* Explainability Link — correlation line from LogWatcher click */}
                        {selectedTimestamp && (
                            <ReferenceLine
                                yAxisId="voltage"
                                x={selectedTimestamp}
                                stroke="#fbbf24"
                                strokeWidth={2}
                                strokeDasharray="6 3"
                                isAnimationActive={false}
                                label={{
                                    value: '📌 Event',
                                    position: 'insideTopRight',
                                    fill: '#fbbf24',
                                    fontSize: 11,
                                    fontWeight: 600
                                }}
                            />
                        )}

                        {/* Directive B: Lines only render with ≥ 2 points; connectNulls=false */}
                        {hasEnoughPoints && (
                            <>
                                <Line
                                    yAxisId="voltage"
                                    type="monotone"
                                    dataKey="voltage"
                                    name="voltage"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    dot={false}
                                    connectNulls={false}
                                    isAnimationActive={false}
                                    activeDot={{ r: 5, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }}
                                />
                                <Line
                                    yAxisId="current"
                                    type="monotone"
                                    dataKey="current"
                                    name="current"
                                    stroke="#f59e0b"
                                    strokeWidth={2}
                                    dot={false}
                                    connectNulls={false}
                                    isAnimationActive={false}
                                    activeDot={{ r: 5, fill: '#f59e0b', stroke: '#fff', strokeWidth: 2 }}
                                />
                                <Line
                                    yAxisId="vibration"
                                    type="monotone"
                                    dataKey="vibration"
                                    name="vibration"
                                    stroke="#10b981"
                                    strokeWidth={2}
                                    dot={false}
                                    connectNulls={false}
                                    isAnimationActive={false}
                                    activeDot={{ r: 5, fill: '#10b981', stroke: '#fff', strokeWidth: 2 }}
                                />
                            </>
                        )}
                    </LineChart>
                </ResponsiveContainer>
            </div>

            <div className={styles.legend}>
                <div className={styles.legendItem}>
                    <span className={styles.legendLine} style={{ background: '#3b82f6' }}></span>
                    <span>Voltage (V)</span>
                </div>
                <div className={styles.legendItem}>
                    <span className={styles.legendLine} style={{ background: '#f59e0b' }}></span>
                    <span>Current (A)</span>
                </div>
                <div className={styles.legendItem}>
                    <span className={styles.legendLine} style={{ background: '#10b981' }}></span>
                    <span>Vibration (g)</span>
                </div>
                <div className={styles.legendItem}>
                    <span className={styles.legendAnomaly}></span>
                    <span>Anomaly Region</span>
                </div>
                <div className={styles.legendItem}>
                    <span className={styles.legendMaintenance}>🔧</span>
                    <span>Maintenance ({maintenanceMarkers.length})</span>
                </div>
                {selectedTimestamp && (
                    <div className={styles.legendItem}>
                        <span className={styles.legendCorrelation}></span>
                        <span>Selected Event</span>
                    </div>
                )}
            </div>

            {/* Maintenance logs list below chart */}
            {maintenanceLogs.length > 0 && (
                <div className={styles.maintenanceList}>
                    <h4 className={styles.maintenanceListTitle}>Recent Maintenance Events</h4>
                    <div className={styles.maintenanceItems}>
                        {[...maintenanceLogs].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).map((log, idx) => (
                            <div 
                                key={idx} 
                                className={styles.maintenanceItem}
                                style={{ borderLeftColor: severityColors[log.severity] }}
                            >
                                <span className={styles.maintenanceType}>
                                    {log.event_type.replace(/_/g, ' ')}
                                </span>
                                <span className={styles.maintenanceTime}>
                                    {new Date(log.timestamp).toLocaleString()}
                                </span>
                                <span className={styles.maintenanceDesc}>
                                    {log.description.slice(0, 60)}{log.description.length > 60 ? '...' : ''}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default SignalChart

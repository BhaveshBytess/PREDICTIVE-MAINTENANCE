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

// Generate mock data for demo
const generateMockData = () => {
    const data = []
    const now = new Date()

    for (let i = 60; i >= 0; i--) {
        const time = new Date(now - i * 60000)
        const baseValue = 15 + Math.sin(i / 5) * 3
        const noise = (Math.random() - 0.5) * 2
        const value = baseValue + noise

        // Add anomaly spike at certain points
        const hasAnomaly = i === 25 || i === 40

        data.push({
            time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
            fullTime: time,
            value: hasAnomaly ? value + 8 : value,
            anomaly: hasAnomaly
        })
    }

    return data
}

/**
 * Calculate anomaly regions by coalescing consecutive anomaly points.
 * 
 * @param {Array} data - Chart data with { time, value, anomaly } objects
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
                regionStart = point.time
            }
        } else {
            // End the current region if we were in one
            if (regionStart !== null) {
                const prevPoint = data[i - 1]
                regions.push({
                    x1: regionStart,
                    x2: prevPoint.time
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
            x2: lastPoint.time
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

function SignalChart({ data, anomalyIndices = [], title, refreshTrigger = 0 }) {
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

    // Use mock data if no real data provided
    const chartData = data?.length > 0 ? data : generateMockData()

    // Mark anomaly points based on indices passed from parent
    const dataWithAnomalies = chartData.map((d, i) => ({
        ...d,
        anomaly: anomalyIndices.includes(i) || d.anomaly
    }))

    // Calculate coalesced anomaly regions for shaded areas
    const anomalyRegions = calculateAnomalyRegions(dataWithAnomalies)

    // Find chart Y-axis max for positioning maintenance markers
    const yMax = Math.max(...dataWithAnomalies.map(d => d.value)) * 1.1

    // Build a time-indexed map from chart data for efficient lookup
    // We need to match maintenance logs to their correct position on the scrolling chart
    const chartTimeMap = new Map()
    dataWithAnomalies.forEach((point, idx) => {
        chartTimeMap.set(point.time, { point, idx })
    })
    
    // Match maintenance logs to chart data points
    // A log is "on chart" if its timestamp matches a visible data point
    const maintenanceMarkers = maintenanceLogs
        .map(log => {
            const logTime = new Date(log.timestamp)
            // Format to match chart's time format (same as data points)
            const logTimeStr = logTime.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit',
                second: '2-digit'  // Match the chart's time format with seconds
            })
            
            // Also try without seconds for backward compatibility
            const logTimeStrNoSec = logTime.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit'
            })
            
            // Check for exact match first (with seconds)
            if (chartTimeMap.has(logTimeStr)) {
                return {
                    ...log,
                    displayTime: logTimeStr,
                    color: severityColors[log.severity] || '#6b7280',
                    chartIndex: chartTimeMap.get(logTimeStr).idx
                }
            }
            
            // Try without seconds
            if (chartTimeMap.has(logTimeStrNoSec)) {
                return {
                    ...log,
                    displayTime: logTimeStrNoSec,
                    color: severityColors[log.severity] || '#6b7280',
                    chartIndex: chartTimeMap.get(logTimeStrNoSec).idx
                }
            }
            
            // Find closest time point within 2 minutes
            const logMs = logTime.getTime()
            let closestMatch = null
            let closestDiff = Infinity
            
            dataWithAnomalies.forEach((point, idx) => {
                // Parse the chart time back to a Date for comparison
                // The chart data should have a fullTime or we parse from time string
                let pointMs
                if (point.fullTime) {
                    pointMs = new Date(point.fullTime).getTime()
                } else {
                    // Approximate: assume today's date with the time string
                    const today = new Date()
                    const timeMatch = point.time.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)/i)
                    if (timeMatch) {
                        let hours = parseInt(timeMatch[1])
                        const mins = parseInt(timeMatch[2])
                        const secs = parseInt(timeMatch[3]) || 0
                        const ampm = timeMatch[4].toUpperCase()
                        
                        if (ampm === 'PM' && hours !== 12) hours += 12
                        if (ampm === 'AM' && hours === 12) hours = 0
                        
                        const pointDate = new Date(today.getFullYear(), today.getMonth(), today.getDate(), hours, mins, secs)
                        pointMs = pointDate.getTime()
                    }
                }
                
                if (pointMs) {
                    const diff = Math.abs(pointMs - logMs)
                    if (diff < closestDiff && diff <= 2 * 60 * 1000) { // Within 2 minutes
                        closestDiff = diff
                        closestMatch = { point, idx }
                    }
                }
            })
            
            if (closestMatch) {
                return {
                    ...log,
                    displayTime: closestMatch.point.time,
                    color: severityColors[log.severity] || '#6b7280',
                    chartIndex: closestMatch.idx
                }
            }
            
            return null // Log is outside chart's visible time range
        })
        .filter(Boolean) // Remove nulls

    return (
        <div className={`glass-card ${styles.container}`}>
            <h3 className={styles.title}>{title}</h3>

            <div className={styles.chartWrapper}>
                <ResponsiveContainer width="100%" height={350}>
                    <LineChart data={dataWithAnomalies} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                        <defs>
                            <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
                                <stop offset="0%" stopColor="#3b82f6" />
                                <stop offset="100%" stopColor="#8b5cf6" />
                            </linearGradient>
                        </defs>

                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(255,255,255,0.1)"
                            vertical={false}
                        />

                        <XAxis
                            dataKey="time"
                            stroke="#6b7280"
                            tick={{ fill: '#9ca3af', fontSize: 10 }}
                            tickLine={false}
                            interval="preserveStartEnd"
                        />

                        <YAxis
                            stroke="#6b7280"
                            tick={{ fill: '#9ca3af', fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                            domain={['auto', 'auto']}
                        />

                        <Tooltip
                            contentStyle={{
                                background: 'rgba(17, 24, 39, 0.95)',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '8px',
                                color: '#f9fafb'
                            }}
                            labelStyle={{ color: '#9ca3af' }}
                            formatter={(value, name, props) => {
                                const suffix = props.payload?.anomaly ? ' ⚠️ ANOMALY' : ''
                                return [`${value.toFixed(2)}${suffix}`, 'Power (mW)']
                            }}
                        />

                        {/* Shaded red regions for anomaly spans */}
                        {anomalyRegions.map((region, idx) => (
                            <ReferenceArea
                                key={`anomaly-region-${idx}`}
                                x1={region.x1}
                                x2={region.x2}
                                fill="#ef4444"
                                fillOpacity={0.2}
                                stroke="#ef4444"
                                strokeOpacity={0.5}
                                strokeWidth={1}
                            />
                        ))}

                        {/* Maintenance log vertical markers */}
                        {maintenanceMarkers.map((marker, idx) => (
                            <ReferenceLine
                                key={`maintenance-${idx}`}
                                x={marker.displayTime}
                                stroke={marker.color}
                                strokeWidth={2}
                                strokeDasharray="4 4"
                                label={{
                                    value: '🔧',
                                    position: 'top',
                                    fill: marker.color,
                                    fontSize: 16
                                }}
                            />
                        ))}

                        <Line
                            type="monotone"
                            dataKey="value"
                            stroke="url(#lineGradient)"
                            strokeWidth={2}
                            dot={false}
                            activeDot={{
                                r: 6,
                                fill: '#3b82f6',
                                stroke: '#fff',
                                strokeWidth: 2
                            }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>

            <div className={styles.legend}>
                <div className={styles.legendItem}>
                    <span className={styles.legendLine}></span>
                    <span>Power Signature</span>
                </div>
                <div className={styles.legendItem}>
                    <span className={styles.legendAnomaly}></span>
                    <span>Anomaly Region</span>
                </div>
                <div className={styles.legendItem}>
                    <span className={styles.legendMaintenance}>🔧</span>
                    <span>Maintenance Log ({maintenanceMarkers.length} on chart{maintenanceLogs.length > maintenanceMarkers.length ? `, ${maintenanceLogs.length} total` : ''})</span>
                </div>
            </div>

            {/* Maintenance logs list below chart */}
            {maintenanceLogs.length > 0 && (
                <div className={styles.maintenanceList}>
                    <h4 className={styles.maintenanceListTitle}>Recent Maintenance Events</h4>
                    <div className={styles.maintenanceItems}>
                        {maintenanceLogs.slice(0, 5).map((log, idx) => (
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

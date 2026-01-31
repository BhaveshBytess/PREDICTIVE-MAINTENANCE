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

// Generate mock data for demo - now using Unix timestamps for X-axis
const generateMockData = () => {
    const data = []
    const now = Date.now()

    for (let i = 60; i >= 0; i--) {
        const timestamp = now - i * 60000
        const baseValue = 15 + Math.sin(i / 5) * 3
        const noise = (Math.random() - 0.5) * 2
        const value = baseValue + noise

        // Add anomaly spike at certain points
        const hasAnomaly = i === 25 || i === 40

        data.push({
            timestamp: timestamp, // Unix timestamp in ms - used as X-axis
            time: new Date(timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
            value: hasAnomaly ? value + 8 : value,
            anomaly: hasAnomaly
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

    // Ensure all data points have Unix timestamps
    const dataWithTimestamps = chartData.map((d, i) => {
        // If data already has timestamp, use it; otherwise derive from fullTime or time string
        let timestamp = d.timestamp
        if (!timestamp && d.fullTime) {
            timestamp = new Date(d.fullTime).getTime()
        }
        if (!timestamp) {
            // Fallback: use current time minus index offset (for legacy data)
            timestamp = Date.now() - (chartData.length - 1 - i) * 60000
        }
        return {
            ...d,
            timestamp,
            anomaly: anomalyIndices.includes(i) || d.anomaly
        }
    })

    // Calculate coalesced anomaly regions for shaded areas
    const anomalyRegions = calculateAnomalyRegions(dataWithTimestamps)

    // Get chart X-axis domain (timestamp range)
    const chartStartTime = dataWithTimestamps.length > 0 ? dataWithTimestamps[0].timestamp : 0
    const chartEndTime = dataWithTimestamps.length > 0 ? dataWithTimestamps[dataWithTimestamps.length - 1].timestamp : 0
    
    // Pure Time-Based Marker Rendering:
    // Simply check if log timestamp falls within chart's X-axis domain
    // NO dependency on matching sensor data points!
    const maintenanceMarkers = maintenanceLogs
        .map(log => {
            const logTimestamp = new Date(log.timestamp).getTime()
            
            // Check if log falls within chart's visible time range
            if (logTimestamp >= chartStartTime && logTimestamp <= chartEndTime) {
                return {
                    ...log,
                    timestamp: logTimestamp, // Unix timestamp for X position
                    color: severityColors[log.severity] || '#6b7280'
                }
            }
            return null // Log is outside chart's visible time range
        })
        .filter(Boolean) // Remove nulls

    // Format timestamp for X-axis tick display
    const formatTimestamp = (ts) => {
        return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    }

    // Log debug info
    console.log(`📊 Chart domain: ${new Date(chartStartTime).toISOString()} to ${new Date(chartEndTime).toISOString()}`)
    console.log(`📋 Maintenance markers: ${maintenanceMarkers.length} visible out of ${maintenanceLogs.length} total`)

    return (
        <div className={`glass-card ${styles.container}`}>
            <h3 className={styles.title}>{title}</h3>

            <div className={styles.chartWrapper}>
                <ResponsiveContainer width="100%" height={350}>
                    <LineChart data={dataWithTimestamps} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
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
                            dataKey="timestamp"
                            type="number"
                            domain={[chartStartTime, chartEndTime]}
                            scale="time"
                            tickFormatter={formatTimestamp}
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

                        {/* Shaded red regions for anomaly spans - use timestamps */}
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

                        {/* Maintenance log vertical markers - PURE TIME-BASED */}
                        {maintenanceMarkers.map((marker, idx) => (
                            <ReferenceLine
                                key={`maintenance-${marker.event_id || idx}`}
                                x={marker.timestamp}
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

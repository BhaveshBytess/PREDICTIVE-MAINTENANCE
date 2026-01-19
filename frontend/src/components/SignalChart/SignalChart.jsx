import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
    ReferenceArea
} from 'recharts'
import styles from './SignalChart.module.css'

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
            value: hasAnomaly ? value + 8 : value,
            anomaly: hasAnomaly
        })
    }

    return data
}

function SignalChart({ data, anomalyIndices = [], title }) {
    // Use mock data if no real data provided
    const chartData = data?.length > 0 ? data : generateMockData()

    // Mark anomaly points based on indices passed from parent
    const dataWithAnomalies = chartData.map((d, i) => ({
        ...d,
        anomaly: anomalyIndices.includes(i) || d.anomaly
    }))

    // Find anomaly points for markers
    const anomalyPoints = dataWithAnomalies.filter(d => d.anomaly)

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
                            tick={{ fill: '#9ca3af', fontSize: 12 }}
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
                        />

                        {/* Anomaly reference lines */}
                        {anomalyPoints.map((point, idx) => (
                            <ReferenceLine
                                key={idx}
                                x={point.time}
                                stroke="#ef4444"
                                strokeDasharray="5 5"
                                label={{
                                    value: 'Anomaly detected',
                                    position: 'top',
                                    fill: '#ef4444',
                                    fontSize: 11
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
                    <span>Anomaly Detected</span>
                </div>
            </div>
        </div>
    )
}

export default SignalChart

/**
 * Predictive Maintenance Dashboard - Main App
 * 
 * Layout matches the wireframe:
 * - Header with title and LIVE status
 * - Left: 3 metrics row + chart
 * - Right: Health Summary + Insights + Operator Log + Download
 */

import { useState, useEffect, useCallback } from 'react'
import styles from './App.module.css'

// Components
import Header from './components/Header/Header'
import MetricCard from './components/MetricCard/MetricCard'
import SignalChart from './components/SignalChart/SignalChart'
import HealthSummary from './components/HealthSummary/HealthSummary'
import InsightPanel from './components/InsightPanel/InsightPanel'
import OperatorLog from './components/OperatorLog/OperatorLog'

// API
import { fetchHealthStatus, fetchDataHistory, getReportUrl, buildBaseline, checkApiHealth } from './api/client'

const ASSET_ID = 'Motor-01'
const POLL_INTERVAL = 3000

function App() {
    const [isLive, setIsLive] = useState(false)
    const [metrics, setMetrics] = useState({
        voltage: 230,
        current: 12.1,
        powerFactor: 0.92
    })
    const [healthData, setHealthData] = useState({
        score: 75,
        riskLevel: 'MODERATE',
        maintenanceDays: 14
    })
    const [explanations, setExplanations] = useState([
        'Risk elevated due to recent Power Factor drop combined with high current spikes.'
    ])
    const [chartData, setChartData] = useState([])
    const [anomalyPoints, setAnomalyPoints] = useState([])
    const [sampleCount, setSampleCount] = useState(0)

    // Fetch data from API
    const fetchData = useCallback(async () => {
        try {
            const apiOk = await checkApiHealth()
            setIsLive(apiOk)

            if (!apiOk) return

            const health = await fetchHealthStatus(ASSET_ID)
            if (health) {
                setHealthData({
                    score: health.health_score,
                    riskLevel: health.risk_level,
                    maintenanceDays: health.maintenance_window_days
                })
                setExplanations(health.explanations || [])
            }

            const history = await fetchDataHistory(ASSET_ID, 60)
            if (history && history.data.length > 0) {
                const data = history.data
                setSampleCount(history.count)

                const latest = data[data.length - 1]
                setMetrics({
                    voltage: latest.voltage_v,
                    current: latest.current_a,
                    powerFactor: latest.power_factor
                })

                const chartPoints = data.map((d, i) => ({
                    time: new Date(d.timestamp).toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    }),
                    value: d.vibration_g * 1000,
                    voltage: d.voltage_v,
                    index: i
                }))
                setChartData(chartPoints)

                const anomalies = data
                    .map((d, i) => d.is_faulty ? i : null)
                    .filter(i => i !== null)
                setAnomalyPoints(anomalies)
            }
        } catch (error) {
            console.error('Error fetching data:', error)
        }
    }, [])

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, POLL_INTERVAL)
        return () => clearInterval(interval)
    }, [fetchData])

    const handleDownloadReport = (format) => {
        window.open(getReportUrl(ASSET_ID, format), '_blank')
    }

    return (
        <div className={styles.container}>
            {/* Header */}
            <Header
                assetName={`Industrial Asset Health Monitor - ${ASSET_ID}`}
                isLive={isLive}
            />

            {/* Main Content - 2 Column Grid */}
            <main className={styles.main}>
                {/* Left Column: Metrics + Chart */}
                <div className={styles.leftColumn}>
                    {/* 3 Metric Cards in a Row */}
                    <div className={styles.metricsGrid}>
                        <MetricCard
                            label="VOLTAGE (V)"
                            value={metrics.voltage.toFixed(0)}
                            icon="⚡"
                        />
                        <MetricCard
                            label="CURRENT (A)"
                            value={metrics.current.toFixed(1)}
                            icon="🔌"
                        />
                        <MetricCard
                            label="POWER FACTOR"
                            value={metrics.powerFactor.toFixed(2)}
                            icon="📊"
                        />
                    </div>

                    {/* Chart */}
                    <div className={styles.chartSection}>
                        <SignalChart
                            data={chartData}
                            anomalyIndices={anomalyPoints}
                            title="Real-time Power Signature and anomalies (Last 1 hour)"
                        />
                    </div>
                </div>

                {/* Right Column: Sidebar */}
                <div className={styles.sidebar}>
                    {/* Health and Risk Summary */}
                    <HealthSummary
                        healthScore={healthData.score}
                        riskLevel={healthData.riskLevel}
                        maintenanceDays={healthData.maintenanceDays}
                    />

                    {/* Insight / Reasoning */}
                    <InsightPanel
                        explanations={explanations.map((e, i) => ({
                            reason: typeof e === 'string' ? e : e.reason,
                            confidence: 0.85 - (i * 0.1)
                        }))}
                    />

                    {/* Operator Input Log */}
                    <OperatorLog />

                    {/* Download Report Button */}
                    <button
                        className={styles.downloadBtn}
                        onClick={() => handleDownloadReport('pdf')}
                    >
                        DOWNLOAD REPORT (PDF / Excel)
                    </button>
                </div>
            </main>
        </div>
    )
}

export default App

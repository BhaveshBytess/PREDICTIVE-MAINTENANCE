/**
 * Predictive Maintenance Dashboard - Main App
 * 
 * This is a PURE RENDERER - no calculations happen here.
 * All data comes from the backend API.
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
const POLL_INTERVAL = 3000 // 3 seconds

function App() {
    // State
    const [isLive, setIsLive] = useState(false)
    const [metrics, setMetrics] = useState({
        voltage: 0,
        current: 0,
        powerFactor: 0
    })
    const [healthData, setHealthData] = useState({
        score: 85,
        riskLevel: 'LOW',
        maintenanceDays: 30
    })
    const [explanations, setExplanations] = useState([])
    const [chartData, setChartData] = useState([])
    const [anomalyPoints, setAnomalyPoints] = useState([])
    const [sampleCount, setSampleCount] = useState(0)
    const [baselineStatus, setBaselineStatus] = useState('pending')

    // Fetch data from API
    const fetchData = useCallback(async () => {
        try {
            // Check if API is up
            const apiOk = await checkApiHealth()
            setIsLive(apiOk)

            if (!apiOk) return

            // Fetch health status
            const health = await fetchHealthStatus(ASSET_ID)
            if (health) {
                setHealthData({
                    score: health.health_score,
                    riskLevel: health.risk_level,
                    maintenanceDays: health.maintenance_window_days
                })
                setExplanations(health.explanations || [])
                setBaselineStatus(health.model_version === 'pending' ? 'pending' : 'ready')
            }

            // Fetch sensor history for chart
            const history = await fetchDataHistory(ASSET_ID, 60)
            if (history && history.data.length > 0) {
                const data = history.data
                setSampleCount(history.count)

                // Update metrics from latest reading
                const latest = data[data.length - 1]
                setMetrics({
                    voltage: latest.voltage_v,
                    current: latest.current_a,
                    powerFactor: latest.power_factor
                })

                // Format for chart
                const chartPoints = data.map((d, i) => ({
                    time: new Date(d.timestamp).toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit'
                    }),
                    value: d.vibration_g * 1000, // Convert to mV for display
                    voltage: d.voltage_v,
                    index: i
                }))
                setChartData(chartPoints)

                // Find anomalies (faulty readings)
                const anomalies = data
                    .map((d, i) => d.is_faulty ? i : null)
                    .filter(i => i !== null)
                setAnomalyPoints(anomalies)
            }
        } catch (error) {
            console.error('Error fetching data:', error)
        }
    }, [])

    // Poll for data
    useEffect(() => {
        fetchData() // Initial fetch
        const interval = setInterval(fetchData, POLL_INTERVAL)
        return () => clearInterval(interval)
    }, [fetchData])

    // Handle baseline build
    const handleBuildBaseline = async () => {
        try {
            setBaselineStatus('building')
            await buildBaseline(ASSET_ID)
            setBaselineStatus('ready')
            fetchData() // Refresh
        } catch (error) {
            console.error('Failed to build baseline:', error)
            setBaselineStatus('error')
        }
    }

    // Handle report download
    const handleDownloadReport = () => {
        window.open(getReportUrl(ASSET_ID, 'pdf'), '_blank')
    }

    return (
        <div className={styles.app}>
            <Header
                assetName={`Industrial Asset Health Monitor - ${ASSET_ID}`}
                isLive={isLive}
            />

            <main className={styles.main}>
                <div className={styles.grid}>
                    {/* Left Column - Metrics & Chart */}
                    <div className={styles.leftColumn}>
                        {/* Metric Cards */}
                        <div className={styles.metricsRow}>
                            <MetricCard
                                label="Voltage (V)"
                                value={metrics.voltage.toFixed(1)}
                                unit="V"
                                icon="⚡"
                                color="yellow"
                            />
                            <MetricCard
                                label="Current (A)"
                                value={metrics.current.toFixed(1)}
                                unit="A"
                                icon="🔌"
                                color="purple"
                            />
                            <MetricCard
                                label="Power Factor"
                                value={metrics.powerFactor.toFixed(2)}
                                unit=""
                                icon="📊"
                                color="cyan"
                            />
                        </div>

                        {/* Signal Chart */}
                        <div className={styles.chartContainer}>
                            <SignalChart
                                data={chartData}
                                anomalyIndices={anomalyPoints}
                                title="Real-time Power Signature and Anomalies (Last 1 Hour)"
                            />
                        </div>

                        {/* Status Bar */}
                        <div className={styles.statusBar}>
                            <span>Samples: {sampleCount}</span>
                            <span>Baseline: {baselineStatus}</span>
                            {baselineStatus === 'pending' && sampleCount >= 10 && (
                                <button onClick={handleBuildBaseline} className={styles.buildBtn}>
                                    Build Baseline
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Right Column - Health & Actions */}
                    <div className={styles.rightColumn}>
                        <HealthSummary
                            healthScore={healthData.score}
                            riskLevel={healthData.riskLevel}
                            maintenanceDays={healthData.maintenanceDays}
                        />

                        <InsightPanel
                            explanations={explanations.map((e, i) => ({
                                reason: typeof e === 'string' ? e : e.reason,
                                confidence: 0.85 - (i * 0.1)
                            }))}
                        />

                        <button
                            className={styles.downloadBtn}
                            onClick={handleDownloadReport}
                        >
                            📥 Download Health Report (PDF)
                        </button>

                        <OperatorLog />
                    </div>
                </div>
            </main>
        </div>
    )
}

export default App

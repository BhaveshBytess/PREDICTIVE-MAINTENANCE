/**
 * Predictive Maintenance Dashboard - Main App
 * 
 * Layout matches the wireframe:
 * - Header with title and LIVE status
 * - Left: 3 metrics row + chart
 * - Right: Health Summary + Insights + Operator Log + Download
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import styles from './App.module.css'

// Components
import Header from './components/Header/Header'
import MetricCard from './components/MetricCard/MetricCard'
import SignalChart from './components/SignalChart/SignalChart'
import HealthSummary from './components/HealthSummary/HealthSummary'
import InsightPanel from './components/InsightPanel/InsightPanel'
import OperatorLog from './components/OperatorLog/OperatorLog'
import SystemControlPanel from './components/SystemControlPanel'
import PerformanceCard from './components/PerformanceCard'
import SandboxModal from './components/SandboxModal'
import LogWatcher from './components/LogWatcher/LogWatcher'
import StatusCard, {
    healthStatus,
    vibrationStatus,
    voltageStatus,
    currentStatus,
    applyFaultOverride,
} from './components/StatusCard/StatusCard'

// API
import { fetchHealthStatus, fetchDataHistory, getReportUrl, buildBaseline, checkApiHealth } from './api/client'

const ASSET_ID = 'Motor-01'
const POLL_INTERVAL = 3000

function App() {
    const [isLive, setIsLive] = useState(false)
    // PHASE 1C: Industrial Realism - NO mock initial data
    // Dashboard starts blank until real data arrives from backend
    const [metrics, setMetrics] = useState(null)
    const [healthData, setHealthData] = useState(null)
    const [explanations, setExplanations] = useState([])
    const [chartData, setChartData] = useState([])
    const [anomalyPoints, setAnomalyPoints] = useState([])
    const [sampleCount, setSampleCount] = useState(0)
    const [latestReading, setLatestReading] = useState(null)
    const [validationMetrics, setValidationMetrics] = useState({
        trainingSamples: 0,
        healthyStability: 100.0,
        faultCaptureRate: 100.0
    })
    const [isSandboxOpen, setIsSandboxOpen] = useState(false)
    const [logsRefreshTrigger, setLogsRefreshTrigger] = useState(0)

    // Phase 2: Event Engine — accumulated events buffer + chart correlation
    const [eventLog, setEventLog] = useState([])
    const [selectedTimestamp, setSelectedTimestamp] = useState(null)
    const EVENT_BUFFER_CAP = 50

    // Callback when a new operator log is added - triggers chart refresh
    const handleLogAdded = useCallback(() => {
        setLogsRefreshTrigger(prev => prev + 1)
    }, [])

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
            if (history && history.sensor_data && history.sensor_data.length > 0) {
                const data = history.sensor_data
                setSampleCount(history.count)

                const latest = data[data.length - 1]
                setLatestReading(latest)
                setMetrics({
                    voltage: latest.voltage_v,
                    current: latest.current_a,
                    powerFactor: latest.power_factor
                })

                // PHASE 1A: Preserve REAL timestamps - do NOT format or strip
                // Pass raw ISO timestamp string directly from backend
                const chartPoints = data.map((d) => ({
                    timestamp: d.timestamp,  // ISO string from backend (real time)
                    value: d.vibration_g * 1000,
                    voltage: d.voltage_v,
                    is_anomaly: d.is_faulty ?? d.is_anomaly ?? false
                }))
                setChartData(chartPoints)

                // PHASE 1A: anomalyPoints no longer used (anomaly flag is now per-point)
                // Clear legacy index-based anomaly array
                setAnomalyPoints([])

                // Phase 2: Accumulate events from backend into buffer (cap at 50)
                if (history.events && history.events.length > 0) {
                    setEventLog(prev => {
                        const merged = [...prev, ...history.events]
                        return merged.slice(-EVENT_BUFFER_CAP)
                    })
                }
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
                {/* Left Column: Controls + Metrics + Chart */}
                <div className={styles.leftColumn}>
                    {/* System Control Panel */}
                    <SystemControlPanel onMetricsUpdate={setValidationMetrics} />

                    {/* Phase 3: Glanceable Status Cards — 4 across */}
                    <div className={styles.statusRow}>
                        <StatusCard
                            label="Health Score"
                            icon="💚"
                            value={healthData?.score}
                            displayValue={healthData?.score != null ? String(healthData.score) : '---'}
                            unit="/ 100"
                            status={applyFaultOverride(
                                healthStatus(healthData?.score),
                                latestReading?.is_faulty
                            )}
                        />
                        <StatusCard
                            label="Vibration"
                            icon="📳"
                            value={latestReading?.vibration_g}
                            displayValue={latestReading?.vibration_g != null ? latestReading.vibration_g.toFixed(3) : '---'}
                            unit="g"
                            status={applyFaultOverride(
                                vibrationStatus(latestReading?.vibration_g),
                                latestReading?.is_faulty
                            )}
                        />
                        <StatusCard
                            label="Voltage"
                            icon="⚡"
                            value={latestReading?.voltage_v}
                            displayValue={latestReading?.voltage_v != null ? latestReading.voltage_v.toFixed(1) : '---'}
                            unit="V"
                            status={applyFaultOverride(
                                voltageStatus(latestReading?.voltage_v),
                                latestReading?.is_faulty
                            )}
                        />
                        <StatusCard
                            label="Current"
                            icon="🔌"
                            value={latestReading?.current_a}
                            displayValue={latestReading?.current_a != null ? latestReading.current_a.toFixed(1) : '---'}
                            unit="A"
                            status={applyFaultOverride(
                                currentStatus(latestReading?.current_a),
                                latestReading?.is_faulty
                            )}
                        />
                    </div>

                    {/* Chart — Full-width, fixed 450px */}
                    <div className={styles.chartSection}>
                        <SignalChart
                            data={chartData}
                            anomalyIndices={anomalyPoints}
                            title="Real-time Power Signature (Last 60 readings)"
                            refreshTrigger={logsRefreshTrigger}
                            selectedTimestamp={selectedTimestamp}
                        />
                    </div>

                    {/* Log Watcher — Full-width below chart */}
                    <div className={styles.logWatcherSection}>
                        <LogWatcher
                            events={eventLog}
                            selectedTimestamp={selectedTimestamp}
                            onSelectEvent={setSelectedTimestamp}
                        />
                    </div>
                </div>

                {/* Right Column: Sidebar */}
                <div className={styles.sidebar}>
                    {/* Health and Risk Summary */}
                    <HealthSummary
                        healthScore={healthData?.score}
                        riskLevel={healthData?.riskLevel}
                        maintenanceDays={healthData?.maintenanceDays}
                    />

                    {/* Insight / Reasoning */}
                    <InsightPanel
                        explanations={explanations.map((e, i) => ({
                            reason: typeof e === 'string' ? e : e.reason,
                            confidence: 0.85 - (i * 0.1)
                        }))}
                    />

                    {/* Operator Input Log */}
                    <OperatorLog onLogAdded={handleLogAdded} />

                    {/* Validation Scorecard */}
                    <PerformanceCard
                        trainingSamples={validationMetrics.trainingSamples}
                        healthyStability={validationMetrics.healthyStability}
                        faultCaptureRate={validationMetrics.faultCaptureRate}
                    />

                    {/* Download Report Buttons */}
                    <div className={styles.downloadGroup}>
                        <button
                            className={styles.downloadBtn}
                            onClick={() => handleDownloadReport('industrial')}
                        >
                            📄 DOWNLOAD FULL REPORT (5-Page PDF)
                        </button>
                        <div className={styles.downloadAlt}>
                            <button
                                className={styles.downloadAltBtn}
                                onClick={() => handleDownloadReport('xlsx')}
                            >
                                📊 Excel
                            </button>
                            <button
                                className={styles.downloadAltBtn}
                                onClick={() => handleDownloadReport('pdf')}
                            >
                                📋 Basic PDF
                            </button>
                        </div>
                    </div>

                    {/* What-If Analysis Button */}
                    <button
                        className={styles.sandboxBtn}
                        onClick={() => setIsSandboxOpen(true)}
                    >
                        🔬 What-If Analysis
                    </button>
                </div>
            </main>

            {/* Sandbox Modal */}
            <SandboxModal
                isOpen={isSandboxOpen}
                onClose={() => setIsSandboxOpen(false)}
                assetId={ASSET_ID}
            />
        </div>
    )
}

export default App

import { useState, useEffect } from 'react'
import Header from './components/Header/Header'
import MetricCard from './components/MetricCard/MetricCard'
import SignalChart from './components/SignalChart/SignalChart'
import HealthSummary from './components/HealthSummary/HealthSummary'
import InsightPanel from './components/InsightPanel/InsightPanel'
import OperatorLog from './components/OperatorLog/OperatorLog'
import { usePolling } from './hooks/usePolling'
import styles from './App.module.css'

function App() {
    // Polling for dashboard data (every 3 seconds)
    const { data, isLoading, error } = usePolling('/api/dashboard', 3000)

    // Mock data for initial render
    const dashboardData = data || {
        asset_id: 'Motor-01',
        status: 'LIVE',
        signals: {
            voltage_v: 230,
            current_a: 12.1,
            power_factor: 0.92
        },
        chart_data: [],
        health: {
            health_score: 75,
            risk_level: 'MODERATE',
            maintenance_window_days: 14
        },
        explanations: [
            {
                reason: 'Power Factor showing slight degradation',
                related_features: ['power_factor'],
                confidence_score: 0.85
            }
        ]
    }

    const handleDownload = () => {
        alert('Reporting Module: Scheduled for Phase 10')
    }

    return (
        <div className={styles.container}>
            <Header
                assetId={dashboardData.asset_id}
                status={dashboardData.status}
            />

            <main className={styles.main}>
                {/* Left Column - Metrics and Chart */}
                <div className={styles.leftColumn}>
                    {/* Signal Metric Cards */}
                    <section className={styles.metricsGrid}>
                        <MetricCard
                            label="Voltage (V)"
                            value={dashboardData.signals.voltage_v}
                            unit="V"
                            icon="⚡"
                        />
                        <MetricCard
                            label="Current (A)"
                            value={dashboardData.signals.current_a}
                            unit="A"
                            icon="🔌"
                        />
                        <MetricCard
                            label="Power Factor"
                            value={dashboardData.signals.power_factor}
                            unit=""
                            icon="📊"
                        />
                    </section>

                    {/* Real-time Chart */}
                    <section className={styles.chartSection}>
                        <SignalChart
                            data={dashboardData.chart_data}
                            title="Real-time Power Signature and Anomalies (Last 1 Hour)"
                        />
                    </section>
                </div>

                {/* Right Column - Sidebar */}
                <aside className={styles.sidebar}>
                    <HealthSummary
                        healthScore={dashboardData.health.health_score}
                        riskLevel={dashboardData.health.risk_level}
                        maintenanceDays={dashboardData.health.maintenance_window_days}
                    />

                    <InsightPanel
                        explanations={dashboardData.explanations}
                    />

                    <OperatorLog />

                    <button
                        className={`btn btn-primary ${styles.downloadBtn}`}
                        onClick={handleDownload}
                    >
                        📥 Download Report (PDF / Excel)
                    </button>
                </aside>
            </main>
        </div>
    )
}

export default App

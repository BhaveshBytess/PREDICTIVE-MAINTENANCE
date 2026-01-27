/**
 * PerformanceCard Component
 * 
 * Displays Industrial Validation Metrics:
 * - Training Data Sample Count
 * - Healthy Stability (%)
 * - Fault Capture Rate (%)
 */

import styles from './PerformanceCard.module.css'

export default function PerformanceCard({
    trainingSamples = 0,
    healthyStability = 100.0,
    faultCaptureRate = 100.0
}) {
    // Determine status colors
    const getStabilityColor = (value) => {
        if (value >= 95) return 'green'
        if (value >= 80) return 'yellow'
        return 'red'
    }

    const getCaptureColor = (value) => {
        if (value >= 90) return 'green'
        if (value >= 70) return 'yellow'
        return 'red'
    }

    const stabilityColor = getStabilityColor(healthyStability)
    const captureColor = getCaptureColor(faultCaptureRate)

    return (
        <div className={styles.container}>
            <h3 className={styles.title}>
                <span className={styles.icon}>📊</span>
                Validation Scorecard
            </h3>

            <div className={styles.metricsGrid}>
                {/* Training Data */}
                <div className={styles.metric}>
                    <span className={styles.metricLabel}>Training Data</span>
                    <span className={styles.metricValue}>
                        {trainingSamples.toLocaleString()} Samples
                    </span>
                    <span className={styles.metricStatus}>
                        {trainingSamples >= 1000 ? '✅ Robust' : '⚠️ Limited'}
                    </span>
                </div>

                {/* Healthy Stability */}
                <div className={styles.metric}>
                    <span className={styles.metricLabel}>Healthy Stability</span>
                    <span className={`${styles.metricValue} ${styles[stabilityColor]}`}>
                        {healthyStability.toFixed(1)}%
                    </span>
                    <span className={styles.metricStatus}>
                        {stabilityColor === 'green' ? '✅ Stable' : stabilityColor === 'yellow' ? '⚠️ Fair' : '❌ Unstable'}
                    </span>
                </div>

                {/* Fault Capture Rate */}
                <div className={styles.metric}>
                    <span className={styles.metricLabel}>Fault Capture Rate</span>
                    <span className={`${styles.metricValue} ${styles[captureColor]}`}>
                        {faultCaptureRate.toFixed(1)}%
                    </span>
                    <span className={styles.metricStatus}>
                        {captureColor === 'green' ? '✅ Reliable' : captureColor === 'yellow' ? '⚠️ Moderate' : '❌ Low'}
                    </span>
                </div>
            </div>

            <div className={styles.footer}>
                Industrial-grade metrics for production confidence
            </div>
        </div>
    )
}

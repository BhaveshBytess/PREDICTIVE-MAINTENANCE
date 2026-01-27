/**
 * PerformanceCard Component
 * 
 * Simple validation metrics card matching dashboard style.
 */

import styles from './PerformanceCard.module.css'

export default function PerformanceCard({
    trainingSamples = 0,
    healthyStability = 100.0,
    faultCaptureRate = 100.0
}) {
    return (
        <div className={styles.container}>
            <h3 className={styles.title}>
                📊 Model Validation
            </h3>

            <div className={styles.metricRow}>
                <span className={styles.label}>Training Data:</span>
                <span className={styles.value}>{trainingSamples.toLocaleString()} samples</span>
            </div>

            <div className={styles.metricRow}>
                <span className={styles.label}>Healthy Stability:</span>
                <span className={`${styles.value} ${healthyStability >= 90 ? styles.good : styles.warn}`}>
                    {healthyStability.toFixed(1)}%
                </span>
            </div>

            <div className={styles.metricRow}>
                <span className={styles.label}>Fault Detection:</span>
                <span className={`${styles.value} ${faultCaptureRate >= 90 ? styles.good : styles.warn}`}>
                    {faultCaptureRate.toFixed(1)}%
                </span>
            </div>
        </div>
    )
}

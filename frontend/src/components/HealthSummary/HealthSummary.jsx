import styles from './HealthSummary.module.css'

function HealthSummary({ healthScore, riskLevel, maintenanceDays }) {
    // Get risk class for styling
    const riskClass = riskLevel?.toLowerCase() || 'low'

    // Format maintenance days - handle null/undefined for industrial realism
    const maintenanceText = maintenanceDays == null
        ? '---'
        : maintenanceDays <= 1
            ? '< 1 day'
            : `~${Math.round(maintenanceDays)} days`

    return (
        <div className={`glass-card ${styles.container}`}>
            <h2 className={styles.title}>Health and Risk Summary</h2>

            <div className={styles.content}>
                {/* Health Score Gauge */}
                <div className={styles.scoreSection}>
                    <div className={styles.gauge}>
                        <svg viewBox="0 0 100 100" className={styles.gaugeSvg}>
                            <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="rgba(255,255,255,0.1)"
                                strokeWidth="8"
                            />
                            <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke={`var(--risk-${riskClass})`}
                                strokeWidth="8"
                                strokeLinecap="round"
                                strokeDasharray={`${(healthScore ?? 0) * 2.83} 283`}
                                transform="rotate(-90 50 50)"
                                className={styles.gaugeProgress}
                            />
                        </svg>
                        <div className={styles.gaugeValue}>
                            <span className={styles.scoreNumber}>{healthScore ?? '---'}</span>
                            <span className={styles.scoreLabel}>Health</span>
                        </div>
                    </div>
                </div>

                {/* Maintenance Window */}
                <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>Estimated Maintenance Window:</span>
                    <span className={styles.infoValue}>{maintenanceText}</span>
                </div>

                {/* Risk Level Badge */}
                <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>RISK:</span>
                    <span className={`risk-badge risk-${riskClass}`}>
                        {riskLevel ?? 'AWAITING DATA'}
                    </span>
                </div>
            </div>
        </div>
    )
}

export default HealthSummary

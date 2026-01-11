import styles from './MetricCard.module.css'

function MetricCard({ label, value, unit, icon }) {
    // Format value for display
    const displayValue = typeof value === 'number'
        ? value.toFixed(value % 1 === 0 ? 0 : 1)
        : value

    return (
        <div className={`glass-card ${styles.card}`}>
            <div className={styles.iconWrapper}>
                <span className={styles.icon}>{icon}</span>
            </div>
            <div className={styles.content}>
                <span className={styles.label}>{label}</span>
                <div className={styles.valueWrapper}>
                    <span className={styles.value}>{displayValue}</span>
                    {unit && <span className={styles.unit}>{unit}</span>}
                </div>
            </div>
        </div>
    )
}

export default MetricCard

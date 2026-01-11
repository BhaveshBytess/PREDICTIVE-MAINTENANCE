import styles from './InsightPanel.module.css'

function InsightPanel({ explanations }) {
    // Handle empty explanations
    if (!explanations || explanations.length === 0) {
        return (
            <div className={`glass-card ${styles.container}`}>
                <h3 className={styles.title}>Insight / Reasoning</h3>
                <p className={styles.nominal}>✅ All systems operating within normal parameters</p>
            </div>
        )
    }

    return (
        <div className={`glass-card ${styles.container}`}>
            <h3 className={styles.title}>Insight / Reasoning</h3>

            <div className={styles.explanations}>
                {explanations.map((exp, idx) => (
                    <div key={idx} className={styles.explanation}>
                        <p className={styles.reason}>{exp.reason}</p>

                        {exp.related_features?.length > 0 && (
                            <div className={styles.features}>
                                {exp.related_features.map((feature, fidx) => (
                                    <span key={fidx} className={styles.featureTag}>
                                        {feature.replace(/_/g, ' ')}
                                    </span>
                                ))}
                            </div>
                        )}

                        {exp.confidence_score && (
                            <div className={styles.confidence}>
                                <div className={styles.confidenceBar}>
                                    <div
                                        className={styles.confidenceFill}
                                        style={{ width: `${exp.confidence_score * 100}%` }}
                                    />
                                </div>
                                <span className={styles.confidenceText}>
                                    {Math.round(exp.confidence_score * 100)}% confidence
                                </span>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}

export default InsightPanel

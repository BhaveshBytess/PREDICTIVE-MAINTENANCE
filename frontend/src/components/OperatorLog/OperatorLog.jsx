import { useState } from 'react'
import styles from './OperatorLog.module.css'

function OperatorLog() {
    const [serviceDate, setServiceDate] = useState('')
    const [wearAssessment, setWearAssessment] = useState('')

    const handleSubmit = (e) => {
        e.preventDefault()

        // UI-Only: Log to console (no backend POST endpoint yet)
        console.log('Operator Log Submitted:', {
            serviceDate,
            wearAssessment,
            timestamp: new Date().toISOString()
        })

        // Clear form
        setServiceDate('')
        setWearAssessment('')

        // Visual feedback
        alert('Log saved locally. Backend sync coming in future update.')
    }

    return (
        <div className={`glass-card ${styles.container}`}>
            <h3 className={styles.title}>Operator Input Log</h3>

            <form onSubmit={handleSubmit} className={styles.form}>
                <div className={styles.field}>
                    <label htmlFor="serviceDate">Last Service Date</label>
                    <input
                        type="date"
                        id="serviceDate"
                        value={serviceDate}
                        onChange={(e) => setServiceDate(e.target.value)}
                        placeholder="DD/MM/YYYY"
                    />
                </div>

                <div className={styles.field}>
                    <label htmlFor="wearAssessment">Visual Wear Assessment</label>
                    <select
                        id="wearAssessment"
                        value={wearAssessment}
                        onChange={(e) => setWearAssessment(e.target.value)}
                    >
                        <option value="">Select assessment...</option>
                        <option value="none">None - Like New</option>
                        <option value="minimal">Minimal - Light Wear</option>
                        <option value="moderate">Moderate - Visible Wear</option>
                        <option value="significant">Significant - Needs Attention</option>
                        <option value="severe">Severe - Critical</option>
                    </select>
                </div>

                <button type="submit" className={`btn btn-secondary ${styles.submitBtn}`}>
                    Save Log Entry
                </button>
            </form>
        </div>
    )
}

export default OperatorLog

import { useState, useEffect } from 'react'
import styles from './OperatorLog.module.css'
import { API_URL } from '../../config'

function OperatorLog() {
    // Options fetched from backend
    const [eventTypes, setEventTypes] = useState([])
    const [severities, setSeverities] = useState([])
    const [isLoadingOptions, setIsLoadingOptions] = useState(true)
    const [optionsError, setOptionsError] = useState(null)

    // Form state
    const [selectedAsset] = useState('Motor-01') // Hardcoded for now
    const [selectedType, setSelectedType] = useState('')
    const [selectedSeverity, setSelectedSeverity] = useState('')
    const [description, setDescription] = useState('')
    const [logDate, setLogDate] = useState('')

    // Submission state
    const [isSubmitting, setIsSubmitting] = useState(false)

    // Fetch event types and severities on mount
    useEffect(() => {
        async function fetchOptions() {
            try {
                setIsLoadingOptions(true)
                setOptionsError(null)

                const response = await fetch(`${API_URL}/api/log/types`)
                
                if (!response.ok) {
                    throw new Error(`Failed to fetch options: ${response.status}`)
                }

                const data = await response.json()
                setEventTypes(data.event_types || [])
                setSeverities(data.severities || [])
            } catch (error) {
                console.error('Error fetching log options:', error)
                setOptionsError(error.message)
            } finally {
                setIsLoadingOptions(false)
            }
        }

        fetchOptions()
    }, [])

    // Form validation
    const isFormValid = () => {
        return (
            selectedAsset.trim() !== '' &&
            selectedType !== '' &&
            selectedSeverity !== '' &&
            description.trim() !== ''
        )
    }

    // Handle form submission
    const handleSubmit = async (e) => {
        e.preventDefault()

        // Validate form
        if (!isFormValid()) {
            alert('❌ Please fill in all required fields')
            return
        }

        setIsSubmitting(true)

        try {
            // Construct payload
            const payload = {
                asset_id: selectedAsset,
                event_type: selectedType,
                severity: selectedSeverity,
                description: description.trim(),
            }

            // Add timestamp if date is provided (convert to UTC ISO string)
            if (logDate) {
                // Create date at noon UTC to avoid timezone issues
                const date = new Date(logDate + 'T12:00:00Z')
                payload.timestamp = date.toISOString()
            }

            console.log('Submitting maintenance log:', payload)

            // Send to backend
            const response = await fetch(`${API_URL}/api/log`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}))
                throw new Error(errorData.detail || `Server error: ${response.status}`)
            }

            const result = await response.json()
            console.log('Log saved successfully:', result)

            // Success feedback
            alert(`✅ Log saved successfully!\n\nEvent ID: ${result.event_id}`)

            // Clear form
            setSelectedType('')
            setSelectedSeverity('')
            setDescription('')
            setLogDate('')

        } catch (error) {
            console.error('Error saving log:', error)
            alert(`❌ Error saving log: ${error.message}`)
        } finally {
            setIsSubmitting(false)
        }
    }

    // Render loading state for options
    if (isLoadingOptions) {
        return (
            <div className={`glass-card ${styles.container}`}>
                <h3 className={styles.title}>Operator Input Log</h3>
                <p className={styles.loading}>Loading options...</p>
            </div>
        )
    }

    // Render error state
    if (optionsError) {
        return (
            <div className={`glass-card ${styles.container}`}>
                <h3 className={styles.title}>Operator Input Log</h3>
                <p className={styles.error}>Failed to load options: {optionsError}</p>
            </div>
        )
    }

    return (
        <div className={`glass-card ${styles.container}`}>
            <h3 className={styles.title}>Operator Input Log</h3>

            <form onSubmit={handleSubmit} className={styles.form}>
                {/* Asset ID (read-only for now) */}
                <div className={styles.field}>
                    <label htmlFor="assetId">Asset ID</label>
                    <input
                        type="text"
                        id="assetId"
                        value={selectedAsset}
                        disabled
                        className={styles.disabledInput}
                    />
                </div>

                {/* Event Type Dropdown */}
                <div className={styles.field}>
                    <label htmlFor="eventType">Event Type *</label>
                    <select
                        id="eventType"
                        value={selectedType}
                        onChange={(e) => setSelectedType(e.target.value)}
                        required
                        disabled={isSubmitting}
                    >
                        <option value="">Select event type...</option>
                        {eventTypes.map((type) => (
                            <option key={type.value} value={type.value}>
                                {type.label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Severity Dropdown */}
                <div className={styles.field}>
                    <label htmlFor="severity">Severity *</label>
                    <select
                        id="severity"
                        value={selectedSeverity}
                        onChange={(e) => setSelectedSeverity(e.target.value)}
                        required
                        disabled={isSubmitting}
                    >
                        <option value="">Select severity...</option>
                        {severities.map((sev) => (
                            <option key={sev} value={sev}>
                                {sev}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Description */}
                <div className={styles.field}>
                    <label htmlFor="description">Description *</label>
                    <textarea
                        id="description"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Describe the maintenance activity..."
                        rows={3}
                        required
                        disabled={isSubmitting}
                        className={styles.textarea}
                    />
                </div>

                {/* Date (optional - for backdating) */}
                <div className={styles.field}>
                    <label htmlFor="logDate">Event Date (optional)</label>
                    <input
                        type="date"
                        id="logDate"
                        value={logDate}
                        onChange={(e) => setLogDate(e.target.value)}
                        disabled={isSubmitting}
                    />
                    <small className={styles.hint}>Leave empty to use current time</small>
                </div>

                {/* Submit Button */}
                <button 
                    type="submit" 
                    className={`btn btn-secondary ${styles.submitBtn}`}
                    disabled={isSubmitting || !isFormValid()}
                >
                    {isSubmitting ? 'Saving...' : 'Save Log Entry'}
                </button>
            </form>
        </div>
    )
}

export default OperatorLog


/**
 * SystemControlPanel Component
 * 
 * Provides UI controls for demo lifecycle:
 * - Calibrate System (IDLE → CALIBRATING → MONITORING_HEALTHY)
 * - Inject Fault (MONITORING_HEALTHY → FAULT_INJECTION)
 * - Reset to Healthy (FAULT_INJECTION → MONITORING_HEALTHY)
 */

import { useState, useEffect, useCallback } from 'react'
import { getSystemState, calibrateSystem, injectFault, resetSystem, stopSession } from '../../api/systemApi'
import styles from './SystemControlPanel.module.css'

// State constants
const STATES = {
    IDLE: 'IDLE',
    CALIBRATING: 'CALIBRATING',
    MONITORING_HEALTHY: 'MONITORING_HEALTHY',
    FAULT_INJECTION: 'FAULT_INJECTION'
}

// Fault types
const FAULT_TYPES = [
    { value: 'DEFAULT', label: 'Random Fault' },
    { value: 'SPIKE', label: 'Sudden Spike' },
    { value: 'DRIFT', label: 'Gradual Drift' }
]

export default function SystemControlPanel({ onMetricsUpdate }) {
    const [systemState, setSystemState] = useState(STATES.IDLE)
    const [message, setMessage] = useState('System ready. Click "Calibrate" to begin.')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)
    const [selectedFaultType, setSelectedFaultType] = useState('DEFAULT')
    const [metrics, setMetrics] = useState({
        trainingSamples: 0,
        healthyStability: 100.0,
        faultCaptureRate: 100.0
    })

    // Poll system state every 2 seconds
    useEffect(() => {
        const fetchState = async () => {
            try {
                const data = await getSystemState()
                setSystemState(data.state)
                setMessage(data.message)
                setError(null)

                // Update metrics
                const newMetrics = {
                    trainingSamples: data.training_samples || 0,
                    healthyStability: data.healthy_stability || 100.0,
                    faultCaptureRate: data.fault_capture_rate || 100.0
                }
                setMetrics(newMetrics)

                // Notify parent of metrics update
                if (onMetricsUpdate) {
                    onMetricsUpdate(newMetrics)
                }
            } catch (err) {
                // Don't show error during polling, just keep last state
                console.error('State poll error:', err)
            }
        }

        fetchState()
        const interval = setInterval(fetchState, 2000)
        return () => clearInterval(interval)
    }, [onMetricsUpdate])

    // Button handlers
    const handleCalibrate = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            await calibrateSystem('Motor-01')
        } catch (err) {
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }, [])

    const handleInjectFault = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            await injectFault('Motor-01', selectedFaultType)
        } catch (err) {
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }, [selectedFaultType])

    const handleReset = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            await resetSystem('Motor-01')
        } catch (err) {
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }, [])

    const handleStop = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            await stopSession()
        } catch (err) {
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }, [])

    // Button disabled states
    const canCalibrate = systemState === STATES.IDLE && !isLoading
    const canInjectFault = systemState === STATES.MONITORING_HEALTHY && !isLoading
    const canReset = systemState === STATES.FAULT_INJECTION && !isLoading
    const canStop = (systemState === STATES.MONITORING_HEALTHY || systemState === STATES.FAULT_INJECTION) && !isLoading

    // State badge color
    const getStateColor = () => {
        switch (systemState) {
            case STATES.IDLE: return 'gray'
            case STATES.CALIBRATING: return 'blue'
            case STATES.MONITORING_HEALTHY: return 'green'
            case STATES.FAULT_INJECTION: return 'red'
            default: return 'gray'
        }
    }

    // State display text
    const getStateDisplay = () => {
        switch (systemState) {
            case STATES.IDLE: return 'Idle'
            case STATES.CALIBRATING: return 'Calibrating...'
            case STATES.MONITORING_HEALTHY: return 'Monitoring (Healthy)'
            case STATES.FAULT_INJECTION: return 'Fault Injection Active'
            default: return systemState
        }
    }

    return (
        <div className={styles.container}>
            <h3 className={styles.title}>
                <span className={styles.icon}>⚙️</span>
                System Control Panel
            </h3>

            {/* State Badge */}
            <div className={styles.stateSection}>
                <span className={styles.stateLabel}>State:</span>
                <span
                    className={styles.stateBadge}
                    style={{ '--badge-color': `var(--color-${getStateColor()})` }}
                >
                    {getStateDisplay()}
                </span>
            </div>

            {/* Status Message */}
            <div className={styles.messageBox}>
                {message}
            </div>

            {/* Error Message */}
            {error && (
                <div className={styles.errorBox}>
                    ⚠️ {error}
                </div>
            )}

            {/* Control Buttons */}
            <div className={styles.buttonGroup}>
                <button
                    className={`${styles.button} ${styles.calibrateBtn}`}
                    onClick={handleCalibrate}
                    disabled={!canCalibrate}
                    title={canCalibrate ? 'Start calibration' : 'Can only calibrate when IDLE'}
                >
                    {systemState === STATES.CALIBRATING ? (
                        <>
                            <span className={styles.spinner}></span>
                            Calibrating...
                        </>
                    ) : (
                        <>🎯 Calibrate</>
                    )}
                </button>

                {/* Fault Type Selector */}
                <div className={styles.faultControl}>
                    <select
                        className={styles.faultSelect}
                        value={selectedFaultType}
                        onChange={(e) => setSelectedFaultType(e.target.value)}
                        disabled={!canInjectFault}
                    >
                        {FAULT_TYPES.map(ft => (
                            <option key={ft.value} value={ft.value}>
                                {ft.label}
                            </option>
                        ))}
                    </select>
                    <button
                        className={`${styles.button} ${styles.faultBtn}`}
                        onClick={handleInjectFault}
                        disabled={!canInjectFault}
                        title={canInjectFault ? 'Inject fault' : 'Can only inject fault when MONITORING_HEALTHY'}
                    >
                        ⚡ Inject Fault
                    </button>
                </div>

                <button
                    className={`${styles.button} ${styles.resetBtn}`}
                    onClick={handleReset}
                    disabled={!canReset}
                    title={canReset ? 'Reset to healthy' : 'Can only reset during FAULT_INJECTION'}
                >
                    🔄 Reset
                </button>

                <button
                    className={`${styles.button} ${styles.stopBtn}`}
                    onClick={handleStop}
                    disabled={!canStop}
                    title={canStop ? 'Stop session and return to IDLE' : 'Can only stop when monitoring'}
                >
                    ⏹️ Stop
                </button>
            </div>

            {/* Instructions */}
            <div className={styles.instructions}>
                <p><strong>Demo Flow:</strong></p>
                <ol>
                    <li>Click <strong>Calibrate</strong> to build baseline from healthy data</li>
                    <li>Wait for calibration to complete (~15 seconds)</li>
                    <li>Click <strong>Inject Fault</strong> to trigger anomaly detection</li>
                    <li>Watch health score drop and red lines appear</li>
                    <li>Click <strong>Reset</strong> to return to healthy state</li>
                </ol>
            </div>
        </div>
    )
}

/**
 * SandboxModal Component
 * 
 * What-If Analysis tool for testing manual sensor inputs:
 * - Preset scenarios (Normal, Motor Stall, Voltage Spike, Bearing Failure)
 * - Manual slider inputs for 4 raw features
 * - Feature contribution display with progress bars
 * - Comparison with live system state
 */

import { useState, useEffect } from 'react'
import styles from './SandboxModal.module.css'

// API base URL - empty string in production uses relative paths
const API_BASE = import.meta.env.PROD ? '' : 'http://localhost:8000'

// Preset scenarios (must match backend)
const PRESETS = [
    {
        name: 'Normal',
        description: 'Healthy operating conditions',
        voltage_v: 230,
        current_a: 15,
        power_factor: 0.92,
        vibration_g: 0.15,
        icon: '✅'
    },
    {
        name: 'Motor Stall',
        description: 'High current, low PF',
        voltage_v: 210,
        current_a: 35,
        power_factor: 0.55,
        vibration_g: 2.5,
        icon: '⚡'
    },
    {
        name: 'Voltage Spike',
        description: 'Grid overvoltage',
        voltage_v: 285,
        current_a: 18,
        power_factor: 0.85,
        vibration_g: 0.35,
        icon: '🔌'
    },
    {
        name: 'Bearing Failure',
        description: 'Excessive vibration',
        voltage_v: 228,
        current_a: 16,
        power_factor: 0.88,
        vibration_g: 3.8,
        icon: '⚙️'
    }
]

// Risk level colors
const RISK_COLORS = {
    LOW: '#10b981',
    MODERATE: '#f59e0b',
    HIGH: '#f97316',
    CRITICAL: '#ef4444'
}

export default function SandboxModal({ isOpen, onClose, assetId = 'asset-001' }) {
    // Input state
    const [voltage, setVoltage] = useState(230)
    const [current, setCurrent] = useState(15)
    const [powerFactor, setPowerFactor] = useState(0.92)
    const [vibration, setVibration] = useState(0.15)

    // Result state
    const [result, setResult] = useState(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)

    // Apply preset
    const applyPreset = (preset) => {
        setVoltage(preset.voltage_v)
        setCurrent(preset.current_a)
        setPowerFactor(preset.power_factor)
        setVibration(preset.vibration_g)
        setResult(null)
        setError(null)
    }

    // Run prediction
    const runPrediction = async () => {
        setIsLoading(true)
        setError(null)

        try {
            const response = await fetch(`${API_BASE}/sandbox/predict`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    voltage_v: voltage,
                    current_a: current,
                    power_factor: powerFactor,
                    vibration_g: vibration,
                    asset_id: assetId
                })
            })

            if (!response.ok) {
                const errData = await response.json()
                throw new Error(errData.detail || 'Prediction failed')
            }

            const data = await response.json()
            setResult(data)
        } catch (err) {
            setError(err.message)
            setResult(null)
        } finally {
            setIsLoading(false)
        }
    }

    // Close on Escape key
    useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape') onClose()
        }
        if (isOpen) {
            document.addEventListener('keydown', handleEscape)
        }
        return () => document.removeEventListener('keydown', handleEscape)
    }, [isOpen, onClose])

    if (!isOpen) return null

    return (
        <div className={styles.overlay} onClick={onClose}>
            <div className={styles.modal} onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className={styles.header}>
                    <h2>🔬 What-If Analysis</h2>
                    <button className={styles.closeBtn} onClick={onClose}>×</button>
                </div>

                {/* Content */}
                <div className={styles.content}>
                    {/* Left: Inputs */}
                    <div className={styles.inputSection}>
                        {/* Presets */}
                        <div className={styles.presets}>
                            <h3>Quick Presets</h3>
                            <div className={styles.presetGrid}>
                                {PRESETS.map(preset => (
                                    <button
                                        key={preset.name}
                                        className={styles.presetBtn}
                                        onClick={() => applyPreset(preset)}
                                        title={preset.description}
                                    >
                                        <span className={styles.presetIcon}>{preset.icon}</span>
                                        <span>{preset.name}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Sliders */}
                        <div className={styles.sliders}>
                            <h3>Manual Input</h3>

                            <div className={styles.sliderGroup}>
                                <label>
                                    Voltage: <strong>{voltage.toFixed(0)}V</strong>
                                </label>
                                <input
                                    type="range"
                                    min="180"
                                    max="300"
                                    step="1"
                                    value={voltage}
                                    onChange={e => setVoltage(parseFloat(e.target.value))}
                                />
                                <span className={styles.range}>180V - 300V</span>
                            </div>

                            <div className={styles.sliderGroup}>
                                <label>
                                    Current: <strong>{current.toFixed(1)}A</strong>
                                </label>
                                <input
                                    type="range"
                                    min="5"
                                    max="50"
                                    step="0.5"
                                    value={current}
                                    onChange={e => setCurrent(parseFloat(e.target.value))}
                                />
                                <span className={styles.range}>5A - 50A</span>
                            </div>

                            <div className={styles.sliderGroup}>
                                <label>
                                    Power Factor: <strong>{powerFactor.toFixed(2)}</strong>
                                </label>
                                <input
                                    type="range"
                                    min="0.3"
                                    max="1.0"
                                    step="0.01"
                                    value={powerFactor}
                                    onChange={e => setPowerFactor(parseFloat(e.target.value))}
                                />
                                <span className={styles.range}>0.30 - 1.00</span>
                            </div>

                            <div className={styles.sliderGroup}>
                                <label>
                                    Vibration: <strong>{vibration.toFixed(2)}g</strong>
                                </label>
                                <input
                                    type="range"
                                    min="0.01"
                                    max="5.0"
                                    step="0.01"
                                    value={vibration}
                                    onChange={e => setVibration(parseFloat(e.target.value))}
                                />
                                <span className={styles.range}>0.01g - 5.00g</span>
                            </div>
                        </div>

                        {/* Test Button */}
                        <button
                            className={styles.testBtn}
                            onClick={runPrediction}
                            disabled={isLoading}
                        >
                            {isLoading ? '⏳ Analyzing...' : '🔍 Test Values'}
                        </button>

                        {error && (
                            <div className={styles.error}>
                                ⚠️ {error}
                            </div>
                        )}
                    </div>

                    {/* Right: Results */}
                    <div className={styles.resultSection}>
                        {result ? (
                            <>
                                {/* Risk Badge */}
                                <div
                                    className={styles.riskBadge}
                                    style={{ backgroundColor: RISK_COLORS[result.risk_level] }}
                                >
                                    <span className={styles.riskLevel}>{result.risk_level}</span>
                                    <span className={styles.healthScore}>
                                        Health: {result.health_score}
                                    </span>
                                </div>

                                {/* Insight */}
                                <div className={styles.insight}>
                                    <h4>💡 Insight</h4>
                                    <p>{result.insight}</p>
                                </div>

                                {/* Feature Contributions */}
                                <div className={styles.contributions}>
                                    <h4>📊 Why This Score?</h4>
                                    {result.feature_contributions.map(contrib => (
                                        <div key={contrib.feature} className={styles.contributionRow}>
                                            <div className={styles.contributionLabel}>
                                                <span>{contrib.feature}</span>
                                                <span className={styles[contrib.status]}>
                                                    {contrib.contribution_percent.toFixed(1)}%
                                                </span>
                                            </div>
                                            <div className={styles.progressBar}>
                                                <div
                                                    className={`${styles.progressFill} ${styles[contrib.status]}`}
                                                    style={{ width: `${Math.min(contrib.contribution_percent, 100)}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Live Comparison */}
                                {result.comparison && result.comparison.live_voltage && (
                                    <div className={styles.comparison}>
                                        <h4>🔄 Comparison with Live State</h4>
                                        <div className={styles.comparisonGrid}>
                                            <div className={styles.comparisonItem}>
                                                <span>Voltage</span>
                                                <span className={getDiffClass(result.comparison.voltage_diff_percent)}>
                                                    {formatDiff(result.comparison.voltage_diff_percent)}
                                                </span>
                                            </div>
                                            <div className={styles.comparisonItem}>
                                                <span>Current</span>
                                                <span className={getDiffClass(result.comparison.current_diff_percent)}>
                                                    {formatDiff(result.comparison.current_diff_percent)}
                                                </span>
                                            </div>
                                            <div className={styles.comparisonItem}>
                                                <span>Power Factor</span>
                                                <span className={getDiffClass(result.comparison.power_factor_diff_percent)}>
                                                    {formatDiff(result.comparison.power_factor_diff_percent)}
                                                </span>
                                            </div>
                                            <div className={styles.comparisonItem}>
                                                <span>Vibration</span>
                                                <span className={getDiffClass(result.comparison.vibration_diff_percent)}>
                                                    {formatDiff(result.comparison.vibration_diff_percent)}
                                                </span>
                                            </div>
                                        </div>
                                        {result.comparison.live_health_score !== null && (
                                            <p className={styles.liveHealth}>
                                                Live System: Health {result.comparison.live_health_score} ({result.comparison.live_risk_level})
                                            </p>
                                        )}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className={styles.placeholder}>
                                <span className={styles.placeholderIcon}>🎯</span>
                                <p>Select a preset or adjust sliders, then click "Test Values"</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

// Helper functions
function formatDiff(value) {
    if (value === null || value === undefined) return '--'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
}

function getDiffClass(value) {
    if (!value) return ''
    if (Math.abs(value) < 5) return styles.diffNormal
    if (Math.abs(value) < 20) return styles.diffModerate
    return styles.diffHigh
}

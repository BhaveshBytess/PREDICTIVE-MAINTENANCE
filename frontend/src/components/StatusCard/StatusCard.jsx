/**
 * StatusCard — Glanceable summary card with threshold-based severity.
 *
 * Each card shows: Large Value + Unit + Status Label + severity tint.
 * Thresholds are hard-coded per Directive C for explainability alignment.
 *
 * Props:
 *   label        – card title (e.g. "Health Score")
 *   value        – numeric value (raw)
 *   unit         – display unit string
 *   icon         – emoji icon
 *   status       – "NORMAL" | "WARNING" | "CRITICAL" (computed by parent)
 *   displayValue – formatted string for display (optional, falls back to value)
 */

import { memo } from 'react'
import styles from './StatusCard.module.css'

/* ── Severity visual config ─────────────────────────────── */
const STATUS_CONFIG = {
    NORMAL: {
        label: 'NORMAL',
        colorVar: 'var(--risk-low)',       // #10b981
        bgTint: 'rgba(16, 185, 129, 0.08)',
        borderTint: 'rgba(16, 185, 129, 0.35)',
    },
    WARNING: {
        label: 'WARNING',
        colorVar: 'var(--risk-moderate)',   // #f59e0b
        bgTint: 'rgba(245, 158, 11, 0.08)',
        borderTint: 'rgba(245, 158, 11, 0.35)',
    },
    CRITICAL: {
        label: 'CRITICAL',
        colorVar: 'var(--risk-critical)',   // #ef4444
        bgTint: 'rgba(239, 68, 68, 0.10)',
        borderTint: 'rgba(239, 68, 68, 0.45)',
    },
}

/* ── Threshold helpers (Directive C) ────────────────────── */

/**
 * Health score → status.
 * 90-100 Normal, 70-89 Warning, <70 Critical.
 */
export function healthStatus(score) {
    if (score == null) return 'NORMAL'
    if (score >= 90) return 'NORMAL'
    if (score >= 70) return 'WARNING'
    return 'CRITICAL'
}

/**
 * Vibration (g) → status.
 * <0.5 Normal, 0.5–1.0 Warning, >1.0 Critical.
 */
export function vibrationStatus(g) {
    if (g == null) return 'NORMAL'
    if (g < 0.5) return 'NORMAL'
    if (g <= 1.0) return 'WARNING'
    return 'CRITICAL'
}

/**
 * Voltage (V) → status.
 * 220-240 Normal, 210-220 or 240-260 Warning, else Critical.
 */
export function voltageStatus(v) {
    if (v == null) return 'NORMAL'
    if (v >= 220 && v <= 240) return 'NORMAL'
    if (v >= 210 && v <= 260) return 'WARNING'
    return 'CRITICAL'
}

/**
 * Current (A) → status.
 * 12-18 Normal, 10-12 or 18-22 Warning, else Critical.
 */
export function currentStatus(a) {
    if (a == null) return 'NORMAL'
    if (a >= 12 && a <= 18) return 'NORMAL'
    if (a >= 10 && a <= 22) return 'WARNING'
    return 'CRITICAL'
}

/**
 * Sync Rule: if is_faulty is true, force CRITICAL.
 */
export function applyFaultOverride(baseStatus, isFaulty) {
    return isFaulty ? 'CRITICAL' : baseStatus
}

/* ── Component ──────────────────────────────────────────── */

const StatusCard = memo(function StatusCard({
    label,
    value,
    unit,
    icon,
    status = 'NORMAL',
    displayValue,
    baselineTarget,
}) {
    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.NORMAL

    return (
        <div
            className={styles.card}
            style={{
                background: cfg.bgTint,
                borderColor: cfg.borderTint,
            }}
        >
            {/* Header: Icon + Status pill */}
            <div className={styles.header}>
                <div className={styles.iconBadge}>
                    <span>{icon}</span>
                </div>
                <span
                    className={styles.pill}
                    style={{ color: cfg.colorVar, borderColor: cfg.colorVar }}
                >
                    {cfg.label}
                </span>
            </div>

            {/* Label */}
            <span className={styles.label}>{label}</span>

            {/* Value + Unit */}
            <div className={styles.valueRow}>
                <span className={styles.value}>
                    {displayValue ?? (value != null ? value : '---')}
                </span>
                {unit && <span className={styles.unit}>{unit}</span>}
            </div>

            {/* Baseline target (learned) */}
            {baselineTarget != null && (
                <span className={styles.target}>Target: {baselineTarget}{unit ? ` ${unit.replace('/ ', '')}` : ''}</span>
            )}
        </div>
    )
})

export default StatusCard

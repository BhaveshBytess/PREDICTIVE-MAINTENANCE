/**
 * LogWatcher — Transition-Based Event Feed
 *
 * Displays backend events (ANOMALY_DETECTED, ANOMALY_CLEARED, HEARTBEAT)
 * as narrative cards with severity-coded left borders.
 *
 * Architectural rules:
 *  - Newest events at bottom (terminal-style)
 *  - Auto-scroll when the user is at the bottom
 *  - Auto-scroll pauses when the user scrolls up manually
 *  - Buffer capped at 50 events to prevent DOM bloat
 *  - Clicking an event card sets `selectedTimestamp` for chart correlation
 */

import { useRef, useEffect, useCallback, memo } from 'react'
import styles from './LogWatcher.module.css'

const EVENT_BUFFER_CAP = 50

/* Severity → visual config */
const SEVERITY_CONFIG = {
    critical: { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.08)', icon: '🔴', label: 'CRITICAL' },
    warning:  { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.08)', icon: '🟡', label: 'WARNING'  },
    info:     { color: '#10b981', bg: 'rgba(16, 185, 129, 0.08)', icon: '🟢', label: 'INFO'     },
}

/* Format ISO timestamp to compact local time */
function formatTime(iso) {
    try {
        const d = new Date(iso)
        return d.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        })
    } catch {
        return iso
    }
}

/* ---------- Single Event Card (memoised) ---------- */
const EventCard = memo(function EventCard({ event, isSelected, onClick }) {
    const sev = SEVERITY_CONFIG[event.severity] || SEVERITY_CONFIG.info

    return (
        <button
            className={`${styles.card} ${isSelected ? styles.cardSelected : ''}`}
            style={{
                borderLeftColor: sev.color,
                background: isSelected ? sev.bg : undefined,
            }}
            onClick={() => onClick(event)}
            title="Click to highlight on chart"
        >
            <div className={styles.cardHeader}>
                <span className={styles.cardIcon}>{sev.icon}</span>
                <span className={styles.cardType}>{event.type.replace(/_/g, ' ')}</span>
                <span className={styles.cardTime}>{formatTime(event.timestamp)}</span>
            </div>
            <p className={styles.cardMessage}>{event.message}</p>
        </button>
    )
})

/* ---------- LogWatcher Panel ---------- */
function LogWatcher({ events = [], selectedTimestamp, onSelectEvent }) {
    const scrollRef = useRef(null)
    const isAutoScrollRef = useRef(true)

    /* ---- Pause Rule: detect manual scroll vs auto-scroll ---- */
    const handleScroll = useCallback(() => {
        const el = scrollRef.current
        if (!el) return
        // If the user is within 40px of the bottom, re-enable auto-scroll
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
        isAutoScrollRef.current = atBottom
    }, [])

    /* ---- Auto-scroll to bottom when new events arrive ---- */
    useEffect(() => {
        if (isAutoScrollRef.current && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [events.length])

    /* ---- Click handler: set selectedTimestamp ---- */
    const handleCardClick = useCallback(
        (event) => {
            if (!onSelectEvent) return
            // Toggle: click same event again → deselect
            const ts = new Date(event.timestamp).getTime()
            onSelectEvent(selectedTimestamp === ts ? null : ts)
        },
        [onSelectEvent, selectedTimestamp],
    )

    /* ---- Render ---- */
    const displayedEvents = events.slice(-EVENT_BUFFER_CAP)

    return (
        <div className={styles.container}>
            {/* Header */}
            <div className={styles.header}>
                <h3 className={styles.title}>
                    <span className={styles.titleIcon}>📡</span>
                    Event Log
                </h3>
                <span className={styles.badge}>{displayedEvents.length}</span>
            </div>

            {/* Scrollable feed */}
            <div
                className={styles.feed}
                ref={scrollRef}
                onScroll={handleScroll}
            >
                {displayedEvents.length === 0 ? (
                    <div className={styles.empty}>
                        Waiting for events…
                    </div>
                ) : (
                    displayedEvents.map((evt, idx) => (
                        <EventCard
                            key={`${evt.timestamp}-${evt.type}-${idx}`}
                            event={evt}
                            isSelected={selectedTimestamp === new Date(evt.timestamp).getTime()}
                            onClick={handleCardClick}
                        />
                    ))
                )}
            </div>

            {/* Footer hint */}
            <div className={styles.footer}>
                Click an event to highlight on chart
            </div>
        </div>
    )
}

export default LogWatcher

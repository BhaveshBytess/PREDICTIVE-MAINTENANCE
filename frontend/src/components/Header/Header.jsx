import styles from './Header.module.css'

function Header({ assetId, status }) {
    const isLive = status === 'LIVE'

    return (
        <header className={styles.header}>
            <div className={styles.titleSection}>
                <h1 className={styles.title}>
                    <span className="gradient-text">Industrial Asset Health Monitor</span>
                    <span className={styles.assetId}> - {assetId}</span>
                </h1>
            </div>

            <div className={styles.statusSection}>
                <div className={`${styles.statusIndicator} ${isLive ? styles.live : styles.offline}`}>
                    <span className={styles.statusDot}></span>
                    <span className={styles.statusText}>STATUS: {status}</span>
                </div>
            </div>
        </header>
    )
}

export default Header

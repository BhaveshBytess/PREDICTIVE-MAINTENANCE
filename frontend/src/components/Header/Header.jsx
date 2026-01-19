import styles from './Header.module.css'

function Header({ assetName, isLive }) {
    return (
        <header className={styles.header}>
            <div className={styles.titleSection}>
                <h1 className={styles.title}>
                    <span className="gradient-text">{assetName || 'Industrial Asset Health Monitor'}</span>
                </h1>
            </div>

            <div className={styles.statusSection}>
                <div className={`${styles.statusIndicator} ${isLive ? styles.live : styles.offline}`}>
                    <span className={styles.statusDot}></span>
                    <span className={styles.statusText}>STATUS: {isLive ? 'LIVE' : 'OFFLINE'}</span>
                </div>
            </div>
        </header>
    )
}

export default Header


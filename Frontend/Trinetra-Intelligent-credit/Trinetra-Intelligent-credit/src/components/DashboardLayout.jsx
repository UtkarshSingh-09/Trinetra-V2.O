import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useApplication } from '../context/ApplicationContext'
import { RefreshCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Sidebar from './Sidebar'
import ConnectionStatus from './ConnectionStatus'
import LanguageSwitcher from './LanguageSwitcher'
import './DashboardLayout.css'

const pageTransition = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
    transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] }
}

export default function DashboardLayout({ children, title, subtitle }) {
    const { resetSession } = useApplication()
    const navigate = useNavigate()
    const { t } = useTranslation()

    const handleNewSession = () => {
        resetSession()
        navigate('/ingestor')
    }

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="dashboard-main">
                <header className="dashboard-header">
                    <div className="header-left">
                        <h1 className="page-title">{title}</h1>
                        {subtitle && <p className="page-subtitle">{subtitle}</p>}
                    </div>
                    <div className="header-right">
                        <ConnectionStatus />
                        <LanguageSwitcher />
                        <button className="btn-secondary new-session-btn" onClick={handleNewSession}>
                            <RefreshCcw size={14} />
                            <span>{t('header.newSession')}</span>
                        </button>
                        <div className="header-search">
                            <span className="material-icons-outlined">search</span>
                            <input type="text" placeholder={t('header.searchPlaceholder')} />
                        </div>
                        <button className="header-icon-btn">
                            <span className="material-icons-outlined">notifications</span>
                            <span className="notification-dot"></span>
                        </button>
                    </div>
                </header>
                <motion.div className="dashboard-content" {...pageTransition}>
                    {children}
                </motion.div>
            </main>
        </div>
    )
}

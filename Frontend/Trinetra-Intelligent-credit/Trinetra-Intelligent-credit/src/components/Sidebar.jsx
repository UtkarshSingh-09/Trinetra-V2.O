import { Link, NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { LayoutDashboard, Upload, Search, Gavel, FileOutput, Database, GitBranch } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import trisastraLogo from '../assets/trisastra-logo.png'
import './Sidebar.css'

export default function Sidebar() {
    const location = useLocation()
    const { t } = useTranslation()

    const navItems = [
        { path: '/dashboard', label: t('sidebar.dashboard'), icon: LayoutDashboard },
        { path: '/ingestor', label: t('sidebar.ingestion'), icon: Upload },
        { path: '/research', label: t('sidebar.research'), icon: Search },
        { path: '/recommendation', label: t('sidebar.decisions'), icon: Gavel },
        { path: '/vectorai', label: t('sidebar.vectorExplorer'), icon: Database },
        { path: '/pipeline', label: t('sidebar.agentPipeline'), icon: GitBranch },
        { path: '/recommendation', label: t('sidebar.exportCam'), icon: FileOutput },
    ]

    return (
        <motion.aside
            className="sidebar"
            initial={{ x: -260 }}
            animate={{ x: 0 }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        >
            <Link to="/dashboard" className="sidebar-brand">
                <img src={trisastraLogo} alt="TRISASTRA AI" className="brand-logo" />
                <div className="brand-text">
                    <h2>{t('sidebar.brand')}</h2>
                    <span className="brand-badge">{t('sidebar.badge')}</span>
                </div>
            </Link>

            <nav className="sidebar-nav">
                {navItems.map((item, index) => {
                    const Icon = item.icon
                    const isActive = location.pathname === item.path
                    return (
                        <NavLink
                            key={`${item.label}-${index}`}
                            to={item.path}
                            className={`nav-item ${isActive ? 'active' : ''}`}
                        >
                            <motion.div
                                className="nav-item-inner"
                            >
                                {isActive && (
                                    <motion.div
                                        className="nav-active-indicator"
                                        layoutId="activeNav"
                                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                    />
                                )}
                                <Icon size={18} className="nav-icon" />
                                <span>{item.label}</span>
                            </motion.div>
                        </NavLink>
                    )
                })}
            </nav>

            <div className="sidebar-user">
                <div className="user-avatar">AM</div>
                <div className="user-info">
                    <span className="user-name">{t('sidebar.userName')}</span>
                    <span className="user-role">{t('sidebar.userRole')}</span>
                </div>
            </div>
        </motion.aside>
    )
}

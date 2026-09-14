import { useApplication } from '../context/ApplicationContext'
import { useTranslation } from 'react-i18next'
import { motion, AnimatePresence } from 'framer-motion'
import { Radio, Wifi, WifiOff, Clock } from 'lucide-react'
import { EVENT_TYPES } from '../services/websocket'
import './AgentFeedWidget.css'

export default function AgentFeedWidget() {
    const { agentFeed, wsConnected } = useApplication()
    const { t } = useTranslation()

    const isVectorMessage = (message) => /vectorai|indexed|upsert|semantic search|hybrid search|embedding/i.test(message || '')

    const getStatusColor = (status) => {
        switch (status?.toUpperCase()) {
            case 'COMPLETED': return 'success'
            case 'RUNNING': case 'IN_PROGRESS': return 'warning'
            case 'FAILED': case 'ERROR': return 'danger'
            default: return 'info'
        }
    }

    return (
        <div className="agent-feed-widget">
            <div className="afw-header">
                <div className="afw-title">
                    <Radio size={16} className={wsConnected ? 'pulse-icon' : ''} />
                    <h4>{t('feed.title')}</h4>
                </div>
                <span className={`afw-status ${wsConnected ? 'connected' : 'disconnected'}`}>
                    {wsConnected ? <><Wifi size={12} /> {t('common.connected')}</> : <><WifiOff size={12} /> {t('common.offline')}</>}
                </span>
            </div>
            <div className="afw-list">
                {agentFeed.length === 0 ? (
                    <div className="afw-empty">
                        <Radio size={20} />
                        <p>{t('feed.waiting')}</p>
                    </div>
                ) : (
                    <AnimatePresence>
                        {agentFeed.map((update, i) => {
                            // Extract event_type label if provided
                            const eventLabel = update.event_type ? EVENT_TYPES[update.event_type] : null;

                            /* TODO: SARVAM_AI_TRANSLATION — Translate dynamic agent status messages (update.message) into selected language using Sarvam AI API */
                            const displayMessage = eventLabel
                                ? `${eventLabel} - ${update.message}`
                                : update.message;
                            const vectorEvent = isVectorMessage(displayMessage);

                            return (
                                <motion.div
                                    key={`${update.agent}-${update.timestamp}-${i}`}
                                    className={`afw-item ${getStatusColor(update.status)} ${vectorEvent ? 'vector-event' : ''}`}
                                    initial={{ opacity: 0, x: -20, height: 0 }}
                                    animate={{ opacity: 1, x: 0, height: 'auto' }}
                                    exit={{ opacity: 0, x: 20 }}
                                    transition={{ duration: 0.3 }}
                                >
                                    <div className={`afw-dot ${getStatusColor(update.status)}`} />
                                    <div className="afw-content">
                                        <div className="afw-agent-row">
                                            <span className="afw-agent">{update.agent || t('feed.unknownAgent')}</span>
                                            <span className={`afw-badge ${getStatusColor(update.status)}`}>
                                                {update.status}
                                            </span>
                                        </div>
                                        {vectorEvent && <span className="afw-vector-chip">{t('feed.actianVectorAI')}</span>}
                                        <p className="afw-message">{displayMessage}</p>
                                        {update.timestamp && (
                                            <span className="afw-time">
                                                <Clock size={10} />
                                                {new Date(update.timestamp).toLocaleTimeString()}
                                            </span>
                                        )}
                                    </div>
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
                )}
            </div>
        </div>
    )
}

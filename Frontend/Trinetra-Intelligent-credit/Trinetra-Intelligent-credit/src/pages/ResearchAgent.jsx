import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, TrendingUp, FileText, ExternalLink, ChevronDown, RefreshCw, Send, Clock, Shield, Globe, Loader2, Sliders, Play } from 'lucide-react'
import { useApplication } from '../context/ApplicationContext'
import DashboardLayout from '../components/DashboardLayout'
import AgentFeedWidget from '../components/AgentFeedWidget'
import { useTranslation } from 'react-i18next'
import './ResearchAgent.css'

export default function ResearchAgent() {
    const { applicationId, ucsoData, agentFeed, addNote, submitPD, triggerStress, refreshApplication, loading } = useApplication()
    const { t } = useTranslation()

    // Officer notes
    const [officerNote, setOfficerNote] = useState('')
    const [authorName, setAuthorName] = useState('')
    const [isSubmittingNote, setIsSubmittingNote] = useState(false)
    const [noteSuccess, setNoteSuccess] = useState(false)

    // PD Transcript
    const [pdData, setPdData] = useState({ interviewer: '', transcript: '', pd_date: '' })
    const [isSubmittingPD, setIsSubmittingPD] = useState(false)
    const [pdSuccess, setPdSuccess] = useState(false)

    // Stress Simulation
    const [stressData, setStressData] = useState({
        revenue_shock_pct: -20,
        interest_rate_hike_bps: 200,
        working_capital_squeeze_pct: -15,
        raw_material_inflation_pct: 10,
    })
    const [isStressing, setIsStressing] = useState(false)
    const [stressSuccess, setStressSuccess] = useState(false)

    // Feed expansion
    const [expandedItem, setExpandedItem] = useState(null)

    // Refresh
    const [isRecalibrating, setIsRecalibrating] = useState(false)

    const handleRecalibrate = useCallback(async () => {
        setIsRecalibrating(true)
        try {
            await refreshApplication()
        } catch (_) { /* noop */ }
        setTimeout(() => setIsRecalibrating(false), 1000)
    }, [refreshApplication])

    const handleSubmitNote = useCallback(async () => {
        if (!officerNote.trim() || !applicationId) return
        setIsSubmittingNote(true)
        setNoteSuccess(false)
        try {
            await addNote({ author: authorName || t('research.officer'), note: officerNote })
            setOfficerNote('')
            setNoteSuccess(true)
            setTimeout(() => setNoteSuccess(false), 3000)
        } catch (err) {
            console.error('Note submission failed', err)
        } finally {
            setIsSubmittingNote(false)
        }
    }, [officerNote, authorName, applicationId, addNote, t])

    const handleSubmitPD = useCallback(async () => {
        if (!pdData.transcript.trim() || !applicationId) return
        setIsSubmittingPD(true)
        setPdSuccess(false)
        try {
            await submitPD({
                interviewer: pdData.interviewer || t('research.officer'),
                transcript: pdData.transcript,
                pd_date: pdData.pd_date || new Date().toISOString().slice(0, 10),
            })
            setPdData({ interviewer: '', transcript: '', pd_date: '' })
            setPdSuccess(true)
            setTimeout(() => setPdSuccess(false), 3000)
        } catch (err) {
            console.error('PD submission failed', err)
        } finally {
            setIsSubmittingPD(false)
        }
    }, [pdData, applicationId, submitPD, t])

    const handleTriggerStress = useCallback(async () => {
        if (!applicationId) return
        setIsStressing(true)
        setStressSuccess(false)
        try {
            await triggerStress(stressData)
            setStressSuccess(true)
            setTimeout(() => setStressSuccess(false), 3000)
        } catch (err) {
            console.error('Stress trigger failed', err)
        } finally {
            setIsStressing(false)
        }
    }, [applicationId, stressData, triggerStress])

    // Extract risk data from ucsoData — mapped to actual Trinetra Agent UCSO keys
    const riskData = ucsoData?.risk || {}
    // Agent outputs risk.score (0.0 to 1.0, higher = riskier).
    // Invert for the UI ring so higher = safer ("confidence").
    const riskScore = riskData.score != null
        ? Math.round((1.0 - riskData.score) * 100)
        : null
    const riskBand = riskData.band || null // LOW, MEDIUM, HIGH, REJECT
    const riskDecision = riskData.decision || null // APPROVE, REVIEW, REJECT

    // Compliance data from agent
    const complianceData = ucsoData?.compliance || {}
    const complianceStatus = complianceData.status || null // PASS or FAIL
    const missingDocs = complianceData.missing_documents || []
    const compliancePct = Math.round(((4 - missingDocs.length) / 4) * 100)

    const getRiskLevel = (score) => {
        if (score === null) return { label: t('common.pending'), color: 'info' }
        if (score >= 75) return { label: t('common.lowRisk'), color: 'success' }
        if (score >= 50) return { label: t('common.mediumRisk'), color: 'warning' }
        return { label: t('common.highRisk'), color: 'danger' }
    }

    const risk = getRiskLevel(riskScore)
    const displayScore = riskScore !== null ? riskScore : '--'

    // Extract notes from ucsoData
    const existingNotes = ucsoData?.human_notes || ucsoData?.notes || []

    // Build crawler items from agent feed for display
    const crawlerItems = agentFeed.slice(0, 10).map((update, i) => ({
        id: `feed-${i}`,
        type: update.status?.toLowerCase() === 'completed' ? 'news' : update.status?.toLowerCase() === 'failed' ? 'lawsuit' : 'filing',
        icon: update.status?.toLowerCase() === 'completed' ? TrendingUp : update.status?.toLowerCase() === 'failed' ? AlertTriangle : FileText,
        color: update.status?.toLowerCase() === 'completed' ? 'success' : update.status?.toLowerCase() === 'failed' ? 'danger' : 'warning',
        title: update.agent || 'Agent Update',
        source: update.status || 'Processing',
        body: update.message || 'No details available',
        time: update.timestamp ? new Date(update.timestamp).toLocaleTimeString() : 'now',
    }))

    // Fallback static items when no live feed
    const STATIC_ITEMS = [
        {
            id: 'static-1', type: 'filing', icon: FileText, color: 'warning',
            title: t('research.awaitingAgentResults'),
            source: t('research.system'),
            body: t('research.awaitingAgentBody'),
            time: 'now',
        },
    ]

    const displayItems = crawlerItems.length > 0 ? crawlerItems : STATIC_ITEMS

    if (!applicationId) {
        return (
            <DashboardLayout title={t('research.title')} subtitle={t('research.subtitle')}>
                <div className="research-page">
                    <div className="no-app-msg">
                        <AlertTriangle size={24} />
                        <h3>{t('common.noAppFound')}</h3>
                        <p dangerouslySetInnerHTML={{ __html: t('common.noAppMsgResearch') }} />
                    </div>
                </div>
            </DashboardLayout>
        )
    }

    return (
        <DashboardLayout title={t('research.title')} subtitle={t('research.subtitle')}>
            <div className="research-page">
                {/* Alert Banner */}
                {riskBand && (
                    <motion.div
                        className="alert-banner"
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                    >
                        <AlertTriangle size={18} className="alert-icon" />
                        <div className="alert-content">
                            <strong>{t('research.riskBandLabel', { band: riskBand })}</strong>
                            <p>{t('research.defaultProbability')} <b>{riskBand}</b> {t('research.byAgent')}. {riskDecision ? `${t('research.decision')}: ${riskDecision}` : ''} {riskScore !== null ? `| ${t('research.confidence')}: ${riskScore}%` : ''}</p>
                        </div>
                        <button className="btn-secondary alert-btn" onClick={handleRecalibrate}>{t('common.refresh')}</button>
                    </motion.div>
                )}

                <div className="research-grid">
                    {/* Crawler Feed / Live Agent Feed */}
                    <div className="crawler-feed">
                        <div className="feed-header">
                            <div className="feed-title">
                                <Globe size={18} />
                                <h3>{t('research.liveAgentFeed')}</h3>
                            </div>
                            <button className="refresh-btn" onClick={handleRecalibrate}>
                                <RefreshCw size={14} className={isRecalibrating ? 'spin' : ''} />
                                {t('common.refresh')}
                            </button>
                        </div>

                        <div className="feed-items">
                            {/* TODO: SARVAM_AI_TRANSLATION — Translate live web intelligence articles/summaries into selected language using Sarvam AI API */}
                            {displayItems.map((item, index) => {
                                const Icon = item.icon
                                const isExpanded = expandedItem === item.id
                                return (
                                    <motion.div
                                        key={item.id}
                                        className={`feed-item ${item.color}`}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: index * 0.1 }}
                                    >
                                        <div className="fi-header" onClick={() => setExpandedItem(isExpanded ? null : item.id)}>
                                            <div className={`fi-icon ${item.color}`}>
                                                <Icon size={16} />
                                            </div>
                                            <div className="fi-title-area">
                                                <h4>{item.title}</h4>
                                                <span className="fi-source">{item.source}</span>
                                            </div>
                                            <div className="fi-right">
                                                <span className="fi-time"><Clock size={12} /> {item.time}</span>
                                                <ChevronDown size={16} className={`fi-chevron ${isExpanded ? 'expanded' : ''}`} />
                                            </div>
                                        </div>
                                        <AnimatePresence>
                                            {isExpanded && (
                                                <motion.div
                                                    className="fi-body"
                                                    initial={{ height: 0, opacity: 0 }}
                                                    animate={{ height: 'auto', opacity: 1 }}
                                                    exit={{ height: 0, opacity: 0 }}
                                                    transition={{ duration: 0.3 }}
                                                >
                                                    <p>{item.body}</p>
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </motion.div>
                                )
                            })}
                        </div>

                        {/* Agent Feed Widget (WebSocket) */}
                        <div className="feed-ws-section">
                            <AgentFeedWidget />
                        </div>
                    </div>

                    {/* Right Panel */}
                    <div className="research-right">
                        {/* Risk Score */}
                        <div className="risk-card">
                            <div className="rc-header">
                                <h3 className="font-serif">{t('research.currentRiskScore')}</h3>
                                <span className="rc-updated"><Clock size={12} /> {loading ? t('research.refreshing') : t('research.liveFromAgents')}</span>
                            </div>
                            <div className="rc-score-wrapper">
                                <motion.div
                                    className={`rc-score-ring ${risk.color}`}
                                    animate={{ rotate: isRecalibrating ? 360 : 0 }}
                                    transition={{ duration: 2, ease: 'linear', repeat: isRecalibrating ? Infinity : 0 }}
                                >
                                    <svg viewBox="0 0 120 120">
                                        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
                                        <motion.circle
                                            cx="60" cy="60" r="52" fill="none"
                                            strokeWidth="8"
                                            strokeLinecap="round"
                                            strokeDasharray={`${2 * Math.PI * 52}`}
                                            animate={{ strokeDashoffset: riskScore !== null ? 2 * Math.PI * 52 * (1 - riskScore / 100) : 2 * Math.PI * 52 }}
                                            transition={{ duration: 1, ease: 'easeOut' }}
                                            className="score-circle"
                                            transform="rotate(-90 60 60)"
                                        />
                                    </svg>
                                    <div className="rc-score-value">
                                        <motion.span
                                            key={displayScore}
                                            initial={{ opacity: 0, scale: 0.5 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            className="score-num"
                                        >
                                            {displayScore}
                                        </motion.span>
                                        <span className="score-max">/100</span>
                                    </div>
                                </motion.div>
                                <span className={`risk-badge ${risk.color}`}>{risk.label}</span>
                            </div>
                            {isRecalibrating && (
                                <motion.div
                                    className="recalibrating"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                >
                                    <RefreshCw size={14} className="spin" />
                                    {t('research.recalibrating')}
                                </motion.div>
                            )}
                        </div>

                        {/* Officer Note Input (Endpoint 4) */}
                        <div className="officer-card">
                            <div className="oc-header">
                                <Shield size={16} />
                                <h3 className="font-serif">{t('research.creditOfficerNotes')}</h3>
                            </div>
                            <p className="oc-desc">{t('research.notesDesc')}</p>
                            <input
                                className="oc-author-input"
                                placeholder={t('research.namePlaceholder')}
                                value={authorName}
                                onChange={(e) => setAuthorName(e.target.value)}
                            />
                            <textarea
                                className="oc-input"
                                placeholder={t('research.notePlaceholder')}
                                value={officerNote}
                                onChange={(e) => setOfficerNote(e.target.value)}
                                rows={4}
                            />
                            <button
                                className="btn-primary oc-submit"
                                onClick={handleSubmitNote}
                                disabled={!officerNote.trim() || isSubmittingNote}
                            >
                                {isSubmittingNote ? <><Loader2 size={14} className="spin" /> {t('research.submitting')}</> : <><Send size={14} /> {t('research.submitNote')}</>}
                            </button>
                            {noteSuccess && <div className="oc-success">✅ {t('research.noteSuccess')}</div>}

                            {/* Existing notes */}
                            {existingNotes.length > 0 && (
                                <div className="oc-notes">
                                    <h4 className="oc-notes-title">{t('research.previousNotes')}</h4>
                                    {/* TODO: SARVAM_AI_TRANSLATION — Translate credit officer notes into selected language using Sarvam AI API */}
                                    {existingNotes.map((note, i) => (
                                        <motion.div
                                            key={i}
                                            className="oc-note"
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                        >
                                            <span className="note-author">{note.author || t('research.officer')}</span>
                                            <span className="note-time">{note.timestamp ? new Date(note.timestamp).toLocaleString() : ''}</span>
                                            <p>{note.note || note.text}</p>
                                        </motion.div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* PD Transcript (Endpoint 5) */}
                        <div className="officer-card">
                            <div className="oc-header">
                                <FileText size={16} />
                                <h3 className="font-serif">{t('research.pdTitle')}</h3>
                            </div>
                            <p className="oc-desc">{t('research.pdDesc')}</p>
                            <div className="pd-form">
                                <input
                                    className="oc-author-input"
                                    placeholder={t('research.interviewerPlaceholder')}
                                    value={pdData.interviewer}
                                    onChange={(e) => setPdData(prev => ({ ...prev, interviewer: e.target.value }))}
                                />
                                <input
                                    className="oc-author-input"
                                    type="date"
                                    value={pdData.pd_date}
                                    onChange={(e) => setPdData(prev => ({ ...prev, pd_date: e.target.value }))}
                                />
                                {/* TODO: SARVAM_AI_TRANSLATION — Translate PD transcript to/from vernacular Indian languages using Sarvam AI API */}
                                <textarea
                                    className="oc-input"
                                    placeholder={t('research.pdTranscriptPlaceholder')}
                                    value={pdData.transcript}
                                    onChange={(e) => setPdData(prev => ({ ...prev, transcript: e.target.value }))}
                                    rows={4}
                                />
                            </div>
                            <button
                                className="btn-primary oc-submit"
                                onClick={handleSubmitPD}
                                disabled={!pdData.transcript.trim() || isSubmittingPD}
                            >
                                {isSubmittingPD ? <><Loader2 size={14} className="spin" /> {t('research.submitting')}</> : <><Send size={14} /> {t('research.submitPD')}</>}
                            </button>
                            {pdSuccess && <div className="oc-success">✅ {t('research.pdSuccess')}</div>}
                        </div>

                        {/* Stress Simulation (Endpoint 6) */}
                        <div className="officer-card stress-card">
                            <div className="oc-header">
                                <Sliders size={16} />
                                <h3 className="font-serif">{t('research.stressTitle')}</h3>
                            </div>
                            <p className="oc-desc">{t('research.stressDesc')}</p>
                            <div className="stress-form">
                                <div className="stress-field">
                                    <label>{t('research.revenueShock')}</label>
                                    <input
                                        className="oc-author-input"
                                        type="number"
                                        value={stressData.revenue_shock_pct}
                                        onChange={(e) => setStressData(prev => ({ ...prev, revenue_shock_pct: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="stress-field">
                                    <label>{t('research.interestRateHike')}</label>
                                    <input
                                        className="oc-author-input"
                                        type="number"
                                        value={stressData.interest_rate_hike_bps}
                                        onChange={(e) => setStressData(prev => ({ ...prev, interest_rate_hike_bps: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="stress-field">
                                    <label>{t('research.workingCapitalSqueeze')}</label>
                                    <input
                                        className="oc-author-input"
                                        type="number"
                                        value={stressData.working_capital_squeeze_pct}
                                        onChange={(e) => setStressData(prev => ({ ...prev, working_capital_squeeze_pct: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="stress-field">
                                    <label>{t('research.rawMaterialInflation')}</label>
                                    <input
                                        className="oc-author-input"
                                        type="number"
                                        value={stressData.raw_material_inflation_pct}
                                        onChange={(e) => setStressData(prev => ({ ...prev, raw_material_inflation_pct: Number(e.target.value) }))}
                                    />
                                </div>
                            </div>
                            <button
                                className="btn-primary oc-submit"
                                onClick={handleTriggerStress}
                                disabled={isStressing}
                            >
                                {isStressing ? <><Loader2 size={14} className="spin" /> {t('research.running')}</> : <><Play size={14} /> {t('research.runStress')}</>}
                            </button>
                            {stressSuccess && <div className="oc-success">✅ {t('research.stressSuccess')}</div>}
                        </div>

                        {/* Compliance Status */}
                        <div className="officer-card compliance-card">
                            <div className="oc-header">
                                <Shield size={16} />
                                <h3 className="font-serif">{t('research.complianceStatus')}</h3>
                            </div>
                            {complianceStatus ? (
                                <>
                                    <div className={`compliance-badge ${complianceStatus === 'PASS' ? 'pass' : 'fail'}`}>
                                        {complianceStatus === 'PASS' ? t('research.compliancePass') : t('research.complianceFail')}
                                    </div>
                                    <div className="compliance-progress">
                                        <div className="compliance-bar">
                                            <div className="compliance-fill" style={{ width: `${compliancePct}%` }} />
                                        </div>
                                        <span className="compliance-pct">{t('research.docsPresent', { pct: compliancePct })}</span>
                                    </div>
                                    {missingDocs.length > 0 && (
                                        <div className="missing-docs">
                                            <h4>{t('research.missingDocs')}</h4>
                                            <ul>
                                                {missingDocs.map((doc, i) => (
                                                    <li key={`miss-${i}`}>{doc}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <p className="oc-desc">{t('research.awaitingCompliance')}</p>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    )
}

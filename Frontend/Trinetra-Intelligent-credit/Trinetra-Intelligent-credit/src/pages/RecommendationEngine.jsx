import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { CheckCircle, TrendingDown, Activity, FileOutput, Download, ArrowRight, Clock, Zap, DollarSign, Percent, Loader2, RefreshCw, AlertTriangle } from 'lucide-react'
import { useApplication } from '../context/ApplicationContext'
import DashboardLayout from '../components/DashboardLayout'
import AgentFeedWidget from '../components/AgentFeedWidget'
import './RecommendationEngine.css'

function CustomTooltip({ active, payload }) {
    if (active && payload && payload.length) {
        return (
            <div className="chart-tooltip">
                <span className="ct-label">{payload[0].payload.name}</span>
                <span className="ct-value">{payload[0].value}%</span>
            </div>
        )
    }
    return null
}

function buildBarData(riskData, t) {
    const fv = riskData?.feature_vector || {}
    // Agent outputs risk-normalized values (higher = worse).
    // Invert so higher bar = safer for the UI.
    const safeScore = (key) => fv[key] != null ? Math.round((1.0 - fv[key]) * 100) : 0

    return [
        { name: t('recommendation.capacityDSCR'), value: safeScore('dscr_normalized'), fill: '#00d4aa' },
        { name: t('recommendation.leverage'), value: safeScore('leverage_normalized'), fill: '#00b4d8' },
        { name: t('recommendation.operatingMargin'), value: safeScore('ebitda_margin_normalized'), fill: '#10b981' },
        { name: t('recommendation.complianceGST'), value: safeScore('gst_discrepancy_norm'), fill: '#f59e0b' },
        { name: t('recommendation.mgmtSentiment'), value: safeScore('news_sentiment_norm'), fill: '#00d4aa' },
    ]
}

function buildPieData(riskData, t) {
    const risk = riskData || {}
    const riskScore = risk.score // 0.0 to 1.0, higher = riskier

    if (riskScore != null) {
        const safe = Math.round((1.0 - riskScore) * 100)
        const moderate = Math.round(riskScore * 60)
        const weak = Math.max(0, 100 - safe - moderate)
        return [
            { name: t('recommendation.strong'), value: Math.max(0, safe), color: '#00d4aa' },
            { name: t('recommendation.moderate'), value: Math.max(0, moderate), color: '#f59e0b' },
            { name: t('recommendation.weak'), value: Math.max(0, weak), color: '#ef4444' },
        ]
    }

    return [
        { name: t('recommendation.strong'), value: 65, color: '#00d4aa' },
        { name: t('recommendation.moderate'), value: 25, color: '#f59e0b' },
        { name: t('recommendation.weak'), value: 10, color: '#ef4444' },
    ]
}

function deriveCreditScore(riskData) {
    const risk = riskData || {}

    // Derive 300-900 scale from agent's risk score (0.0 = safest → 900, 1.0 = riskiest → 300)
    if (risk.score != null) return Math.round(900 - (risk.score * 600))
    return null
}

function safelyParse(val) {
    if (typeof val === 'string') {
        try { return JSON.parse(val) } catch (e) { return {} }
    }
    return val || {}
}

export default function RecommendationEngine() {
    const { applicationId, ucsoData, agentFeed, refreshApplication, loading } = useApplication()
    const { t, i18n } = useTranslation()
    const [camGenerated, setCamGenerated] = useState(false)
    const [isRefreshing, setIsRefreshing] = useState(false)

    // Auto-refresh every 30 seconds if data incomplete
    useEffect(() => {
        if (!applicationId) return

        console.log("Current ucsoData inside RecommendationEngine:", ucsoData)
        const riskData = safelyParse(ucsoData?.risk)
        const camData = safelyParse(ucsoData?.cam_output)

        const hasRisk = Object.keys(riskData).length > 0
        const hasCam = !!camData?.s3_key
        const isRejected = riskData?.decision === 'REJECT'

        // Stop polling only if we have risk AND (we have CAM or it was rejected)
        if (hasRisk && (hasCam || isRejected)) return

        const interval = setInterval(() => {
            refreshApplication()
        }, 30000)

        return () => clearInterval(interval)
    }, [applicationId, ucsoData, refreshApplication])

    const handleManualRefresh = useCallback(async () => {
        setIsRefreshing(true)
        try {
            await refreshApplication()
        } catch (_) { /* noop */ }
        setTimeout(() => setIsRefreshing(false), 1000)
    }, [refreshApplication])

    const handleRefresh = handleManualRefresh

    const [isGeneratingCam, setIsGeneratingCam] = useState(false)

    const handleDownloadCAM = async () => {
        let camOut = ucsoData?.cam_output
        if (typeof camOut === 'string') {
            try { camOut = JSON.parse(camOut) } catch (e) { camOut = {} }
        }
        const activeLang = i18n.language || 'en'
        const camLang = camOut?.language || 'en'
        const s3Key = camOut?.languages?.[activeLang]?.s3_key || (camLang === activeLang ? camOut?.s3_key : null)

        if (s3Key) {
            if (s3Key.startsWith('http')) {
                const separator = s3Key.includes('?') ? '&' : '?'
                window.open(`${s3Key}${separator}lang=${activeLang}`, '_blank')
            } else {
                import('../services/api').then(({ BASE_URL }) => {
                    const filename = s3Key.includes('/') ? s3Key.split('/').pop() : `CAM_${applicationId}_${activeLang}.docx`
                    window.open(`${BASE_URL}/api/files/${applicationId}?filename=${encodeURIComponent(filename)}&lang=${activeLang}`, '_blank')
                })
            }
        } else {
            setIsGeneratingCam(true)
            try {
                const { ApplicationService } = await import('../services/api')
                if (applicationId) {
                    await ApplicationService.generateCAM(applicationId, activeLang)
                    // Poll until CAM report in activeLang is generated
                    const startTime = Date.now()
                    const pollInterval = setInterval(async () => {
                        try {
                            const updatedApp = await refreshApplication()
                            const updatedCam = safelyParse(updatedApp?.ucso_data?.cam_output)
                            const ready = !!(
                                updatedCam?.languages?.[activeLang]?.s3_key ||
                                (updatedCam?.language === activeLang && updatedCam?.s3_key)
                            )
                            if (ready || Date.now() - startTime > 90000) {
                                clearInterval(pollInterval)
                                setIsGeneratingCam(false)
                            }
                        } catch (_) {
                            if (Date.now() - startTime > 90000) {
                                clearInterval(pollInterval)
                                setIsGeneratingCam(false)
                            }
                        }
                    }, 3000)
                }
            } catch (err) {
                console.log('CAM generation request note:', err?.message)
                setIsGeneratingCam(false)
            }
        }
    }

    // Derive data from ucsoData — mapped to actual Trinetra Agent UCSO keys
    const applicant = safelyParse(ucsoData?.applicant)
    const risk = safelyParse(ucsoData?.risk)
    const compliance = safelyParse(ucsoData?.compliance)
    const camOutput = safelyParse(ucsoData?.cam_output)
    const activeLang = i18n.language || 'en'
    const camLanguage = camOutput?.language || 'en'
    const hasCam = !!(camOutput?.languages?.[activeLang]?.s3_key || (camLanguage === activeLang && camOutput?.s3_key))

    const creditScore = deriveCreditScore(risk)

    const loanAmount = applicant.loan_amount
    // Agent outputs recommended_rate_bps (e.g. 963.8) → convert to percentage
    const suggestedRate = risk.recommended_rate_bps != null ? (risk.recommended_rate_bps / 100).toFixed(2) : null
    const recommendedLimit = risk.recommended_limit
    // Band = default probability category: LOW, MEDIUM, HIGH, REJECT
    const riskBand = risk.band || null
    // Decision = final action: APPROVE, REVIEW, REJECT
    const riskDecision = risk.decision || null

    const barData = buildBarData(risk, t)
    const pieData = buildPieData(risk, t)

    // Build activity from agent feed
    const activityLog = agentFeed.slice(0, 8).map((update, i) => ({
        id: `act-${i}`,
        action: update.agent || 'Agent Update',
        detail: update.status ? String(update.status).toUpperCase() : 'PROCESSING',
        time: update.timestamp ? new Date(update.timestamp).toLocaleTimeString() : 'now',
        status: update.status?.toLowerCase() === 'completed' ? 'success'
            : update.status?.toLowerCase() === 'failed' ? 'warning'
                : 'info',
    }))

    // Fallback activity if no feed
    const STATIC_ACTIVITY = [
        { id: 'sa-1', action: t('recommendation.awaitingResults'), detail: t('recommendation.awaitingResultsDetail'), time: 'now', status: 'info' },
    ]
    const displayActivity = activityLog.length > 0 ? activityLog : STATIC_ACTIVITY

    // AI Decision items from ucsoData — using top_risk_factors array from agent
    const decisions = []
    const topRiskFactors = Array.isArray(risk.top_risk_factors) ? risk.top_risk_factors : []

    if (topRiskFactors.length) {
        topRiskFactors.forEach((factor) => {
            const shapVal = factor.shap_value || factor.contribution || 0
            const featureName = factor.feature || 'Unknown Factor'
            decisions.push({
                icon: shapVal > 0.1 ? TrendingDown : Activity,
                title: featureName
                    .replace(/_normalized/g, '').replace(/_norm/g, '')
                    .replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                color: shapVal > 0.1 ? 'warning' : 'success',
                detail: `SHAP: ${(shapVal * 100).toFixed(1)}% | Weight: ${((factor.weight || 0) * 100).toFixed(0)}%`,
            })
        })
    }

    // Rejection reasons & corrective actions from agent
    const rejectionReasons = Array.isArray(risk.rejection_reasons) ? risk.rejection_reasons : []
    const correctiveActions = Array.isArray(risk.corrective_actions) ? risk.corrective_actions : []

    const AI_DECISIONS = decisions.length > 0 ? decisions : [
        { icon: TrendingDown, title: t('recommendation.cashFlowAnalysis'), color: 'success', detail: t('recommendation.awaitingFinancial') },
        { icon: Activity, title: t('recommendation.debtRatioAnalysis'), color: 'success', detail: t('recommendation.awaitingFinancial') },
        { icon: CheckCircle, title: t('recommendation.marketPosition'), color: 'success', detail: t('recommendation.awaitingFinancial') },
    ]

    if (!applicationId) {
        return (
            <DashboardLayout title={t('recommendation.title')} subtitle={t('recommendation.subtitleNoApp')}>
                <div className="reco-page">
                    <div className="no-app-msg">
                        <AlertTriangle size={24} />
                        <h3>{t('common.noAppFound')}</h3>
                        <p dangerouslySetInnerHTML={{ __html: t('common.noAppMsg') }} />
                    </div>
                </div>
            </DashboardLayout>
        )
    }

    return (
        <DashboardLayout title={t('recommendation.title')} subtitle={t('recommendation.subtitleWithApp', { id: applicationId.slice(0, 8) })}>
            <div className="reco-page">
                {/* Refresh bar */}
                <div className="reco-refresh-bar">
                    <span className="reco-refresh-label">
                        {loading ? <><Loader2 size={14} className="spin" /> {t('recommendation.refreshingData')}</> : t('recommendation.dataFromAgents')}
                    </span>
                    <button className="refresh-btn" onClick={handleRefresh}>
                        <RefreshCw size={14} className={isRefreshing ? 'spin' : ''} />
                        {t('common.refresh')}
                    </button>
                </div>

                {/* Score Cards */}
                <motion.div
                    className="score-cards"
                    initial="initial"
                    animate="animate"
                    variants={{ animate: { transition: { staggerChildren: 0.1 } } }}
                >
                    {[
                        {
                            icon: Zap,
                            label: t('recommendation.trinetraScore'),
                            value: creditScore !== null ? String(creditScore) : '--',
                            sub: creditScore !== null ? t('recommendation.outOf900') : t('common.pending'),
                            color: 'primary',
                            glow: creditScore !== null,
                        },
                        {
                            icon: DollarSign,
                            label: recommendedLimit ? t('recommendation.recommendedLimit') : t('recommendation.loanAmount'),
                            value: recommendedLimit
                                ? `₹${(recommendedLimit / 100000).toFixed(1)}L`
                                : loanAmount ? `₹${(loanAmount / 100000).toFixed(1)}L` : '--',
                            sub: recommendedLimit ? t('recommendation.agentRecommended') : loanAmount ? t('recommendation.asRequested') : t('common.pending'),
                            color: 'success',
                        },
                        {
                            icon: Percent,
                            label: t('recommendation.interestRate'),
                            value: suggestedRate ? `${suggestedRate}%` : '--',
                            sub: suggestedRate ? t('recommendation.agentRecommended') : t('common.pending'),
                            color: 'info',
                        },
                        {
                            icon: Activity,
                            label: t('recommendation.riskAssessment'),
                            value: riskBand || '--',
                            sub: riskDecision ? t('recommendation.decisionLabel', { decision: riskDecision }) : t('common.pending'),
                            color: riskBand === 'LOW' ? 'success' : riskBand === 'REJECT' || riskBand === 'HIGH' ? 'danger' : 'warning',
                        },
                    ].map((card) => (
                        <motion.div
                            key={card.label}
                            className={`score-card ${card.color} ${card.glow ? 'glow' : ''} ${card.label.includes('Limit') || card.label.includes('Loan Amount') ? 'loan-amount-card' : ''}`}
                            variants={{
                                initial: { opacity: 0, y: 20 },
                                animate: { opacity: 1, y: 0 }
                            }}
                            whileHover={{ y: -4, transition: { duration: 0.2 } }}
                        >
                            <div className={`sc-icon-wrap ${card.color}`}>
                                <card.icon size={20} />
                            </div>
                            <span className="sc-label">{card.label}</span>
                            <div className="sc-value-row">
                                <span className={`sc-value ${card.color}`}>{card.value}</span>
                                <span className="sc-sub">{card.sub}</span>
                            </div>
                        </motion.div>
                    ))}
                </motion.div>

                <div className="reco-grid">
                    {/* AI Decision Logic */}
                    <div className="decision-panel">
                        <div className="dp-header">
                            <h3 className="font-serif">{t('recommendation.aiDecisionLogic')}</h3>
                            <span className="dp-sub">
                                {decisions.length > 0
                                    ? t('recommendation.shapAnalysis')
                                    : t('recommendation.awaitingAnalysis')}
                            </span>
                        </div>

                        <div className="decision-items">
                            {AI_DECISIONS.map((item, i) => {
                                const Icon = item.icon
                                return (
                                    <motion.div
                                        key={`${item.title}-${i}`}
                                        className={`decision-item ${item.color}`}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.3 + i * 0.15 }}
                                        whileHover={{ x: 4, transition: { duration: 0.2 } }}
                                    >
                                        <div className={`di-icon ${item.color}`}>
                                            <Icon size={18} />
                                        </div>
                                        <div className="di-content">
                                            <h4>{item.title}</h4>
                                            <p>{item.detail}</p>
                                        </div>
                                    </motion.div>
                                )
                            })}
                        </div>

                        <motion.button
                            className="btn-primary generate-btn"
                            disabled={isGeneratingCam}
                            onClick={() => {
                                handleDownloadCAM()
                            }}
                            whileHover={{ scale: isGeneratingCam ? 1 : 1.02 }}
                            whileTap={{ scale: isGeneratingCam ? 1 : 0.98 }}
                        >
                            {hasCam ? (
                                <>
                                    <Download size={16} />
                                    {t('recommendation.downloadCam')}
                                </>
                            ) : isGeneratingCam ? (
                                <>
                                    <RefreshCw size={16} className="spin" />
                                    {t('recommendation.agentProcessing')}
                                </>
                            ) : (
                                <>
                                    <FileOutput size={16} />
                                    {t('recommendation.generateCam')}
                                </>
                            )}
                        </motion.button>

                        {camGenerated && !hasCam && (
                            <motion.div
                                className="cam-ready"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                            >
                                <div className="cam-info">
                                    <FileOutput size={18} className="cam-icon" />
                                    <div>
                                        <strong>{t('recommendation.creditAppraisalMemo')}</strong>
                                        <span>{t('recommendation.camAutoGenerated')}</span>
                                    </div>
                                </div>
                                <button className="btn-secondary cam-download">
                                    <Download size={14} /> {t('common.download')}
                                </button>
                            </motion.div>
                        )}

                        {/* Rejection Reasons */}
                        {rejectionReasons.length > 0 && (
                            <div className="rejection-section">
                                <h4 className="font-serif rejection-title"><AlertTriangle size={16} /> {t('recommendation.rejectionReasons')}</h4>
                                <ul className="rejection-list">
                                    {/* TODO: SARVAM_AI_TRANSLATION — Translate rejection reasons into selected language using Sarvam AI API */}
                                    {rejectionReasons.map((reason, i) => (
                                        <li key={`rej-${i}`} className="rejection-item">{reason}</li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Corrective Actions */}
                        {correctiveActions.length > 0 && (
                            <div className="corrective-section">
                                <h4 className="font-serif corrective-title"><CheckCircle size={16} /> {t('recommendation.correctiveActions')}</h4>
                                <ul className="corrective-list">
                                    {/* TODO: SARVAM_AI_TRANSLATION — Translate corrective actions into selected language using Sarvam AI API */}
                                    {correctiveActions.map((action, i) => (
                                        <li key={`cor-${i}`} className="corrective-item">{action}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>

                    {/* Charts */}
                    <div className="charts-panel">
                        <div className="chart-card">
                            <h3 className="font-serif">{t('recommendation.assessmentBreakdown')}</h3>
                            <ResponsiveContainer width="100%" height={220}>
                                <BarChart data={barData} barSize={20} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                                    <XAxis
                                        dataKey="name"
                                        tick={{ fill: '#8892a8', fontSize: 11 }}
                                        axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        tick={{ fill: '#8892a8', fontSize: 11 }}
                                        axisLine={false}
                                        tickLine={false}
                                        domain={[0, 100]}
                                    />
                                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                        {barData.map((entry, i) => (
                                            <Cell key={i} fill={entry.fill} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>

                        <div className="chart-card">
                            <h3 className="font-serif">{t('recommendation.riskDistribution')}</h3>
                            <div className="pie-wrapper">
                                <ResponsiveContainer width="100%" height={180}>
                                    <PieChart>
                                        <Pie
                                            data={pieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={50}
                                            outerRadius={75}
                                            paddingAngle={3}
                                            dataKey="value"
                                        >
                                            {pieData.map((entry, i) => (
                                                <Cell key={i} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <Tooltip />
                                    </PieChart>
                                </ResponsiveContainer>
                                <div className="pie-legend">
                                    {pieData.map(d => (
                                        <div key={d.name} className="pl-item">
                                            <span className="pl-dot" style={{ background: d.color }} />
                                            <span className="pl-label">{d.name}</span>
                                            <span className="pl-value">{d.value}%</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="reco-grid">
                    {/* Agent Feed */}
                    <div className="agent-feed-panel">
                        <AgentFeedWidget />
                    </div>

                    {/* Activity Log */}
                    <div className="activity-section">
                        <div className="as-header">
                            <h3 className="font-serif">{t('recommendation.recentActivity')}</h3>
                            <button className="btn-secondary as-btn" onClick={handleRefresh}>
                                <RefreshCw size={12} className={isRefreshing ? 'spin' : ''} /> {t('common.refresh')}
                            </button>
                        </div>
                        <div className="activity-list">
                            {displayActivity.map((item, i) => (
                                <motion.div
                                    key={item.id}
                                    className="activity-item"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.5 + i * 0.1 }}
                                >
                                    <div className={`ai-dot ${item.status}`} />
                                    <div className="ai-content">
                                        <span className="ai-action">{item.action}</span>
                                        <span className="ai-detail">{item.detail}</span>
                                    </div>
                                    <span className="ai-time"><Clock size={11} /> {item.time}</span>
                                </motion.div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    )
}

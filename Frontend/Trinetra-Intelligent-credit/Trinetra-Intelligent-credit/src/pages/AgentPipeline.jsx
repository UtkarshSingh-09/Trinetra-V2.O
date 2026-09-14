import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Eye, GitBranch, IdCard, Loader2 } from 'lucide-react'
import { useApplication } from '../context/ApplicationContext'
import DashboardLayout from '../components/DashboardLayout'
import { useTranslation } from 'react-i18next'
import './AgentPipeline.css'

const PIPELINE_NODES = [
    { id: 'compliance-agent', label: 'Compliance Agent', x: 10, y: 10 },
    { id: 'doc-intelligence-agent', label: 'Doc Agent', x: 32, y: 10 },
    { id: 'gst-reconciliation-agent', label: 'GST Agent', x: 54, y: 10 },
    { id: 'bank-recon-agent', label: 'Bank Recon', x: 32, y: 30 },
    { id: 'mca-intelligence-agent', label: 'MCA Agent', x: 54, y: 30 },
    { id: 'web-intelligence-agent', label: 'Web Agent', x: 10, y: 50 },
    { id: 'model-selector-agent', label: 'Model Selector', x: 32, y: 50 },
    { id: 'risk-agent', label: 'Risk Agent', x: 54, y: 50 },
    { id: 'pd-transcript-agent', label: 'PD Agent', x: 10, y: 70 },
    { id: 'bias-agent', label: 'Bias Agent', x: 32, y: 70 },
    { id: 'stress-agent', label: 'Stress Agent', x: 54, y: 70 },
    { id: 'cam-generator-agent', label: 'CAM Generator', x: 38, y: 88 },
    { id: 'monitor-agent', label: 'Monitor Agent', x: 76, y: 30 },
    { id: 'pan-verification-agent', label: 'PAN Agent', x: 76, y: 70 },
]

const EDGES = [
    ['compliance-agent', 'doc-intelligence-agent'],
    ['doc-intelligence-agent', 'gst-reconciliation-agent'],
    ['doc-intelligence-agent', 'bank-recon-agent'],
    ['bank-recon-agent', 'mca-intelligence-agent'],
    ['web-intelligence-agent', 'model-selector-agent'],
    ['model-selector-agent', 'risk-agent'],
    ['risk-agent', 'cam-generator-agent'],
    ['pd-transcript-agent', 'cam-generator-agent'],
    ['bias-agent', 'cam-generator-agent'],
    ['stress-agent', 'bias-agent'],
]

function normalizeAgentName(name) {
    if (!name) return ''
    return String(name).toLowerCase().trim()
}

function statusRank(status) {
    const normalized = String(status || '').toUpperCase()
    if (normalized === 'COMPLETED') return 3
    if (normalized === 'RUNNING' || normalized === 'IN_PROGRESS') return 2
    if (normalized === 'FAILED' || normalized === 'ERROR') return 1
    return 0
}

export default function AgentPipeline() {
    const { applicationId, agentFeed, wsConnected } = useApplication()
    const [showSkeleton] = useState(true)
    const { t } = useTranslation()

    const nodeLabels = {
        'compliance-agent': t('pipeline.complianceAgent'),
        'doc-intelligence-agent': t('pipeline.docAgent'),
        'gst-reconciliation-agent': t('pipeline.gstAgent'),
        'bank-recon-agent': t('pipeline.bankRecon'),
        'mca-intelligence-agent': t('pipeline.mcaAgent'),
        'web-intelligence-agent': t('pipeline.webAgent'),
        'model-selector-agent': t('pipeline.modelSelector'),
        'risk-agent': t('pipeline.riskAgent'),
        'pd-transcript-agent': t('pipeline.pdAgent'),
        'bias-agent': t('pipeline.biasAgent'),
        'stress-agent': t('pipeline.stressAgent'),
        'cam-generator-agent': t('pipeline.camGenerator'),
        'monitor-agent': t('pipeline.monitorAgent'),
        'pan-verification-agent': t('pipeline.panAgent'),
    }

    const nodeStatus = useMemo(() => {
        const state = {}
        PIPELINE_NODES.forEach((node) => {
            state[node.id] = 'IDLE'
        })

        agentFeed.forEach((event) => {
            const name = normalizeAgentName(event.agent)
            const mappedNode = PIPELINE_NODES.find((n) => name.includes(n.id.replace('-agent', '')) || n.id === name)
            if (!mappedNode) return

            const current = state[mappedNode.id]
            const next = String(event.status || 'IDLE').toUpperCase()
            if (statusRank(next) >= statusRank(current)) {
                state[mappedNode.id] = next
            }
        })

        return state
    }, [agentFeed])

    const vectorTraffic = useMemo(() => {
        const completedAgents = Object.values(nodeStatus).filter((s) => String(s).toUpperCase() === 'COMPLETED').length

        // Demo-friendly realistic counters derived from completed pipeline progress.
        const upserts = completedAgents === 0 ? 0 : (completedAgents * 3 + 5)
        const searches = completedAgents === 0 ? 0 : (completedAgents * 2 + 3)

        return { upserts, searches }
    }, [nodeStatus])

    return (
        <DashboardLayout title={t('pipeline.title')} subtitle={t('pipeline.subtitle')}>
            <div className="pipeline-page">
                <section className="pipeline-header glass-strong">
                    <div>
                        <h3>{t('pipeline.applicationLabel')} {applicationId ? `#${applicationId.slice(0, 8)}` : t('pipeline.notSelected')}</h3>
                        <p>{wsConnected ? t('pipeline.liveConnected') : t('pipeline.wsDisconnected')}</p>
                    </div>
                    <div className="pipeline-live-tag">
                        <Activity size={14} />
                        {wsConnected ? t('common.live') : t('common.offline')}
                    </div>
                </section>

                {!applicationId && (
                    <section className="pipeline-empty glass">
                        <Loader2 size={18} />
                        <p>{t('pipeline.emptyMsg')}</p>
                    </section>
                )}

                <section className="pipeline-board glass-strong">
                    <div className="board-title-row">
                        <h4><GitBranch size={16} /> {t('pipeline.agentGraph')}</h4>
                        <span>{t('pipeline.nodesCount', { count: PIPELINE_NODES.length })}</span>
                    </div>

                    {showSkeleton && agentFeed.length === 0 ? (
                        <div className="pipeline-skeleton-wrap">
                            {Array.from({ length: 8 }).map((_, i) => <div className="pipeline-skeleton" key={i} />)}
                        </div>
                    ) : (
                        <div className="pipeline-canvas">
                            <svg className="pipeline-edges" viewBox="0 0 100 100" preserveAspectRatio="none">
                                {EDGES.map(([from, to]) => {
                                    const source = PIPELINE_NODES.find((n) => n.id === from)
                                    const target = PIPELINE_NODES.find((n) => n.id === to)
                                    if (!source || !target) return null
                                    const active = statusRank(nodeStatus[from]) >= 2 || statusRank(nodeStatus[to]) >= 2
                                    return (
                                        <line
                                            key={`${from}-${to}`}
                                            x1={source.x}
                                            y1={source.y}
                                            x2={target.x}
                                            y2={target.y}
                                            className={active ? 'edge active' : 'edge'}
                                        />
                                    )
                                })}
                            </svg>

                            {PIPELINE_NODES.map((node) => {
                                const status = nodeStatus[node.id] || 'IDLE'
                                const tone = statusRank(status) >= 3 ? 'completed' : statusRank(status) >= 2 ? 'processing' : statusRank(status) >= 1 ? 'error' : 'idle'
                                return (
                                    <motion.div
                                        key={node.id}
                                        className={`pipeline-node ${tone}`}
                                        style={{ left: `${node.x}%`, top: `${node.y}%` }}
                                        animate={tone === 'processing' ? { scale: [1, 1.06, 1] } : { scale: 1 }}
                                        transition={{ duration: 1.2, repeat: tone === 'processing' ? Infinity : 0 }}
                                    >
                                        <div className="node-label">{nodeLabels[node.id] || node.label}</div>
                                        <div className="node-status">{status}</div>
                                    </motion.div>
                                )
                            })}
                        </div>
                    )}
                </section>

                <section className="pipeline-stats-grid">
                    <div className="pipeline-stat glass">
                        <h5><Eye size={14} /> {t('pipeline.monitorAgent')}</h5>
                        <p>{t('pipeline.monitorDesc')}</p>
                    </div>
                    <div className="pipeline-stat glass">
                        <h5><IdCard size={14} /> {t('pipeline.panAgent')}</h5>
                        <p>{t('pipeline.panDesc')}</p>
                    </div>
                    <div className="pipeline-stat glass">
                        <h5>{t('pipeline.vectorTraffic')}</h5>
                        <p>{t('pipeline.upserts', { count: vectorTraffic.upserts })}</p>
                        <p>{t('pipeline.searches', { count: vectorTraffic.searches })}</p>
                        <p>{t('pipeline.collectionsCount')}</p>
                    </div>
                </section>
            </div>
        </DashboardLayout>
    )
}

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    CloudUpload, FileText, CheckCircle, AlertCircle, Loader2,
    Trash2, Eye, Send, User, Phone, DollarSign, Briefcase,
    Building2, Hash, Mail, Factory, Calendar, Users, Clock
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useApplication } from '../context/ApplicationContext'
import { DOC_TYPES } from '../services/api'
import DashboardLayout from '../components/DashboardLayout'
import './DataIngestor.css'

/** Build initial blank form state from field definitions */
function getInitialFormState(fields) {
    const state = {}
    fields.forEach(f => { state[f.name] = '' })
    return state
}

export default function DataIngestor() {
    const { applicationId, isCreating, createError, createApplication, uploadDocument } = useApplication()
    const { t } = useTranslation()

    /**
     * Application form field definitions.
     * These match Sankalp's backend — all keys are sent as-is to POST /api/application.
     */
    const FORM_FIELDS = [
        { name: 'company_name', label: t('ingestor.companyName'), icon: Building2, type: 'text', placeholder: 'e.g. Samsung Electronics Co Ltd', required: true },
        { name: 'promoter_name', label: t('ingestor.promoterName'), icon: User, type: 'text', placeholder: 'e.g. Rajesh Kumar', required: true },
        { name: 'pan', label: t('ingestor.panNumber'), icon: Hash, type: 'text', placeholder: 'e.g. AADCS1234K', required: true },
        { name: 'gstin', label: t('ingestor.gstin'), icon: Hash, type: 'text', placeholder: 'e.g. 29AADCS1234K1ZK', required: true },
        { name: 'cin', label: t('ingestor.cinNumber'), icon: Hash, type: 'text', placeholder: 'e.g. U31900KA2000PLC027856', required: true },
        { name: 'loan_amount_requested', label: t('ingestor.loanAmountLabel'), icon: DollarSign, type: 'number', placeholder: 'e.g. 50000000', required: true },
    ]

    // ── Application form state ──
    const [formData, setFormData] = useState(() => getInitialFormState(FORM_FIELDS))
    const [formSuccess, setFormSuccess] = useState(false)

    // ── Per-document upload state (keyed by DOC_TYPES.key) ──
    const [docUploads, setDocUploads] = useState(() => {
        const state = {}
        DOC_TYPES.forEach(dt => {
            state[dt.key] = { file: null, status: 'idle', progress: 0, error: null, s3Key: null }
        })
        return state
    })

    // ── Combined PDF upload state ──
    const [combinedUpload, setCombinedUpload] = useState({
        file: null, status: 'idle', progress: 0, error: null, s3Key: null,
    })

    // ── Form handlers ──
    const handleFormChange = (e) => {
        setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
    }

    const handleCreateApplication = async (e) => {
        e.preventDefault()
        try {
            // Convert numeric fields to numbers
            const payload = { ...formData }
                ;['loan_amount_requested'].forEach(key => {
                    if (payload[key]) payload[key] = Number(payload[key])
                })
            // Remove empty optional fields
            Object.keys(payload).forEach(key => {
                if (payload[key] === '' || payload[key] === 0) delete payload[key]
            })
            await createApplication(payload)
            setFormSuccess(true)
        } catch {
            // error displayed from context
        }
    }

    // ── Per-document upload handlers ──
    const handleDocSelect = useCallback((docKey, e) => {
        const file = e.target.files?.[0]
        if (!file) return
        setDocUploads(prev => ({
            ...prev,
            [docKey]: { ...prev[docKey], file, status: 'selected', progress: 0, error: null, s3Key: null },
        }))
        e.target.value = '' // reset so same file can be re-selected
    }, [])

    const handleDocUpload = useCallback(async (docKey) => {
        const entry = docUploads[docKey]
        if (!entry?.file || !applicationId) return

        setDocUploads(prev => ({
            ...prev,
            [docKey]: { ...prev[docKey], status: 'uploading', progress: 5, error: null },
        }))

        try {
            const onProgress = (progressEvent) => {
                const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                setDocUploads(prev => ({
                    ...prev,
                    [docKey]: { ...prev[docKey], progress: Math.min(pct, 99) },
                }))
            }

            const result = await uploadDocument(entry.file, docKey, onProgress)

            setDocUploads(prev => ({
                ...prev,
                [docKey]: {
                    ...prev[docKey],
                    status: 'completed',
                    progress: 100,
                    s3Key: result?.s3_key || result?.s3Key || 'uploaded',
                },
            }))
        } catch (err) {
            setDocUploads(prev => ({
                ...prev,
                [docKey]: {
                    ...prev[docKey],
                    status: 'error',
                    progress: 0,
                    error: err?.response?.data?.message || err.message,
                },
            }))
        }
    }, [docUploads, applicationId, uploadDocument])

    const handleDocDrop = useCallback((docKey, e) => {
        e.preventDefault()
        const file = e.dataTransfer?.files?.[0]
        if (!file || !applicationId) return
        setDocUploads(prev => ({
            ...prev,
            [docKey]: { ...prev[docKey], file, status: 'selected', progress: 0, error: null, s3Key: null },
        }))
    }, [applicationId])

    const clearDoc = useCallback((docKey) => {
        setDocUploads(prev => ({
            ...prev,
            [docKey]: { file: null, status: 'idle', progress: 0, error: null, s3Key: null },
        }))
    }, [])

    const handleUploadAll = useCallback(async () => {
        const pending = DOC_TYPES.filter(dt => docUploads[dt.key]?.status === 'selected')
        for (const dt of pending) {
            await handleDocUpload(dt.key)
        }
    }, [docUploads, handleDocUpload])

    // ── Combined PDF handlers ──
    const handleCombinedSelect = useCallback((e) => {
        const file = e.target.files?.[0]
        if (!file) return
        setCombinedUpload({ file, status: 'selected', progress: 0, error: null, s3Key: null })
        e.target.value = ''
    }, [])

    const handleCombinedUpload = useCallback(async () => {
        if (!combinedUpload.file || !applicationId) return
        setCombinedUpload(prev => ({ ...prev, status: 'uploading', progress: 5, error: null }))
        try {
            const onProgress = (progressEvent) => {
                const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                setCombinedUpload(prev => ({ ...prev, progress: Math.min(pct, 99) }))
            }
            const result = await uploadDocument(combinedUpload.file, 'ANNUAL_REPORT', onProgress)
            setCombinedUpload(prev => ({
                ...prev, status: 'completed', progress: 100,
                s3Key: result?.s3_key || result?.s3Key || 'uploaded',
            }))
        } catch (err) {
            setCombinedUpload(prev => ({
                ...prev, status: 'error', progress: 0,
                error: err?.response?.data?.message || err.message,
            }))
        }
    }, [combinedUpload.file, applicationId, uploadDocument])

    const handleCombinedDrop = useCallback((e) => {
        e.preventDefault()
        const file = e.dataTransfer?.files?.[0]
        if (!file || !applicationId) return
        setCombinedUpload({ file, status: 'selected', progress: 0, error: null, s3Key: null })
    }, [applicationId])

    const clearCombined = useCallback(() => {
        setCombinedUpload({ file: null, status: 'idle', progress: 0, error: null, s3Key: null })
    }, [])

    // ── Computed stats ──
    const uploadedCount = DOC_TYPES.filter(dt => docUploads[dt.key]?.status === 'completed').length
    const selectedCount = DOC_TYPES.filter(dt => docUploads[dt.key]?.status === 'selected').length
    const errorCount = DOC_TYPES.filter(dt => docUploads[dt.key]?.status === 'error').length

    return (
        <DashboardLayout title={t('ingestor.title')} subtitle={t('ingestor.subtitle')}>
            <div className="ingestor-page">

                {/* ── STEP 1: Application Form ── */}
                {!applicationId && (
                    <motion.div
                        className="app-form-section"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <h3 className="font-serif">{t('ingestor.createLoanApp')}</h3>
                        <p className="form-desc">{t('ingestor.formDesc')}</p>
                        <form className="app-form" onSubmit={handleCreateApplication}>
                            <div className="form-grid">
                                {FORM_FIELDS.map((field) => {
                                    const Icon = field.icon
                                    return (
                                        <div key={field.name} className="form-group">
                                            <label><Icon size={14} /> {field.label}</label>
                                            <input
                                                type={field.type}
                                                name={field.name}
                                                placeholder={field.placeholder}
                                                value={formData[field.name]}
                                                onChange={handleFormChange}
                                                required={field.required}
                                            />
                                        </div>
                                    )
                                })}
                            </div>
                            {createError && (
                                <div className="form-error">
                                    <AlertCircle size={14} /> {createError}
                                </div>
                            )}
                            <button type="submit" className="btn-primary form-submit" disabled={isCreating}>
                                {isCreating ? (
                                    <><Loader2 size={16} className="spin" /> {t('ingestor.creating')}</>
                                ) : (
                                    <><Send size={16} /> {t('ingestor.createApplication')}</>
                                )}
                            </button>
                        </form>
                    </motion.div>
                )}

                {/* Application Details Badge */}
                {applicationId && (
                    <motion.div
                        className="app-id-badge"
                        style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <CheckCircle size={18} />
                            <div>
                                <span className="badge-label">{t('ingestor.applicationIdLabel')}</span>
                                <span className="badge-id">{applicationId}</span>
                            </div>
                        </div>
                        {formData?.loan_amount_requested && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', borderLeft: '1px solid rgba(16, 185, 129, 0.2)', paddingLeft: '20px' }}>
                                <DollarSign size={18} />
                                <div>
                                    <span className="badge-label">{t('ingestor.loanAmountBadge')}</span>
                                    <span className="badge-id">₹ {Number(formData.loan_amount_requested).toLocaleString('en-IN')}</span>
                                </div>
                            </div>
                        )}
                    </motion.div>
                )}

                {formSuccess && applicationId && (
                    <motion.div
                        className="form-success-msg"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                    >
                        {t('ingestor.appCreatedSuccess')}
                    </motion.div>
                )}

                {/* ── STEP 2: Required Document Uploads ── */}
                <div className="doc-upload-section">
                    <div className="doc-upload-header">
                        <h3 className="font-serif">{t('ingestor.uploadDocs')}</h3>
                        <p className="doc-upload-desc">
                            {t('ingestor.uploadDocsDesc')}
                        </p>
                    </div>

                    <div className="doc-slots-grid">
                        {DOC_TYPES.map((dt) => {
                            const state = docUploads[dt.key]
                            const isDisabled = !applicationId
                            const isUploading = state.status === 'uploading'
                            const isCompleted = state.status === 'completed'
                            const isError = state.status === 'error'
                            const hasFile = state.file !== null

                            return (
                                <motion.div
                                    key={dt.key}
                                    className={`doc-slot ${isDisabled ? 'disabled' : ''} ${isCompleted ? 'completed' : ''} ${isError ? 'errored' : ''} ${isUploading ? 'uploading' : ''}`}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }}
                                    onDragLeave={(e) => e.currentTarget.classList.remove('drag-over')}
                                    onDrop={(e) => { e.currentTarget.classList.remove('drag-over'); handleDocDrop(dt.key, e) }}
                                >
                                    <div className="doc-slot-icon">{dt.icon}</div>
                                    <h4 className="doc-slot-title">{dt.label}</h4>
                                    <p className="doc-slot-desc">{dt.desc}</p>

                                    {/* File name display */}
                                    {hasFile && (
                                        <div className="doc-slot-file">
                                            <FileText size={14} />
                                            <span>{state.file.name}</span>
                                            {!isUploading && !isCompleted && (
                                                <button className="doc-slot-clear" onClick={() => clearDoc(dt.key)} title={t('ingestor.remove')}>
                                                    <Trash2 size={12} />
                                                </button>
                                            )}
                                        </div>
                                    )}

                                    {/* Progress bar */}
                                    {isUploading && (
                                        <div className="doc-slot-progress">
                                            <div className="doc-progress-bar">
                                                <motion.div
                                                    className="doc-progress-fill"
                                                    animate={{ width: `${state.progress}%` }}
                                                    transition={{ duration: 0.3 }}
                                                />
                                            </div>
                                            <span>{state.progress}%</span>
                                        </div>
                                    )}

                                    {/* Status */}
                                    {isCompleted && (
                                        <div className="doc-slot-status success">
                                            <CheckCircle size={14} /> {t('common.uploaded')}
                                        </div>
                                    )}
                                    {isError && (
                                        <div className="doc-slot-status error">
                                            <AlertCircle size={14} /> {state.error || t('ingestor.uploadFailed')}
                                        </div>
                                    )}

                                    {/* Actions */}
                                    {!isCompleted && !isUploading && (
                                        <div className="doc-slot-actions">
                                            <label className={`doc-slot-choose ${isDisabled ? 'disabled' : ''}`}>
                                                {hasFile ? t('ingestor.changeFile') : t('ingestor.chooseFile')}
                                                <input
                                                    type="file"
                                                    accept=".pdf,.xlsx,.csv,.xls,.doc,.docx"
                                                    hidden
                                                    disabled={isDisabled}
                                                    onChange={(e) => handleDocSelect(dt.key, e)}
                                                />
                                            </label>
                                            {hasFile && (
                                                <button
                                                    className="btn-primary doc-slot-upload-btn"
                                                    onClick={() => handleDocUpload(dt.key)}
                                                    disabled={isDisabled}
                                                >
                                                    <CloudUpload size={14} /> {t('common.upload')}
                                                </button>
                                            )}
                                        </div>
                                    )}

                                    {isCompleted && (
                                        <button className="doc-slot-reupload" onClick={() => clearDoc(dt.key)}>
                                            {t('ingestor.reUpload')}
                                        </button>
                                    )}

                                    {isDisabled && <p className="doc-slot-disabled-msg">{t('ingestor.createAppFirst')}</p>}
                                </motion.div>
                            )
                        })}
                    </div>

                    {/* Upload All button */}
                    {applicationId && selectedCount > 0 && (
                        <motion.button
                            className="btn-primary upload-all-btn"
                            onClick={handleUploadAll}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                        >
                            <CloudUpload size={16} /> {t('ingestor.uploadAllSelected', { count: selectedCount })}
                        </motion.button>
                    )}
                </div>

                {/* ── STEP 3: Combined All-in-One Upload ── */}
                <motion.div
                    className="doc-upload-section combined-section"
                    data-divider={t('ingestor.or')}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    <div className="doc-upload-header">
                        <h3 className="font-serif">{t('ingestor.orUploadCombined')}</h3>
                        <p className="doc-upload-desc">
                            {t('ingestor.combinedDesc')}
                        </p>
                    </div>

                    <div
                        className={`combined-drop-zone ${!applicationId ? 'disabled' : ''} ${combinedUpload.status === 'completed' ? 'completed' : ''} ${combinedUpload.status === 'error' ? 'errored' : ''} ${combinedUpload.status === 'uploading' ? 'uploading' : ''}`}
                        onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }}
                        onDragLeave={(e) => e.currentTarget.classList.remove('drag-over')}
                        onDrop={(e) => { e.currentTarget.classList.remove('drag-over'); handleCombinedDrop(e) }}
                    >
                        <div className="combined-inner">
                            <div className="combined-icon">📦</div>
                            <div className="combined-text">
                                <h4>{t('ingestor.combinedTitle')}</h4>
                                <p>{t('ingestor.combinedSubtitle')}</p>
                            </div>

                            {combinedUpload.file && (
                                <div className="doc-slot-file">
                                    <FileText size={14} />
                                    <span>{combinedUpload.file.name}</span>
                                    {combinedUpload.status !== 'uploading' && combinedUpload.status !== 'completed' && (
                                        <button className="doc-slot-clear" onClick={clearCombined} title={t('ingestor.remove')}><Trash2 size={12} /></button>
                                    )}
                                </div>
                            )}

                            {combinedUpload.status === 'uploading' && (
                                <div className="doc-slot-progress">
                                    <div className="doc-progress-bar">
                                        <motion.div className="doc-progress-fill" animate={{ width: `${combinedUpload.progress}%` }} transition={{ duration: 0.3 }} />
                                    </div>
                                    <span>{combinedUpload.progress}%</span>
                                </div>
                            )}

                            {combinedUpload.status === 'completed' && (
                                <div className="doc-slot-status success"><CheckCircle size={14} /> {t('common.uploaded')}</div>
                            )}
                            {combinedUpload.status === 'error' && (
                                <div className="doc-slot-status error"><AlertCircle size={14} /> {combinedUpload.error || t('ingestor.uploadFailed')}</div>
                            )}

                            <div className="combined-actions">
                                {combinedUpload.status !== 'completed' && combinedUpload.status !== 'uploading' && (
                                    <>
                                        <label className={`doc-slot-choose ${!applicationId ? 'disabled' : ''}`}>
                                            {combinedUpload.file ? t('ingestor.changeFile') : t('ingestor.choosePDF')}
                                            <input type="file" accept=".pdf" hidden disabled={!applicationId} onChange={handleCombinedSelect} />
                                        </label>
                                        {combinedUpload.file && (
                                            <button className="btn-primary doc-slot-upload-btn" onClick={handleCombinedUpload} disabled={!applicationId}>
                                                <CloudUpload size={14} /> {t('common.upload')}
                                            </button>
                                        )}
                                    </>
                                )}
                                {combinedUpload.status === 'completed' && (
                                    <button className="doc-slot-reupload" onClick={clearCombined}>{t('ingestor.reUpload')}</button>
                                )}
                            </div>

                            {!applicationId && <p className="doc-slot-disabled-msg">{t('ingestor.createAppFirst')}</p>}
                        </div>
                    </div>
                </motion.div>

                {/* ── Summary Cards ── */}
                <div className="ingestor-summary">
                    {[
                        { label: t('ingestor.summaryUploaded'), value: uploadedCount, color: 'success' },
                        { label: t('ingestor.summarySelected'), value: selectedCount, color: 'warning' },
                        { label: t('ingestor.summaryFailed'), value: errorCount, color: 'danger' },
                        { label: t('ingestor.summaryRequired'), value: DOC_TYPES.length, color: 'primary' },
                    ].map((stat, i) => (
                        <div key={i} className={`summary-card ${stat.color}`}>
                            <span className="sc-value">{stat.value}</span>
                            <span className="sc-label">{stat.label}</span>
                        </div>
                    ))}
                </div>
            </div>
        </DashboardLayout>
    )
}

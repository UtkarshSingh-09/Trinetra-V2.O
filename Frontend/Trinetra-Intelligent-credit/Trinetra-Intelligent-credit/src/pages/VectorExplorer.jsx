import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Database, Filter, Search, Sparkles } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import DashboardLayout from '../components/DashboardLayout'
import { VectorAIService } from '../services/api'
import './VectorExplorer.css'

const DEFAULT_COLLECTION = 'news_articles'

function normalizeScore(raw) {
    if (raw == null) return 0
    const val = Number(raw)
    if (Number.isNaN(val)) return 0
    if (val > 0 && val <= 1) return Number((val * 100).toFixed(2))
    return Number(val.toFixed(2))
}

function getResultScore(item) {
    return normalizeScore(item.score ?? item.similarity ?? item.distance ?? 0)
}

function summarizeResult(item) {
    const metadata = item.metadata || {}
    const text = metadata.text || metadata.chunk || metadata.content || metadata.summary || ''
    if (!text) return 'No preview text available.'
    return text.length > 160 ? `${text.slice(0, 160)}...` : text
}

export default function VectorExplorer() {
    const [collections, setCollections] = useState([])
    const [selectedCollection, setSelectedCollection] = useState(DEFAULT_COLLECTION)
    const [query, setQuery] = useState('fraud in textile company')
    const [debouncedQuery, setDebouncedQuery] = useState('fraud in textile company')
    const [results, setResults] = useState([])
    const [activeDoc, setActiveDoc] = useState(null)
    const [topK, setTopK] = useState(5)
    const [loadingCollections, setLoadingCollections] = useState(true)
    const [loadingResults, setLoadingResults] = useState(false)
    const [hybridEnabled, setHybridEnabled] = useState(false)
    const [filters, setFilters] = useState({
        application_id: '',
        agent: '',
        phase: '',
    })

    const { t } = useTranslation()

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedQuery(query), 300)
        return () => clearTimeout(timer)
    }, [query])

    useEffect(() => {
        const loadCollections = async () => {
            try {
                setLoadingCollections(true)
                const res = await VectorAIService.getCollections()
                const payload = res.data?.collections || []
                const normalized = payload.map((item) => {
                    if (typeof item === 'string') {
                        return {
                            name: item,
                            label: item.replace(/_/g, ' '),
                            owner: 'unknown',
                            icon: '📦',
                        }
                    }
                    return {
                        name: item.name,
                        label: item.label || item.name?.replace(/_/g, ' '),
                        owner: item.owner || 'unknown',
                        icon: item.icon || '📦',
                    }
                })
                setCollections(normalized)
                if (normalized.length > 0 && !normalized.some((c) => c.name === selectedCollection)) {
                    setSelectedCollection(normalized[0].name)
                }
            } catch (error) {
                console.error('Failed to load VectorAI collections', error)
                setCollections([])
            } finally {
                setLoadingCollections(false)
            }
        }

        loadCollections()
    }, [selectedCollection])

    useEffect(() => {
        const runSearch = async () => {
            if (!debouncedQuery.trim()) {
                setResults([])
                setActiveDoc(null)
                return
            }

            try {
                setLoadingResults(true)
                const cleanedFilters = Object.fromEntries(
                    Object.entries(filters).filter(([, value]) => value && value.trim())
                )

                const res = hybridEnabled
                    ? await VectorAIService.hybridSearch({
                        query: debouncedQuery,
                        collection: selectedCollection,
                        top_k: topK,
                        filters: cleanedFilters,
                    })
                    : await VectorAIService.search({
                        query: debouncedQuery,
                        collection: selectedCollection,
                        top_k: topK,
                    })

                const nextResults = res.data?.results || []
                setResults(nextResults)
                setActiveDoc(nextResults[0] || null)
            } catch (error) {
                console.error('VectorAI search failed', error)
                setResults([])
                setActiveDoc(null)
            } finally {
                setLoadingResults(false)
            }
        }

        runSearch()
    }, [debouncedQuery, selectedCollection, topK, hybridEnabled, filters])

    const chartData = useMemo(
        () => results.map((item, index) => ({
            name: item.id || item.document_id || `Result ${index + 1}`,
            score: getResultScore(item),
        })),
        [results]
    )

    const handleFilterChange = (key, value) => {
        setFilters((prev) => ({ ...prev, [key]: value }))
    }

    return (
        <DashboardLayout title={t('vector.title')} subtitle={t('vector.subtitle')}>
            <div className="vector-explorer-page">
                <section className="vector-toolbar glass-strong">
                    <div className="toolbar-left">
                        <div className="toolbar-title-row">
                            <Database size={18} />
                            <h3>{t('vector.searchTitle')}</h3>
                        </div>
                        <div className="search-input-wrap">
                            <Search size={16} />
                            {/* TODO: SARVAM_AI_TRANSLATION — Enable cross-lingual semantic search by translating queries via Sarvam AI API */}
                            <input
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder={t('vector.searchPlaceholder')}
                            />
                        </div>
                    </div>

                    <div className="toolbar-right">
                        <label>
                            {t('vector.collection')}
                            <select value={selectedCollection} onChange={(e) => setSelectedCollection(e.target.value)}>
                                {collections.map((c) => (
                                    <option key={c.name} value={c.name}>{c.name}</option>
                                ))}
                            </select>
                        </label>
                        <label>
                            {t('vector.topK')}
                            <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
                                {[3, 5, 8, 10].map((k) => <option key={k} value={k}>{k}</option>)}
                            </select>
                        </label>
                    </div>
                </section>

                <section className="vector-hybrid glass">
                    <div className="hybrid-head">
                        <label className="hybrid-toggle">
                            <input
                                type="checkbox"
                                checked={hybridEnabled}
                                onChange={(e) => setHybridEnabled(e.target.checked)}
                            />
                            <Filter size={14} />
                            {t('vector.hybridSearch')}
                        </label>
                    </div>
                    <div className="hybrid-fields">
                        <input
                            placeholder="application_id"
                            value={filters.application_id}
                            onChange={(e) => handleFilterChange('application_id', e.target.value)}
                            disabled={!hybridEnabled}
                        />
                        <input
                            placeholder="agent"
                            value={filters.agent}
                            onChange={(e) => handleFilterChange('agent', e.target.value)}
                            disabled={!hybridEnabled}
                        />
                        <input
                            placeholder="phase"
                            value={filters.phase}
                            onChange={(e) => handleFilterChange('phase', e.target.value)}
                            disabled={!hybridEnabled}
                        />
                    </div>
                </section>

                <div className="vector-main-grid">
                    <section className="vector-results glass-strong">
                        <div className="section-head">
                            <h4>{t('vector.results')}</h4>
                            <span>{loadingResults ? t('common.searching') : t('vector.matches', { count: results.length })}</span>
                        </div>

                        {loadingResults ? (
                            <div className="skeleton-list">
                                {Array.from({ length: 4 }).map((_, i) => <div className="skeleton-row" key={i} />)}
                            </div>
                        ) : (
                            <div className="result-list">
                                {results.map((item, idx) => (
                                    <button
                                        key={`${item.id || idx}`}
                                        className={`result-item ${activeDoc === item ? 'active' : ''}`}
                                        onClick={() => setActiveDoc(item)}
                                    >
                                        <span className="result-score">{getResultScore(item)}</span>
                                        <div className="result-meta">
                                            <strong>{item.id || item.document_id || `result-${idx + 1}`}</strong>
                                            <p>{summarizeResult(item)}</p>
                                        </div>
                                    </button>
                                ))}
                                {!results.length && (
                                    <div className="empty-box">
                                        <Sparkles size={18} />
                                        <p>{t('vector.noResults')}</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {!!chartData.length && (
                            <div className="score-chart-wrap">
                                <ResponsiveContainer width="100%" height={220}>
                                    <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(0,0,0,0.08)" />
                                        <XAxis type="number" domain={[0, 'dataMax']} />
                                        <YAxis type="category" dataKey="name" width={120} />
                                        <Tooltip />
                                        <Bar dataKey="score" fill="#111111" radius={[0, 6, 6, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </section>

                    <section className="vector-inspector glass">
                        <div className="section-head">
                            <h4>{t('vector.collectionInspector')}</h4>
                            <span>{selectedCollection}</span>
                        </div>
                        {activeDoc ? (
                            <div className="inspector-body">
                                <p><strong>{t('vector.docId')}</strong> {activeDoc.id || activeDoc.document_id || 'n/a'}</p>
                                <p><strong>{t('vector.similarity')}</strong> {getResultScore(activeDoc)}</p>
                                <p><strong>{t('vector.agent')}</strong> {activeDoc.metadata?.agent || 'unknown'}</p>
                                <p><strong>{t('vector.updated')}</strong> {activeDoc.metadata?.indexed_at || 'unknown'}</p>
                                <div className="metadata-box">
                                    <h5>{t('vector.metadata')}</h5>
                                    <pre>{JSON.stringify(activeDoc.metadata || {}, null, 2)}</pre>
                                </div>
                                <div className="metadata-box">
                                    <h5>{t('vector.embeddingPreview')}</h5>
                                    <pre>{JSON.stringify((activeDoc.vector || []).slice(0, 8), null, 2)}</pre>
                                </div>
                            </div>
                        ) : (
                            <div className="empty-box">
                                <p>{t('vector.selectResult')}</p>
                            </div>
                        )}
                    </section>
                </div>

                <section className="collections-grid glass-strong">
                    <div className="section-head">
                        <h4>{t('vector.allCollections')}</h4>
                        <span>{loadingCollections ? t('common.loading') : t('vector.collectionsCount', { count: collections.length })}</span>
                    </div>
                    {loadingCollections ? (
                        <div className="collection-skeleton-grid">
                            {Array.from({ length: 8 }).map((_, i) => <div className="skeleton-card" key={i} />)}
                        </div>
                    ) : (
                        <div className="collection-cards">
                            {collections.map((collection) => (
                                <button
                                    key={collection.name}
                                    className={`collection-card ${selectedCollection === collection.name ? 'selected' : ''}`}
                                    onClick={() => setSelectedCollection(collection.name)}
                                >
                                    <div className="collection-icon">{collection.icon}</div>
                                    <div>
                                        <h5>{collection.name}</h5>
                                        <p>{collection.owner}</p>
                                        <small>{t('vector.lastUpdated')}</small>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </DashboardLayout>
    )
}

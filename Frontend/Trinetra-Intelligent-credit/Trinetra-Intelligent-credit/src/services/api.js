import axios from 'axios';

// Set VITE_API_BASE_URL in your .env file to the ngrok URL Sankalp shares
// e.g. VITE_API_BASE_URL=https://abc123.ngrok-free.app
const BASE_URL = import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL
    : (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '80') ? '' : 'http://localhost:8000');

if (import.meta.env.DEV) {
    console.log(`🚀 [API] Using BASE_URL: ${BASE_URL}`);
}

const apiClient = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',  // bypass ngrok free-tier interstitial
    },
});

/**
 * Supported document types — must match backend enum.
 * All 4 are required for compliance to pass.
 */
export const DOC_TYPES = [
    { key: 'ANNUAL_REPORT', label: 'Annual Report', icon: '📄', desc: 'Company annual financial report' },
    { key: 'BANK_STMT', label: 'Bank Statement', icon: '🏦', desc: '12-month bank statement' },
    { key: 'GST_RETURN', label: 'GST Return', icon: '📊', desc: 'GST return filings' },
    { key: 'ITR', label: 'ITR Filing', icon: '📋', desc: 'Income Tax Return' },
];

export const ApplicationService = {
    /**
     * Create a new loan application
     * POST /api/application
     * Body is a flexible JSON map — backend stores it under ucsoData.applicant
     */
    createApplication: (data) =>
        apiClient.post('/api/application', data),

    /**
     * Fetch full application (includes all agent namespaces)
     * GET /api/application/{id}
     */
    getApplication: (applicationId) =>
        apiClient.get(`/api/application/${applicationId}`, {
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
            }
        }),

    /**
     * Add a human (credit officer) note
     * POST /api/application/{id}/notes
     */
    addNote: (applicationId, data) =>
        apiClient.post(`/api/application/${applicationId}/notes`, data),

    /**
     * Submit PD (Personal Discussion) transcript
     * POST /api/application/{id}/pd
     */
    submitPD: (applicationId, data) =>
        apiClient.post(`/api/application/${applicationId}/pd`, data),

    /**
     * Trigger a stress-test simulation
     * POST /api/application/{id}/stress
     * Fields: revenue_shock_pct, interest_rate_hike_bps,
     *         working_capital_squeeze_pct, raw_material_inflation_pct
     */
    triggerStress: (applicationId, data) =>
        apiClient.post(`/api/application/${applicationId}/stress`, data),

    /**
     * Upload a document (PDF / file)
     * POST /api/files/upload  (multipart/form-data)
     *
     * IMPORTANT: Do NOT set Content-Type header — let browser set it with boundary.
     * The application_id goes into the form body, NOT the URL.
     *
     * @param {string} applicationId
     * @param {File}   file
     * @param {string} type  'ANNUAL_REPORT' | 'BANK_STMT' | 'GST_RETURN' | 'ITR'
     * @param {Function} onUploadProgress  axios progress callback
     */
    uploadDocument: (applicationId, file, type, onUploadProgress) => {
        const form = new FormData();
        form.append('file', file);
        form.append('application_id', applicationId);
        form.append('type', type || 'ANNUAL_REPORT');
        return apiClient.post('/api/files/upload', form, {
            headers: { 'Content-Type': undefined }, // let browser set boundary
            onUploadProgress,
        });
    },

    /**
     * Generate CAM report with dynamic LLM routing (English vs Telugu)
     * POST /api/application/{id}/generate-cam?lang=en|te
     */
    generateCAM: (applicationId, lang = 'en') =>
        apiClient.post(`/api/application/${applicationId}/generate-cam`, { lang }, {
            params: { lang },
        }),
};

export const VectorAIService = {
    getCollections: () => apiClient.get('/api/vectorai/collections'),

    search: ({ query, collection = 'news_articles', top_k = 5 }) =>
        apiClient.get('/api/vectorai/search', {
            params: {
                q: query,
                collection,
                top_k,
            },
        }),

    hybridSearch: ({ query, collection = 'news_articles', top_k = 5, filters = {} }) =>
        apiClient.post('/api/vectorai/hybrid-search', {
            query,
            collection,
            top_k,
            filters,
        }),
};

export { BASE_URL };
export default apiClient;

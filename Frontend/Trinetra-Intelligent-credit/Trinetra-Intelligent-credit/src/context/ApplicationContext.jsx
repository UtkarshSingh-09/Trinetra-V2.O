import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { ApplicationService } from '../services/api';
import { subscribeToAgentFeed } from '../services/websocket';

const ApplicationContext = createContext(null);

/**
 * Global state for the current loan application session.
 * Wrap your app (or the dashboard routes) with <ApplicationProvider>.
 */
export function ApplicationProvider({ children }) {
    const [applicationId, setApplicationId] = useState(
        () => sessionStorage.getItem('applicationId') || null
    );
    const [ucsoData, setUcsoData] = useState(null);
    const [agentFeed, setAgentFeed] = useState([]);  // live WS messages
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [wsConnected, setWsConnected] = useState(false);
    const wsClientRef = useRef(null);

    /** Create application and persist ID */
    const createApplication = useCallback(async (formData) => {
        setIsCreating(true);
        setCreateError(null);
        try {
            const res = await ApplicationService.createApplication(formData);
            const data = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;

            // FastAPI returns { id: "..." }, Spring Boot returned { applicationId: "..." }
            const appId = data.id || data.applicationId;
            setApplicationId(appId);
            setUcsoData(data.ucsoData || data);
            sessionStorage.setItem('applicationId', appId);
            return data;
        } catch (err) {
            const msg = err?.response?.data?.message || err?.response?.data || err.message;
            setCreateError(typeof msg === 'string' ? msg : JSON.stringify(msg));
            throw err;
        } finally {
            setIsCreating(false);
        }
    }, []);

    /** Refresh full application data from backend */
    const refreshApplication = useCallback(async (id) => {
        const targetId = id || applicationId;
        if (!targetId) return;
        setLoading(true);
        try {
            const res = await ApplicationService.getApplication(targetId);
            const data = res.data;
            setUcsoData(data.ucsoData || data);
            return data;
        } catch (err) {
            console.error('Failed to refresh application', err);
        } finally {
            setLoading(false);
        }
    }, [applicationId]);

    /** Add a human note (Endpoint 4) */
    const addNote = useCallback(async (noteData) => {
        if (!applicationId) return;
        try {
            const res = await ApplicationService.addNote(applicationId, {
                author: noteData.author || 'Credit Officer',
                note: noteData.note,
                timestamp: new Date().toISOString(),
            });
            setUcsoData(res.data?.ucsoData || res.data);
            return res.data;
        } catch (err) {
            console.error('Failed to add note', err);
            throw err;
        }
    }, [applicationId]);

    /** Submit PD transcript (Endpoint 5) */
    const submitPD = useCallback(async (pdData) => {
        if (!applicationId) return;
        try {
            const res = await ApplicationService.submitPD(applicationId, pdData);
            setUcsoData(res.data?.ucsoData || res.data);
            return res.data;
        } catch (err) {
            console.error('Failed to submit PD', err);
            throw err;
        }
    }, [applicationId]);

    /** Trigger stress simulation (Endpoint 6) */
    const triggerStress = useCallback(async (stressData) => {
        if (!applicationId) return;
        try {
            const res = await ApplicationService.triggerStress(applicationId, stressData);
            return res.data;
        } catch (err) {
            console.error('Failed to trigger stress', err);
            throw err;
        }
    }, [applicationId]);

    /** Upload document (Endpoint 7) */
    const uploadDocument = useCallback(async (file, type, onProgress) => {
        if (!applicationId) throw new Error('No applicationId — create application first');
        try {
            const res = await ApplicationService.uploadDocument(applicationId, file, type, onProgress);
            return res.data;
        } catch (err) {
            console.error('Failed to upload document', err);
            throw err;
        }
    }, [applicationId]);

    /** Push a new live agent message onto the feed */
    const pushAgentUpdate = useCallback((update) => {
        setAgentFeed((prev) => [update, ...prev].slice(0, 50)); // keep last 50
    }, []);

    /** WebSocket: auto-connect when applicationId is set */
    useEffect(() => {
        if (!applicationId) return;

        // Clean up previous connection
        if (wsClientRef.current) {
            try { wsClientRef.current.close(); } catch (_) { /* noop */ }
        }

        const connectWebSocket = () => {
            const client = subscribeToAgentFeed(applicationId, (update) => {
                pushAgentUpdate(update);
                // Also refresh the full application data when agent completes
                if (update.status === 'COMPLETED' || update.status === 'completed') {
                    refreshApplication();
                }
            });

            if (!client) return;

            wsClientRef.current = client;

            // Track connection status natively
            client.onopen = (event) => {
                setWsConnected(true);
            };

            client.onclose = () => {
                setWsConnected(false);
                console.log('🔴 WebSocket disconnected');
                // Auto-reconnect after 3 seconds if we still have an applicationId
                if (sessionStorage.getItem('applicationId')) {
                    setTimeout(() => connectWebSocket(), 3000);
                }
            };
        };

        connectWebSocket();

        return () => {
            if (wsClientRef.current) {
                try { wsClientRef.current.close(); } catch (_) { /* noop */ }
            }
            setWsConnected(false);
        };
    }, [applicationId, pushAgentUpdate, refreshApplication]);

    /** Auto-fetch application data on mount if we have a persisted ID */
    useEffect(() => {
        if (applicationId && !ucsoData) {
            refreshApplication();
        }
    }, [applicationId, ucsoData, refreshApplication]);

    /** Clear session to start over */
    const resetSession = useCallback(() => {
        sessionStorage.removeItem('applicationId');
        setApplicationId(null);
        setUcsoData(null);
        setAgentFeed([]);
        setCreateError(null);
        if (wsClientRef.current) {
            try { wsClientRef.current.close(); } catch (_) { /* noop */ }
            wsClientRef.current = null;
        }
    }, []);

    const value = {
        applicationId,
        ucsoData,
        agentFeed,
        isCreating,
        createError,
        loading,
        wsConnected,
        createApplication,
        refreshApplication,
        pushAgentUpdate,
        setUcsoData,
        addNote,
        submitPD,
        triggerStress,
        uploadDocument,
        resetSession,
    };

    return (
        <ApplicationContext.Provider value={value}>
            {children}
        </ApplicationContext.Provider>
    );
}

export function useApplication() {
    const ctx = useContext(ApplicationContext);
    if (!ctx) throw new Error('useApplication must be used within ApplicationProvider');
    return ctx;
}

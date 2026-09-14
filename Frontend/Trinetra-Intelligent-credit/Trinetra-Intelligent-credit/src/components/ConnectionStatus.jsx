import { useApplication } from '../context/ApplicationContext'
import { useTranslation } from 'react-i18next'
import { Wifi, WifiOff } from 'lucide-react'
import './ConnectionStatus.css'

export default function ConnectionStatus() {
    const { wsConnected, applicationId } = useApplication()
    const { t } = useTranslation()

    if (!applicationId) return null

    return (
        <div className={`connection-status ${wsConnected ? 'connected' : 'disconnected'}`}>
            {wsConnected ? (
                <><Wifi size={12} /> <span>{t('common.live')}</span></>
            ) : (
                <><WifiOff size={12} /> <span>{t('common.offline')}</span></>
            )}
        </div>
    )
}

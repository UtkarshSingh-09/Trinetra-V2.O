import { useTranslation } from 'react-i18next'
import './LanguageSwitcher.css'

export default function LanguageSwitcher() {
    const { i18n } = useTranslation()

    const handleChange = (e) => {
        i18n.changeLanguage(e.target.value)
    }

    return (
        <select
            className="language-switcher"
            value={i18n.language}
            onChange={handleChange}
        >
            <option value="en">English</option>
            <option value="te">తెలుగు</option>
            <option value="ta">தமிழ்</option>
        </select>
    )
}

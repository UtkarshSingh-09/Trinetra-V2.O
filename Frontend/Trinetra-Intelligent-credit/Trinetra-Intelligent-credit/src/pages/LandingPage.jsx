import { useRef, useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform, useInView, useMotionValue, useSpring } from 'framer-motion'
import { ArrowRight, ArrowUpRight, Shield, Brain, Landmark, Globe, Database } from 'lucide-react'
import { SiSap, SiOracle, SiStripe } from 'react-icons/si'
import { FaAws } from 'react-icons/fa'
import Spline from '@splinetool/react-spline'
import AmbientRingsBackground from '../components/AmbientRingsBackground'
import { useTranslation } from 'react-i18next'
import LanguageSwitcher from '../components/LanguageSwitcher'
import './LandingPage.css'

const fadeUp = {
    initial: { opacity: 0, y: 60 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] }
}

// ── Cursor-Following Glow ────────────────────────────────────────────
function CursorGlow() {
    const mouseX = useMotionValue(0)
    const mouseY = useMotionValue(0)

    const springX = useSpring(mouseX, { stiffness: 80, damping: 20 })
    const springY = useSpring(mouseY, { stiffness: 80, damping: 20 })

    useEffect(() => {
        const handleMove = (e) => {
            mouseX.set(e.clientX)
            mouseY.set(e.clientY)
        }
        window.addEventListener('mousemove', handleMove)
        return () => window.removeEventListener('mousemove', handleMove)
    }, [mouseX, mouseY])

    return (
        <motion.div
            className="cursor-glow"
            style={{
                left: springX,
                top: springY,
            }}
        />
    )
}

// ── 3D Tilt Card ─────────────────────────────────────────────────────
function TiltCard({ children, className }) {
    const ref = useRef(null)
    const [tilt, setTilt] = useState({ x: 0, y: 0 })
    const [glowPos, setGlowPos] = useState({ x: 50, y: 50 })

    const handleMouseMove = useCallback((e) => {
        if (!ref.current) return
        const rect = ref.current.getBoundingClientRect()
        const x = e.clientX - rect.left
        const y = e.clientY - rect.top
        const rotateX = ((y / rect.height) - 0.5) * -18
        const rotateY = ((x / rect.width) - 0.5) * 18
        setTilt({ x: rotateX, y: rotateY })
        setGlowPos({ x: (x / rect.width) * 100, y: (y / rect.height) * 100 })
    }, [])

    const handleMouseLeave = useCallback(() => {
        setTilt({ x: 0, y: 0 })
        setGlowPos({ x: 50, y: 50 })
    }, [])

    return (
        <motion.div
            ref={ref}
            className={`tilt-card ${className || ''}`}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            animate={{ rotateX: tilt.x, rotateY: tilt.y }}
            transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            style={{ transformStyle: 'preserve-3d', perspective: 1000 }}
        >
            {/* Inner glow highlight */}
            <div
                className="tilt-glow"
                style={{
                    background: `radial-gradient(circle at ${glowPos.x}% ${glowPos.y}%, rgba(204,255,0,0.18) 0%, transparent 60%)`
                }}
            />
            <div style={{ transform: 'translateZ(20px)', position: 'relative', zIndex: 1 }}>
                {children}
            </div>
        </motion.div>
    )
}

// ── Animated Section ─────────────────────────────────────────────────
function AnimatedSection({ children, className, id }) {
    const ref = useRef(null)
    const isInView = useInView(ref, { once: true, margin: '-100px' })
    return (
        <motion.section
            ref={ref}
            id={id}
            className={className}
            initial={{ opacity: 0, y: 80 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        >
            {children}
        </motion.section>
    )
}

// ── Compact Ticker ────────────────────────────────────────────────────
function TickerTape({ text }) {
    return (
        <div className="ticker-wrapper">
            <motion.div
                className="ticker-track"
                animate={{ x: ['0%', '-50%'] }}
                transition={{ duration: 25, ease: 'linear', repeat: Infinity }}
            >
                <span>{text}&nbsp;&nbsp;&nbsp;{text}&nbsp;&nbsp;&nbsp;{text}&nbsp;&nbsp;&nbsp;{text}&nbsp;&nbsp;&nbsp;{text}</span>
            </motion.div>
        </div>
    )
}

// ── Card Scroll Wrapper ──────────────────────────────────────────────────
const CardWrapper = ({ index, totalCards, children }) => {
    const targetRef = useRef(null);
    const { scrollYProgress } = useScroll({
        target: targetRef,
        offset: ["start 15vh", "end 15vh"]
    });

    const scale = useTransform(scrollYProgress, [0, 1], [1, 1 - (totalCards - index - 1) * 0.05]);
    const filter = useTransform(scrollYProgress, [0, 1], ["brightness(1)", "brightness(0.6)"]);
    const isLast = index === totalCards - 1;

    return (
        <div ref={targetRef} className="card-scroll-wrapper" style={{ height: isLast ? 'auto' : '85vh', position: 'relative', width: '100%' }}>
            <motion.div
                className="stacking-card glass"
                style={{
                    position: 'sticky',
                    top: `calc(15vh + ${index * 20}px)`,
                    scale: isLast ? 1 : scale,
                    filter: isLast ? 'brightness(1)' : filter,
                    transformOrigin: 'top center',
                }}
            >
                {children}
            </motion.div>
        </div>
    );
};

export default function LandingPage() {
    const { t } = useTranslation()
    const containerRef = useRef(null)
    const { scrollYProgress } = useScroll({ target: containerRef, offset: ['start start', 'end end'] })

    const heroY = useTransform(scrollYProgress, [0, 0.2], [0, 150])
    const heroOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0])
    const shape1Y = useTransform(scrollYProgress, [0, 1], [0, -400])
    const shape2Y = useTransform(scrollYProgress, [0, 1], [0, 300])
    const rotateShape = useTransform(scrollYProgress, [0, 1], [0, 90])

    return (
        <div className="landing-page" ref={containerRef}>

            {/* Cursor-following acid green glow */}
            <CursorGlow />

            {/* Background Moving Elements */}
            <div className="bg-elements">
                <motion.div className="bg-shape shape-1" style={{ y: shape1Y, rotate: rotateShape }} />
                <motion.div className="bg-shape shape-2" style={{ y: shape2Y, rotate: rotateShape }} />
            </div>

            {/* Premium Ambient Background */}
            <AmbientRingsBackground />

            {/* ── Glassmorphism Navigation ── */}
            <motion.nav
                className="landing-nav"
                initial={{ y: -80, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            >
                <div className="nav-container">
                    <div className="nav-brand">
                        <div className="brand-dot" />
                        <span className="brand-name">{t('sidebar.brand')}</span>
                    </div>
                    <div className="nav-links">
                        <a href="#solutions">{t('landing.solutions')}</a>
                        <a href="#platform">{t('landing.platform')}</a>
                        <a href="#integrations">{t('landing.ecosystem')}</a>
                    </div>
                    <div className="nav-actions">
                        <LanguageSwitcher />
                        <button className="btn-secondary nav-ghost-btn">{t('landing.clientPortal')}</button>
                        <Link to="/ingestor" className="btn-primary nav-cta-btn">
                            {t('landing.initializeApp')} <ArrowUpRight size={14} />
                        </Link>
                    </div>
                </div>
            </motion.nav>

            {/* ── Hero Section ── */}
            <section className="hero">
                <motion.div className="hero-content" style={{ y: heroY, opacity: heroOpacity }}>

                    {/* Live badge */}
                    <motion.div className="hero-overhead" {...fadeUp}>
                        <div className="pulse-indicator" />
                        <span>{t('landing.liveBadge')}</span>
                    </motion.div>

                    <div className="hero-split-layout">
                        {/* Left Column: Text & CTA */}
                        <div className="hero-text-content">
                            {/* Giant Titles */}
                            <div className="hero-title-wrapper">
                                <motion.h1
                                    className="hero-title-main"
                                    initial={{ opacity: 0, x: -80 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ duration: 1, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
                                >
                                    {t('landing.heroTitle1')}
                                </motion.h1>
                                <motion.h1
                                    className="hero-title-sub"
                                    initial={{ opacity: 0, x: 80 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ duration: 1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
                                >
                                    {t('landing.heroTitle2')}
                                </motion.h1>
                                <motion.h1
                                    className="hero-title-accent"
                                    initial={{ opacity: 0, y: 60 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 1, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
                                >
                                    <span className="highlight-text">{t('landing.heroTitle3')}</span>
                                </motion.h1>
                            </div>

                            <motion.div
                                className="hero-description-block"
                                initial={{ opacity: 0, y: 40 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.9, delay: 0.5 }}
                            >
                                <p className="hero-description">
                                    {t('landing.heroCopy')}
                                </p>
                                <div className="hero-cta">
                                    <Link to="/ingestor" className="btn-primary btn-xl">
                                        {t('landing.startAnalysis')} <ArrowRight size={18} />
                                    </Link>
                                    <button className="btn-icon-only" aria-label="Watch Video">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                            <polygon points="5 3 19 12 5 21 5 3" />
                                        </svg>
                                    </button>
                                </div>
                            </motion.div>
                        </div>

                        {/* Right Column: Spline Robot */}
                        <motion.div
                            className="hero-visual-right"
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.7, duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                        >
                            <div className="spline-container">
                                <Spline scene="https://prod.spline.design/mDHgPoEvQXt62R-q/scene.splinecode" />
                            </div>
                        </motion.div>
                    </div>
                </motion.div>
            </section>

            {/* ── Compact Ticker ── */}
            <TickerTape text={t('landing.ticker')} />

            {/* ── Core Modules ── */}
            <AnimatedSection className="modules-section" id="platform">
                <div className="section-header-left">
                    <h2>{t('landing.modulesTitle').split('\n').map((line, i) => <span key={i}>{line}{i === 0 && <br />}</span>)}</h2>
                    <p>{t('landing.modulesSubtitle')}</p>
                </div>

                <div className="stacking-cards-container">
                    {/* Card 1: Ingestion */}
                    <CardWrapper index={0} totalCards={3}>
                        <div className="stack-card-inner">
                            <div className="stack-text">
                                <span className="premium-badge badge-neutral">
                                    <span className="badge-dot" /> {t('landing.badge01')}
                                </span>
                                <h2>{t('landing.card1Title')}</h2>
                                <p>{t('landing.card1Body')}</p>
                                <ul className="premium-feature-list">
                                    <li>{t('landing.card1Feat1')}</li>
                                    <li>{t('landing.card1Feat2')}</li>
                                    <li>{t('landing.card1Feat3')}</li>
                                </ul>
                            </div>
                            <div className="stack-visual light-bg">
                                <div className="vercel-mock-card">
                                    <div className="mock-card-header">
                                        <div className="mock-title">query <strong>getFinancials</strong> <ArrowUpRight size={14} /></div>
                                        <div className="mock-subtitle">7.15M Documents &nbsp;•&nbsp; 9% &nbsp;•&nbsp; 734ms P95</div>
                                    </div>
                                    <div className="mock-card-body split">
                                        <div className="mock-stat-block">
                                            <span className="stat-label">{t('landing.extractionAccuracy')}</span>
                                            <div className="stat-value-row">
                                                <div className="spinner-pie" />
                                                <span className="huge-number">99.3<span className="percent">%</span></span>
                                            </div>
                                            <span className="stat-trend positive">{t('landing.upFrom')}</span>
                                        </div>
                                        <div className="mock-stat-block right-align">
                                            <span className="stat-label">{t('landing.maxConfidence')}</span>
                                            <span className="huge-number">99.9<span className="percent">%</span></span>
                                            <span className="stat-impact">{t('landing.ocrImpact')}</span>
                                        </div>
                                    </div>
                                    <div className="mock-card-footer">
                                        <div className="mock-bar-header">
                                            <span className="bar-title">90.5 GB <span className="faded">(69.8%)</span></span>
                                        </div>
                                        <div className="mock-progress-track">
                                            <div className="mock-progress-fill" style={{ width: '30%' }} />
                                            <div className="mock-progress-fill light" style={{ width: '40%' }} />
                                        </div>
                                        <ul className="mock-legend">
                                            <li><span className="dot purple" /> Parsed 12.8 GB (9.8%)</li>
                                            <li><span className="dot dark-purple" /> Raw Images 26.3 GB (20.3%)</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </CardWrapper>

                    {/* Card 2: Analysis */}
                    <CardWrapper index={1} totalCards={3}>
                        <div className="stack-card-inner">
                            <div className="stack-text">
                                <span className="premium-badge badge-neutral">
                                    <span className="badge-dot" /> {t('landing.badge02')}
                                </span>
                                <h2>{t('landing.card2Title')}</h2>
                                <p>{t('landing.card2Body')}</p>
                                <ul className="premium-feature-list">
                                    <li>{t('landing.card2Feat1')}</li>
                                    <li>{t('landing.card2Feat2')}</li>
                                    <li>{t('landing.card2Feat3')}</li>
                                </ul>
                            </div>
                            <div className="stack-visual light-bg">
                                <div className="vercel-mock-card">
                                    <div className="mock-card-header">
                                        <div className="mock-title">agent <strong>MarketScan</strong> <ArrowUpRight size={14} /></div>
                                        <div className="mock-subtitle">Active Instances &nbsp;•&nbsp; 12.4K Req/s</div>
                                    </div>
                                    <div className="mock-card-body">
                                        <div className="mock-stat-block">
                                            <span className="stat-label">{t('landing.anomaliesDetected')}</span>
                                            <div className="stat-value-row">
                                                <span className="huge-number">1,204</span>
                                            </div>
                                        </div>
                                        <div className="mock-activity-graph">
                                            {/* Simulate a bar chart */}
                                            {[40, 60, 30, 80, 50, 90, 45, 75, 20, 100, 65, 85].map((h, i) => (
                                                <div key={i} className={`mock-bar ${h > 70 ? 'alert' : ''}`} style={{ height: `${h}%` }} />
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </CardWrapper>

                    {/* Card 3: Decision */}
                    <CardWrapper index={2} totalCards={3}>
                        <div className="stack-card-inner">
                            <div className="stack-text">
                                <span className="premium-badge badge-neutral">
                                    <span className="badge-dot" /> {t('landing.badge03')}
                                </span>
                                <h2>{t('landing.card3Title')}</h2>
                                <p>{t('landing.card3Body')}</p>
                                <ul className="premium-feature-list">
                                    <li>{t('landing.card3Feat1')}</li>
                                    <li>{t('landing.card3Feat2')}</li>
                                    <li>{t('landing.card3Feat3')}</li>
                                </ul>
                                <Link to="/recommendation" className="btn-primary" style={{ marginTop: '24px' }}>{t('landing.exploreSDK')}</Link>
                            </div>
                            <div className="stack-visual light-bg">
                                <div className="vercel-mock-card">
                                    <div className="mock-card-header">
                                        <div className="mock-title">generate <strong>CAM_Report</strong> <ArrowUpRight size={14} /></div>
                                        <div className="mock-subtitle">Avg. Generation Time &nbsp;•&nbsp; 2.4s</div>
                                    </div>
                                    <div className="mock-card-body split align-center">
                                        <div className="mock-status-circle border-green">
                                            <span>{t('landing.ready')}</span>
                                        </div>
                                        <div className="mock-doc-lines">
                                            <div className="doc-line w-full" />
                                            <div className="doc-line w-3/4" />
                                            <div className="doc-line w-1/2" />
                                            <div className="doc-line w-full mt" />
                                        </div>
                                    </div>
                                    <div className="mock-card-footer flex-row">
                                        <button className="mock-btn primary">{t('landing.downloadPDF')}</button>
                                        <button className="mock-btn secondary">{t('landing.viewSource')}</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </CardWrapper>
                </div>
            </AnimatedSection>

            {/* ── Features ── */}
            <AnimatedSection className="features-section" id="solutions">
                <div className="features-editorial-layout">
                    <div className="features-sticky-column">
                        <h2>{t('landing.featuresTitle')}</h2>
                        <p>{t('landing.featuresSub')}</p>
                        <Link to="/ingestor" className="btn-primary" style={{ marginTop: '32px' }}>{t('landing.beginNow')}</Link>
                    </div>

                    <div className="features-scrolling-column">
                        {[
                            { icon: Shield, title: t('landing.feat1Title'), desc: t('landing.feat1Desc') },
                            { icon: Landmark, title: t('landing.feat2Title'), desc: t('landing.feat2Desc') },
                            { icon: Brain, title: t('landing.feat3Title'), desc: t('landing.feat3Desc') },
                            { icon: Globe, title: t('landing.feat4Title'), desc: t('landing.feat4Desc') }
                        ].map((feat, i) => (
                            <motion.div
                                key={i}
                                className="feature-block"
                                initial={{ opacity: 0, x: 50 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true, margin: '-50px' }}
                                transition={{ duration: 0.6, delay: i * 0.1 }}
                            >
                                <div className="feat-icon-ring">
                                    <feat.icon size={24} strokeWidth={1.5} />
                                </div>
                                <div className="feat-text">
                                    <h4>{feat.title}</h4>
                                    <p>{feat.desc}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </AnimatedSection>

            {/* ── Integrations ── */}
            <AnimatedSection className="integrations-section" id="integrations">
                <div className="centered-header">
                    <h2>{t('landing.integrationsTitle')}</h2>
                    <p>{t('landing.integrationsSub')}</p>
                </div>

                <div className="integration-grid">
                    {[
                        { name: 'Actian VectorAI', Icon: Database, highlight: true },
                        { name: 'SAP ERP', Icon: SiSap },
                        { name: 'Oracle DB', Icon: SiOracle },
                        { name: 'AWS S3', Icon: FaAws },
                        { name: 'Stripe', Icon: SiStripe }
                    ].map((app, i) => (
                        <motion.div
                            key={i}
                            className={`integration-pill glass ${app.highlight ? 'highlight' : ''}`}
                            whileHover={{ scale: 1.05, y: -5 }}
                        >
                            <app.Icon size={22} />
                            <span>{app.name}</span>
                        </motion.div>
                    ))}
                </div>
            </AnimatedSection>

            {/* ── Footer ── */}
            <footer className="editorial-footer">
                <div className="footer-cta glass-strong">
                    <h2>{t('landing.footerCTA')}</h2>
                    <p>{t('landing.footerCopy')}</p>
                    <Link to="/ingestor" className="btn-primary btn-xl" style={{ marginTop: '40px' }}>
                        {t('landing.initializePlatform')} <ArrowUpRight size={20} />
                    </Link>
                </div>

                <div className="footer-bottom">
                    <div className="brand-lockup">
                        <div className="brand-dot" />
                        <span>{t('sidebar.brand')}</span>
                    </div>
                    <div className="footer-links">
                        <a href="#">{t('landing.security')}</a>
                        <a href="#">{t('landing.privacy')}</a>
                        <a href="#">{t('landing.terms')}</a>
                    </div>
                    <div className="footer-copy">{t('landing.copyright')}</div>
                </div>
            </footer>
        </div>
    )
}

"""Modern Glassmorphic Aerospace Theme with Animated Microgravity & Plume Flame Background."""
from __future__ import annotations

import streamlit as st


def apply_flame_theme(
    title: str,
    subtitle: str,
    badge: str = "NASA SPACE APPS 2026 • MICROGRAVITY COMBUSTION INTELLIGENCE",
) -> None:
    """Inject modern glassmorphic CSS, full-viewport animated SVG/CSS flames, and hero banner."""
    ember_spans = []
    for i in range(1, 21):
        left_pct = (i * 17 + 7) % 96 + 2
        delay_s = round((i * 0.67) % 8.5, 2)
        dur_s = round(6.5 + (i * 0.83) % 7.0, 2)
        size_px = 3 + (i % 5) * 2
        is_blue = i % 4 == 0
        color_css = (
            "radial-gradient(circle, #e0f2fe 0%, #38bdf8 55%, rgba(56,189,248,0) 100%)"
            if is_blue
            else "radial-gradient(circle, #fff7ed 0%, #fb923c 45%, #ea580c 75%, rgba(234,88,12,0) 100%)"
        )
        glow_css = "0 0 12px #38bdf8" if is_blue else "0 0 14px #f97316"
        ember_spans.append(
            f'<span class="flame-ember" style="left:{left_pct}%; width:{size_px}px; height:{size_px}px; '
            f"animation-delay:{delay_s}s; animation-duration:{dur_s}s; "
            f'background:{color_css}; box-shadow:{glow_css};"></span>'
        )
    embers_html = "".join(ember_spans)

    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

/* 1. Root & App Canvas */
html, body, .stApp {{
    background: radial-gradient(circle at 82% 18%, rgba(14, 116, 144, 0.16) 0%, transparent 42%),
                radial-gradient(circle at 20% 88%, rgba(234, 88, 12, 0.22) 0%, transparent 50%),
                radial-gradient(circle at 50% 100%, rgba(185, 28, 28, 0.24) 0%, transparent 55%),
                linear-gradient(180deg, #04060d 0%, #080c1a 55%, #0c1022 100%) !important;
    color: #f8fafc !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

/* Ensure main content sits above the animated flame canvas */
[data-testid="stAppViewContainer"] > .main {{
    position: relative;
    z-index: 2;
}}

[data-testid="stHeader"] {{
    background: rgba(4, 6, 13, 0.45) !important;
    backdrop-filter: blur(12px);
}}

/* 2. Full-Viewport Animated Flame Background Layer */
.flame-bg-stage {{
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
}}

/* Subtle Aerospace Telemetry Grid */
.flame-bg-grid {{
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(148, 163, 184, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(148, 163, 184, 0.03) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(ellipse at center, rgba(0,0,0,0.85) 20%, transparent 85%);
}}

/* 0g Spherical Diffusion Flame Orb (Upper-Right Ambient Background) */
.microgravity-orb-wrap {{
    position: absolute;
    top: 7%;
    right: 6%;
    width: 340px;
    height: 340px;
    border-radius: 50%;
    filter: blur(1px);
    opacity: 0.55;
    animation: orbFloat 11s ease-in-out infinite alternate;
}}

.microgravity-orb-outer {{
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(
        circle,
        rgba(255, 255, 255, 0.85) 0%,
        rgba(125, 211, 252, 0.72) 22%,
        rgba(14, 165, 233, 0.48) 46%,
        rgba(59, 130, 246, 0.22) 64%,
        rgba(249, 115, 22, 0.10) 78%,
        transparent 92%
    );
    box-shadow:
        0 0 80px rgba(56, 189, 248, 0.35),
        inset 0 0 45px rgba(249, 115, 22, 0.22);
    animation: orbPulse 5.5s ease-in-out infinite alternate;
}}

/* Animated Bottom Buoyant Flame Plumes */
.flame-plume-container {{
    position: absolute;
    left: -8%;
    right: -8%;
    bottom: -70px;
    height: 360px;
    filter: url(#flame-turbulence-filter) blur(14px);
    mix-blend-mode: screen;
    opacity: 0.62;
}}

.flame-wave {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    border-radius: 50% 50% 0 0;
    transform-origin: bottom center;
}}

.flame-wave.w1 {{
    height: 250px;
    background: radial-gradient(ellipse at 50% 100%, rgba(255, 94, 0, 0.68) 0%, rgba(220, 38, 38, 0.32) 48%, transparent 78%);
    animation: flameDance1 4.2s ease-in-out infinite alternate;
}}

.flame-wave.w2 {{
    height: 210px;
    left: 10%;
    right: 5%;
    background: radial-gradient(ellipse at 45% 100%, rgba(251, 146, 60, 0.65) 0%, rgba(234, 88, 12, 0.28) 52%, transparent 80%);
    animation: flameDance2 3.4s ease-in-out infinite alternate;
}}

.flame-wave.w3 {{
    height: 165px;
    left: 22%;
    right: 18%;
    background: radial-gradient(ellipse at 52% 100%, rgba(254, 240, 138, 0.55) 0%, rgba(245, 158, 11, 0.26) 50%, transparent 76%);
    animation: flameDance3 2.7s ease-in-out infinite alternate;
}}

/* Individual Flickering Flame Tongues along Horizon */
.flame-tongue {{
    position: absolute;
    bottom: -35px;
    width: 180px;
    height: 240px;
    background: radial-gradient(ellipse at 50% 90%, rgba(255,237,213,0.75) 0%, rgba(251,146,60,0.58) 32%, rgba(220,38,38,0.22) 64%, transparent 82%);
    border-radius: 50% 50% 35% 35%;
    transform-origin: center bottom;
    animation: tongueFlicker 3.1s ease-in-out infinite alternate;
}}

/* Rising Ember Particles */
.flame-ember {{
    position: absolute;
    bottom: -20px;
    border-radius: 50%;
    opacity: 0;
    animation-name: riseEmber;
    animation-timing-function: ease-in-out;
    animation-iteration-count: infinite;
}}

@keyframes flameDance1 {{
    0%   {{ transform: scaleY(0.92) scaleX(0.98) skewX(-2deg); }}
    50%  {{ transform: scaleY(1.08) scaleX(1.03) skewX(2deg); }}
    100% {{ transform: scaleY(0.96) scaleX(1.01) skewX(-1.5deg); }}
}}

@keyframes flameDance2 {{
    0%   {{ transform: scaleY(1.05) translateX(-18px) skewX(3deg); }}
    100% {{ transform: scaleY(0.88) translateX(22px) skewX(-3deg); }}
}}

@keyframes flameDance3 {{
    0%   {{ transform: scaleY(0.90) translateX(12px) scaleX(0.95); }}
    100% {{ transform: scaleY(1.14) translateX(-14px) scaleX(1.06); }}
}}

@keyframes tongueFlicker {{
    0%   {{ transform: scaleY(0.85) scaleX(1.05) rotate(-3deg); opacity: 0.55; }}
    50%  {{ transform: scaleY(1.16) scaleX(0.92) rotate(2deg); opacity: 0.85; }}
    100% {{ transform: scaleY(0.95) scaleX(1.02) rotate(-1deg); opacity: 0.65; }}
}}

@keyframes orbPulse {{
    0%   {{ transform: scale(0.94); opacity: 0.72; }}
    100% {{ transform: scale(1.07); opacity: 0.96; }}
}}

@keyframes orbFloat {{
    0%   {{ transform: translate(0px, 0px); }}
    100% {{ transform: translate(-22px, 18px); }}
}}

@keyframes riseEmber {{
    0%   {{ transform: translateY(0) translateX(0) scale(0.7); opacity: 0; }}
    18%  {{ opacity: 0.85; }}
    65%  {{ opacity: 0.55; }}
    100% {{ transform: translateY(-88vh) translateX(34px) scale(0.15); opacity: 0; }}
}}

/* 3. Glassmorphic Sidebar */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, rgba(8, 12, 26, 0.88) 0%, rgba(12, 17, 34, 0.92) 100%) !important;
    backdrop-filter: blur(20px) !important;
    border-right: 1px solid rgba(251, 146, 60, 0.20) !important;
}}

/* 4. Hero Header Card */
.flame-hero-card {{
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 1.45rem 1.85rem;
    margin-bottom: 1.35rem;
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.82) 0%, rgba(23, 18, 38, 0.78) 55%, rgba(39, 17, 22, 0.74) 100%);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(251, 146, 60, 0.30);
    box-shadow:
        0 18px 45px rgba(0, 0, 0, 0.55),
        inset 0 1px 0 rgba(255, 255, 255, 0.10);
    overflow: hidden;
}}

.flame-hero-card::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #f97316 0%, #facc15 35%, #38bdf8 75%, #f97316 100%);
}}

.flame-hero-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.26rem 0.78rem;
    border-radius: 999px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #fdba74;
    background: rgba(249, 115, 22, 0.14);
    border: 1px solid rgba(249, 115, 22, 0.35);
    margin-bottom: 0.55rem;
}}

.flame-hero-title {{
    margin: 0;
    font-size: 2.05rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(95deg, #ffffff 0%, #fed7aa 48%, #7dd3fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.18;
}}

.flame-hero-subtitle {{
    margin: 0.42rem 0 0 0;
    font-size: 0.96rem;
    color: #cbd5e1;
    max-width: 820px;
    line-height: 1.5;
}}

.flame-emblem-box {{
    display: flex;
    align-items: center;
    gap: 1.1rem;
    flex-shrink: 0;
}}

/* 5. Glassmorphic Metric Cards & Containers */
[data-testid="stMetric"] {{
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.78) 0%, rgba(17, 24, 39, 0.64) 100%) !important;
    backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(251, 146, 60, 0.22) !important;
    border-top: 2px solid rgba(249, 115, 22, 0.65) !important;
    border-radius: 14px !important;
    padding: 0.95rem 1.15rem !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.38) !important;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease !important;
}}

[data-testid="stMetric"]:hover {{
    transform: translateY(-3px);
    border-color: rgba(56, 189, 248, 0.55) !important;
    box-shadow: 0 14px 34px rgba(249, 115, 22, 0.18) !important;
}}

[data-testid="stMetricValue"] {{
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important;
    color: #fff7ed !important;
}}

[data-testid="stMetricLabel"] {{
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    color: #94a3b8 !important;
}}

/* Bordered st.container(border=True) & Expanders */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: rgba(13, 19, 36, 0.72) !important;
    backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(148, 163, 184, 0.18) !important;
    border-radius: 15px !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35) !important;
}}

[data-testid="stExpander"] {{
    background: rgba(13, 19, 36, 0.68) !important;
    backdrop-filter: blur(14px) !important;
    border: 1px solid rgba(251, 146, 60, 0.22) !important;
    border-radius: 14px !important;
}}

/* 6. Modern Pill Tabs */
[data-baseweb="tab-list"] {{
    gap: 0.5rem !important;
    background: rgba(15, 23, 42, 0.65) !important;
    padding: 0.4rem !important;
    border-radius: 12px !important;
    border: 1px solid rgba(148, 163, 184, 0.15) !important;
}}

[data-baseweb="tab"] {{
    border-radius: 9px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 600 !important;
    color: #cbd5e1 !important;
    transition: all 0.2s ease !important;
}}

[aria-selected="true"][data-baseweb="tab"] {{
    background: linear-gradient(135deg, rgba(234, 88, 12, 0.28) 0%, rgba(56, 189, 248, 0.22) 100%) !important;
    color: #ffffff !important;
    border: 1px solid rgba(251, 146, 60, 0.45) !important;
    box-shadow: 0 4px 16px rgba(249, 115, 22, 0.22) !important;
}}

/* 7. Primary & Secondary Action Buttons */
.stButton > button {{
    border-radius: 10px !important;
    font-weight: 600 !important;
    border: 1px solid rgba(251, 146, 60, 0.35) !important;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.90) 100%) !important;
    color: #f8fafc !important;
    transition: all 0.2s ease !important;
}}

.stButton > button:hover {{
    border-color: #fb923c !important;
    box-shadow: 0 0 18px rgba(249, 115, 22, 0.35) !important;
    transform: translateY(-1px) !important;
}}

.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, #ea580c 0%, #f97316 50%, #f59e0b 100%) !important;
    border: 1px solid rgba(254, 215, 170, 0.5) !important;
    color: #ffffff !important;
    box-shadow: 0 6px 22px rgba(234, 88, 12, 0.40) !important;
}}
</style>

<!-- Full-Viewport Animated Flame & Microgravity Diffusion Orb Background -->
<div class="flame-bg-stage" aria-hidden="true">
    <div class="flame-bg-grid"></div>

    <!-- SVG Turbulence Filter for Real-Time Fluid Flame Distortion -->
    <svg width="0" height="0" style="position:absolute;">
        <defs>
            <filter id="flame-turbulence-filter" x="-20%" y="-20%" width="140%" height="140%">
                <feTurbulence type="fractalNoise" baseFrequency="0.012 0.035" numOctaves="3" seed="7" result="noise">
                    <animate attributeName="baseFrequency" values="0.012 0.035;0.016 0.048;0.012 0.035" dur="6s" repeatCount="indefinite" />
                </feTurbulence>
                <feDisplacementMap in="SourceGraphic" in2="noise" scale="34" xChannelSelector="R" yChannelSelector="G" />
            </filter>
        </defs>
    </svg>

    <!-- 0g Spherical Blue Diffusion Flame Orb (FLEX / ACME Microgravity Signature) -->
    <div class="microgravity-orb-wrap">
        <div class="microgravity-orb-outer"></div>
    </div>

    <!-- Bottom Buoyant Flame Plumes -->
    <div class="flame-plume-container">
        <div class="flame-wave w1"></div>
        <div class="flame-wave w2"></div>
        <div class="flame-wave w3"></div>
        <div class="flame-tongue" style="left:8%; animation-delay:0.1s;"></div>
        <div class="flame-tongue" style="left:26%; height:280px; animation-delay:0.8s;"></div>
        <div class="flame-tongue" style="left:47%; height:260px; animation-delay:0.4s;"></div>
        <div class="flame-tongue" style="left:68%; height:290px; animation-delay:1.2s;"></div>
        <div class="flame-tongue" style="left:84%; height:230px; animation-delay:0.6s;"></div>
    </div>

    <!-- Rising Glowing Embers -->
    {embers_html}
</div>

<!-- Glassmorphic Hero Banner with Dual 1g vs 0g Animated SVG Flame Emblem -->
<div class="flame-hero-card">
    <div>
        <div class="flame-hero-badge">🔥 {badge}</div>
        <h1 class="flame-hero-title">{title}</h1>
        <p class="flame-hero-subtitle">{subtitle}</p>
    </div>
    <div class="flame-emblem-box">
        <svg width="128" height="86" viewBox="0 0 128 86" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <radialGradient id="orb0g" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="#ffffff"/>
                    <stop offset="35%" stop-color="#38bdf8"/>
                    <stop offset="72%" stop-color="#0284c7" stop-opacity="0.55"/>
                    <stop offset="100%" stop-color="#f97316" stop-opacity="0"/>
                </radialGradient>
                <linearGradient id="plume1g" x1="50%" y1="100%" x2="50%" y2="0%">
                    <stop offset="0%" stop-color="#fde047"/>
                    <stop offset="45%" stop-color="#f97316"/>
                    <stop offset="90%" stop-color="#dc2626" stop-opacity="0.75"/>
                    <stop offset="100%" stop-color="#dc2626" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <!-- 1g Buoyant Teardrop Flame -->
            <g>
                <path d="M34 68 C20 68 15 52 24 35 C29 25 34 15 34 8 C34 15 39 25 44 35 C53 52 48 68 34 68 Z" fill="url(#plume1g)">
                    <animateTransform attributeName="transform" type="scale" values="1 1; 0.96 1.06; 1 1" dur="2.2s" repeatCount="indefinite" additive="sum"/>
                </path>
                <text x="34" y="81" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="JetBrains Mono, monospace">1g Plume</text>
            </g>
            <!-- 0g Spherical Diffusion Flame -->
            <g>
                <circle cx="92" cy="40" r="26" fill="url(#orb0g)">
                    <animate attributeName="r" values="24;28;24" dur="3.2s" repeatCount="indefinite"/>
                </circle>
                <circle cx="92" cy="40" r="19" stroke="#38bdf8" stroke-width="1" stroke-dasharray="3 3" opacity="0.75">
                    <animateTransform attributeName="transform" type="rotate" from="0 92 40" to="360 92 40" dur="14s" repeatCount="indefinite"/>
                </circle>
                <text x="92" y="81" text-anchor="middle" fill="#7dd3fc" font-size="9" font-family="JetBrains Mono, monospace">0g Sphere</text>
            </g>
        </svg>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )

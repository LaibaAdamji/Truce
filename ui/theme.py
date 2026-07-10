"""
ui/theme.py
Color tokens, typography, and CSS injection. Warm neutral base,
citrus palette reserved for small accents (buttons, badges, highlights).
Call apply_theme() once at the top of app.py, before anything else renders.
"""
import streamlit as st

# --- Accent palette (used sparingly: buttons, badges, highlights) ---
OLIVE = "#BDC749"
CREAM_ORANGE = "#F8D084"
BRICK_RED = "#B53209"
AMBER = "#E59113"

LIGHT = {
    "bg": "#FAF6EF",
    "surface": "#FFFFFF",
    "surface_glass": "rgba(255, 255, 255, 0.72)",
    "text": "#2B2620",
    "text_muted": "#6B6459",
    "border": "#DDD2C0",
    "sidebar_bg": "#F2EBDD",
}

DARK = {
    "bg": "#211D1A",
    "surface": "#2C2722",
    "surface_glass": "rgba(44, 39, 34, 0.82)",
    "text": "#F5F0E8",
    "text_muted": "#BBB0A0",
    "border": "#4A4038",
    "sidebar_bg": "#18140F",
}

STATUS_COLORS = {
    "draft": "#A69C8C",
    "requirements_extracted": AMBER,
    "clarifications_pending": AMBER,
    "pricing_ready": CREAM_ORANGE,
    "negotiating": AMBER,
    "contract_generated": OLIVE,
    "signed": OLIVE,
    "completed": OLIVE,
    "cancelled": BRICK_RED,
}


def apply_theme(mode: str = "light") -> None:
    """mode: 'light' or 'dark'. Injects CSS variables + base styling."""
    palette = DARK if mode == "dark" else LIGHT

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        :root {{
            --bg: {palette['bg']};
            --surface: {palette['surface']};
            --surface-glass: {palette['surface_glass']};
            --text: {palette['text']};
            --text-muted: {palette['text_muted']};
            --border: {palette['border']};
            --sidebar-bg: {palette['sidebar_bg']};
            --accent-olive: {OLIVE};
            --accent-cream: {CREAM_ORANGE};
            --accent-red: {BRICK_RED};
            --accent-amber: {AMBER};
        }}

        /* --- Typography: force it everywhere Streamlit renders, --- */
        /* --- since [class*="css"] doesn't match modern Streamlit's real classes --- */
        html, body, .stApp, .stApp * {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        .stApp {{
            background-color: var(--bg);
            color: var(--text);
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        /* Streamlit's own chrome (top toolbar) -- blend it instead of stark black */
        header[data-testid="stHeader"] {{
            background-color: var(--bg) !important;
        }}

        /* Sidebar never inherited our theme vars before -- explicit now */
        section[data-testid="stSidebar"] {{
            background-color: var(--sidebar-bg) !important;
            border-right: 1px solid var(--border);
        }}

        /* --- Force real text contrast: Streamlit hardcodes its own default --- */
        /* --- paragraph/heading colors regardless of our theme, so anything --- */
        /* --- without one of our own truce- classes needs an explicit override --- */
        .stMarkdown p:not([class*="truce-"]),
        .stMarkdown li:not([class*="truce-"]),
        .stMarkdown span:not([class*="truce-"]):not(.truce-badge) {{
            color: var(--text);
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: var(--text) !important;
        }}
        [data-testid="stCaptionContainer"] p {{
            color: var(--text-muted) !important;
        }}
        label, .stRadio label p, .stCheckbox label p {{
            color: var(--text) !important;
        }}

        /* --- Generic glass cards (used by static markdown blocks) --- */
        .truce-card {{
            background: var(--surface-glass);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }}
        .truce-card:hover {{
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.10);
            transform: translateY(-2px);
        }}

        .truce-card-glass {{
            background: var(--surface-glass); backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border); border-radius: 20px; padding: 1.5rem;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }}
        .truce-card-glass:hover {{
            box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
            transform: translateY(-1px);
        }}

        /* --- Real st.container(key=...) cards --- */
        /* Use key="cardwrap_<anything>" on any container to get card styling */
        /* that actually wraps its children (unlike splitting <div> across */
        /* separate st.markdown calls, which does NOT nest in the real DOM). */
        div[class*="st-key-cardwrap_"] > div,
        div[class*="st-key-project_card"] > div {{
            background: var(--surface-glass);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 14px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
            transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
        }}
        div[class*="st-key-project_card"] > div:hover {{
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.10);
            transform: translateY(-2px);
            border-color: var(--accent-amber);
        }}

        /* --- Buttons: ghost by default, amber only for primary actions --- */
        .stButton > button {{
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--surface);
            color: var(--text) !important;
            padding: 0.6rem 1.4rem;
            font-weight: 600;
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
            cursor: pointer;
        }}
        .stButton > button p {{ color: inherit !important; }}
        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
            border-color: var(--accent-amber);
            color: var(--accent-amber) !important;
        }}
        .stButton > button:active {{
            transform: translateY(0) scale(0.97);
        }}
        .stButton > button[kind="primary"] {{
            background: var(--accent-amber);
            color: #FFFFFF !important;
            border: none;
            box-shadow: 0 2px 8px rgba(229, 145, 19, 0.25);
        }}
        .stButton > button[kind="primary"]:hover {{
            box-shadow: 0 4px 16px rgba(229, 145, 19, 0.35);
            color: #FFFFFF !important;
        }}

        /* Sidebar buttons stay quiet -- no amber glow floating in the nav */
        section[data-testid="stSidebar"] .stButton > button {{
            width: 100%;
            background: transparent;
            border: 1px solid transparent;
            box-shadow: none;
            font-weight: 500;
            text-align: left;
            justify-content: flex-start;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: var(--surface);
            border-color: var(--border);
            transform: none;
            box-shadow: none;
        }}

        .truce-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #FFFFFF;
        }}

        h1, h2, h3 {{
            font-weight: 800;
            letter-spacing: -0.02em;
        }}

        .block-container {{
            padding-top: 2.5rem;
            padding-bottom: 3rem;
        }}
        /* Fix low-contrast text inputs -- Streamlit's own classes need direct targeting */
        .stTextInput input, .stNumberInput input, .stTextArea textarea {{
            color: var(--text) !important;
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }}
        .stTextInput input::placeholder, .stTextArea textarea::placeholder {{
            color: var(--text-muted) !important;
            opacity: 1 !important;
        }}

        .truce-secondary {{ color: var(--text-muted) !important; }}
        .truce-badge-success {{ background: var(--accent-olive); color:#fff; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; }}
        .truce-badge-pending {{ background: var(--accent-cream); color:#5A4A28; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; }}
        .truce-badge-active {{ background: var(--accent-amber); color:#fff; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; }}
        .truce-badge-warning {{ background: var(--accent-red); color:#fff; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; }}
        .truce-bubble {{
            border-radius: 14px; padding: 0.75rem 1rem; margin: 6px 0; max-width: 80%;
            animation: truce-bubble-in 0.35s ease both;
        }}
        .truce-bubble-offer {{ background: var(--surface); border: 1px solid var(--border); font-weight:600; }}
        .truce-bubble-mediator {{ background: var(--accent-cream); color:#5A4A28; margin-left: auto; }}
        .truce-loading-text {{ color: var(--accent-amber); font-style: italic; }}

        @keyframes truce-bubble-in {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .truce-round-marker {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 22px; height: 22px; border-radius: 50%;
            background: var(--surface); border: 1px solid var(--border);
            color: var(--text-muted); font-size: 0.7rem; font-weight: 700;
            margin-right: 8px; flex-shrink: 0;
        }}

        .truce-empty-state {{
            text-align: center; padding: 2rem 1rem;
            color: var(--text-muted);
        }}
        .truce-empty-state .truce-empty-icon {{
            font-size: 1.8rem; margin-bottom: 0.4rem; opacity: 0.7;
        }}

        /* --- Responsive tightening on small screens --- */
        @media (max-width: 640px) {{
            .truce-card, .truce-card-glass {{ padding: 1rem; }}
            div[class*="st-key-project_card"] > div,
            div[class*="st-key-cardwrap_"] > div {{ padding: 1rem; }}
            .block-container {{ padding-top: 1.5rem; padding-left: 1rem; padding-right: 1rem; }}
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )


def render_theme_toggle() -> None:
    """Renders a light/dark mode toggle button. Call once, inside the sidebar."""
    current = st.session_state.get("theme_mode", "light")
    if current == "light":
        icon, label, next_mode = "🌙", "Dark mode", "dark"
    else:
        icon, label, next_mode = "☀️", "Light mode", "light"

    if st.button(f"{icon}  {label}", key="theme_toggle", use_container_width=True):
        st.session_state["theme_mode"] = next_mode
        st.rerun()


def status_badge_html(status: str) -> str:
    color = STATUS_COLORS.get(status, "#A69C8C")
    label = status.replace("_", " ").title()
    return f'<span class="truce-badge" style="background:{color};">{label}</span>'
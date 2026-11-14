"""Streamlit dashboard home. Run: streamlit run frontend/app.py"""
import streamlit as st

from components.api_client import health

st.set_page_config(page_title="Flame in Freefall", page_icon="🔥", layout="wide")

st.title("🔥 Flame in Freefall")
st.caption("AI-powered fire safety insights from NASA microgravity combustion data")

status = health()
st.sidebar.success("Backend online") if status else st.sidebar.error("Backend offline (start uvicorn on :8000)")

st.markdown(
    """
Use the pages in the sidebar:
- **Explorer** – browse & filter experiments
- **Insights** – ranked fire-safety findings
- **Risk Simulator** – estimate flammability for Moon/Mars cabin conditions
- **Ask the Data** – chat with NASA combustion reports
"""
)

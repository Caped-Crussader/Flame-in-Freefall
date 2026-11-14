import streamlit as st

from components.api_client import post

st.title("💬 Ask the Data")

if q := st.chat_input("e.g. How does flame spread change at 34% O2 and 56 kPa?"):
    st.chat_message("user").write(q)
    res = post("/api/chat/", {"question": q})
    st.chat_message("assistant").write(res.get("answer"))
    if res.get("sources"):
        st.caption("Sources: " + ", ".join(res["sources"]))

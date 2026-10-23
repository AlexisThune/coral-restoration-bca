import hmac
import os

import streamlit as st


def require_pilot_access():
    expected_password = os.environ.get("PILOT_PASSWORD")
    if not expected_password:
        st.error(
            "Private pilot access is not configured. Set the PILOT_PASSWORD "
            "environment variable before starting the app."
        )
        st.stop()

    if st.session_state.get("pilot_authenticated"):
        return

    st.title("Private pilot")
    with st.form("pilot_login"):
        supplied_password = st.text_input("Access password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if hmac.compare_digest(supplied_password, expected_password):
            st.session_state.pilot_authenticated = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()

import streamlit as st
import numpy as np

import utils.database as db
from utils.database import enrich_user_data
from utils.auth import get_authenticator, check_authentication
from utils.logout_handler import check_logout_status, is_authenticated

# Check URL parameters for logout status
query_params = st.query_params
if query_params.get("logged_out") == "true":
    st.success("✅ Successfully logged out!")
    st.balloons()
    # Clear the URL parameter
    st.query_params.clear()

# Check for logout flag and show message
if check_logout_status():
    st.success("You have been logged out successfully!")
    st.info("You can now log in again.")

# Initialize authentication check
authenticator = check_authentication()

# Check if user is already authenticated (from cookies)
if is_authenticated() and not check_logout_status():
    username = st.session_state.get("username")
    
    # Only fetch user data once
    if "user_data" not in st.session_state and username:
        user_data = db.fetch_user_by_username(username)
        if user_data:
            user_data = enrich_user_data(user_data)
            st.session_state.user_data = user_data
            
    # Redirect to dashboard if already authenticated
    if "user_data" in st.session_state:
        st.success(f"Welcome back, {st.session_state.user_data['name']}!")
        st.info("Redirecting to dashboard...")
        st.switch_page("pages/dashboard.py")

# Show debug info (remove in production)
# st.write("Session State Debug:", {
#     "authentication_status": st.session_state.get("authentication_status"),
#     "username": st.session_state.get("username"),
#     "name": st.session_state.get("name")
# })

# -- Render login form with error handling --
try:
    login_result = authenticator.login("main", key="Login_button")
    
    # Handle case where login returns None
    if login_result is None:
        name, authentication_status, username = None, None, None
    else:
        name, authentication_status, username = login_result
        
except Exception as e:
    st.error(f"Login form error: {e}")
    # Set default values
    name, authentication_status, username = None, None, None

# -- Handle login outcomes --
if authentication_status is True:
    # Update session state
    st.session_state.authentication_status = authentication_status
    st.session_state.name = name
    st.session_state.username = username
    
    # Only fetch user data once
    if "user_data" not in st.session_state:
        user_data = db.fetch_user_by_username(username)
        if user_data:
            user_data = enrich_user_data(user_data)
            st.session_state.user_data = user_data
        else:
            st.error("User not found.")
            st.stop()

    st.success(f"Welcome, {st.session_state.user_data['name']}!")
    st.switch_page("pages/dashboard.py")

elif authentication_status is False:
    st.error("Username or password is incorrect")

elif authentication_status is None:
    st.warning("Please enter your username and password")
# logout_handler.py
import streamlit as st
from utils.auth import get_authenticator
import time

def handle_logout():
    """Dedicated logout handler with multiple methods"""
    authenticator = get_authenticator()
    
    # Method 1: Try streamlit-authenticator logout
    try:
        authenticator.logout(location="unrendered")
    except Exception as e:
        st.write(f"Authenticator logout failed: {e}")
    
    # Method 2: Manual cookie clearing via st.query_params (if available)
    try:
        st.query_params.clear()
    except:
        pass
    
    # Method 3: Clear all session state
    session_keys = list(st.session_state.keys())
    for key in session_keys:
        del st.session_state[key]
    
    # Method 4: Set explicit logout flags and reset authentication
    st.session_state.clear()
    st.session_state.authentication_status = False
    st.session_state.name = None
    st.session_state.username = None
    st.session_state.logged_out = True
    st.session_state.logout_timestamp = time.time()
    
    # Method 5: Remove authenticator from session state to force recreation
    if "authenticator" in st.session_state:
        del st.session_state["authenticator"]
    
    return True

def clear_cookies_js():
    """Return JavaScript code to clear cookies and redirect to login"""
    return """
    <script>
    console.log('Clearing cookies...');
    
    // Method 1: Clear specific cookie
    document.cookie = "Rhaya_HR_Internal=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=" + window.location.hostname;
    document.cookie = "Rhaya_HR_Internal=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    
    // Method 2: Clear all cookies
    document.cookie.split(";").forEach(function(c) { 
        var eqPos = c.indexOf("=");
        var name = eqPos > -1 ? c.substr(0, eqPos) : c;
        document.cookie = name.trim() + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/";
        document.cookie = name.trim() + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;domain=" + window.location.hostname;
    });
    
    // Method 3: Clear localStorage and sessionStorage
    if (typeof(Storage) !== "undefined") {
        localStorage.clear();
        sessionStorage.clear();
    }
    
    console.log('Cookies cleared, redirecting to login...');
    
    // Automatic redirect to login page
    setTimeout(function() {
        window.location.href = window.location.pathname.replace('/pages/dashboard.py', '/pages/login.py');
    }, 1000);
    </script>
    """

def check_logout_status():
    """Check if user just logged out"""
    return st.session_state.get("logged_out", False)

def is_authenticated():
    """Check if user is properly authenticated"""
    return (
        st.session_state.get("authentication_status") == True and
        st.session_state.get("username") is not None and
        not st.session_state.get("logged_out", False)
    )
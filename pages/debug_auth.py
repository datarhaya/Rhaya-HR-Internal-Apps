# debug_auth.py
import streamlit as st
from utils.auth import get_authenticator
from utils.logout_handler import handle_logout, clear_cookies_js
import time

st.title("🔍 Authentication Debug Page")

st.markdown("### Current Session State")
st.json(dict(st.session_state))

st.markdown("### Browser Cookies (via JavaScript)")
st.markdown("""
<script>
document.getElementById('cookie-display').innerHTML = 'Cookies: ' + document.cookie;
</script>
<div id='cookie-display'>Loading cookies...</div>
""", unsafe_allow_html=True)

st.markdown("### Authentication Tests")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Test Authenticator Login Check"):
        authenticator = get_authenticator()
        try:
            name, auth_status, username = authenticator.login(location='unrendered')
            st.write("Login check result:")
            st.write(f"Name: {name}")
            st.write(f"Auth Status: {auth_status}")
            st.write(f"Username: {username}")
        except Exception as e:
            st.error(f"Login check failed: {e}")

with col2:
    if st.button("Clear Session State"):
        st.session_state.clear()
        st.success("Session state cleared!")
        st.rerun()

with col3:
    if st.button("Test Logout Handler"):
        handle_logout()
        st.success("Logout handler executed!")

st.markdown("### Manual Cookie Operations")

col1, col2 = st.columns(2)

with col1:
    if st.button("Show All Cookies"):
        st.markdown("""
        <script>
        console.log('All cookies:', document.cookie);
        alert('All cookies: ' + document.cookie);
        </script>
        """, unsafe_allow_html=True)

with col2:
    if st.button("Clear All Cookies Manually"):
        st.markdown(clear_cookies_js(), unsafe_allow_html=True)

st.markdown("### Authenticator Object Info")
try:
    authenticator = get_authenticator()
    st.write("Authenticator created successfully")
    st.write(f"Cookie name: {authenticator.cookie_name}")
    st.write(f"Cookie expiry days: {authenticator.cookie_expiry_days}")
    
    # Try to access cookie handler if available
    if hasattr(authenticator, 'cookie_handler'):
        st.write("Cookie handler exists")
    else:
        st.write("No cookie handler found")
        
except Exception as e:
    st.error(f"Authenticator error: {e}")

st.markdown("### Manual Logout Test")
if st.button("🚨 Nuclear Logout Option"):
    # Clear everything possible
    st.session_state.clear()
    
    # Set explicit logout state
    st.session_state.authentication_status = False
    st.session_state.logged_out = True
    st.session_state.manual_logout = True
    
    # JavaScript to clear everything
    st.markdown("""
    <script>
    // Clear all cookies
    document.cookie.split(";").forEach(function(c) { 
        var eqPos = c.indexOf("=");
        var name = eqPos > -1 ? c.substr(0, eqPos) : c;
        document.cookie = name.trim() + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/";
        document.cookie = name.trim() + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;domain=" + window.location.hostname;
        document.cookie = name.trim() + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;domain=." + window.location.hostname;
    });
    
    // Clear storage
    if (typeof(Storage) !== "undefined") {
        localStorage.clear();
        sessionStorage.clear();
    }
    
    alert('Everything cleared! Redirecting to login...');
    
    // Redirect to login page
    setTimeout(function() {
        window.location.href = 'pages/login.py';
    }, 1000);
    </script>
    """, unsafe_allow_html=True)
    
    st.success("Nuclear logout executed!")

# Navigation
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("← Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
with col2:
    if st.button("Go to Login →"):
        st.switch_page("pages/login.py")
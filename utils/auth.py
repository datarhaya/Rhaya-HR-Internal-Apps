# auth.py
import streamlit_authenticator as stauth
import utils.database as db
import streamlit as st
import time

def get_authenticator():
    # Check if authenticator already exists in session state
    if "authenticator" in st.session_state:
        return st.session_state.authenticator
    
    users_auth = db.get_all_auth()
    credentials = {"usernames": {}}

    for doc in users_auth.stream():
        user_data = doc.to_dict()
        credentials["usernames"][user_data["username"]] = {
            "name": user_data["name"],
            "password": user_data["password"],
        }

    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="Rhaya_HR_Internal",  # Remove spaces from cookie name
        key="abcdef123456789012345678901234",  # Use a longer, more secure key (32 chars)
        cookie_expiry_days=30,
        preauthorized=None
    )

    # Store authenticator in session state
    st.session_state.authenticator = authenticator
    return authenticator

def check_authentication():
    """Helper function to check authentication status"""
    authenticator = get_authenticator()
    
    # Try to get authentication from cookies first
    try:
        # This will automatically check cookies and set session state
        login_result = authenticator.login(location='unrendered')
        
        # Handle case where login returns None
        if login_result is not None:
            name, authentication_status, username = login_result
            
            # Update session state if cookie authentication successful
            if authentication_status:
                st.session_state.authentication_status = authentication_status
                st.session_state.name = name
                st.session_state.username = username
        else:
            # If login returns None, check current session state
            pass
            
    except Exception as e:
        # If cookie check fails, continue with normal flow
        pass
    
    return authenticator

def logout_user():
    """Dedicated logout function"""
    authenticator = get_authenticator()
    
    # Method 1: Try using the authenticator's logout method
    try:
        authenticator.logout(location="unrendered")
    except:
        pass
    
    # Method 2: Manual cookie clearing via JavaScript
    cookie_clear_script = f"""
    <script>
    // Clear specific cookie
    document.cookie = "Rhaya_HR_Internal=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    
    // Clear all cookies (backup method)
    document.cookie.split(";").forEach(function(c) {{ 
        document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
    }});
    </script>
    """
    
    # Method 3: Clear session state
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]
    
    # Set logout flag
    st.session_state.logged_out = True
    st.session_state.logout_time = time.time()
    
    return cookie_clear_script
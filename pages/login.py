# login.py - FIXED for streamlit-authenticator 0.4.2
import streamlit as st
import numpy as np

import utils.database as db
from utils.database import enrich_user_data
from utils.auth import get_authenticator, check_authentication
from utils.logout_handler import check_logout_status, is_authenticated

# Import password management functions
from utils.password_management import PasswordManager
import streamlit_authenticator as stauth

def force_password_change_form(username):
    """Force password change for users who logged in with temporary password"""
    st.subheader("🔐 Password Change Required")
    st.warning("You logged in with a temporary password. Please set a new password to continue.")
    
    password_manager = PasswordManager()
    
    with st.form("force_password_change"):
        new_password = st.text_input("New Password", type="password", 
                                   help="Minimum 8 characters with uppercase, lowercase, number, and special character")
        confirm_password = st.text_input("Confirm New Password", type="password")
        
        # Real-time password strength indicator
        if new_password:
            is_valid, errors, strength, score = password_manager.validate_password_strength(new_password)
            
            # Color-coded strength indicator
            strength_colors = {
                "Very Strong": "🟢",
                "Strong": "🟡", 
                "Medium": "🟠",
                "Weak": "🔴"
            }
            
            st.markdown(f"**Password Strength:** {strength_colors.get(strength, '⚪')} {strength}")
            
            if errors:
                st.error("Password requirements not met:")
                for error in errors:
                    st.error(f"• {error}")
        
        # Show password requirements
        with st.expander("📋 Password Requirements"):
            st.markdown("""
            **Your password must contain:**
            - ✅ At least 8 characters (12+ recommended)
            - ✅ At least one lowercase letter (a-z)
            - ✅ At least one uppercase letter (A-Z)
            - ✅ At least one number (0-9)
            - ✅ At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
            
            **Additional recommendations:**
            - Avoid common words or patterns
            - Don't reuse recent passwords
            - Use a unique password not used elsewhere
            """)
        
        submitted = st.form_submit_button("Set New Password", type="primary")
        
        if submitted:
            if not new_password or not confirm_password:
                st.error("Both password fields are required")
                return
            
            if new_password != confirm_password:
                st.error("Passwords do not match")
                return
            
            # Validate password strength
            is_valid, errors, strength, score = password_manager.validate_password_strength(new_password)
            if not is_valid:
                st.error("Password does not meet requirements:")
                for error in errors:
                    st.error(f"• {error}")
                return
            
            # Update password
            success, message = password_manager.update_password(username, new_password)
            if success:
                st.success("✅ Password updated successfully!")
                st.balloons()
                st.session_state.force_password_change = False
                st.info("Redirecting to dashboard...")
                
                # Small delay for user to see the success message
                import time
                time.sleep(2)
                st.rerun()
            else:
                st.error(f"Failed to update password: {message}")

def verify_temporary_password(username, password):
    """Check if the provided password is a valid temporary password"""
    try:
        password_manager = PasswordManager()
        is_valid, token_data = password_manager.verify_reset_token(username, password)
        return is_valid, token_data
    except Exception as e:
        st.error(f"Error verifying temporary password: {e}")
        return False, None

def verify_regular_password(username, password):
    """Verify regular password using the fixed password manager"""
    try:
        password_manager = PasswordManager()
        
        # Get user's stored password from database
        db_instance = db.get_db()
        users_auth = db_instance.collection("users_auth")
        user_query = users_auth.where("username", "==", username).limit(1).stream()
        
        for doc in user_query:
            user_data = doc.to_dict()
            stored_password = user_data.get("password", "")
            
            # Use the fixed password verification method
            if password_manager.verify_password_stauth(password, stored_password):
                return True, user_data
        
        return False, None
        
    except Exception as e:
        st.error(f"Error verifying regular password: {e}")
        return False, None

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
    
    # Check if user needs to change password (from temp password login)
    if st.session_state.get("force_password_change", False):
        force_password_change_form(username)
        st.stop()
    
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

# Add password management navigation
st.title("HR Internal Apps")

# Add password management links before login form
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔑 Forgot Password?", help="Reset your password via email"):
        st.switch_page("pages/password_management.py")
with col2:
    if st.button("🔧 Reset Authentication", help="Clear authentication data"):
        st.switch_page("pages/reset_auth.py")

@st.dialog("Login help and troubleshooting")
def login_help():
    """Show help for login issues"""
    st.markdown("""
            **Regular Login:**
            - Use your assigned username and password
            
            **Using Temporary Password:**
            - Copy the temporary password exactly from your email
            - You'll be required to set a new password immediately
            - Temporary passwords expire after 24 hours
            
            **Forgot Password:**
            - Click "Forgot Password?" above
            - Enter your username or email
            - Check your email for a temporary password
            
            **Having Issues:**
            - Try "Reset Authentication" to clear cookies
            - Contact IT support if problems persist
            """)
    
with col3:
    if st.button("❓ Help", help="Login help and troubleshooting"):
        login_help()

st.markdown("---")

# -- FIXED Custom login form to handle temporary passwords --
with st.form("login_form"):
    st.subheader("🔓 Login to Your Account")
    
    username_input = st.text_input("Username", placeholder="Enter your username")
    password_input = st.text_input("Password", type="password", placeholder="Enter your password")
    
    # Help text for temporary passwords
    st.caption("💡 Using a temporary password? Copy it exactly from your email.")
    
    login_submitted = st.form_submit_button("🚀 Login", type="primary", use_container_width=True)
    
    if login_submitted:
        if not username_input or not password_input:
            st.error("Please enter both username and password")
        else:
            # First, try to verify if this is a temporary password
            is_temp_password, temp_data = verify_temporary_password(username_input, password_input)
            
            if is_temp_password:
                # Temporary password is valid - set up forced password change
                st.success("✅ Temporary password verified!")
                st.info("🔐 You must set a new password to continue...")
                
                # Set session state for authentication
                st.session_state.authentication_status = True
                st.session_state.username = username_input
                st.session_state.force_password_change = True
                
                # Get user data for display
                user_data = db.fetch_user_by_username(username_input)
                if user_data:
                    user_data = enrich_user_data(user_data)
                    st.session_state.user_data = user_data
                    st.session_state.name = user_data.get("name")
                
                # Rerun to show password change form
                st.rerun()
            
            else:
                # Try regular password authentication using FIXED method
                try:
                    is_valid_regular, user_auth_data = verify_regular_password(username_input, password_input)
                    
                    if is_valid_regular:
                        # Login successful
                        st.session_state.authentication_status = True
                        st.session_state.name = user_auth_data.get("name")
                        st.session_state.username = username_input
                        st.session_state.force_password_change = False
                        
                        # Fetch and store user data
                        employee_data = db.fetch_user_by_username(username_input)
                        if employee_data:
                            employee_data = enrich_user_data(employee_data)
                            st.session_state.user_data = employee_data
                        
                        st.success(f"Welcome, {st.session_state.name}!")
                        st.info("Redirecting to dashboard...")
                        st.switch_page("pages/dashboard.py")
                    else:
                        st.error("❌ Username or password is incorrect")
                        
                        # Show helpful message for temporary passwords
                        st.info("💡 If you're using a temporary password, make sure you copied it exactly from the email")
                        
                except Exception as e:
                    st.error(f"Login error: {e}")

# Additional help section at bottom
st.markdown("---")

with st.expander("🔒 Security Information"):
    st.markdown("""
    **Password Security:**
    - Never share your login credentials
    - Use strong, unique passwords
    - Change your password regularly
    
    **Temporary Passwords:**
    - Only valid for 24 hours
    - Can only be used once
    - Must be changed immediately upon login
    
    **Need Help?**
    - Contact your IT administrator
    - Check your email spam folder for reset emails
    - Use "Reset Authentication" if having persistent issues
    """)

# Show debug info only in development (remove in production)
# if st.secrets.get("environment", "production") == "development":
#     with st.expander("🐛 Debug Info (Dev Only)"):
#         st.write("Session State Debug:", {
#             "authentication_status": st.session_state.get("authentication_status"),
#             "username": st.session_state.get("username"),
#             "name": st.session_state.get("name"),
#             "force_password_change": st.session_state.get("force_password_change", False)
#         })
# pages/password_management.py - CORRECTED VERSION
import streamlit as st
from utils.logout_handler import is_authenticated

# Import the fixed password manager
try:
    from utils.password_management import PasswordManager, password_reset_limiter
    PASSWORD_MANAGEMENT_AVAILABLE = True
except ImportError:
    st.warning("Password management not available. Please check your setup.")
    PASSWORD_MANAGEMENT_AVAILABLE = False

def change_password_form():
    """Password change form for authenticated users"""
    st.subheader("🔐 Change Password")
    
    if not is_authenticated():
        st.error("You must be logged in to change your password")
        return
    
    if not PASSWORD_MANAGEMENT_AVAILABLE:
        st.error("Password management system not available")
        return
    
    username = st.session_state.get("username")
    password_manager = PasswordManager()
    
    with st.form("change_password_form"):
        st.markdown("**🔒 Update your account password**")
        
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        
        # Show password requirements
        with st.expander("📋 Password Requirements"):
            st.markdown("""
            **Your password must contain:**
            - At least 8 characters (12+ recommended)
            - At least one lowercase letter (a-z)
            - At least one uppercase letter (A-Z)
            - At least one number (0-9)
            - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
            """)
        
        submitted = st.form_submit_button("🔄 Change Password", type="primary")
        
        if submitted:
            # Validate inputs
            if not all([current_password, new_password, confirm_password]):
                st.error("All fields are required")
                return
            
            if new_password != confirm_password:
                st.error("New passwords do not match")
                return
            
            # Validate password strength
            try:
                is_valid, errors, strength, score = password_manager.validate_password_strength(new_password)
                if not is_valid:
                    st.error("Password does not meet requirements:")
                    for error in errors:
                        st.error(f"• {error}")
                    return
                
                # Show password strength
                strength_colors = {
                    "Very Strong": "🟢",
                    "Strong": "🟡", 
                    "Medium": "🟠",
                    "Weak": "🔴"
                }
                st.info(f"Password Strength: {strength_colors.get(strength, '⚪')} {strength}")
                
            except Exception as e:
                st.error(f"Error validating password: {e}")
                return
            
            # Verify current password
            try:
                is_valid, message = password_manager.verify_current_password(username, current_password)
                if not is_valid:
                    st.error(f"Current password verification failed: {message}")
                    return
            except Exception as e:
                st.error(f"Error verifying current password: {e}")
                return
            
            # Update password
            try:
                success, message = password_manager.update_password(username, new_password)
                if success:
                    st.success("✅ Password changed successfully!")
                    st.balloons()
                    st.info("🔄 Please log out and log back in with your new password for security")
                    
                    # Option to logout immediately
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🚪 Logout Now", type="primary"):
                            from utils.logout_handler import handle_logout, clear_cookies_js
                            handle_logout()
                            st.markdown(clear_cookies_js(), unsafe_allow_html=True)
                            st.stop()
                    with col2:
                        if st.button("📊 Continue to Dashboard"):
                            st.switch_page("pages/dashboard.py")
                else:
                    st.error(f"Failed to change password: {message}")
            except Exception as e:
                st.error(f"Error updating password: {e}")

def forgot_password_form():
    """Forgot password form for non-authenticated users"""
    st.subheader("🔑 Reset Your Password")
    
    if not PASSWORD_MANAGEMENT_AVAILABLE:
        st.error("Password management system not available")
        return
    
    password_manager = PasswordManager()
    
    # Check if email is configured
    if not password_manager.email_config or not password_manager.email_config.get("sender_email"):
        st.error("⚠️ Email is not configured. Please contact your administrator for password reset.")
        return
    
    st.info("📧 Enter your username or email to receive a temporary password")
    
    with st.form("forgot_password_form"):
        identifier = st.text_input(
            "Username or Email", 
            placeholder="Enter your username or email address",
            help="We'll send a temporary password to your registered email address"
        )
        
        submitted = st.form_submit_button("📨 Send Reset Email", type="primary")
        
        if submitted:
            if not identifier:
                st.error("Please enter your username or email")
                return
            
            # Check rate limiting
            try:
                can_proceed, remaining_time = password_reset_limiter.check_rate_limit(identifier)
                if not can_proceed:
                    st.error(f"⏰ Too many reset attempts. Please wait {int(remaining_time)} minutes before trying again.")
                    return
                
                # Record the attempt
                password_reset_limiter.record_attempt(identifier)
            except Exception as e:
                st.warning(f"Rate limiting error: {e}")
            
            # Find user
            try:
                user_data = password_manager.find_user_by_identifier(identifier)
                if not user_data:
                    # For security, don't reveal if user exists or not
                    st.success("📧 If an account exists with that username/email, a reset email has been sent.")
                    st.info("Please check your email (including spam folder) for instructions.")
                    return
                
                username = user_data.get("username")
                email = user_data.get("email")
                
                if not email:
                    st.error("No email address found for this account. Please contact your administrator.")
                    return
                
            except Exception as e:
                st.error(f"Error finding user: {e}")
                return
            
            # Generate reset token and temporary password
            try:
                token_data = password_manager.create_password_reset_token(username)
                
                # Store token
                success, token_id = password_manager.store_reset_token(token_data)
                if not success:
                    st.error(f"Failed to create reset token: {token_id}")
                    return
                
                # Send email
                email_sent, email_message = password_manager.send_reset_email(
                    email, username, token_data["temp_password"], token_data["token"]
                )
                
                if email_sent:
                    st.success("✅ Password reset email sent!")
                    st.info(f"📧 Check your email at {email[:3]}***{email.split('@')[1]} for instructions")
                    
                    # Security information
                    with st.expander("🔒 Important Security Information"):
                        st.markdown("""
                        **What happens next:**
                        1. Check your email for a temporary password
                        2. Use the temporary password to log in (expires in 24 hours)
                        3. You'll be required to set a new password immediately
                        4. Your old password remains valid until you use the temporary password
                        
                        **Security notes:**
                        - Only use passwords sent to your registered email
                        - Contact IT if you receive unexpected reset emails
                        - The temporary password can only be used once
                        """)
                else:
                    st.error(f"Failed to send email: {email_message}")
                    st.info("Please try again later or contact your IT administrator.")
                    
            except Exception as e:
                st.error(f"Error processing password reset: {e}")

def force_password_change_form(username):
    """Force password change form for temporary password users"""
    st.subheader("🔐 Password Change Required")
    st.warning("You logged in with a temporary password. Please set a new password to continue.")
    
    if not PASSWORD_MANAGEMENT_AVAILABLE:
        st.error("Password management system not available")
        return
    
    password_manager = PasswordManager()
    
    with st.form("force_password_change"):
        new_password = st.text_input("New Password", type="password", 
                                   help="Minimum 8 characters with uppercase, lowercase, number, and special character")
        confirm_password = st.text_input("Confirm New Password", type="password")
        
        # Show password requirements
        with st.expander("📋 Password Requirements"):
            st.markdown("""
            **Your password must contain:**
            - At least 8 characters (12+ recommended)
            - At least one lowercase letter (a-z)
            - At least one uppercase letter (A-Z)
            - At least one number (0-9)
            - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
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
            try:
                is_valid, errors, strength, score = password_manager.validate_password_strength(new_password)
                if not is_valid:
                    st.error("Password does not meet requirements:")
                    for error in errors:
                        st.error(f"• {error}")
                    return
                
                # Show password strength
                strength_colors = {
                    "Very Strong": "🟢",
                    "Strong": "🟡", 
                    "Medium": "🟠",
                    "Weak": "🔴"
                }
                st.info(f"Password Strength: {strength_colors.get(strength, '⚪')} {strength}")
                
            except Exception as e:
                st.error(f"Error validating password: {e}")
                return
            
            # Update password
            try:
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
            except Exception as e:
                st.error(f"Error updating password: {e}")

def test_password_system():
    """Test function to verify the password system works"""
    st.subheader("🧪 Password System Test")
    
    if not PASSWORD_MANAGEMENT_AVAILABLE:
        st.error("Password management system not available")
        return
    
    password_manager = PasswordManager()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Test Password Hashing"):
            test_password = "TestPassword123!"
            hashed = password_manager.hash_password_stauth(test_password)
            
            if hashed:
                st.success("✅ Password hashing works")
                st.code(f"Original: {test_password}")
                st.code(f"Hashed: {hashed[:50]}...")
                
                # Test verification
                if password_manager.verify_password_stauth(test_password, hashed):
                    st.success("✅ Password verification works")
                else:
                    st.error("❌ Password verification failed")
            else:
                st.error("❌ Password hashing failed")
    
    with col2:
        if st.button("Test Password Strength"):
            test_passwords = [
                "123",
                "password",
                "Password1", 
                "Password123!",
                "MyVeryStr0ng!Password"
            ]
            
            st.write("**Password Strength Test:**")
            for pwd in test_passwords:
                is_valid, errors, strength, score = password_manager.validate_password_strength(pwd)
                
                strength_colors = {
                    "Very Strong": "🟢",
                    "Strong": "🟡", 
                    "Medium": "🟠",
                    "Weak": "🔴"
                }
                
                st.write(f"{strength_colors.get(strength, '⚪')} **{pwd}**: {strength}")
    
    # Email configuration test
    st.markdown("---")
    if st.button("Test Email Configuration"):
        if password_manager.email_config:
            st.success("✅ Email configuration loaded")
            
            # Display config (hide password)
            config_display = {k: v for k, v in password_manager.email_config.items() if k != "sender_password"}
            config_display["sender_password"] = "***" if password_manager.email_config.get("sender_password") else "Not set"
            st.json(config_display)
        else:
            st.error("❌ Email configuration not available")

def show_help_section():
    """Show help information"""
    with st.expander("🆘 Password Management Help", expanded=True):
        
        tab1, tab2, tab3 = st.tabs(["🔐 Change Password", "🔑 Reset Password", "🛡️ Security Tips"])
        
        with tab1:
            st.markdown("""
            ### Changing Your Password (Logged In)
            
            1. Enter your current password for verification
            2. Create a new strong password following our requirements
            3. Confirm your new password by entering it again
            4. Click "Change Password" to update
            
            **After changing:**
            - Log out and back in for full security
            - You'll receive an email confirmation
            - Update any saved passwords in browsers/apps
            """)
        
        with tab2:
            st.markdown("""
            ### Reset Password (Forgot Password)
            
            1. Enter your username or email address
            2. Click "Send Reset Email"
            3. Check your email for a temporary password
            4. Log in with the temporary password
            5. Immediately create a new permanent password
            
            **Important:**
            - Temporary passwords expire in 24 hours
            - Can only be used once
            - Check spam/junk folders if email doesn't arrive
            """)
        
        with tab3:
            st.markdown("""
            ### Security Best Practices
            
            - Use a unique password for this system
            - Include a mix of character types
            - Don't share your password with anyone
            - Log out when using shared computers
            - Report suspicious activity immediately
            
            **Troubleshooting:**
            - Ensure current password is correct
            - Check new password meets requirements
            - Copy temporary passwords exactly from email
            - Contact IT if problems persist
            """)

def main():
    """Main password management page"""
    st.set_page_config(
        page_title="Password Management - HR System",
        page_icon="🔐",
        layout="centered"
    )
    
    # Header
    st.markdown("""
    # 🔐 Password Management
    Secure password reset and change functionality
    """)
    
    # Show appropriate form based on authentication status
    if is_authenticated():
        st.success("🔓 You are currently logged in")
        
        # Show user info
        username = st.session_state.get("username", "Unknown")
        st.info(f"👤 Logged in as: **{username}**")
        
        # Tabs for different functions
        # tab1, tab2 = st.tabs(["🔄 Change Password", "🧪 Test System"])
        
        # with tab1:
            # change_password_form()

        change_password_form()
        
        # with tab2:
        #     test_password_system()
        
    else:
        st.warning("🔒 Password reset for non-authenticated users")
        
        # # Tabs for reset and testing
        # tab1, tab2 = st.tabs(["🔑 Reset Password", "🧪 Test System"])
        
        # with tab1:
        #     forgot_password_form()
        
        # with tab2:
        #     test_password_system()
        forgot_password_form()
    
    # Navigation
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("← Login Page", type="secondary", use_container_width=True):
            st.switch_page("pages/login.py")
    
    with col2:
        if is_authenticated():
            if st.button("📊 Dashboard", type="primary", use_container_width=True):
                st.switch_page("pages/dashboard.py")
        else:
            if st.button("🔄 Reset Auth", type="secondary", use_container_width=True):
                st.switch_page("pages/reset_auth.py")
    
    with col3:
        if st.button("❓ Help", type="secondary", use_container_width=True):
            show_help_section()

# Run the main function
if __name__ == "__main__":
    main()
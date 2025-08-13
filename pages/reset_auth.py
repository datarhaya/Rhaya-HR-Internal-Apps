# reset_auth.py
import streamlit as st

def reset_authentication():
    """Complete authentication reset"""
    
    st.title("🔄 Authentication Reset")
    
    st.warning("This will completely reset your authentication state.")
    
    if st.button("Reset Everything", type="primary"):
        # Clear all session state
        st.session_state.clear()
        
        # Set explicit reset values
        st.session_state.authentication_status = False
        st.session_state.name = None
        st.session_state.username = None
        st.session_state.logged_out = True
        st.session_state.reset_performed = True
        
        # JavaScript to clear cookies and storage
        st.markdown("""
        <script>
        console.log('Performing complete reset...');
        
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
        
        console.log('Reset complete');
        alert('Reset complete! Redirecting to login...');
        
        // Redirect after delay
        setTimeout(function() {
            window.location.href = '/pages/login.py';
        }, 2000);
        </script>
        """, unsafe_allow_html=True)
        
        st.success("✅ Authentication reset complete!")
        st.info("Redirecting to login page...")
        
    st.markdown("---")
    if st.button("← Back to Login"):
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    reset_authentication()
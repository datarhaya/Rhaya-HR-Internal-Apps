# utils/password_management.py 
import streamlit as st
import streamlit_authenticator as stauth
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import string
import hashlib
from datetime import datetime, timedelta
import utils.database as db
from utils.auth import get_authenticator, check_authentication
from utils.logout_handler import is_authenticated
from utils.secrets_manager import secrets as app_secrets, get_email_config
import re
import logging
import bcrypt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PasswordManager:
    """Fixed password management compatible with streamlit-authenticator 0.4.2"""
    
    def __init__(self):
        self.db = db.get_db()
        self.email_config = self.get_email_config()
    
    def get_email_config(self):
        """Get email configuration from secrets manager"""
        try:
            email_config = app_secrets.email_config
            return {
                "smtp_server": email_config.get("smtp_server", "smtp.gmail.com"),
                "smtp_port": int(email_config.get("smtp_port", 587)),
                "use_tls": email_config.get("use_tls", True),
                "sender_email": email_config.get("sender_email"),
                "sender_password": email_config.get("sender_password"),
                "sender_name": email_config.get("sender_name", "HR Management System"),
                "company_name": email_config.get("company_name", "Your Company"),
                "support_email": email_config.get("support_email", "support@yourcompany.com"),
                "max_reset_attempts": int(email_config.get("max_reset_attempts", 3)),
                "reset_cooldown_minutes": int(email_config.get("reset_cooldown_minutes", 15)),
            }
        except Exception as e:
            st.error(f"Error loading email configuration: {e}")
            return None
    
    def verify_password_bcrypt(self, password, hashed_password):
        """Verify password using bcrypt - compatible method"""
        try:
            # Convert string hash to bytes if needed
            if isinstance(hashed_password, str):
                hashed_password = hashed_password.encode('utf-8')
            if isinstance(password, str):
                password = password.encode('utf-8')
            
            return bcrypt.checkpw(password, hashed_password)
        except Exception as e:
            logger.error(f"Error verifying password with bcrypt: {e}")
            return False
    
    def hash_password_bcrypt(self, password):
        """Hash password using bcrypt"""
        try:
            if isinstance(password, str):
                password = password.encode('utf-8')
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password, salt).decode('utf-8')
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            return None
    
    def verify_password_stauth(self, password, hashed_password):
        """Verify password using streamlit-authenticator compatible method"""
        try:
            # For streamlit-authenticator 0.4.2, we need to use the authenticate method indirectly
            # or use bcrypt directly since the Hasher class methods may not be available
            
            # Try bcrypt first (most common)
            if self.verify_password_bcrypt(password, hashed_password):
                return True
            
            # Fallback: try to use stauth if available
            try:
                # Create temporary credentials to test
                test_credentials = {
                    "usernames": {
                        "test": {
                            "name": "test",
                            "password": hashed_password
                        }
                    }
                }
                
                authenticator = stauth.Authenticate(
                    test_credentials,
                    "test_cookie",
                    "test_key",
                    30
                )
                
                # This is a workaround - we create a temporary authenticator to test the password
                # Note: This approach may need adjustment based on your specific setup
                return self.verify_password_bcrypt(password, hashed_password)
                
            except Exception as e:
                logger.warning(f"Streamlit-authenticator verification failed: {e}")
                return self.verify_password_bcrypt(password, hashed_password)
                
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def hash_password_stauth(self, password):
        """Hash password using streamlit-authenticator compatible method"""
        try:
            # Use bcrypt directly for compatibility
            return self.hash_password_bcrypt(password)
            
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            # Fallback to bcrypt
            return self.hash_password_bcrypt(password)
    
    def generate_secure_password(self, length=12):
        """Generate a cryptographically secure password"""
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase  
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(special)
        ]
        
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)
    
    def validate_password_strength(self, password):
        """Comprehensive password strength validation"""
        errors = []
        score = 0
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        elif len(password) >= 12:
            score += 1
        
        if len(password) > 128:
            errors.append("Password must be less than 128 characters")
            
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        else:
            score += 1
            
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        else:
            score += 1
            
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one number")
        else:
            score += 1
            
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            errors.append("Password must contain at least one special character")
        else:
            score += 1
        
        if len(set(password)) < len(password) * 0.7:
            errors.append("Password has too many repeated characters")
        
        common_patterns = [r'123', r'abc', r'password', r'admin', r'user', r'qwerty', r'asdf']
        for pattern in common_patterns:
            if re.search(pattern, password.lower()):
                errors.append(f"Password contains common pattern: {pattern}")
        
        if score >= 5 and len(password) >= 12:
            strength = "Very Strong"
        elif score >= 4 and len(password) >= 10:
            strength = "Strong"
        elif score >= 3 and len(password) >= 8:
            strength = "Medium"
        else:
            strength = "Weak"
        
        is_valid = len(errors) == 0
        return is_valid, errors, strength, score
    
    def verify_current_password(self, username, current_password):
        """Verify user's current password - FIXED VERSION"""
        try:
            users_auth = self.db.collection("users_auth")
            user_query = users_auth.where("username", "==", username).limit(1).stream()
            
            for doc in user_query:
                user_data = doc.to_dict()
                stored_password = user_data.get("password", "")
                
                # Use the fixed password verification
                if self.verify_password_stauth(current_password, stored_password):
                    logger.info(f"Password verification successful for user: {username}")
                    return True, "Password verified"
                else:
                    logger.warning(f"Password verification failed for user: {username}")
                    return False, "Current password is incorrect"
            
            logger.warning(f"User not found: {username}")
            return False, "User not found"
            
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False, f"Verification error: {str(e)}"
    
    def update_password(self, username, new_password):
        """Update user password - FIXED VERSION"""
        try:
            users_auth = self.db.collection("users_auth")
            user_query = users_auth.where("username", "==", username).limit(1).stream()
            
            for doc in user_query:
                # Hash new password using the fixed method
                new_password_hash = self.hash_password_stauth(new_password)
                
                if not new_password_hash:
                    return False, "Failed to hash password"
                
                # Update password
                doc.reference.update({
                    "password": new_password_hash,
                    "password_changed_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "force_password_change": False
                })
                
                logger.info(f"Password updated for user: {username}")
                return True, "Password updated successfully"
            
            return False, "User not found"
            
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            return False, f"Update error: {str(e)}"
    
    def create_password_reset_token(self, username):
        """Create secure password reset token"""
        timestamp = datetime.now().isoformat()
        random_component = secrets.token_urlsafe(32)
        token_data = f"{username}:{timestamp}:{random_component}"
        
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()
        temp_password = self.generate_secure_password(16)
        temp_password_hash = self.hash_password_stauth(temp_password)
        
        return {
            "token": token_hash,
            "username": username,
            "temp_password": temp_password,
            "temp_password_hash": temp_password_hash,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=24),
            "used": False,
            "ip_address": "unknown",
            "user_agent": "unknown"
        }
    
    def store_reset_token(self, token_data):
        """Store password reset token"""
        try:
            self.cleanup_expired_tokens()
            
            tokens_ref = self.db.collection("password_reset_tokens")
            token_ref = tokens_ref.document()
            token_data["token_id"] = token_ref.id
            token_ref.set(token_data)
            
            logger.info(f"Password reset token created for user: {token_data['username']}")
            return True, token_ref.id
            
        except Exception as e:
            logger.error(f"Error storing reset token: {e}")
            return False, str(e)
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens"""
        try:
            tokens_ref = self.db.collection("password_reset_tokens")
            expired_query = tokens_ref.where("expires_at", "<", datetime.now()).stream()
            
            for doc in expired_query:
                doc.reference.delete()
                
        except Exception as e:
            logger.error(f"Error cleaning up tokens: {e}")
    
    def verify_reset_token(self, username, temp_password):
        """Verify and consume a reset token - FIXED VERSION"""
        try:
            tokens_ref = self.db.collection("password_reset_tokens")
            
            valid_query = tokens_ref.where("username", "==", username)\
                                   .where("used", "==", False)\
                                   .where("expires_at", ">", datetime.now()).stream()
            
            for doc in valid_query:
                token_data = doc.to_dict()
                stored_hash = token_data.get("temp_password_hash", "")
                
                # Use the fixed password verification
                if self.verify_password_stauth(temp_password, stored_hash):
                    # Mark token as used
                    doc.reference.update({
                        "used": True,
                        "used_at": datetime.now(),
                        "used_ip": "unknown"
                    })
                    
                    logger.info(f"Password reset token used for user: {username}")
                    return True, token_data
            
            return False, "Invalid or expired temporary password"
            
        except Exception as e:
            logger.error(f"Error verifying reset token: {e}")
            return False, str(e)
    
    def send_reset_email(self, email, username, temp_password, token):
        """Send password reset email"""
        try:
            if not self.email_config or not all([self.email_config.get("sender_email"), self.email_config.get("sender_password")]):
                return False, "Email configuration not complete"
            
            # Create simple email message
            msg = MIMEMultipart()
            msg['From'] = f"{self.email_config['sender_name']} <{self.email_config['sender_email']}>"
            msg['To'] = email
            msg['Subject'] = f"Password Reset - {self.email_config['company_name']} HR System"
            
            # Email body
            body = f"""
Dear {username},

You have requested a password reset for your HR Management System account.

Your temporary password is: {temp_password}

IMPORTANT SECURITY INFORMATION:
- This temporary password will expire in 24 hours
- You MUST change this password on your first login
- Your old password will remain active until you successfully log in with this temporary password
- If you did not request this reset, please contact IT immediately

To use this temporary password:
1. Go to the login page
2. Enter your username
3. Enter the temporary password above
4. You will be prompted to change your password immediately

For security reasons, this temporary password can only be used once.

Best regards,
{self.email_config['company_name']} HR Management System

---
This is an automated message. Please do not reply to this email.
If you need assistance, please contact your IT administrator.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"])
            if self.email_config.get("use_tls", True):
                server.starttls()
            server.login(self.email_config["sender_email"], self.email_config["sender_password"])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Password reset email sent to: {email[:3]}***{email.split('@')[1]}")
            return True, "Email sent successfully"
            
        except Exception as e:
            logger.error(f"Failed to send reset email: {e}")
            return False, f"Email delivery failed: {str(e)}"
    
    def find_user_by_username(self, username):
        """Find user data by username"""
        try:
            users_auth = self.db.collection("users_auth")
            user_query = users_auth.where("username", "==", username).limit(1).stream()
            
            for doc in user_query:
                user_auth_data = doc.to_dict()
                employee_id = user_auth_data.get("employee_id")
                
                if employee_id:
                    employee_data = self.db.collection("users_db").document(employee_id).get().to_dict()
                    if employee_data:
                        return {
                            "username": username,
                            "email": employee_data.get("email"),
                            "name": employee_data.get("name"),
                            "employee_id": employee_id
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding user: {e}")
            return None
    
    def find_user_by_identifier(self, identifier):
        """Find user by username or email"""
        try:
            # Try username first
            user_data = self.find_user_by_username(identifier)
            if user_data:
                return user_data
            
            # Try email
            users_db = self.db.collection("users_db")
            email_query = users_db.where("email", "==", identifier).limit(1).stream()
            
            for doc in email_query:
                employee_data = doc.to_dict()
                employee_id = doc.id
                
                users_auth = self.db.collection("users_auth")
                auth_query = users_auth.where("employee_id", "==", employee_id).limit(1).stream()
                
                for auth_doc in auth_query:
                    user_auth_data = auth_doc.to_dict()
                    return {
                        "username": user_auth_data.get("username"),
                        "email": employee_data.get("email"),
                        "name": employee_data.get("name"),
                        "employee_id": employee_id
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding user by identifier: {e}")
            return None

# Rate limiting class
class PasswordResetRateLimit:
    def __init__(self):
        self.attempts = {}
    
    def check_rate_limit(self, username, max_attempts=3, cooldown_minutes=15):
        """Check if user has exceeded rate limit"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        if username not in self.attempts:
            self.attempts[username] = {"count": 0, "last_attempt": now}
            return True, 0
        
        user_attempts = self.attempts[username]
        time_since_last = now - user_attempts["last_attempt"]
        
        if time_since_last > timedelta(minutes=cooldown_minutes):
            self.attempts[username] = {"count": 0, "last_attempt": now}
            return True, 0
        
        if user_attempts["count"] >= max_attempts:
            remaining_time = timedelta(minutes=cooldown_minutes) - time_since_last
            return False, remaining_time.total_seconds() // 60
        
        return True, user_attempts["count"]
    
    def record_attempt(self, username):
        """Record a password reset attempt"""
        from datetime import datetime
        
        now = datetime.now()
        if username in self.attempts:
            self.attempts[username]["count"] += 1
            self.attempts[username]["last_attempt"] = now
        else:
            self.attempts[username] = {"count": 1, "last_attempt": now}

# Global rate limiter
password_reset_limiter = PasswordResetRateLimit()

# Test function to verify the fix
def test_password_verification():
    """Test function to verify password verification works"""
    st.write("Testing password verification...")
    
    pm = PasswordManager()
    
    # Test password hashing
    test_password = "TestPassword123!"
    hashed = pm.hash_password_stauth(test_password)
    
    if hashed:
        st.success("✅ Password hashing works")
        
        # Test password verification
        if pm.verify_password_stauth(test_password, hashed):
            st.success("✅ Password verification works")
        else:
            st.error("❌ Password verification failed")
    else:
        st.error("❌ Password hashing failed")

if __name__ == "__main__":
    test_password_verification()
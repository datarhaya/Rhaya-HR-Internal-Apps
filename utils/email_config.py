# utils/email_config.py - Email configuration and templates
import streamlit as st

# Email templates for different scenarios
class EmailTemplates:
    
    @staticmethod
    def password_reset_template(username, temp_password, token_short, company_name="Your Company"):
        """Template for password reset emails"""
        return {
            "subject": f"Password Reset - {company_name} HR System",
            "html_body": f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; }}
                    .password-box {{ background-color: #fff; border: 2px solid #007bff; padding: 15px; 
                                   margin: 20px 0; text-align: center; font-size: 18px; font-weight: bold; }}
                    .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
                    .footer {{ background-color: #6c757d; color: white; padding: 15px; text-align: center; font-size: 12px; }}
                    .button {{ background-color: #007bff; color: white; padding: 12px 25px; 
                              text-decoration: none; border-radius: 5px; display: inline-block; margin: 15px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 Password Reset Request</h1>
                        <p>{company_name} HR Management System</p>
                    </div>
                    
                    <div class="content">
                        <h2>Hello {username},</h2>
                        
                        <p>You have requested a password reset for your HR Management System account.</p>
                        
                        <div class="password-box">
                            Your temporary password: <code>{temp_password}</code>
                        </div>
                        
                        <div class="warning">
                            <h3>⚠️ IMPORTANT SECURITY INFORMATION</h3>
                            <ul>
                                <li><strong>Expires in 24 hours</strong> - Use this password soon</li>
                                <li><strong>One-time use only</strong> - This password can only be used once</li>
                                <li><strong>Must be changed</strong> - You'll be required to set a new password immediately</li>
                                <li><strong>Old password still valid</strong> - Until you use this temporary password</li>
                                <li><strong>Contact IT immediately</strong> - If you didn't request this reset</li>
                            </ul>
                        </div>
                        
                        <h3>🚀 How to use this temporary password:</h3>
                        <ol>
                            <li>Go to the HR System login page</li>
                            <li>Enter your username: <strong>{username}</strong></li>
                            <li>Enter the temporary password exactly as shown above</li>
                            <li>You will be prompted to create a new password immediately</li>
                        </ol>
                        
                        <p><strong>Reset Token (for support):</strong> {token_short}...</p>
                        
                        <p>If you're having trouble logging in or didn't request this reset, please contact your IT administrator immediately.</p>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated message from {company_name} HR Management System.</p>
                        <p>Please do not reply to this email. For support, contact your IT administrator.</p>
                        <p>© {company_name} - Confidential and Proprietary</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            "text_body": f"""
Password Reset - {company_name} HR Management System

Hello {username},

You have requested a password reset for your HR Management System account.

TEMPORARY PASSWORD: {temp_password}

IMPORTANT SECURITY INFORMATION:
- This temporary password expires in 24 hours
- Can only be used once
- You MUST change this password on first login  
- Your old password remains active until you use this temporary password
- Contact IT immediately if you didn't request this reset

HOW TO USE:
1. Go to the HR System login page
2. Username: {username}
3. Password: {temp_password}
4. Create new password when prompted

Reset Token (for support): {token_short}...

If you're having trouble or didn't request this reset, contact your IT administrator immediately.

---
This is an automated message from {company_name} HR Management System.
Do not reply to this email. For support, contact your IT administrator.
© {company_name} - Confidential and Proprietary
            """
        }
    
    @staticmethod
    def password_changed_notification(username, timestamp, ip_address=None):
        """Template for password change notifications"""
        location_info = f" from IP address {ip_address}" if ip_address else ""
        
        return {
            "subject": "Password Changed Successfully - HR System",
            "html_body": f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background-color: #28a745; color: white; padding: 20px; text-align: center;">
                        <h1>✅ Password Changed Successfully</h1>
                    </div>
                    
                    <div style="background-color: #f9f9f9; padding: 30px;">
                        <h2>Hello {username},</h2>
                        
                        <p>Your password has been successfully changed{location_info}.</p>
                        
                        <p><strong>Change Date:</strong> {timestamp}</p>
                        
                        <div style="background-color: #d1ecf1; border-left: 4px solid #17a2b8; padding: 15px; margin: 20px 0;">
                            <h3>🛡️ Security Reminder</h3>
                            <p>If you did not make this change, please contact your IT administrator immediately and consider:</p>
                            <ul>
                                <li>Changing your password again</li>
                                <li>Reviewing your account activity</li>
                                <li>Enabling additional security measures</li>
                            </ul>
                        </div>
                        
                        <p>Thank you for keeping your account secure!</p>
                    </div>
                    
                    <div style="background-color: #6c757d; color: white; padding: 15px; text-align: center; font-size: 12px;">
                        <p>This is an automated security notification.</p>
                        <p>Do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            "text_body": f"""
Password Changed Successfully - HR System

Hello {username},

Your password has been successfully changed{location_info}.

Change Date: {timestamp}

SECURITY REMINDER:
If you did not make this change, contact your IT administrator immediately and consider:
- Changing your password again
- Reviewing your account activity  
- Enabling additional security measures

Thank you for keeping your account secure!

---
This is an automated security notification.
Do not reply to this email.
            """
        }

# Email configuration helper
def get_email_config():
    """Get email configuration from Streamlit secrets with fallbacks"""
    try:
        email_config = st.secrets.get("email", {})
        
        config = {
            # SMTP Server settings
            "smtp_server": email_config.get("smtp_server", "smtp.gmail.com"),
            "smtp_port": int(email_config.get("smtp_port", 587)),
            "use_tls": email_config.get("use_tls", True),
            
            # Authentication
            "sender_email": email_config.get("sender_email"),
            "sender_password": email_config.get("sender_password"),  # App password for Gmail
            "sender_name": email_config.get("sender_name", "HR Management System"),
            
            # Company settings
            "company_name": email_config.get("company_name", "Your Company"),
            "support_email": email_config.get("support_email", "support@yourcompany.com"),
            
            # Security settings
            "max_reset_attempts": int(email_config.get("max_reset_attempts", 3)),
            "reset_cooldown_minutes": int(email_config.get("reset_cooldown_minutes", 15)),
        }
        
        return config
        
    except Exception as e:
        st.error(f"Error loading email configuration: {e}")
        return None

def validate_email_config():
    """Validate that email configuration is properly set up"""
    config = get_email_config()
    
    if not config:
        return False, "Email configuration not found"
    
    required_fields = ["sender_email", "sender_password"]
    missing_fields = [field for field in required_fields if not config.get(field)]
    
    if missing_fields:
        return False, f"Missing required email configuration: {', '.join(missing_fields)}"
    
    return True, "Email configuration is valid"

# Sample secrets.toml configuration
def get_sample_secrets_config():
    """Return sample secrets configuration for email"""
    return """
# Add this to your .streamlit/secrets.toml file

[email]
# SMTP Configuration (Gmail example)
smtp_server = "smtp.gmail.com"
smtp_port = 587
use_tls = true

# Email credentials (use App Password for Gmail)
sender_email = "your-hr-system@yourcompany.com"
sender_password = "your-app-password-here"
sender_name = "HR Management System"

# Company information
company_name = "Your Company Name"
support_email = "it-support@yourcompany.com"

# Security settings
max_reset_attempts = 3
reset_cooldown_minutes = 15

# For other email providers:
# Office 365: smtp_server = "smtp.office365.com", smtp_port = 587
# Yahoo: smtp_server = "smtp.mail.yahoo.com", smtp_port = 587
# Custom SMTP: Use your provider's settings
"""

# Rate limiting for password reset requests
class PasswordResetRateLimit:
    def __init__(self):
        self.attempts = {}  # username -> {count, last_attempt}
    
    def check_rate_limit(self, username, max_attempts=3, cooldown_minutes=15):
        """Check if user has exceeded rate limit for password resets"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        config = get_email_config()
        
        if config:
            max_attempts = config.get("max_reset_attempts", 3)
            cooldown_minutes = config.get("reset_cooldown_minutes", 15)
        
        if username not in self.attempts:
            self.attempts[username] = {"count": 0, "last_attempt": now}
            return True, 0
        
        user_attempts = self.attempts[username]
        time_since_last = now - user_attempts["last_attempt"]
        
        # Reset counter if cooldown period has passed
        if time_since_last > timedelta(minutes=cooldown_minutes):
            self.attempts[username] = {"count": 0, "last_attempt": now}
            return True, 0
        
        # Check if limit exceeded
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

# Global rate limiter instance
password_reset_limiter = PasswordResetRateLimit()
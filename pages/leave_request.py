# Enhanced leave_request.py with file upload INSIDE the form
import streamlit as st
from datetime import datetime, date, timedelta
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    LEAVE_TYPES, submit_leave_request, get_employee_leave_quota,
    get_employee_leave_requests, calculate_working_days
)

# Import Firebase Storage utilities
try:
    from utils.firebase_storage import (
        FirebaseStorageManager, 
        display_file_attachment,
        get_storage_config
    )
    STORAGE_AVAILABLE = True
except ImportError:
    st.warning("⚠️ Firebase Storage not configured. File uploads will be disabled.")
    STORAGE_AVAILABLE = False

import pandas as pd

# Authentication check
if not is_authenticated():
    st.warning("You must log in first.")
    if st.button("Go to Login Page"):
        st.switch_page("pages/login.py")
    st.stop()

# Get user data
if "user_data" not in st.session_state:
    st.error("Session expired. Please log in again.")
    st.switch_page("pages/login.py")
    st.stop()

user_data = st.session_state["user_data"]
employee_id = user_data.get("employee_id")
access_level = user_data.get("access_level", 4)

def upload_file_to_firebase(uploaded_file, employee_id, request_type="leave"):
    """
    Upload file to Firebase Storage (called during form submission)
    
    Args:
        uploaded_file: Streamlit uploaded file object
        employee_id: Employee ID
        request_type: Type of request
        
    Returns:
        dict: Upload result
    """
    if not STORAGE_AVAILABLE:
        return {"success": False, "message": "Firebase Storage not available"}
    
    try:
        storage_manager = FirebaseStorageManager()
        
        if not storage_manager.bucket:
            return {"success": False, "message": "Storage not initialized"}
        
        result = storage_manager.upload_file(
            uploaded_file,
            employee_id,
            request_type
        )
        
        return result
        
    except Exception as e:
        return {"success": False, "message": f"Upload error: {str(e)}"}

def show_attachment_in_history(request):
    """Show file attachment in request history"""
    
    if not request.get("attachment"):
        return
    
    attachment_data = request["attachment"]
    
    # Handle both old and new attachment formats
    if isinstance(attachment_data, dict) and attachment_data.get("file_path"):
        # Firebase Storage format
        st.markdown("**📎 Attachment:**")
        
        if STORAGE_AVAILABLE:
            display_file_attachment(
                attachment_data.get("file_path"),
                attachment_data
            )
        else:
            # Fallback display
            st.caption(f"📎 {attachment_data.get('original_filename', 'Unknown file')}")
            st.caption(f"Size: {attachment_data.get('file_size', 0) / 1024:.1f} KB")
    
    elif isinstance(attachment_data, str):
        # Legacy format (just filename)
        st.caption(f"📎 Legacy attachment: {attachment_data}")
    
    else:
        # Unknown format
        st.caption("📎 Attachment information unavailable")

# Page header
st.title("📝 Leave Request System")

# Show admin indicator
if access_level == 1:
    st.success("🔑 **Admin Access:** You can view all leave requests across the organization")

# Logout button
if st.sidebar.button("🚪 Logout", key="logout_leave"):
    handle_logout()
    st.success("Logged out! Redirecting...")
    st.markdown(clear_cookies_js(), unsafe_allow_html=True)
    st.stop()

# Navigation
col1, col2 = st.columns([1, 1])
with col1:
    if st.sidebar.button("🏠 Back to Dashboard"):
        st.switch_page("pages/dashboard.py")

with col2:
    # Show approvals button for managers
    if access_level in [1, 2, 3]:
        if st.button("✅ Approve Requests"):
            st.switch_page("pages/leave_approval.py")

st.divider()

# Create tabs
tab1, tab2, tab3 = st.tabs(["📝 New Request", "📊 My Leave Status", "📋 Request History"])

with tab1:
    st.subheader("Submit New Leave Request")
    
    # Get leave quota info
    leave_quota = get_employee_leave_quota(employee_id) if employee_id else None
    
    if leave_quota:
        # Display current leave balance
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Annual Quota", f"{leave_quota.get('annual_quota', 14)} days")
        with col2:
            st.metric("Used", f"{leave_quota.get('annual_used', 0)} days")
        with col3:
            remaining = leave_quota.get('annual_quota', 14) - leave_quota.get('annual_used', 0) - leave_quota.get('annual_pending', 0)
            st.metric("Available", f"{remaining} days")
    
    st.markdown("---")
    
    # Show file upload info
    if STORAGE_AVAILABLE:
        storage_config = get_storage_config()
        st.info(f"📎 **File Upload Available:** Max {storage_config.get('max_file_size_mb', 10)} MB | Types: {', '.join(storage_config.get('allowed_extensions', []))}")
    else:
        st.warning("📁 File upload not available - Contact administrator")
    
    # Leave request form with file upload INSIDE
    with st.form("leave_request_form"):
        st.markdown("### Leave Request Details")
        
        # Leave type selection
        leave_type_options = {}
        for key, config in LEAVE_TYPES.items():
            # Filter by gender if applicable
            if config.get("gender_specific"):
                user_gender = user_data.get("gender", "").lower()
                if config["gender_specific"] != user_gender:
                    continue
            leave_type_options[key] = f"{config['name']} - {config['description']}"
        
        selected_leave_type = st.selectbox(
            "Leave Type *",
            options=list(leave_type_options.keys()),
            format_func=lambda x: leave_type_options[x],
            help="Select the type of leave you want to request"
        )
        
        # Date selection
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date *",
                min_value=date.today(),
                help="First day of leave"
            )
        
        with col2:
            # Set minimum end date to start date
            min_end_date = start_date if start_date else date.today()
            end_date = st.date_input(
                "End Date *",
                min_value=min_end_date,
                value=min_end_date,
                help="Last day of leave"
            )
        
        # Calculate and display working days
        if start_date and end_date:
            working_days = calculate_working_days(start_date, end_date)
            st.info(f"📅 **Working days:** {working_days} days")
            
            # Show warning for fixed-day leave types
            leave_config = LEAVE_TYPES.get(selected_leave_type, {})
            if leave_config.get("fixed_days"):
                fixed_days = leave_config["fixed_days"]
                if working_days != fixed_days:
                    st.warning(f"⚠️ {leave_config['name']} must be exactly {fixed_days} working days")
        
        # Reason for leave
        reason = st.text_area(
            "Reason *",
            placeholder="Please provide the reason for your leave request...",
            help="Explain why you need this leave",
            max_chars=500
        )
        
        # Emergency contact (for certain leave types)
        emergency_contact = None
        if selected_leave_type in ["maternity", "marriage"]:
            emergency_contact = st.text_input(
                "Emergency Contact",
                placeholder="Name and phone number of emergency contact",
                help="Required for extended leave periods"
            )
        
        # File upload INSIDE the form
        st.markdown("### 📎 Supporting Documents (Optional)")
        
        if STORAGE_AVAILABLE:
            storage_config = get_storage_config()
            
            # Show upload guidelines
            with st.expander("ℹ️ File Upload Guidelines"):
                st.markdown(f"""
                **Accepted file types:** {', '.join(storage_config.get('allowed_extensions', []))}
                **Maximum file size:** {storage_config.get('max_file_size_mb', 10)} MB
                **Security:** All files are encrypted and securely stored
                
                **Recommended for different leave types:**
                - 🏥 **Sick Leave:** Medical certificate
                - 💒 **Marriage Leave:** Wedding invitation or certificate  
                - ⚰️ **Bereavement Leave:** Death certificate or funeral notice
                - 🤱 **Maternity Leave:** Medical documentation
                """)
            
            # File uploader INSIDE form
            uploaded_file = st.file_uploader(
                "Choose file to attach",
                type=[ext.replace(".", "") for ext in storage_config.get('allowed_extensions', [])],
                help=f"Upload supporting documents (max {storage_config.get('max_file_size_mb', 10)} MB)",
                key="leave_file_uploader"
            )
            
            # Show file preview if file selected
            if uploaded_file:
                st.success(f"📄 **File selected:** {uploaded_file.name}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"**Size:** {uploaded_file.size / (1024 * 1024):.2f} MB")
                with col2:
                    st.caption(f"**Type:** {uploaded_file.name.split('.')[-1].upper()}")
                with col3:
                    st.caption(f"**Ready for upload** ✅")
        
        else:
            st.info("📁 File upload not available - Contact administrator to enable file attachments")
            uploaded_file = None
        
        # Submit button for the form
        submit_button = st.form_submit_button("🚀 Submit Leave Request", type="primary")
        
        if submit_button:
            # Validation
            if not all([start_date, end_date, reason.strip()]):
                st.error("❌ Please fill in all required fields")
            elif start_date > end_date:
                st.error("❌ Start date cannot be after end date")
            elif start_date < date.today():
                st.error("❌ Cannot request leave for past dates")
            else:
                # Show processing message
                with st.spinner("Processing leave request..."):
                    
                    # Prepare leave data
                    leave_data = {
                        "leave_type": selected_leave_type,
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "reason": reason.strip()
                    }
                    
                    if emergency_contact:
                        leave_data["emergency_contact"] = emergency_contact
                    
                    # Handle file upload if file was selected
                    file_upload_success = True
                    if uploaded_file and STORAGE_AVAILABLE:
                        st.info("📤 Uploading file...")
                        
                        # Upload file to Firebase Storage
                        upload_result = upload_file_to_firebase(
                            uploaded_file, 
                            employee_id, 
                            request_type="leave"
                        )
                        
                        if upload_result["success"]:
                            st.success(f"✅ File uploaded: {uploaded_file.name}")
                            
                            # Add file attachment data to leave request
                            leave_data["attachment"] = {
                                "file_path": upload_result["file_path"],
                                "original_filename": upload_result["file_metadata"]["original_filename"],
                                "file_size": upload_result["file_metadata"]["file_size"],
                                "mime_type": upload_result["file_metadata"]["mime_type"],
                                "upload_timestamp": upload_result["file_metadata"]["upload_timestamp"],
                                "storage_type": "firebase"
                            }
                        else:
                            st.error(f"❌ File upload failed: {upload_result['message']}")
                            st.warning("⚠️ Leave request will be submitted without attachment")
                            file_upload_success = False
                    
                    # Submit leave request
                    st.info("📝 Submitting leave request...")
                    result = submit_leave_request(employee_id, leave_data)
                    
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        st.balloons()
                        
                        # Show summary
                        st.markdown("### 📋 Request Summary")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            leave_type_name = LEAVE_TYPES.get(selected_leave_type, {}).get('name', 'Unknown')
                            st.write(f"**Leave Type:** {leave_type_name}")
                            st.write(f"**Duration:** {working_days} working days")
                            st.write(f"**Period:** {start_date} to {end_date}")
                        
                        with col2:
                            st.write(f"**Status:** 🕐 Pending Approval")
                            if uploaded_file and file_upload_success:
                                st.write(f"**Attachment:** ✅ {uploaded_file.name}")
                            elif uploaded_file and not file_upload_success:
                                st.write(f"**Attachment:** ❌ Upload failed")
                            else:
                                st.write(f"**Attachment:** ➖ None")
                        
                        st.info("📧 Your request has been sent to your supervisor for approval.")
                        
                        # Auto-refresh after success
                        import time
                        time.sleep(3)
                        st.rerun()
                        
                    else:
                        st.error(f"❌ {result['message']}")
                        
                        # If leave request failed but file was uploaded, offer to delete the file
                        if uploaded_file and file_upload_success and leave_data.get("attachment"):
                            st.warning("⚠️ Leave request failed but file was uploaded. The uploaded file will be cleaned up automatically.")

with tab2:
    st.subheader("📊 My Leave Status")
    
    if leave_quota:
        # Detailed quota breakdown
        annual_quota = leave_quota.get("annual_quota", 14)
        annual_used = leave_quota.get("annual_used", 0)
        annual_pending = leave_quota.get("annual_pending", 0)
        available = annual_quota - annual_used - annual_pending
        
        st.markdown("### Annual Leave Quota")
        
        # Progress visualization
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Quota", f"{annual_quota} days")
        
        with col2:
            st.metric("Used", f"{annual_used} days")
            if annual_quota > 0:
                st.progress(annual_used / annual_quota)
        
        with col3:
            st.metric("Pending", f"{annual_pending} days")
            if annual_quota > 0:
                st.progress(annual_pending / annual_quota if annual_pending > 0 else 0.0)
        
        with col4:
            st.metric("Available", f"{available} days")
            if annual_quota > 0:
                st.progress(available / annual_quota if available > 0 else 0.0)
        
        # Visual quota representation
        st.markdown("### Quota Visualization")
        
        quota_data = {
            "Used": annual_used,
            "Pending": annual_pending,
            "Available": available
        }
        
        colors = ["#ff6b6b", "#ffd93d", "#6bcf7f"]
        col_widths = [quota_data[key] / annual_quota if annual_quota > 0 else 0 for key in quota_data.keys()]
        
        # Display quota bar
        cols = st.columns([max(0.1, width) for width in col_widths] + [0.1])
        for i, (label, value) in enumerate(quota_data.items()):
            if value > 0:
                with cols[i]:
                    st.markdown(f"""
                    <div style="background-color: {colors[i]}; padding: 10px; border-radius: 5px; text-align: center; margin: 2px;">
                        <strong>{label}</strong><br>{value} days
                    </div>
                    """, unsafe_allow_html=True)
    
    else:
        st.warning("⚠️ Unable to load leave quota information")

with tab3:
    st.subheader("📋 My Leave Request History")
    
    # Get and display leave requests with attachment support
    all_requests = get_employee_leave_requests(employee_id) if employee_id else []
    
    if not all_requests:
        st.info("📋 No leave requests found.")
    else:
        st.write(f"📊 **Total Requests:** {len(all_requests)}")
        
        # Display requests
        for i, request in enumerate(all_requests):
            with st.container():
                # Create columns for request details
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    leave_type_name = LEAVE_TYPES.get(request["leave_type"], {}).get("name", "Unknown")
                    st.write(f"**{leave_type_name}**")
                    st.caption(f"📅 {request['start_date']} to {request['end_date']}")
                    if request.get("reason"):
                        st.caption(f"💭 {request['reason'][:100]}{'...' if len(request['reason']) > 100 else ''}")
                
                with col2:
                    st.write(f"**{request.get('working_days', 0)} days**")
                
                with col3:
                    status = request.get("status", "unknown")
                    if status == "pending":
                        st.warning("🕐 Pending")
                    elif status == "approved_final":
                        st.success("✅ Approved")
                    elif status == "rejected":
                        st.error("❌ Rejected")
                    else:
                        st.info("📋 Processing")
                
                with col4:
                    submitted_date = request.get("submitted_at")
                    if hasattr(submitted_date, "timestamp"):
                        submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime("%d/%m/%Y")
                    else:
                        submitted_str = "Unknown"
                    st.caption(f"Submitted: {submitted_str}")
                
                # Show additional details in expander
                with st.expander(f"Details - {leave_type_name} ({request['start_date']})"):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.write("**Request Information:**")
                        st.write(f"• **Type:** {leave_type_name}")
                        st.write(f"• **Duration:** {request.get('working_days', 0)} working days")
                        st.write(f"• **Period:** {request['start_date']} to {request['end_date']}")
                        st.write(f"• **Status:** {status.title()}")
                        
                        if request.get("emergency_contact"):
                            st.write(f"• **Emergency Contact:** {request['emergency_contact']}")
                    
                    with col_b:
                        st.write("**Processing Information:**")
                        
                        if hasattr(submitted_date, "timestamp"):
                            submitted_full = datetime.fromtimestamp(submitted_date.timestamp()).strftime("%d %B %Y, %H:%M")
                            st.write(f"• **Submitted:** {submitted_full}")
                        
                        if request.get("approved_at"):
                            approved_date = request["approved_at"]
                            if hasattr(approved_date, "timestamp"):
                                approved_str = datetime.fromtimestamp(approved_date.timestamp()).strftime("%d %B %Y, %H:%M")
                                st.write(f"• **Approved:** {approved_str}")
                        
                        if request.get("rejected_at"):
                            rejected_date = request["rejected_at"]
                            if hasattr(rejected_date, "timestamp"):
                                rejected_str = datetime.fromtimestamp(rejected_date.timestamp()).strftime("%d %B %Y, %H:%M")
                                st.write(f"• **Rejected:** {rejected_str}")
                        
                        if request.get("approver_comments"):
                            st.write(f"• **Comments:** {request['approver_comments']}")
                    
                    # Full reason
                    if request.get("reason"):
                        st.write("**Reason:**")
                        st.write(request["reason"])
                    
                    # Show attachment with Firebase Storage support
                    show_attachment_in_history(request)
                
                st.divider()

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if access_level in [1, 2, 3]:
        if st.button("✅ Approve Requests", use_container_width=True):
            st.switch_page("pages/leave_approval.py")

with col3:
    if access_level == 1:
        if st.button("⚙️ Admin Panel", use_container_width=True):
            st.switch_page("pages/admin_control.py")

# Sidebar info
# if STORAGE_AVAILABLE:
#     st.sidebar.markdown("### 📁 File Storage")
#     try:
#         storage_config = get_storage_config()
#         st.sidebar.success("✅ Firebase Storage Active")
#         st.sidebar.caption(f"Max file size: {storage_config.get('max_file_size_mb', 10)} MB")
#         st.sidebar.caption(f"Allowed types: {len(storage_config.get('allowed_extensions', []))} formats")
#     except:
#         st.sidebar.warning("⚠️ Storage configuration issue")
# else:
#     st.sidebar.warning("📁 File storage disabled")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
# Enhanced leave_request.py with admin view for all history
import streamlit as st
from datetime import datetime, date, timedelta
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    LEAVE_TYPES, submit_leave_request, get_employee_leave_quota,
    get_employee_leave_requests, calculate_working_days
)
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

def get_all_leave_history_admin():
    """Get all leave requests in the system for admin view"""
    try:
        requests = []
        query = db.db.collection("leave_requests").order_by("submitted_at", direction=db.firestore.Query.DESCENDING)
        
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Enrich with employee data
            employee_data = db.db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
            if employee_data:
                request_data["employee_name"] = employee_data.get("name")
                request_data["employee_email"] = employee_data.get("email")
                request_data["employee_division"] = employee_data.get("division_name", "Unknown")
                request_data["employee_role"] = employee_data.get("role_name", "Unknown")
            
            # Enrich with approver data
            if request_data.get("approver_id"):
                approver_data = db.db.collection("users_db").document(request_data["approver_id"]).get().to_dict()
                if approver_data:
                    request_data["approver_name"] = approver_data.get("name", "Unknown")
                    request_data["approver_role"] = approver_data.get("role_name", "Unknown")
            
            requests.append(request_data)
        
        return requests
        
    except Exception as e:
        st.error(f"Error getting all leave history: {e}")
        return []

# Page header
st.title("📝 Leave Request System")

# Show admin indicator
if access_level == 1:
    st.success("🔑 **Admin Access:** You can view all leave requests across the organization")

# Logout button
if st.button("🚪 Logout", key="logout_leave"):
    handle_logout()
    st.success("Logged out! Redirecting...")
    st.markdown(clear_cookies_js(), unsafe_allow_html=True)
    st.stop()

# Navigation
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🏠 Back to Dashboard"):
        st.switch_page("pages/dashboard.py")

with col2:
    # Show approvals button for managers
    if access_level in [1, 2, 3]:
        if st.button("✅ Approve Requests"):
            st.switch_page("pages/leave_approval.py")

st.divider()

# Create different tabs based on access level
if access_level == 1:  # Admin gets additional tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 New Request", 
        "📊 My Leave Status", 
        "📋 My Request History",
        "🌐 All System History"
    ])
else:
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
    
    # Leave request form
    with st.form("leave_request_form"):
        st.markdown("### Leave Request Details")
        
        # Leave type selection
        leave_type_options = {}
        for key, config in LEAVE_TYPES.items():
            # Filter by gender if applicable
            if config.get("gender_specific"):
                # Assuming we have gender in user data
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
        
        # File upload for documentation (optional)
        uploaded_file = st.file_uploader(
            "Supporting Documents (Optional)",
            type=['pdf', 'jpg', 'jpeg', 'png'],
            help="Upload medical certificate, invitation, or other supporting documents"
        )
        
        # Submit button
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
                # Prepare leave data
                leave_data = {
                    "leave_type": selected_leave_type,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "reason": reason.strip()
                }
                
                if emergency_contact:
                    leave_data["emergency_contact"] = emergency_contact
                
                if uploaded_file:
                    # In a real implementation, you'd save the file and store the path
                    leave_data["attachment"] = f"attachment_{uploaded_file.name}"
                
                # Submit request
                result = submit_leave_request(employee_id, leave_data)
                
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                    st.info("Your request has been sent to your supervisor for approval.")
                    
                    # Clear form by rerunning
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

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
        
        # Create a visual bar
        quota_data = {
            "Used": annual_used,
            "Pending": annual_pending,
            "Available": available
        }
        
        colors = ["#ff6b6b", "#ffd93d", "#6bcf7f"]
        col_widths = [quota_data[key] / annual_quota if annual_quota > 0 else 0 for key in quota_data.keys()]
        
        # Display quota bar
        cols = st.columns([max(0.1, width) for width in col_widths] + [0.1])  # Ensure minimum width
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
    
    st.markdown("---")
    
    # Leave types information
    st.markdown("### Available Leave Types")
    
    for leave_type, config in LEAVE_TYPES.items():
        # Filter by gender if applicable
        if config.get("gender_specific"):
            user_gender = user_data.get("gender", "").lower()
            if config["gender_specific"] != user_gender:
                continue
        
        with st.expander(f"{config['name']} - {config['description']}"):
            if config.get("has_quota"):
                st.write(f"📊 **Quota:** {config.get('max_days', 'Variable')} days per year")
            elif config.get("fixed_days"):
                st.write(f"📅 **Duration:** {config['fixed_days']} days")
            elif config.get("max_consecutive"):
                st.write(f"⏰ **Limit:** {config['max_consecutive']} consecutive days without medical certificate")
            elif config.get("max_per_month"):
                st.write(f"📅 **Limit:** {config['max_per_month']} day per month")
            
            if config.get("once_per_marriage"):
                st.write("⚠️ **Note:** Can only be used once per marriage")
            
            st.write(f"✅ **Approval Required:** {'Yes' if config['requires_approval'] else 'No'}")

with tab3:
    st.subheader("📋 My Leave Request History")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "Pending", "Approved", "Rejected"],
            index=0
        )
    
    with col2:
        year_filter = st.selectbox(
            "Filter by Year",
            options=["All"] + [str(year) for year in range(datetime.now().year, datetime.now().year - 3, -1)],
            index=0
        )
    
    with col3:
        leave_type_filter = st.selectbox(
            "Filter by Type",
            options=["All"] + [config["name"] for config in LEAVE_TYPES.values()],
            index=0
        )
    
    # Get leave requests
    all_requests = get_employee_leave_requests(employee_id) if employee_id else []
    
    # Apply filters
    filtered_requests = []
    for request in all_requests:
        # Status filter
        if status_filter != "All":
            if status_filter.lower() == "approved" and request.get("status") != "approved_final":
                continue
            elif status_filter.lower() != "approved" and request.get("status") != status_filter.lower():
                continue
        
        # Year filter
        if year_filter != "All":
            request_year = datetime.strptime(request["start_date"], "%Y-%m-%d").year
            if request_year != int(year_filter):
                continue
        
        # Leave type filter
        if leave_type_filter != "All":
            request_leave_type = LEAVE_TYPES.get(request["leave_type"], {}).get("name", "Unknown")
            if request_leave_type != leave_type_filter:
                continue
        
        filtered_requests.append(request)
    
    if not filtered_requests:
        st.info("📋 No leave requests found matching the selected filters.")
    else:
        st.write(f"📊 **Total Requests:** {len(filtered_requests)}")
        
        # Display requests
        for i, request in enumerate(filtered_requests):
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
                    
                    # Attachment info
                    if request.get("attachment"):
                        st.write(f"📎 **Attachment:** {request['attachment']}")
                
                st.divider()

# Admin-only tab for all system history
if access_level == 1:
    with tab4:
        st.subheader("🌐 All System Leave History (Admin View)")
        st.info("👑 **Admin Privilege:** View complete leave history across the organization")
        
        # Get all leave history
        all_system_history = get_all_leave_history_admin()
        
        if not all_system_history:
            st.info("📋 No leave requests found in the system.")
        else:
            st.success(f"📊 **{len(all_system_history)}** total requests found across all employees")
            
            # Enhanced filter options for admin
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                admin_status_filter = st.selectbox(
                    "Status",
                    options=["All", "Pending", "Approved", "Rejected"],
                    key="admin_status_filter"
                )
            
            with col2:
                admin_division_filter = st.selectbox(
                    "Division",
                    options=["All"] + list(set([r.get("employee_division", "Unknown") for r in all_system_history])),
                    key="admin_division_filter"
                )
            
            with col3:
                admin_year_filter = st.selectbox(
                    "Year",
                    options=["All"] + [str(year) for year in range(datetime.now().year, datetime.now().year - 3, -1)],
                    key="admin_year_filter"
                )
            
            with col4:
                admin_leave_type_filter = st.selectbox(
                    "Leave Type",
                    options=["All"] + [LEAVE_TYPES.get(lt, {}).get("name", lt) for lt in set([r.get("leave_type") for r in all_system_history])],
                    key="admin_leave_type_filter"
                )
            
            with col5:
                admin_employee_filter = st.text_input(
                    "Employee Name",
                    placeholder="Search by name...",
                    key="admin_employee_filter"
                )
            
            # Apply filters
            filtered_system_history = all_system_history
            
            if admin_status_filter != "All":
                if admin_status_filter.lower() == "approved":
                    filtered_system_history = [r for r in filtered_system_history if r.get("status") == "approved_final"]
                elif admin_status_filter.lower() == "rejected":
                    filtered_system_history = [r for r in filtered_system_history if r.get("status") == "rejected"]
                elif admin_status_filter.lower() == "pending":
                    filtered_system_history = [r for r in filtered_system_history if r.get("status") == "pending"]
            
            if admin_division_filter != "All":
                filtered_system_history = [r for r in filtered_system_history if r.get("employee_division") == admin_division_filter]
            
            if admin_year_filter != "All":
                filtered_system_history = [r for r in filtered_system_history if datetime.strptime(r.get("start_date", "1900-01-01"), "%Y-%m-%d").year == int(admin_year_filter)]
            
            if admin_leave_type_filter != "All":
                filtered_system_history = [r for r in filtered_system_history if LEAVE_TYPES.get(r.get("leave_type"), {}).get("name") == admin_leave_type_filter]
            
            if admin_employee_filter.strip():
                filtered_system_history = [r for r in filtered_system_history if admin_employee_filter.lower() in r.get("employee_name", "").lower()]
            
            # Display filtered results
            if filtered_system_history:
                st.info(f"📊 Showing {len(filtered_system_history)} of {len(all_system_history)} requests")
                
                # Summary statistics for filtered data
                filtered_approved = len([r for r in filtered_system_history if r.get("status") == "approved_final"])
                filtered_rejected = len([r for r in filtered_system_history if r.get("status") == "rejected"])
                filtered_pending = len([r for r in filtered_system_history if r.get("status") == "pending"])
                
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                with col_stat1:
                    st.metric("Filtered Total", len(filtered_system_history))
                with col_stat2:
                    approval_rate = (filtered_approved / len(filtered_system_history) * 100) if len(filtered_system_history) > 0 else 0
                    st.metric("Approved", filtered_approved, f"{approval_rate:.1f}%")
                with col_stat3:
                    st.metric("Rejected", filtered_rejected)
                with col_stat4:
                    st.metric("Pending", filtered_pending)
                
                # View options
                view_mode = st.radio(
                    "View Mode:",
                    options=["Table View", "Detailed View", "Summary Cards"],
                    horizontal=True
                )
                
                if view_mode == "Table View":
                    # Convert to DataFrame for table display
                    table_data = []
                    for req in filtered_system_history:
                        leave_type_name = LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')
                        
                        # Format dates
                        submitted_date = req.get('submitted_at')
                        if hasattr(submitted_date, 'timestamp'):
                            submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                        else:
                            submitted_str = 'Unknown'
                        
                        # Status with icon
                        status = req.get("status", "unknown")
                        if status == "pending":
                            status_display = "🕐 Pending"
                        elif status == "approved_final":
                            status_display = "✅ Approved"
                        elif status == "rejected":
                            status_display = "❌ Rejected"
                        else:
                            status_display = "📋 Processing"
                        
                        table_data.append({
                            "Employee": req.get("employee_name", "Unknown"),
                            "Division": req.get("employee_division", "Unknown"),
                            "Leave Type": leave_type_name,
                            "Days": req.get("working_days", 0),
                            "Start Date": req.get("start_date"),
                            "End Date": req.get("end_date"),
                            "Status": status_display,
                            "Approver": req.get("approver_name", "Unknown"),
                            "Submitted": submitted_str
                        })
                    
                    df_admin = pd.DataFrame(table_data)
                    st.dataframe(df_admin, use_container_width=True, hide_index=True)
                    
                    # Export option
                    if st.button("📊 Export Filtered Data"):
                        csv = df_admin.to_csv(index=False)
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name=f"filtered_leave_history_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                
                elif view_mode == "Detailed View":
                    # Show detailed cards (limited to first 20 for performance)
                    display_count = min(20, len(filtered_system_history))
                    st.info(f"Showing detailed view for first {display_count} requests")
                    
                    for req in filtered_system_history[:display_count]:
                        with st.container():
                            # Header
                            leave_type_name = LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')
                            status = req.get("status", "unknown")
                            
                            col_header1, col_header2, col_header3 = st.columns([2, 1, 1])
                            
                            with col_header1:
                                st.markdown(f"**👤 {req.get('employee_name', 'Unknown')}** - {leave_type_name}")
                            
                            with col_header2:
                                if status == "pending":
                                    st.warning("🕐 Pending")
                                elif status == "approved_final":
                                    st.success("✅ Approved")
                                elif status == "rejected":
                                    st.error("❌ Rejected")
                                else:
                                    st.info("📋 Processing")
                            
                            with col_header3:
                                st.write(f"**{req.get('working_days', 0)} days**")
                            
                            # Details
                            col_det1, col_det2, col_det3 = st.columns(3)
                            
                            with col_det1:
                                st.write(f"**📧 Email:** {req.get('employee_email', 'N/A')}")
                                st.write(f"**🏢 Division:** {req.get('employee_division', 'Unknown')}")
                                st.write(f"**💼 Role:** {req.get('employee_role', 'Unknown')}")
                            
                            with col_det2:
                                st.write(f"**📅 Period:** {req.get('start_date')} to {req.get('end_date')}")
                                
                                submitted_date = req.get('submitted_at')
                                if hasattr(submitted_date, 'timestamp'):
                                    submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %B %Y, %H:%M')
                                    st.write(f"**📤 Submitted:** {submitted_str}")
                                
                                if req.get('reason'):
                                    st.write(f"**💭 Reason:** {req['reason'][:100]}{'...' if len(req['reason']) > 100 else ''}")
                            
                            with col_det3:
                                if req.get("approver_name"):
                                    st.write(f"**✅ Approver:** {req.get('approver_name')}")
                                    st.write(f"**🎭 Approver Role:** {req.get('approver_role', 'Unknown')}")
                                
                                # Processing date
                                processed_date = req.get('approved_at') or req.get('rejected_at')
                                if processed_date and hasattr(processed_date, 'timestamp'):
                                    processed_str = datetime.fromtimestamp(processed_date.timestamp()).strftime('%d %B %Y, %H:%M')
                                    st.write(f"**⏰ Processed:** {processed_str}")
                                
                                if req.get('approver_comments'):
                                    st.write(f"**💬 Comments:** {req['approver_comments']}")
                            
                            st.markdown("---")
                
                elif view_mode == "Summary Cards":
                    # Group by division or leave type for summary
                    summary_by = st.selectbox(
                        "Summarize by:",
                        options=["Division", "Leave Type", "Status", "Month"],
                        key="admin_summary_by"
                    )
                    
                    if summary_by == "Division":
                        division_summary = {}
                        for req in filtered_system_history:
                            division = req.get("employee_division", "Unknown")
                            if division not in division_summary:
                                division_summary[division] = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
                            
                            division_summary[division]["total"] += 1
                            status = req.get("status", "pending")
                            if status == "approved_final":
                                division_summary[division]["approved"] += 1
                            elif status == "rejected":
                                division_summary[division]["rejected"] += 1
                            elif status == "pending":
                                division_summary[division]["pending"] += 1
                        
                        # Display division cards
                        for division, stats in division_summary.items():
                            with st.container():
                                st.markdown(f"### 🏢 {division} Division")
                                
                                col1, col2, col3, col4, col5 = st.columns(5)
                                
                                with col1:
                                    st.metric("Total", stats["total"])
                                with col2:
                                    st.metric("Approved", stats["approved"])
                                with col3:
                                    st.metric("Rejected", stats["rejected"])
                                with col4:
                                    st.metric("Pending", stats["pending"])
                                with col5:
                                    approval_rate = (stats["approved"] / stats["total"] * 100) if stats["total"] > 0 else 0
                                    st.metric("Approval Rate", f"{approval_rate:.1f}%")
                                
                                st.markdown("---")
                    
                    elif summary_by == "Leave Type":
                        leave_type_summary = {}
                        for req in filtered_system_history:
                            leave_type = LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')
                            if leave_type not in leave_type_summary:
                                leave_type_summary[leave_type] = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
                            
                            leave_type_summary[leave_type]["total"] += 1
                            status = req.get("status", "pending")
                            if status == "approved_final":
                                leave_type_summary[leave_type]["approved"] += 1
                            elif status == "rejected":
                                leave_type_summary[leave_type]["rejected"] += 1
                            elif status == "pending":
                                leave_type_summary[leave_type]["pending"] += 1
                        
                        # Display leave type cards
                        for leave_type, stats in leave_type_summary.items():
                            with st.container():
                                st.markdown(f"### 📝 {leave_type}")
                                
                                col1, col2, col3, col4, col5 = st.columns(5)
                                
                                with col1:
                                    st.metric("Total", stats["total"])
                                with col2:
                                    st.metric("Approved", stats["approved"])
                                with col3:
                                    st.metric("Rejected", stats["rejected"])
                                with col4:
                                    st.metric("Pending", stats["pending"])
                                with col5:
                                    approval_rate = (stats["approved"] / stats["total"] * 100) if stats["total"] > 0 else 0
                                    st.metric("Approval Rate", f"{approval_rate:.1f}%")
                                
                                st.markdown("---")
                    
                    elif summary_by == "Month":
                        monthly_summary = {}
                        for req in filtered_system_history:
                            try:
                                start_date = datetime.strptime(req.get("start_date", "1900-01-01"), "%Y-%m-%d")
                                month_key = start_date.strftime("%Y-%m")
                                if month_key not in monthly_summary:
                                    monthly_summary[month_key] = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
                                
                                monthly_summary[month_key]["total"] += 1
                                status = req.get("status", "pending")
                                if status == "approved_final":
                                    monthly_summary[month_key]["approved"] += 1
                                elif status == "rejected":
                                    monthly_summary[month_key]["rejected"] += 1
                                elif status == "pending":
                                    monthly_summary[month_key]["pending"] += 1
                            except:
                                continue
                        
                        # Display monthly cards (sorted)
                        for month, stats in sorted(monthly_summary.items(), reverse=True):
                            with st.container():
                                month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
                                st.markdown(f"### 📅 {month_display}")
                                
                                col1, col2, col3, col4, col5 = st.columns(5)
                                
                                with col1:
                                    st.metric("Total", stats["total"])
                                with col2:
                                    st.metric("Approved", stats["approved"])
                                with col3:
                                    st.metric("Rejected", stats["rejected"])
                                with col4:
                                    st.metric("Pending", stats["pending"])
                                with col5:
                                    approval_rate = (stats["approved"] / stats["total"] * 100) if stats["total"] > 0 else 0
                                    st.metric("Approval Rate", f"{approval_rate:.1f}%")
                                
                                st.markdown("---")
            else:
                st.info("No requests match the selected filters.")

# Footer with navigation
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

# Statistics for the current year (in sidebar)
if filtered_requests or (access_level == 1 and all_system_history):
    st.sidebar.markdown("### 📊 Leave Statistics")
    
    # For regular users, show their own stats
    if access_level != 1:
        current_year_requests = [r for r in all_requests 
                               if datetime.strptime(r["start_date"], "%Y-%m-%d").year == datetime.now().year]
        
        if current_year_requests:
            total_requests = len(current_year_requests)
            approved_requests = len([r for r in current_year_requests if r.get("status") == "approved_final"])
            pending_requests = len([r for r in current_year_requests if r.get("status") == "pending"])
            rejected_requests = len([r for r in current_year_requests if r.get("status") == "rejected"])
            
            st.sidebar.metric("My Requests", total_requests)
            st.sidebar.metric("Approved", approved_requests)
            st.sidebar.metric("Pending", pending_requests)
            st.sidebar.metric("Rejected", rejected_requests)
            
            # Approval rate
            if total_requests > 0:
                approval_rate = (approved_requests / total_requests) * 100
                st.sidebar.metric("My Approval Rate", f"{approval_rate:.1f}%")
    
    # For admin users, show system-wide stats
    else:
        current_year_system = [r for r in all_system_history 
                              if datetime.strptime(r.get("start_date", "1900-01-01"), "%Y-%m-%d").year == datetime.now().year]
        
        if current_year_system:
            total_system = len(current_year_system)
            approved_system = len([r for r in current_year_system if r.get("status") == "approved_final"])
            pending_system = len([r for r in current_year_system if r.get("status") == "pending"])
            rejected_system = len([r for r in current_year_system if r.get("status") == "rejected"])
            
            st.sidebar.markdown("**System-wide (Current Year)**")
            st.sidebar.metric("Total Requests", total_system)
            st.sidebar.metric("Approved", approved_system)
            st.sidebar.metric("Pending", pending_system)
            st.sidebar.metric("Rejected", rejected_system)
            
            # System approval rate
            if total_system > 0:
                system_approval_rate = (approved_system / total_system) * 100
                st.sidebar.metric("System Approval Rate", f"{system_approval_rate:.1f}%")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
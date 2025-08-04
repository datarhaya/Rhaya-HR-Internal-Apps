# Enhanced leave_approval.py with admin view for all requests
import streamlit as st
from datetime import datetime
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    LEAVE_TYPES, DIVISIONS, get_pending_approvals_for_approver, 
    approve_leave_request, reject_leave_request, get_employee_leave_quota,
    get_team_members, get_approval_chain
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

# Check if user has approval permissions (or is admin)
if access_level not in [1, 2, 3]:
    st.error("🚫 Access Denied: You don't have permission to approve leave requests.")
    st.info("Only Admin, HR Staff, and Division Heads can approve leave requests.")
    if st.button("🏠 Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

def get_all_leave_requests():
    """Get all leave requests in the system (for admin view)"""
    try:
        requests = []
        query = db.collection("leave_requests").order_by("submitted_at", direction=db.firestore.Query.DESCENDING)
        
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Enrich with employee data
            employee_data = db.db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
            if employee_data:
                request_data["employee_name"] = employee_data.get("name")
                request_data["employee_email"] = employee_data.get("email")
                request_data["employee_division"] = DIVISIONS.get(employee_data.get("division_id"), "Unknown")
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
        st.error(f"Error getting all requests: {e}")
        return []

def get_all_leave_history():
    """Get all processed leave requests (approved/rejected) for admin view"""
    try:
        all_requests = get_all_leave_requests()
        # Filter for processed requests
        history = [r for r in all_requests if r.get("status") in ["approved_final", "rejected"]]
        return history
    except Exception as e:
        st.error(f"Error getting leave history: {e}")
        return []

# Page header
st.title("Leave Request Approval")
st.markdown(f"**Approver:** {user_data.get('name')} | **Role:** {user_data.get('role_name')}")

# Show different interface for admin (level 1)
if access_level == 1:
    st.success("🔑 **Admin Access:** You can view and manage all leave requests in the system")
else:
    # Show approval scope for non-admin users
    team_info = get_team_members(employee_id) if employee_id else {"direct_reports": [], "division_reports": [], "total_count": 0}
    if team_info["total_count"] > 0:
        st.info(f"👥 **Your Approval Scope:** {team_info['total_count']} team members")

# Logout button
if st.button("🚪 Logout", key="logout_approval"):
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
    if st.button("📝 My Leave Requests"):
        st.switch_page("pages/leave_request.py")

st.divider()

# Create different tabs based on access level
if access_level == 1:  # Admin gets additional tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 My Pending Approvals", 
        "🌐 All Pending Requests", 
        "📊 All Leave History",
        "👥 My Team", 
        "📈 System Overview"
    ])
else:
    tab1, tab2, tab3 = st.tabs(["📋 Pending Approvals", "👥 My Team", "📊 Approval History"])

with tab1:
    st.subheader("📋 My Pending Approvals")
    
    # Get pending approvals for this user
    pending_approvals = get_pending_approvals_for_approver(employee_id) if employee_id else []

    if not pending_approvals:
        st.success("🎉 No pending leave requests for your approval!")
        st.info("All caught up! Check back later for new requests.")
    else:
        st.markdown(f"### 📋 Pending Approvals ({len(pending_approvals)})")
        st.warning(f"⚠️ You have **{len(pending_approvals)}** leave request(s) awaiting your approval.")

        # Process each pending request (same logic as before)
        for i, request in enumerate(pending_approvals):
            with st.container():
                # Request header with enhanced info
                col_header1, col_header2 = st.columns([3, 1])
                
                with col_header1:
                    st.markdown(f"#### 📝 Request #{i+1} - {request.get('employee_name', 'Unknown')}")
                
                with col_header2:
                    # Show approval type badge
                    approval_type = request.get('approval_type', 'unknown')
                    if approval_type == 'direct_supervisor':
                        st.success("👤 Direct Report")
                    elif approval_type == 'division_head':
                        st.info("🏢 Division Member")
                    else:
                        st.warning("⚡ Escalated")

                # Employee and request info
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**👤 Employee:** {request.get('employee_name', 'Unknown')}")
                    st.markdown(f"**📧 Email:** {request.get('employee_email', 'N/A')}")
                    st.markdown(f"**🏢 Division:** {request.get('employee_division', 'Unknown')}")
                    st.markdown(f"**💼 Role:** {request.get('employee_role', 'Unknown')}")
                    
                    leave_type_name = LEAVE_TYPES.get(request['leave_type'], {}).get('name', 'Unknown')
                    st.markdown(f"**📝 Leave Type:** {leave_type_name}")
                
                with col2:
                    st.markdown(f"**📅 Duration:** {request.get('working_days', 0)} working days")
                    st.markdown(f"**📆 Period:**")
                    st.markdown(f"{request['start_date']} to {request['end_date']}")
                
                with col3:
                    submitted_date = request.get('submitted_at')
                    if hasattr(submitted_date, 'timestamp'):
                        submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                    else:
                        submitted_str = 'Unknown'
                    st.markdown(f"**📤 Submitted:** {submitted_str}")
                    st.markdown(f"**⏰ Status:** 🕐 Pending")

                # Reason
                if request.get('reason'):
                    st.markdown("**💭 Reason:**")
                    st.write(request['reason'])

                # Employee leave balance (for annual leave)
                if request['leave_type'] == 'annual':
                    employee_quota = get_employee_leave_quota(request['employee_id'])
                    if employee_quota:
                        st.markdown("**📊 Employee Leave Balance:**")
                        
                        col_a, col_b, col_c, col_d = st.columns(4)
                        
                        with col_a:
                            st.metric("Quota", f"{employee_quota.get('annual_quota', 14)} days")
                        with col_b:
                            st.metric("Used", f"{employee_quota.get('annual_used', 0)} days")
                        with col_c:
                            pending = employee_quota.get('annual_pending', 0)
                            st.metric("Pending", f"{pending} days")
                        with col_d:
                            remaining = (employee_quota.get('annual_quota', 14) - 
                                       employee_quota.get('annual_used', 0) - 
                                       pending)
                            st.metric("Available", f"{remaining} days")
                        
                        # Warning if request exceeds available balance
                        if request.get('working_days', 0) > remaining:
                            st.error(f"⚠️ **Warning:** This request ({request.get('working_days', 0)} days) exceeds available balance ({remaining} days)")

                # Additional information
                if request.get('emergency_contact'):
                    st.markdown(f"**📞 Emergency Contact:** {request['emergency_contact']}")

                if request.get('attachment'):
                    st.markdown(f"**📎 Attachment:** {request['attachment']}")

                st.markdown("---")
                
                # Approval actions
                st.markdown("**🎯 Action Required:**")
                
                # Create unique keys for each request
                approve_key = f"approve_{request['id']}"
                reject_key = f"reject_{request['id']}"
                comments_key = f"comments_{request['id']}"
                
                # Comments field
                approval_comments = st.text_area(
                    "💬 Comments (Optional)",
                    key=comments_key,
                    placeholder="Add any comments for the employee...",
                    help="Comments will be visible to the employee",
                    max_chars=500
                )
                
                # Action buttons
                col_approve, col_reject, col_info = st.columns([1, 1, 2])
                
                with col_approve:
                    if st.button(f"✅ Approve", key=approve_key, type="primary", use_container_width=True):
                        if f"confirm_approve_{request['id']}" not in st.session_state:
                            st.session_state[f"confirm_approve_{request['id']}"] = True
                            st.rerun()
                
                with col_reject:
                    if st.button(f"❌ Reject", key=reject_key, type="secondary", use_container_width=True):
                        if f"confirm_reject_{request['id']}" not in st.session_state:
                            st.session_state[f"confirm_reject_{request['id']}"] = True
                            st.rerun()
                
                with col_info:
                    st.info("💡 Review carefully before deciding")

                # Handle approval confirmation
                if st.session_state.get(f"confirm_approve_{request['id']}"):
                    st.warning("⚠️ **CONFIRM APPROVAL**")
                    st.write(f"Approve {request.get('working_days', 0)} days of {leave_type_name} for {request.get('employee_name')}?")
                    
                    col_yes, col_no = st.columns(2)
                    
                    with col_yes:
                        if st.button(f"🟢 Yes, Approve", key=f"yes_approve_{request['id']}", type="primary"):
                            result = approve_leave_request(request['id'], employee_id, approval_comments)
                            
                            if result['success']:
                                st.success(f"✅ {result['message']}")
                                st.balloons()
                                
                                # Clear confirmation state
                                if f"confirm_approve_{request['id']}" in st.session_state:
                                    del st.session_state[f"confirm_approve_{request['id']}"]
                                
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {result['message']}")
                    
                    with col_no:
                        if st.button(f"🔴 Cancel", key=f"cancel_approve_{request['id']}"):
                            if f"confirm_approve_{request['id']}" in st.session_state:
                                del st.session_state[f"confirm_approve_{request['id']}"]
                            st.rerun()

                # Handle rejection confirmation
                if st.session_state.get(f"confirm_reject_{request['id']}"):
                    st.warning("⚠️ **CONFIRM REJECTION**")
                    st.write(f"Reject {leave_type_name} request from {request.get('employee_name')}?")
                    
                    # Require comments for rejection
                    if not approval_comments.strip():
                        st.error("📝 Please provide a reason for rejection in the comments field above.")
                    else:
                        col_yes, col_no = st.columns(2)
                        
                        with col_yes:
                            if st.button(f"🔴 Yes, Reject", key=f"yes_reject_{request['id']}", type="secondary"):
                                result = reject_leave_request(request['id'], employee_id, approval_comments)
                                
                                if result['success']:
                                    st.success(f"✅ {result['message']}")
                                    
                                    if f"confirm_reject_{request['id']}" in st.session_state:
                                        del st.session_state[f"confirm_reject_{request['id']}"]
                                    
                                    import time
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                        
                        with col_no:
                            if st.button(f"🟢 Cancel", key=f"cancel_reject_{request['id']}"):
                                if f"confirm_reject_{request['id']}" in st.session_state:
                                    del st.session_state[f"confirm_reject_{request['id']}"]
                                st.rerun()
                
                st.markdown("---")
                st.markdown("")  # Space between requests

# Admin-only tabs
if access_level == 1:
    with tab2:
        st.subheader("🌐 All Pending Leave Requests (Admin View)")
        st.info("👑 **Admin Privilege:** View all pending requests across the organization")
        
        # Get all pending requests
        all_pending = []
        try:
            query = db.db.collection("leave_requests").where("status", "==", "pending")
            
            for doc in query.stream():
                request_data = doc.to_dict()
                request_data["id"] = doc.id
                
                # Enrich with employee data
                employee_data = db.db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
                if employee_data:
                    request_data["employee_name"] = employee_data.get("name")
                    request_data["employee_email"] = employee_data.get("email")
                    request_data["employee_division"] = DIVISIONS.get(employee_data.get("division_id"), "Unknown")
                    request_data["employee_role"] = employee_data.get("role_name", "Unknown")
                
                # Enrich with approver data
                if request_data.get("approver_id"):
                    approver_data = db.db.collection("users_db").document(request_data["approver_id"]).get().to_dict()
                    if approver_data:
                        request_data["approver_name"] = approver_data.get("name", "Unknown")
                        request_data["approver_role"] = approver_data.get("role_name", "Unknown")
                
                all_pending.append(request_data)
        
        except Exception as e:
            st.error(f"Error loading all pending requests: {e}")
        
        if not all_pending:
            st.success("🎉 No pending leave requests in the system!")
        else:
            st.warning(f"⚠️ **{len(all_pending)}** pending requests across all divisions")
            
            # Filter options
            col1, col2, col3 = st.columns(3)
            
            with col1:
                division_filter = st.selectbox(
                    "Filter by Division", 
                    options=["All"] + list(set([r.get("employee_division", "Unknown") for r in all_pending])),
                    key="admin_division_filter"
                )
            
            with col2:
                leave_type_filter = st.selectbox(
                    "Filter by Leave Type",
                    options=["All"] + [LEAVE_TYPES.get(lt, {}).get("name", lt) for lt in set([r.get("leave_type") for r in all_pending])],
                    key="admin_leave_type_filter"
                )
            
            with col3:
                approver_filter = st.selectbox(
                    "Filter by Approver",
                    options=["All"] + list(set([r.get("approver_name", "Unknown") for r in all_pending])),
                    key="admin_approver_filter"
                )
            
            # Apply filters
            filtered_pending = all_pending
            if division_filter != "All":
                filtered_pending = [r for r in filtered_pending if r.get("employee_division") == division_filter]
            if leave_type_filter != "All":
                filtered_pending = [r for r in filtered_pending if LEAVE_TYPES.get(r.get("leave_type"), {}).get("name") == leave_type_filter]
            if approver_filter != "All":
                filtered_pending = [r for r in filtered_pending if r.get("approver_name") == approver_filter]
            
            # Display filtered results
            if filtered_pending:
                st.info(f"📊 Showing {len(filtered_pending)} of {len(all_pending)} requests")
                
                # Convert to DataFrame for better display
                display_data = []
                for req in filtered_pending:
                    leave_type_name = LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')
                    submitted_date = req.get('submitted_at')
                    if hasattr(submitted_date, 'timestamp'):
                        submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                    else:
                        submitted_str = 'Unknown'
                    
                    display_data.append({
                        "Employee": req.get("employee_name", "Unknown"),
                        "Division": req.get("employee_division", "Unknown"),
                        "Leave Type": leave_type_name,
                        "Days": req.get("working_days", 0),
                        "Period": f"{req.get('start_date')} to {req.get('end_date')}",
                        "Approver": req.get("approver_name", "Unknown"),
                        "Submitted": submitted_str,
                        "Status": "🕐 Pending"
                    })
                
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Detailed view option
                if st.button("🔍 View Detailed Requests"):
                    for req in filtered_pending[:5]:  # Show first 5 in detail
                        with st.expander(f"📝 {req.get('employee_name')} - {LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Employee:** {req.get('employee_name')}")
                                st.write(f"**Email:** {req.get('employee_email')}")
                                st.write(f"**Division:** {req.get('employee_division')}")
                                st.write(f"**Role:** {req.get('employee_role')}")
                                st.write(f"**Duration:** {req.get('working_days')} days")
                            
                            with col2:
                                st.write(f"**Leave Type:** {LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')}")
                                st.write(f"**Period:** {req.get('start_date')} to {req.get('end_date')}")
                                st.write(f"**Approver:** {req.get('approver_name', 'Unknown')}")
                                st.write(f"**Approver Role:** {req.get('approver_role', 'Unknown')}")
                                
                                submitted_date = req.get('submitted_at')
                                if hasattr(submitted_date, 'timestamp'):
                                    submitted_full = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %B %Y, %H:%M')
                                    st.write(f"**Submitted:** {submitted_full}")
                            
                            if req.get('reason'):
                                st.write("**Reason:**")
                                st.write(req['reason'])
            else:
                st.info("No requests match the selected filters.")

    with tab3:
        st.subheader("📊 Complete Leave History (Admin View)")
        st.info("👑 **Admin Privilege:** View all processed leave requests")
        
        # Get all processed requests
        all_history = get_all_leave_history()
        
        if not all_history:
            st.info("📋 No processed leave requests found.")
        else:
            st.success(f"📊 **{len(all_history)}** processed requests found")
            
            # Filter options
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                status_filter_history = st.selectbox(
                    "Status",
                    options=["All", "Approved", "Rejected"],
                    key="admin_history_status"
                )
            
            with col2:
                division_filter_history = st.selectbox(
                    "Division",
                    options=["All"] + list(set([r.get("employee_division", "Unknown") for r in all_history])),
                    key="admin_history_division"
                )
            
            with col3:
                year_filter_history = st.selectbox(
                    "Year",
                    options=["All"] + [str(year) for year in range(datetime.now().year, datetime.now().year - 3, -1)],
                    key="admin_history_year"
                )
            
            with col4:
                approver_filter_history = st.selectbox(
                    "Processed By",
                    options=["All"] + list(set([r.get("approver_name", "Unknown") for r in all_history])),
                    key="admin_history_approver"
                )
            
            # Apply filters
            filtered_history = all_history
            
            if status_filter_history != "All":
                if status_filter_history == "Approved":
                    filtered_history = [r for r in filtered_history if r.get("status") == "approved_final"]
                elif status_filter_history == "Rejected":
                    filtered_history = [r for r in filtered_history if r.get("status") == "rejected"]
            
            if division_filter_history != "All":
                filtered_history = [r for r in filtered_history if r.get("employee_division") == division_filter_history]
            
            if year_filter_history != "All":
                filtered_history = [r for r in filtered_history if datetime.strptime(r.get("start_date", "1900-01-01"), "%Y-%m-%d").year == int(year_filter_history)]
            
            if approver_filter_history != "All":
                filtered_history = [r for r in filtered_history if r.get("approver_name") == approver_filter_history]
            
            # Display results
            if filtered_history:
                st.info(f"📊 Showing {len(filtered_history)} of {len(all_history)} requests")
                
                # Summary statistics
                approved_count = len([r for r in filtered_history if r.get("status") == "approved_final"])
                rejected_count = len([r for r in filtered_history if r.get("status") == "rejected"])
                
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("Total Processed", len(filtered_history))
                with col_stat2:
                    st.metric("Approved", approved_count, f"{(approved_count/len(filtered_history)*100):.1f}%")
                with col_stat3:
                    st.metric("Rejected", rejected_count, f"{(rejected_count/len(filtered_history)*100):.1f}%")
                
                # Convert to DataFrame
                history_display = []
                for req in filtered_history:
                    leave_type_name = LEAVE_TYPES.get(req.get('leave_type'), {}).get('name', 'Unknown')
                    
                    # Get processed date
                    processed_date = req.get('approved_at') or req.get('rejected_at')
                    if hasattr(processed_date, 'timestamp'):
                        processed_str = datetime.fromtimestamp(processed_date.timestamp()).strftime('%d %b %Y')
                    else:
                        processed_str = 'Unknown'
                    
                    status_icon = "✅ Approved" if req.get("status") == "approved_final" else "❌ Rejected"
                    
                    history_display.append({
                        "Employee": req.get("employee_name", "Unknown"),
                        "Division": req.get("employee_division", "Unknown"),
                        "Leave Type": leave_type_name,
                        "Days": req.get("working_days", 0),
                        "Period": f"{req.get('start_date')} to {req.get('end_date')}",
                        "Status": status_icon,
                        "Processed By": req.get("approver_name", "Unknown"),
                        "Processed Date": processed_str
                    })
                
                df_history = pd.DataFrame(history_display)
                st.dataframe(df_history, use_container_width=True, hide_index=True)
                
                # Export option
                if st.button("📊 Export to CSV"):
                    csv = df_history.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"leave_history_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No requests match the selected filters.")

# Continue with remaining tabs (My Team and System Overview for admin)
if access_level != 1:
    # Non-admin users get the regular My Team tab
    with tab2:
        st.subheader("👥 My Team Overview")
        
        team_info = get_team_members(employee_id) if employee_id else {"direct_reports": [], "division_reports": [], "total_count": 0}
        
        if team_info["total_count"] == 0:
            st.info("👥 You don't have any team members assigned for leave approval.")
        else:
            # Team statistics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Team Members", team_info["total_count"])
            with col2:
                st.metric("Direct Reports", len(team_info["direct_reports"]))
            with col3:
                st.metric("Division Members", len(team_info["division_reports"]))
            
            # Display team members
            if team_info["direct_reports"]:
                st.markdown("### 👤 Direct Reports")
                for member in team_info["direct_reports"]:
                    with st.expander(f"👤 {member.get('name', 'Unknown')} - {member.get('role_name', 'Unknown Role')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Email:** {member.get('email', 'N/A')}")
                            st.write(f"**Division:** {DIVISIONS.get(member.get('division_id'), 'Unknown')}")
                            st.write(f"**Role:** {member.get('role_name', 'Unknown')}")
                        
                        with col2:
                            member_quota = get_employee_leave_quota(member['employee_id'])
                            if member_quota:
                                remaining = (member_quota.get('annual_quota', 14) - 
                                           member_quota.get('annual_used', 0) - 
                                           member_quota.get('annual_pending', 0))
                                st.write(f"**Leave Balance:** {remaining}/{member_quota.get('annual_quota', 14)} days")
            
            if team_info["division_reports"]:
                st.markdown("### 🏢 Division Members")
                for member in team_info["division_reports"]:
                    with st.expander(f"🏢 {member.get('name', 'Unknown')} - {member.get('role_name', 'Unknown Role')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Email:** {member.get('email', 'N/A')}")
                            st.write(f"**Division:** {DIVISIONS.get(member.get('division_id'), 'Unknown')}")
                            st.write(f"**Role:** {member.get('role_name', 'Unknown')}")
                        
                        with col2:
                            member_quota = get_employee_leave_quota(member['employee_id'])
                            if member_quota:
                                remaining = (member_quota.get('annual_quota', 14) - 
                                           member_quota.get('annual_used', 0) - 
                                           member_quota.get('annual_pending', 0))
                                st.write(f"**Leave Balance:** {remaining}/{member_quota.get('annual_quota', 14)} days")
    
    with tab3:
        st.subheader("📊 My Approval History")
        st.info("📊 Personal approval history feature coming soon!")

else:
    # Admin gets additional tabs
    with tab4:
        st.subheader("👥 Organization Overview (Admin)")
        st.info("👑 **Admin View:** Complete organizational structure and team information")
        
        # Get organizational overview
        try:
            all_users = list(db.db.collection("users_db").where("is_active", "==", True).stream())
            
            # Organize by divisions
            divisions_overview = {}
            supervisors_overview = {}
            
            for doc in all_users:
                user_info = doc.to_dict()
                user_info["employee_id"] = doc.id
                
                division = user_info.get("division_name", "Unknown")
                if division not in divisions_overview:
                    divisions_overview[division] = []
                divisions_overview[division].append(user_info)
                
                # Track supervisors
                if user_info.get("access_level") in [1, 2, 3]:
                    supervisor_id = user_info["employee_id"]
                    if supervisor_id not in supervisors_overview:
                        supervisors_overview[supervisor_id] = {
                            "info": user_info,
                            "direct_reports": [],
                            "division_members": []
                        }
            
            # Calculate direct reports
            for doc in all_users:
                user_info = doc.to_dict()
                supervisor_id = user_info.get("direct_supervisor_id")
                if supervisor_id and supervisor_id in supervisors_overview:
                    supervisors_overview[supervisor_id]["direct_reports"].append(user_info)
            
            # Display division overview
            st.markdown("### 🏢 Division Overview")
            
            for division, members in divisions_overview.items():
                with st.expander(f"🏢 {division} Division ({len(members)} members)"):
                    # Division stats
                    access_levels = {}
                    for member in members:
                        level = member.get("access_level", 4)
                        access_levels[level] = access_levels.get(level, 0) + 1
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Members", len(members))
                    with col2:
                        st.metric("Managers (L1-3)", sum([access_levels.get(i, 0) for i in [1, 2, 3]]))
                    with col3:
                        st.metric("Staff (L4)", access_levels.get(4, 0))
                    with col4:
                        with_supervisors = len([m for m in members if m.get("direct_supervisor_id")])
                        st.metric("With Direct Supervisors", with_supervisors)
                    
                    # List members
                    for member in members[:10]:  # Show first 10
                        st.write(f"• **{member.get('name')}** - {member.get('role_name', 'Unknown')} (Level {member.get('access_level', 4)})")
                    
                    if len(members) > 10:
                        st.write(f"... and {len(members) - 10} more members")
            
            # Display supervisor overview
            st.markdown("### 👥 Supervisors Overview")
            
            for supervisor_id, sup_data in supervisors_overview.items():
                sup_info = sup_data["info"]
                direct_count = len(sup_data["direct_reports"])
                
                if direct_count > 0:  # Only show supervisors with direct reports
                    with st.expander(f"👤 {sup_info.get('name')} - {direct_count} direct reports"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Role:** {sup_info.get('role_name', 'Unknown')}")
                            st.write(f"**Division:** {sup_info.get('division_name', 'Unknown')}")
                            st.write(f"**Access Level:** {sup_info.get('access_level')}")
                            st.write(f"**Email:** {sup_info.get('email')}")
                        
                        with col2:
                            st.write("**Direct Reports:**")
                            for report in sup_data["direct_reports"]:
                                st.write(f"• {report.get('name')} ({report.get('role_name', 'Unknown')})")
        
        except Exception as e:
            st.error(f"Error loading organizational overview: {e}")
    
    with tab5:
        st.subheader("📈 System Overview (Admin)")
        st.info("👑 **Admin Dashboard:** System-wide leave management statistics")
        
        # System-wide statistics
        try:
            # Get current year statistics
            current_year = datetime.now().year
            year_start = datetime(current_year, 1, 1)
            
            all_requests = list(db.db.collection("leave_requests").where("created_at", ">=", year_start).stream())
            all_requests_data = [doc.to_dict() for doc in all_requests]
            
            if all_requests_data:
                total_requests = len(all_requests_data)
                approved_requests = len([r for r in all_requests_data if r.get("status") == "approved_final"])
                pending_requests = len([r for r in all_requests_data if r.get("status") == "pending"])
                rejected_requests = len([r for r in all_requests_data if r.get("status") == "rejected"])
                
                # Main metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Requests", total_requests, help=f"All requests in {current_year}")
                
                with col2:
                    approval_rate = (approved_requests / total_requests * 100) if total_requests > 0 else 0
                    st.metric("Approved", approved_requests, f"{approval_rate:.1f}%")
                
                with col3:
                    st.metric("Pending", pending_requests, help="Awaiting approval")
                
                with col4:
                    rejection_rate = (rejected_requests / total_requests * 100) if total_requests > 0 else 0
                    st.metric("Rejected", rejected_requests, f"{rejection_rate:.1f}%")
                
                # Additional system metrics
                st.markdown("### 📊 Detailed Analytics")
                
                # Leave type breakdown
                leave_type_counts = {}
                for request in all_requests_data:
                    leave_type = request.get("leave_type", "unknown")
                    leave_type_counts[leave_type] = leave_type_counts.get(leave_type, 0) + 1
                
                if leave_type_counts:
                    st.markdown("**Leave Type Distribution:**")
                    
                    # Convert to readable names
                    readable_counts = {}
                    for leave_type, count in leave_type_counts.items():
                        readable_name = LEAVE_TYPES.get(leave_type, {}).get("name", leave_type.title())
                        readable_counts[readable_name] = count
                    
                    # Display as chart
                    df_chart = pd.DataFrame(list(readable_counts.items()), columns=["Leave Type", "Count"])
                    st.bar_chart(df_chart.set_index("Leave Type"))
                
                # Monthly trend (if enough data)
                st.markdown("### 📅 Monthly Trends")
                monthly_requests = {}
                for request in all_requests_data:
                    try:
                        start_date = datetime.strptime(request.get("start_date", "1900-01-01"), "%Y-%m-%d")
                        month_key = start_date.strftime("%Y-%m")
                        monthly_requests[month_key] = monthly_requests.get(month_key, 0) + 1
                    except:
                        continue
                
                if monthly_requests:
                    # Sort by month
                    sorted_months = sorted(monthly_requests.items())
                    if len(sorted_months) > 1:
                        df_monthly = pd.DataFrame(sorted_months, columns=["Month", "Requests"])
                        st.line_chart(df_monthly.set_index("Month"))
                    else:
                        st.info("Not enough data for monthly trend analysis")
                
                # Division-wise breakdown
                st.markdown("### 🏢 Division-wise Statistics")
                
                # Get division stats
                division_stats = {}
                for request in all_requests_data:
                    # Get employee division
                    employee_id = request.get("employee_id")
                    if employee_id:
                        try:
                            employee_data = db.db.collection("users_db").document(employee_id).get().to_dict()
                            if employee_data:
                                division = employee_data.get("division_name", "Unknown")
                                if division not in division_stats:
                                    division_stats[division] = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
                                
                                division_stats[division]["total"] += 1
                                status = request.get("status", "pending")
                                if status == "approved_final":
                                    division_stats[division]["approved"] += 1
                                elif status == "rejected":
                                    division_stats[division]["rejected"] += 1
                                elif status == "pending":
                                    division_stats[division]["pending"] += 1
                        except:
                            continue
                
                if division_stats:
                    # Display division stats
                    division_display = []
                    for division, stats in division_stats.items():
                        approval_rate = (stats["approved"] / stats["total"] * 100) if stats["total"] > 0 else 0
                        division_display.append({
                            "Division": division,
                            "Total Requests": stats["total"],
                            "Approved": stats["approved"],
                            "Pending": stats["pending"],
                            "Rejected": stats["rejected"],
                            "Approval Rate": f"{approval_rate:.1f}%"
                        })
                    
                    df_divisions = pd.DataFrame(division_display)
                    st.dataframe(df_divisions, use_container_width=True, hide_index=True)
                
                # Top performers (approvers)
                st.markdown("### 🏆 Approval Activity")
                
                approver_stats = {}
                for request in all_requests_data:
                    if request.get("status") in ["approved_final", "rejected"]:
                        approver_id = request.get("approved_by") or request.get("rejected_by")
                        if approver_id:
                            if approver_id not in approver_stats:
                                approver_stats[approver_id] = {"approved": 0, "rejected": 0, "total": 0}
                            
                            approver_stats[approver_id]["total"] += 1
                            if request.get("status") == "approved_final":
                                approver_stats[approver_id]["approved"] += 1
                            else:
                                approver_stats[approver_id]["rejected"] += 1
                
                if approver_stats:
                    # Get approver names and display top 10
                    approver_display = []
                    for approver_id, stats in approver_stats.items():
                        try:
                            approver_data = db.db.collection("users_db").document(approver_id).get().to_dict()
                            if approver_data:
                                name = approver_data.get("name", "Unknown")
                                role = approver_data.get("role_name", "Unknown")
                                approval_rate = (stats["approved"] / stats["total"] * 100) if stats["total"] > 0 else 0
                                
                                approver_display.append({
                                    "Approver": name,
                                    "Role": role,
                                    "Total Processed": stats["total"],
                                    "Approved": stats["approved"],
                                    "Rejected": stats["rejected"],
                                    "Approval Rate": f"{approval_rate:.1f}%"
                                })
                        except:
                            continue
                    
                    # Sort by total processed
                    approver_display.sort(key=lambda x: x["Total Processed"], reverse=True)
                    
                    if approver_display:
                        df_approvers = pd.DataFrame(approver_display[:10])  # Top 10
                        st.dataframe(df_approvers, use_container_width=True, hide_index=True)
                
                # System health indicators
                st.markdown("### 🏥 System Health Indicators")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Average processing time (mock calculation)
                    avg_processing_days = 2.3  # This would be calculated from actual data
                    st.metric("Avg Processing Time", f"{avg_processing_days} days", help="Average time from submission to approval/rejection")
                
                with col2:
                    # Pending requests older than 5 days
                    old_pending = 0  # This would be calculated from actual data
                    st.metric("Overdue Requests", old_pending, help="Pending requests older than 5 days")
                
                with col3:
                    # System uptime (mock)
                    st.metric("System Availability", "99.9%", help="System uptime percentage")
                
                # Quick actions for admin
                st.markdown("### ⚡ Quick Admin Actions")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📊 Export All Data"):
                        # This would export comprehensive data
                        all_data = []
                        for request in all_requests_data:
                            employee_id = request.get("employee_id")
                            employee_data = None
                            try:
                                employee_data = db.db.collection("users_db").document(employee_id).get().to_dict()
                            except:
                                pass
                            
                            leave_type_name = LEAVE_TYPES.get(request.get('leave_type'), {}).get('name', 'Unknown')
                            
                            all_data.append({
                                "Employee": employee_data.get("name", "Unknown") if employee_data else "Unknown",
                                "Email": employee_data.get("email", "Unknown") if employee_data else "Unknown",
                                "Division": employee_data.get("division_name", "Unknown") if employee_data else "Unknown", 
                                "Leave Type": leave_type_name,
                                "Start Date": request.get("start_date"),
                                "End Date": request.get("end_date"),
                                "Working Days": request.get("working_days", 0),
                                "Status": request.get("status"),
                                "Reason": request.get("reason", ""),
                                "Submitted Date": request.get("submitted_at"),
                                "Processed Date": request.get("approved_at") or request.get("rejected_at")
                            })
                        
                        if all_data:
                            df_export = pd.DataFrame(all_data)
                            csv = df_export.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Complete Data",
                                data=csv,
                                file_name=f"complete_leave_data_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv"
                            )
                
                with col2:
                    if st.button("🔔 Send Reminders"):
                        st.info("Reminder system would send notifications to approvers with pending requests")
                
                with col3:
                    if st.button("📈 Generate Report"):
                        st.info("Comprehensive system report generation would be triggered")
                
            else:
                st.info(f"No leave requests found for {current_year}")
                
                # Show system status even without requests
                st.markdown("### 🏥 System Status")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.success("✅ Database: Connected")
                with col2:
                    st.success("✅ Authentication: Active")
                with col3:
                    st.success("✅ Leave System: Operational")
        
        except Exception as e:
            st.error(f"Error loading system overview: {e}")

# Sidebar with enhanced information
st.sidebar.markdown("### 📋 Approval Guidelines")

st.sidebar.markdown("""
**Before approving, consider:**
- ✅ Business needs and team coverage
- ✅ Employee's leave balance  
- ✅ Validity of reason provided
- ✅ Supporting documentation
- ✅ Department workload
- ✅ Approval authority (direct vs division)
""")

# Show different sidebar content for admin
if access_level == 1:
    st.sidebar.markdown("### 👑 Admin Privileges")
    st.sidebar.success("✅ View all system requests")
    st.sidebar.success("✅ Access complete leave history")
    st.sidebar.success("✅ Organization overview")
    st.sidebar.success("✅ System analytics")
    st.sidebar.success("✅ Export capabilities")
    
    st.sidebar.markdown("### 📊 System Quick Stats")
    try:
        # Quick stats for sidebar
        total_pending = len(list(db.db.collection("leave_requests").where("status", "==", "pending").limit(50).stream()))
        st.sidebar.metric("Total Pending", total_pending)
        
        total_users = len(list(db.db.collection("users_db").where("is_active", "==", True).limit(100).stream()))
        st.sidebar.metric("Active Users", total_users)
    except:
        st.sidebar.info("Loading stats...")

else:
    # Regular user sidebar
    st.sidebar.markdown("### 👥 Your Approval Scope")
    
    team_info = get_team_members(employee_id) if employee_id else {"direct_reports": [], "division_reports": [], "total_count": 0}
    
    if team_info["direct_reports"]:
        st.sidebar.markdown("**Direct Reports:**")
        for member in team_info["direct_reports"][:5]:  # Show first 5
            st.sidebar.write(f"• {member.get('name', 'Unknown')}")
        if len(team_info["direct_reports"]) > 5:
            st.sidebar.write(f"... and {len(team_info['direct_reports']) - 5} more")

    if team_info["division_reports"]:
        st.sidebar.markdown("**Division Members:**")
        for member in team_info["division_reports"][:5]:  # Show first 5
            st.sidebar.write(f"• {member.get('name', 'Unknown')}")
        if len(team_info["division_reports"]) > 5:
            st.sidebar.write(f"... and {len(team_info['division_reports']) - 5} more")

st.sidebar.markdown("### 📊 Leave Types")
for leave_type, config in LEAVE_TYPES.items():
    with st.sidebar.expander(config['name']):
        st.write(config['description'])
        if config.get('has_quota'):
            st.write(f"Quota: {config.get('max_days', 'Variable')} days/year")
        elif config.get('fixed_days'):
            st.write(f"Fixed: {config['fixed_days']} days")

st.sidebar.markdown("### 🆘 Need Help?")
st.sidebar.info("""
**HR Contact:**
📧 hr@company.com
📞 Extension 100

**Leave Policy:**
📖 Employee Handbook Section 4.2
""")

# Footer
st.markdown("---")
if access_level == 1:
    st.caption("🔑 Enhanced Admin Approval System | Complete organizational access")
else:
    st.caption("📋 Enhanced Approval System | Team-based access")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("💡 Tip: Refresh to see latest requests | 🔄 System automatically handles approval hierarchy")
# Enhanced leave_approval.py with dialog details and individual selection
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
from utils.firebase_storage import display_file_attachment

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

# Check if user has approval permissions
if access_level not in [1, 2, 3]:
    st.error("🚫 Access Denied: You don't have permission to approve leave requests.")
    st.info("Only Admin, HR Staff, and Division Heads can approve leave requests.")
    if st.button("🏠 Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

# Initialize session state
if "selected_leave_requests" not in st.session_state:
    st.session_state.selected_leave_requests = set()

if "show_employee_dialog" not in st.session_state:
    st.session_state.show_employee_dialog = False

if "dialog_employee_id" not in st.session_state:
    st.session_state.dialog_employee_id = None

@st.dialog("Employee Details")
def show_employee_details():
    if st.session_state.dialog_employee_id:
        try:
            # Get employee data
            employee_data = db.db.collection("users_db").document(st.session_state.dialog_employee_id).get().to_dict()
            
            if employee_data:
                st.markdown(f"### 👤 {employee_data.get('name', 'Unknown')}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**📧 Email:** {employee_data.get('email', 'N/A')}")
                    st.write(f"**🏢 Division:** {employee_data.get('division_name', 'Unknown')}")
                    st.write(f"**💼 Role:** {employee_data.get('role_name', 'Unknown')}")
                    st.write(f"**🔑 Access Level:** {employee_data.get('access_level', 4)}")
                
                with col2:
                    # Get leave quota
                    leave_quota = get_employee_leave_quota(st.session_state.dialog_employee_id)
                    
                    if leave_quota:
                        annual_quota = leave_quota.get("annual_quota", 14)
                        annual_used = leave_quota.get("annual_used", 0)
                        annual_pending = leave_quota.get("annual_pending", 0)
                        available = annual_quota - annual_used - annual_pending
                        
                        st.write(f"**📊 Leave Quota:** {annual_quota} days")
                        st.write(f"**✅ Used:** {annual_used} days")
                        st.write(f"**🕐 Pending:** {annual_pending} days")
                        st.write(f"**📅 Available:** {available} days")
                    else:
                        st.write("**📊 Leave Balance:** No data available")
                
                # Additional info
                join_date = employee_data.get('start_joining_date')
                if join_date and hasattr(join_date, 'timestamp'):
                    join_str = datetime.fromtimestamp(join_date.timestamp()).strftime('%d %B %Y')
                    st.write(f"**📅 Joined:** {join_str}")
                
                # Supervisor info
                supervisor_id = employee_data.get("direct_supervisor_id")
                if supervisor_id:
                    try:
                        supervisor_data = db.db.collection("users_db").document(supervisor_id).get().to_dict()
                        if supervisor_data:
                            st.write(f"**👥 Supervisor:** {supervisor_data.get('name', 'Unknown')}")
                    except:
                        pass
                
                # Contact info
                if employee_data.get("phone_number"):
                    st.write(f"**📱 Phone:** {employee_data.get('phone_number')}")
                
                # Employee status
                st.write(f"**💼 Status:** {employee_data.get('employee_status', 'Unknown')}")
            else:
                st.error("Employee data not found")
        
        except Exception as e:
            st.error(f"Error loading employee details: {e}")
    
    if st.button("Close", type="primary"):
        st.session_state.show_employee_dialog = False
        st.session_state.dialog_employee_id = None
        st.rerun()

# Page header
st.title("📝 Leave Request Approval")
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

# Show employee details dialog
if st.session_state.show_employee_dialog:
    show_employee_details()

# Main content - Pending Approvals
st.subheader("📋 My Pending Leave Approvals")

# Get pending approvals for this user
pending_approvals = get_pending_approvals_for_approver(employee_id) if employee_id else []

if not pending_approvals:
    st.success("🎉 No pending leave requests for your approval!")
    st.info("All caught up! Check back later for new requests.")
else:
    st.markdown(f"### 📋 Pending Approvals ({len(pending_approvals)})")
    st.warning(f"⚠️ You have **{len(pending_approvals)}** leave request(s) awaiting your approval.")

    # Bulk actions section
    if len(pending_approvals) > 1:
        st.markdown("### ⚡ Bulk Actions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("☑️ Select All"):
                st.session_state.selected_leave_requests = {req["id"] for req in pending_approvals}
                st.rerun()
        
        with col2:
            if st.button("☐ Clear Selection"):
                st.session_state.selected_leave_requests.clear()
                st.rerun()
        
        with col3:
            selected_count = len(st.session_state.selected_leave_requests)
            if selected_count > 0:
                if st.button(f"✅ Approve Selected ({selected_count})"):
                    st.session_state.bulk_approve_selected = True
        
        with col4:
            if selected_count > 0:
                if st.button(f"❌ Reject Selected ({selected_count})"):
                    st.session_state.bulk_reject_selected = True
        
        # Handle bulk approve selected
        if st.session_state.get("bulk_approve_selected"):
            st.warning("⚠️ **CONFIRM BULK APPROVAL**")
            selected_requests = [req for req in pending_approvals if req["id"] in st.session_state.selected_leave_requests]
            total_days = sum(req.get("working_days", 0) for req in selected_requests)
            
            st.write(f"Approve {len(selected_requests)} requests totaling {total_days} days?")
            
            bulk_comments = st.text_area("Bulk approval comments:", key="bulk_approve_leave_comments")
            
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Confirm Bulk Approve"):
                    approved_count = 0
                    for req_id in st.session_state.selected_leave_requests:
                        result = approve_leave_request(req_id, employee_id, bulk_comments or "Bulk approved")
                        if result["success"]:
                            approved_count += 1
                    
                    st.success(f"✅ Bulk approved {approved_count} requests")
                    st.session_state.bulk_approve_selected = False
                    st.session_state.selected_leave_requests.clear()
                    st.rerun()
            
            with col_no:
                if st.button("❌ Cancel"):
                    st.session_state.bulk_approve_selected = False
                    st.rerun()
        
        # Handle bulk reject selected
        if st.session_state.get("bulk_reject_selected"):
            st.warning("⚠️ **CONFIRM BULK REJECTION**")
            selected_requests = [req for req in pending_approvals if req["id"] in st.session_state.selected_leave_requests]
            
            st.write(f"Reject {len(selected_requests)} selected requests?")
            
            bulk_comments = st.text_area("Bulk rejection reason:", key="bulk_reject_leave_comments", help="Required for rejection")
            
            if bulk_comments.strip():
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("❌ Confirm Bulk Reject"):
                        rejected_count = 0
                        for req_id in st.session_state.selected_leave_requests:
                            result = reject_leave_request(req_id, employee_id, bulk_comments)
                            if result["success"]:
                                rejected_count += 1
                        
                        st.success(f"✅ Bulk rejected {rejected_count} requests")
                        st.session_state.bulk_reject_selected = False
                        st.session_state.selected_leave_requests.clear()
                        st.rerun()
                
                with col_no:
                    if st.button("❌ Cancel"):
                        st.session_state.bulk_reject_selected = False
                        st.rerun()
            else:
                st.error("Please provide a reason for bulk rejection")
        
        st.markdown("---")

    # Individual requests with checkboxes
    for i, request in enumerate(pending_approvals):
        with st.container():
            # Checkbox and header
            col_check, col_header1, col_header2 = st.columns([0.5, 2.5, 1])
            
            with col_check:
                is_selected = st.checkbox(
                    "",
                    value=request["id"] in st.session_state.selected_leave_requests,
                    key=f"select_leave_{request['id']}",
                    label_visibility="collapsed"
                )
                
                if is_selected and request["id"] not in st.session_state.selected_leave_requests:
                    st.session_state.selected_leave_requests.add(request["id"])
                    st.rerun()
                elif not is_selected and request["id"] in st.session_state.selected_leave_requests:
                    st.session_state.selected_leave_requests.discard(request["id"])
                    st.rerun()
            
            with col_header1:
                leave_type_name = LEAVE_TYPES.get(request['leave_type'], {}).get('name', 'Unknown')
                st.markdown(f"#### 📝 {request.get('employee_name', 'Unknown')}")
                st.markdown(f"**{leave_type_name}** - {request['start_date']} to {request['end_date']}")
            
            with col_header2:
                working_days = request.get('working_days', 0)
                st.metric("Days", f"{working_days}")

            # Basic info and actions
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**👤 Employee:** {request.get('employee_name', 'Unknown')}")
                st.markdown(f"**📅 Period:** {request['start_date']} to {request['end_date']}")
                
                # Show employee details button
                if st.button(f"🔍 View Details", key=f"details_leave_{request['id']}"):
                    st.session_state.dialog_employee_id = request.get('employee_id')
                    st.session_state.show_employee_dialog = True
                    st.rerun()
            
            with col2:
                submitted_date = request.get('submitted_at')
                if hasattr(submitted_date, 'timestamp'):
                    submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                else:
                    submitted_str = 'Unknown'
                st.markdown(f"**📤 Submitted:** {submitted_str}")
                st.markdown(f"**⏰ Status:** 🕐 Pending")
            
            with col3:
                st.markdown("**🎯 Quick Actions:**")
                
                col_quick1, col_quick2 = st.columns(2)
                
                with col_quick1:
                    if st.button("✅", key=f"quick_approve_leave_{request['id']}", help="Quick Approve"):
                        result = approve_leave_request(request['id'], employee_id, "Quick approved")
                        if result['success']:
                            st.success("✅ Approved!")
                            st.rerun()
                        else:
                            st.error(result['message'])
                
                with col_quick2:
                    if st.button("❌", key=f"quick_reject_leave_{request['id']}", help="Quick Reject"):
                        if f"quick_reject_reason_leave_{request['id']}" not in st.session_state:
                            st.session_state[f"quick_reject_reason_leave_{request['id']}"] = True
                            st.rerun()

            # Quick reject reason
            if st.session_state.get(f"quick_reject_reason_leave_{request['id']}"):
                quick_reason = st.text_input(
                    "Rejection reason:",
                    key=f"reason_leave_{request['id']}",
                    placeholder="Provide reason for rejection"
                )
                
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("Confirm Reject", key=f"confirm_reject_leave_{request['id']}"):
                        if quick_reason.strip():
                            result = reject_leave_request(request['id'], employee_id, quick_reason)
                            if result['success']:
                                st.success("❌ Rejected!")
                                del st.session_state[f"quick_reject_reason_leave_{request['id']}"]
                                st.rerun()
                            else:
                                st.error(result['message'])
                        else:
                            st.error("Please provide a reason")
                
                with col_cancel:
                    if st.button("Cancel", key=f"cancel_reject_leave_{request['id']}"):
                        del st.session_state[f"quick_reject_reason_leave_{request['id']}"]
                        st.rerun()

            # Leave request details in clean format
            st.markdown("**📋 Leave Request Details:**")
            
            with st.container():
                col_type, col_reason = st.columns([1, 2])
                
                with col_type:
                    st.write(f"**Type:** {leave_type_name}")
                    st.write(f"**Duration:** {working_days} working days")
                
                with col_reason:
                    if request.get('reason'):
                        st.write(f"**Reason:** {request['reason']}")
                    
                    if request.get('emergency_contact'):
                        st.write(f"**Emergency Contact:** {request['emergency_contact']}")
                    
                    if request.get("attachment"):
                        st.markdown("**📎 Attachments:**")
                        attachment_data = request["attachment"]
                        
                        if isinstance(attachment_data, dict) and attachment_data.get("file_path"):
                            display_file_attachment(
                                attachment_data.get("file_path"), 
                                attachment_data
                            )
                        else:
                            st.caption(f"📎 {attachment_data}")

            st.markdown("---")
            
            # Detailed approval actions
            with st.expander(f"⚙️ Detailed Actions - {request.get('employee_name')}"):
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
                        
                        st.markdown("---")
                
                # Create unique keys for each request
                approve_key = f"approve_leave_{request['id']}"
                reject_key = f"reject_leave_{request['id']}"
                comments_key = f"comments_leave_{request['id']}"
                
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
                        if f"confirm_approve_leave_{request['id']}" not in st.session_state:
                            st.session_state[f"confirm_approve_leave_{request['id']}"] = True
                            st.rerun()
                
                with col_reject:
                    if st.button(f"❌ Reject", key=reject_key, type="secondary", use_container_width=True):
                        if f"confirm_reject_leave_{request['id']}" not in st.session_state:
                            st.session_state[f"confirm_reject_leave_{request['id']}"] = True
                            st.rerun()
                
                with col_info:
                    st.info("💡 Review carefully before deciding")

                # Handle approval confirmation
                if st.session_state.get(f"confirm_approve_leave_{request['id']}"):
                    st.warning("⚠️ **CONFIRM APPROVAL**")
                    st.write(f"Approve {request.get('working_days', 0)} days of {leave_type_name} for {request.get('employee_name')}?")
                    
                    col_yes, col_no = st.columns(2)
                    
                    with col_yes:
                        if st.button(f"🟢 Yes, Approve", key=f"yes_approve_leave_{request['id']}", type="primary"):
                            result = approve_leave_request(request['id'], employee_id, approval_comments)
                            
                            if result['success']:
                                st.success(f"✅ {result['message']}")
                                st.balloons()
                                
                                # Clear confirmation state
                                if f"confirm_approve_leave_{request['id']}" in st.session_state:
                                    del st.session_state[f"confirm_approve_leave_{request['id']}"]
                                
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {result['message']}")
                    
                    with col_no:
                        if st.button(f"🔴 Cancel", key=f"cancel_approve_leave_{request['id']}"):
                            if f"confirm_approve_leave_{request['id']}" in st.session_state:
                                del st.session_state[f"confirm_approve_leave_{request['id']}"]
                            st.rerun()

                # Handle rejection confirmation
                if st.session_state.get(f"confirm_reject_leave_{request['id']}"):
                    st.warning("⚠️ **CONFIRM REJECTION**")
                    st.write(f"Reject {leave_type_name} request from {request.get('employee_name')}?")
                    
                    # Require comments for rejection
                    if not approval_comments.strip():
                        st.error("📝 Please provide a reason for rejection in the comments field above.")
                    else:
                        col_yes, col_no = st.columns(2)
                        
                        with col_yes:
                            if st.button(f"🔴 Yes, Reject", key=f"yes_reject_leave_{request['id']}", type="secondary"):
                                result = reject_leave_request(request['id'], employee_id, approval_comments)
                                
                                if result['success']:
                                    st.success(f"✅ {result['message']}")
                                    
                                    if f"confirm_reject_leave_{request['id']}" in st.session_state:
                                        del st.session_state[f"confirm_reject_leave_{request['id']}"]
                                    
                                    import time
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                        
                        with col_no:
                            if st.button(f"🟢 Cancel", key=f"cancel_reject_leave_{request['id']}"):
                                if f"confirm_reject_leave_{request['id']}" in st.session_state:
                                    del st.session_state[f"confirm_reject_leave_{request['id']}"]
                                st.rerun()
            
            st.markdown("---")
            st.markdown("")  # Space between requests

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

**Quick Actions:**
- Use checkboxes for bulk actions
- Click 🔍 View Details for employee info
- Use ✅/❌ for quick approve/reject
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

# Show pending count in sidebar
if pending_approvals:
    st.sidebar.metric("Pending Approvals", len(pending_approvals))
    
    # Show selection count
    if st.session_state.selected_leave_requests:
        st.sidebar.metric("Selected", len(st.session_state.selected_leave_requests))
else:
    st.sidebar.success("All caught up! ✅")

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
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if st.button("📝 My Leave Requests", use_container_width=True):
        st.switch_page("pages/leave_request.py")

with col3:
    if access_level == 1:
        if st.button("⚙️ Admin Panel", use_container_width=True):
            st.switch_page("pages/admin_control.py")

if access_level == 1:
    st.caption("🔑 Enhanced Admin Approval System | Complete organizational access")
else:
    st.caption("📋 Enhanced Approval System | Team-based access")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("💡 Tip: Refresh to see latest requests | 🔄 System automatically handles approval hierarchy")
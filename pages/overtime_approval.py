# pages/overtime_approval.py - Enhanced with individual selection and dialog details
import streamlit as st
from datetime import datetime, date, timedelta
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    get_pending_overtime_approvals_for_approver, approve_overtime_request, 
    reject_overtime_request, get_all_overtime_requests_admin,
    admin_override_overtime_request, get_employee_overtime_balance,
    get_overtime_report_data, reset_overtime_balances, get_team_members
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

# Check if user has approval permissions
if access_level not in [1, 2, 3]:
    st.error("🚫 Access Denied: You don't have permission to approve overtime requests.")
    st.info("Only Admin, HR Staff, and Division Heads can approve overtime requests.")
    if st.button("🏠 Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

# Initialize session state for selections and dialogs
if "selected_requests" not in st.session_state:
    st.session_state.selected_requests = set()

if "show_employee_dialog" not in st.session_state:
    st.session_state.show_employee_dialog = False

if "dialog_employee_id" not in st.session_state:
    st.session_state.dialog_employee_id = None

if "show_request_dialog" not in st.session_state:
    st.session_state.show_request_dialog = False

if "dialog_request" not in st.session_state:
    st.session_state.dialog_request = None

@st.dialog("Request Details")
def show_request_details():
    if st.session_state.dialog_request:
        request = st.session_state.dialog_request
        
        st.markdown(f"### ⏰ {request.get('employee_name', 'Unknown')}")
        
        # Basic info
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**📧 Email:** {request.get('employee_email', 'N/A')}")
            st.write(f"**🏢 Division:** {request.get('employee_division', 'Unknown')}")
            st.write(f"**💼 Role:** {request.get('employee_role', 'Unknown')}")
        
        with col2:
            week_start = request.get('week_start', '')
            week_end = request.get('week_end', '')
            st.write(f"**📅 Period:** {week_start} to {week_end}")
            st.write(f"**⏰ Total Hours:** {request.get('total_hours', 0):.1f}h")
            
            submitted_date = request.get('submitted_at')
            if hasattr(submitted_date, 'timestamp'):
                submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %B %Y, %H:%M')
                st.write(f"**📤 Submitted:** {submitted_str}")
        
        st.markdown("---")
        
        # Overtime entries
        st.markdown("**📋 Overtime Details:**")
        
        for entry in request.get('overtime_entries', []):
            entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
            day_name = entry_date.strftime('%A')
            date_str = entry_date.strftime('%d %B')
            
            with st.container():
                col_date, col_hours, col_desc = st.columns([1, 1, 3])
                
                with col_date:
                    st.write(f"**{day_name}**")
                    st.caption(date_str)
                
                with col_hours:
                    st.write(f"**{entry['hours']}h**")
                
                with col_desc:
                    st.write(entry['description'])
        
        # Overall reason
        if request.get('reason'):
            st.markdown("**💭 Overall Reason:**")
            st.write(request['reason'])
        
        st.markdown("---")
        
        # Quick actions in dialog
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ Quick Approve", type="primary"):
                result = approve_overtime_request(request['id'], employee_id, "Approved from dialog")
                if result['success']:
                    st.success("✅ Approved!")
                    st.session_state.show_request_dialog = False
                    st.session_state.dialog_request = None
                    st.rerun()
                else:
                    st.error(result['message'])
        
        with col2:
            if st.button("❌ Quick Reject"):
                st.session_state.show_reject_reason = True
        
        with col3:
            if st.button("🔍 Employee Details"):
                st.session_state.dialog_employee_id = request.get('employee_id')
                st.session_state.show_employee_dialog = True
                st.session_state.show_request_dialog = False
                st.rerun()
        
        # Handle reject reason
        if st.session_state.get("show_reject_reason"):
            reject_reason = st.text_area("Rejection reason:", placeholder="Provide reason for rejection")
            
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("Confirm Reject"):
                    if reject_reason.strip():
                        result = reject_overtime_request(request['id'], employee_id, reject_reason)
                        if result['success']:
                            st.success("❌ Rejected!")
                            st.session_state.show_request_dialog = False
                            st.session_state.dialog_request = None
                            st.session_state.show_reject_reason = False
                            st.rerun()
                        else:
                            st.error(result['message'])
                    else:
                        st.error("Please provide a reason")
            
            with col_cancel:
                if st.button("Cancel"):
                    st.session_state.show_reject_reason = False
                    st.rerun()
    
    if st.button("Close", type="secondary"):
        st.session_state.show_request_dialog = False
        st.session_state.dialog_request = None
        if "show_reject_reason" in st.session_state:
            del st.session_state.show_reject_reason
        st.rerun()

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
                    # Get overtime balance
                    current_month = datetime.now().strftime("%Y-%m")
                    balance = get_employee_overtime_balance(st.session_state.dialog_employee_id, current_month)
                    
                    if balance:
                        st.write(f"**⏰ Approved Hours:** {balance.get('approved_hours', 0):.1f}h")
                        st.write(f"**💰 Balance Hours:** {balance.get('balance_hours', 0):.1f}h")
                        st.write(f"**💵 Paid Hours:** {balance.get('paid_hours', 0):.1f}h")
                        
                        # Estimated pay
                        overtime_rate = employee_data.get('overtime_rate', 0)
                        if overtime_rate > 0:
                            estimated_pay = balance.get('balance_hours', 0) * overtime_rate
                            st.write(f"**💲 Est. Pay:** ${estimated_pay:.2f}")
                    else:
                        st.write("**⏰ Balance:** No data this month")
                
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
            else:
                st.error("Employee data not found")
        
        except Exception as e:
            st.error(f"Error loading employee details: {e}")
    
    if st.button("Close", type="primary"):
        st.session_state.show_employee_dialog = False
        st.session_state.dialog_employee_id = None
        st.rerun()

# Page header
st.title("⏰ Overtime Request Approval")
st.markdown(f"**Approver:** {user_data.get('name')} | **Role:** {user_data.get('role_name')}")

# Show different interface for admin (level 1)
if access_level == 1:
    st.success("🔑 **Admin Access:** You can view and manage all overtime requests in the system")
else:
    # Show approval scope for non-admin users
    team_info = get_team_members(employee_id) if employee_id else {"direct_reports": [], "division_reports": [], "total_count": 0}
    if team_info["total_count"] > 0:
        st.info(f"👥 **Your Approval Scope:** {team_info['total_count']} team members")

# Logout button
if st.button("🚪 Logout", key="logout_overtime_approval"):
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
    if st.button("⏰ My Overtime"):
        st.switch_page("pages/overtime_management.py")

st.divider()

# Show dialogs
if st.session_state.show_request_dialog:
    show_request_details()

if st.session_state.show_employee_dialog:
    show_employee_details()

# Create different tabs based on access level
if access_level == 1:  # Admin gets additional tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 My Pending Approvals", 
        "🌐 All Overtime Requests",
        "📊 Payroll Reports",
        "⚙️ Admin Controls"
    ])
else:
    tab1, tab2 = st.tabs(["📋 Pending Approvals", "📊 Approval History"])

with tab1:
    st.subheader("📋 My Pending Overtime Approvals")
    
    # Get pending approvals for this user
    pending_approvals = get_pending_overtime_approvals_for_approver(employee_id) if employee_id else []

    if not pending_approvals:
        st.success("🎉 No pending overtime requests for your approval!")
        st.info("All caught up! Check back later for new requests.")
    else:
        st.markdown(f"### 📋 Pending Approvals ({len(pending_approvals)})")
        st.warning(f"⚠️ You have **{len(pending_approvals)}** overtime request(s) awaiting your approval.")

        # Bulk actions section - Available for both supervisors and admin
        if len(pending_approvals) > 1 and access_level in [1, 2, 3]:
            st.markdown("### ⚡ Bulk Actions")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("☑️ Select All"):
                    st.session_state.selected_requests = {req["id"] for req in pending_approvals}
                    st.rerun()
            
            with col2:
                if st.button("☐ Clear Selection"):
                    st.session_state.selected_requests.clear()
                    st.rerun()
            
            with col3:
                selected_count = len(st.session_state.selected_requests)
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
                selected_requests = [req for req in pending_approvals if req["id"] in st.session_state.selected_requests]
                total_hours = sum(req.get("total_hours", 0) for req in selected_requests)
                
                st.write(f"Approve {len(selected_requests)} requests totaling {total_hours:.1f} hours?")
                
                bulk_comments = st.text_area("Bulk approval comments:", key="bulk_approve_comments")
                
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Confirm Bulk Approve"):
                        approved_count = 0
                        for req_id in st.session_state.selected_requests:
                            result = approve_overtime_request(req_id, employee_id, bulk_comments or "Bulk approved")
                            if result["success"]:
                                approved_count += 1
                        
                        st.success(f"✅ Bulk approved {approved_count} requests")
                        st.session_state.bulk_approve_selected = False
                        st.session_state.selected_requests.clear()
                        st.rerun()
                
                with col_no:
                    if st.button("❌ Cancel"):
                        st.session_state.bulk_approve_selected = False
                        st.rerun()
            
            # Handle bulk reject selected
            if st.session_state.get("bulk_reject_selected"):
                st.warning("⚠️ **CONFIRM BULK REJECTION**")
                selected_requests = [req for req in pending_approvals if req["id"] in st.session_state.selected_requests]
                
                st.write(f"Reject {len(selected_requests)} selected requests?")
                
                bulk_comments = st.text_area("Bulk rejection reason:", key="bulk_reject_comments", help="Required for rejection")
                
                if bulk_comments.strip():
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("❌ Confirm Bulk Reject"):
                            rejected_count = 0
                            for req_id in st.session_state.selected_requests:
                                result = reject_overtime_request(req_id, employee_id, bulk_comments)
                                if result["success"]:
                                    rejected_count += 1
                            
                            st.success(f"✅ Bulk rejected {rejected_count} requests")
                            st.session_state.bulk_reject_selected = False
                            st.session_state.selected_requests.clear()
                            st.rerun()
                    
                    with col_no:
                        if st.button("❌ Cancel"):
                            st.session_state.bulk_reject_selected = False
                            st.rerun()
                else:
                    st.error("Please provide a reason for bulk rejection")
            
            st.markdown("---")

        # Individual requests - Simplified table format for supervisors
        if access_level in [2, 3]:  # Supervisor view - simplified table
            st.markdown("### 📋 Requests Overview")
            
            # Create table data
            table_data = []
            for request in pending_approvals:
                # Format overtime dates
                entries = request.get('overtime_entries', [])
                if entries:
                    dates = []
                    for entry in entries:
                        entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                        dates.append(entry_date.strftime('%d %b'))
                    date_range = f"{min(dates)} - {max(dates)}" if len(dates) > 1 else dates[0] if dates else "N/A"
                else:
                    date_range = "N/A"
                
                # Format submitted date
                submitted_date = request.get('submitted_at')
                if hasattr(submitted_date, 'timestamp'):
                    submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                else:
                    submitted_str = 'Unknown'
                
                table_data.append({
                    "employee_name": request.get('employee_name', 'Unknown'),
                    "overtime_dates": date_range,
                    "total_hours": request.get('total_hours', 0),
                    "submitted_on": submitted_str,
                    "status": "🕐 Pending",
                    "request_id": request["id"],
                    "employee_id": request.get('employee_id')
                })
            
            # Display as interactive table
            for i, row in enumerate(table_data):
                with st.container():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([0.3, 2, 1.5, 1, 1, 1, 1])
                    
                    with col1:
                        is_selected = st.checkbox(
                            "",
                            value=row["request_id"] in st.session_state.selected_requests,
                            key=f"select_table_{row['request_id']}",
                            label_visibility="collapsed"
                        )
                        
                        if is_selected and row["request_id"] not in st.session_state.selected_requests:
                            st.session_state.selected_requests.add(row["request_id"])
                            st.rerun()
                        elif not is_selected and row["request_id"] in st.session_state.selected_requests:
                            st.session_state.selected_requests.discard(row["request_id"])
                            st.rerun()
                    
                    with col2:
                        st.write(f"**{row['employee_name']}**")
                    
                    with col3:
                        st.write(row['overtime_dates'])
                    
                    with col4:
                        st.write(f"**{row['total_hours']:.1f}h**")
                    
                    with col5:
                        st.write(row['submitted_on'])
                    
                    with col6:
                        st.write(row['status'])
                    
                    with col7:
                        if st.button("🔍 Detail", key=f"detail_table_{row['request_id']}"):
                            # Store request details for dialog
                            request_detail = next(req for req in pending_approvals if req["id"] == row["request_id"])
                            st.session_state.dialog_request = request_detail
                            st.session_state.show_request_dialog = True
                            st.rerun()
                    
                    st.divider()
        
        else:  # Admin view - detailed cards
            # Individual requests with checkboxes for admin
            for i, request in enumerate(pending_approvals):
                with st.container():
                    # Checkbox and header
                    col_check, col_header1, col_header2 = st.columns([0.5, 2.5, 1])
                    
                    with col_check:
                        is_selected = st.checkbox(
                            "",
                            value=request["id"] in st.session_state.selected_requests,
                            key=f"select_{request['id']}",
                            label_visibility="collapsed"
                        )
                        
                        if is_selected and request["id"] not in st.session_state.selected_requests:
                            st.session_state.selected_requests.add(request["id"])
                            st.rerun()
                        elif not is_selected and request["id"] in st.session_state.selected_requests:
                            st.session_state.selected_requests.discard(request["id"])
                            st.rerun()
                
                with col_header1:
                    week_start = request.get('week_start', '')
                    week_end = request.get('week_end', '')
                    st.markdown(f"#### ⏰ {request.get('employee_name', 'Unknown')}")
                    st.markdown(f"**Week:** {week_start} to {week_end}")
                
                with col_header2:
                    total_hours = request.get('total_hours', 0)
                    st.metric("Total Hours", f"{total_hours:.1f}h")

                # Basic info and detail button
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**👤 Employee:** {request.get('employee_name', 'Unknown')}")
                    st.markdown(f"**📅 Days:** {len(request.get('overtime_entries', []))}")
                    
                    # Show employee details button
                    if st.button(f"🔍 View Details", key=f"details_{request['id']}"):
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
                        if st.button("✅", key=f"quick_approve_{request['id']}", help="Quick Approve"):
                            result = approve_overtime_request(request['id'], employee_id, "Quick approved")
                            if result['success']:
                                st.success("✅ Approved!")
                                st.rerun()
                            else:
                                st.error(result['message'])
                    
                    with col_quick2:
                        if st.button("❌", key=f"quick_reject_{request['id']}", help="Quick Reject"):
                            if f"quick_reject_reason_{request['id']}" not in st.session_state:
                                st.session_state[f"quick_reject_reason_{request['id']}"] = True
                                st.rerun()

                # Quick reject reason
                if st.session_state.get(f"quick_reject_reason_{request['id']}"):
                    quick_reason = st.text_input(
                        "Rejection reason:",
                        key=f"reason_{request['id']}",
                        placeholder="Provide reason for rejection"
                    )
                    
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("Confirm Reject", key=f"confirm_reject_{request['id']}"):
                            if quick_reason.strip():
                                result = reject_overtime_request(request['id'], employee_id, quick_reason)
                                if result['success']:
                                    st.success("❌ Rejected!")
                                    del st.session_state[f"quick_reject_reason_{request['id']}"]
                                    st.rerun()
                                else:
                                    st.error(result['message'])
                            else:
                                st.error("Please provide a reason")
                    
                    with col_cancel:
                        if st.button("Cancel", key=f"cancel_reject_{request['id']}"):
                            del st.session_state[f"quick_reject_reason_{request['id']}"]
                            st.rerun()

                # Overtime entries in clean format
                st.markdown("**📋 Overtime Entries:**")
                
                for entry in request.get('overtime_entries', []):
                    entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                    day_name = entry_date.strftime('%A')
                    date_str = entry_date.strftime('%d %b')
                    
                    with st.container():
                        col_date, col_hours, col_desc = st.columns([1, 1, 3])
                        
                        with col_date:
                            st.write(f"**{day_name}**")
                            st.caption(date_str)
                        
                        with col_hours:
                            st.write(f"**{entry['hours']}h**")
                        
                        with col_desc:
                            st.write(entry['description'])

                # Overall reason
                if request.get('reason'):
                    st.markdown("**💭 Overall Reason:**")
                    st.write(request['reason'])

                st.markdown("---")
                
                # Detailed approval actions
                with st.expander(f"⚙️ Detailed Actions - {request.get('employee_name')}"):
                    # Create unique keys for each request
                    approve_key = f"approve_ot_{request['id']}"
                    reject_key = f"reject_ot_{request['id']}"
                    comments_key = f"comments_ot_{request['id']}"
                    
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
                            if f"confirm_approve_ot_{request['id']}" not in st.session_state:
                                st.session_state[f"confirm_approve_ot_{request['id']}"] = True
                                st.rerun()
                    
                    with col_reject:
                        if st.button(f"❌ Reject", key=reject_key, type="secondary", use_container_width=True):
                            if f"confirm_reject_ot_{request['id']}" not in st.session_state:
                                st.session_state[f"confirm_reject_ot_{request['id']}"] = True
                                st.rerun()
                    
                    with col_info:
                        st.info(f"💡 {total_hours:.1f}h @ overtime rate")

                    # Handle approval confirmation
                    if st.session_state.get(f"confirm_approve_ot_{request['id']}"):
                        st.warning("⚠️ **CONFIRM APPROVAL**")
                        st.write(f"Approve {total_hours:.1f} hours of overtime for {request.get('employee_name')}?")
                        
                        col_yes, col_no = st.columns(2)
                        
                        with col_yes:
                            if st.button(f"🟢 Yes, Approve", key=f"yes_approve_ot_{request['id']}", type="primary"):
                                result = approve_overtime_request(request['id'], employee_id, approval_comments)
                                
                                if result['success']:
                                    st.success(f"✅ {result['message']}")
                                    st.balloons()
                                    
                                    # Clear confirmation state
                                    if f"confirm_approve_ot_{request['id']}" in st.session_state:
                                        del st.session_state[f"confirm_approve_ot_{request['id']}"]
                                    
                                    import time
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                        
                        with col_no:
                            if st.button(f"🔴 Cancel", key=f"cancel_approve_ot_{request['id']}"):
                                if f"confirm_approve_ot_{request['id']}" in st.session_state:
                                    del st.session_state[f"confirm_approve_ot_{request['id']}"]
                                st.rerun()

                    # Handle rejection confirmation
                    if st.session_state.get(f"confirm_reject_ot_{request['id']}"):
                        st.warning("⚠️ **CONFIRM REJECTION**")
                        st.write(f"Reject overtime request from {request.get('employee_name')}?")
                        
                        # Require comments for rejection
                        if not approval_comments.strip():
                            st.error("📝 Please provide a reason for rejection in the comments field above.")
                        else:
                            col_yes, col_no = st.columns(2)
                            
                            with col_yes:
                                if st.button(f"🔴 Yes, Reject", key=f"yes_reject_ot_{request['id']}", type="secondary"):
                                    result = reject_overtime_request(request['id'], employee_id, approval_comments)
                                    
                                    if result['success']:
                                        st.success(f"✅ {result['message']}")
                                        
                                        if f"confirm_reject_ot_{request['id']}" in st.session_state:
                                            del st.session_state[f"confirm_reject_ot_{request['id']}"]
                                        
                                        import time
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {result['message']}")
                            
                            with col_no:
                                if st.button(f"🟢 Cancel", key=f"cancel_reject_ot_{request['id']}"):
                                    if f"confirm_reject_ot_{request['id']}" in st.session_state:
                                        del st.session_state[f"confirm_reject_ot_{request['id']}"]
                                    st.rerun()
                
                st.markdown("---")
                st.markdown("")  # Space between requests

# Admin-only tabs
if access_level == 1:
    with tab2:
        st.subheader("🌐 All Overtime Requests (Admin View)")
        st.info("👑 **Admin Privilege:** View and manage all overtime requests across the organization")
        
        # Get all overtime requests
        all_overtime_requests = get_all_overtime_requests_admin()
        
        if not all_overtime_requests:
            st.info("📋 No overtime requests found in the system.")
        else:
            st.success(f"📊 **{len(all_overtime_requests)}** total overtime requests found")
            
            # Filter options
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                status_filter = st.selectbox(
                    "Status",
                    options=["All", "Pending", "Approved", "Rejected"],
                    key="admin_ot_status_filter"
                )
            
            with col2:
                division_filter = st.selectbox(
                    "Division",
                    options=["All"] + list(set([r.get("employee_division", "Unknown") for r in all_overtime_requests])),
                    key="admin_ot_division_filter"
                )
            
            with col3:
                month_filter = st.selectbox(
                    "Month",
                    options=["All"] + [f"{datetime.now().year}-{m:02d}" for m in range(1, 13)],
                    key="admin_ot_month_filter"
                )
            
            with col4:
                approver_filter = st.selectbox(
                    "Approver",
                    options=["All"] + list(set([r.get("approver_name", "Unknown") for r in all_overtime_requests if r.get("approver_name")])),
                    key="admin_ot_approver_filter"
                )
            
            # Apply filters
            filtered_requests = all_overtime_requests
            
            if status_filter != "All":
                filtered_requests = [r for r in filtered_requests if r.get("status") == status_filter.lower()]
            
            if division_filter != "All":
                filtered_requests = [r for r in filtered_requests if r.get("employee_division") == division_filter]
            
            if month_filter != "All":
                filtered_requests = [r for r in filtered_requests if r.get("week_start", "").startswith(month_filter)]
            
            if approver_filter != "All":
                filtered_requests = [r for r in filtered_requests if r.get("approver_name") == approver_filter]
            
            # Display filtered results
            if filtered_requests:
                st.info(f"📊 Showing {len(filtered_requests)} of {len(all_overtime_requests)} requests")
                
                # Summary statistics
                total_hours = sum([r.get("total_hours", 0) for r in filtered_requests])
                approved_hours = sum([r.get("total_hours", 0) for r in filtered_requests if r.get("status") == "approved"])
                pending_count = len([r for r in filtered_requests if r.get("status") == "pending"])
                
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                with col_stat1:
                    st.metric("Total Requests", len(filtered_requests))
                with col_stat2:
                    st.metric("Total Hours", f"{total_hours:.1f}h")
                with col_stat3:
                    st.metric("Approved Hours", f"{approved_hours:.1f}h")
                with col_stat4:
                    st.metric("Pending", pending_count)
                
                # Admin actions for pending requests
                if pending_count > 0:
                    st.markdown("### ⚡ Admin Override Actions")
                    st.warning(f"You can override approval/rejection for {pending_count} pending requests")
                    
                    col_bulk1, col_bulk2 = st.columns(2)
                    
                    with col_bulk1:
                        if st.button("🔄 Bulk Approve All Pending", type="primary"):
                            st.session_state.bulk_approve_overtime = True
                    
                    with col_bulk2:
                        if st.button("❌ Bulk Reject All Pending", type="secondary"):
                            st.session_state.bulk_reject_overtime = True
                    
                    # Handle bulk actions (same as before)
                    if st.session_state.get("bulk_approve_overtime"):
                        st.warning("⚠️ **CONFIRM BULK APPROVAL**")
                        bulk_comments = st.text_area("Bulk approval comments:", key="bulk_approve_comments")
                        
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Confirm Bulk Approve"):
                                approved_count = 0
                                for request in filtered_requests:
                                    if request.get("status") == "pending":
                                        result = admin_override_overtime_request(
                                            request["id"], employee_id, "approve", 
                                            bulk_comments or "Bulk approved by admin"
                                        )
                                        if result["success"]:
                                            approved_count += 1
                                
                                st.success(f"✅ Bulk approved {approved_count} requests")
                                st.session_state.bulk_approve_overtime = False
                                st.rerun()
                        
                        with col_no:
                            if st.button("❌ Cancel"):
                                st.session_state.bulk_approve_overtime = False
                                st.rerun()
                    
                    if st.session_state.get("bulk_reject_overtime"):
                        st.warning("⚠️ **CONFIRM BULK REJECTION**")
                        bulk_comments = st.text_area("Bulk rejection reason:", key="bulk_reject_comments", help="Required for rejection")
                        
                        if bulk_comments.strip():
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button("❌ Confirm Bulk Reject"):
                                    rejected_count = 0
                                    for request in filtered_requests:
                                        if request.get("status") == "pending":
                                            result = admin_override_overtime_request(
                                                request["id"], employee_id, "reject", bulk_comments
                                            )
                                            if result["success"]:
                                                rejected_count += 1
                                    
                                    st.success(f"✅ Bulk rejected {rejected_count} requests")
                                    st.session_state.bulk_reject_overtime = False
                                    st.rerun()
                            
                            with col_no:
                                if st.button("❌ Cancel"):
                                    st.session_state.bulk_reject_overtime = False
                                    st.rerun()
                        else:
                            st.error("Please provide a reason for bulk rejection")
                
                # Convert to DataFrame for table display
                table_data = []
                for req in filtered_requests:
                    submitted_date = req.get('submitted_at')
                    if hasattr(submitted_date, 'timestamp'):
                        submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                    else:
                        submitted_str = 'Unknown'
                    
                    # Status with icon
                    status = req.get("status", "unknown")
                    if status == "pending":
                        status_display = "🕐 Pending"
                    elif status == "approved":
                        status_display = "✅ Approved"
                    elif status == "rejected":
                        status_display = "❌ Rejected"
                    else:
                        status_display = "📋 Processing"
                    
                    processor_name = req.get("final_processor_name", "")
                    is_admin_override = req.get("is_admin_override", False)
                    processor_display = f"{processor_name} {'(Admin)' if is_admin_override else ''}" if processor_name else ""
                    
                    table_data.append({
                        "Employee": req.get("employee_name", "Unknown"),
                        "Division": req.get("employee_division", "Unknown"),
                        "Week": f"{req.get('week_start')} to {req.get('week_end')}",
                        "Hours": f"{req.get('total_hours', 0):.1f}h",
                        "Status": status_display,
                        "Approver": req.get("approver_name", "Unknown"),
                        "Processed By": processor_display,
                        "Submitted": submitted_str
                    })
                
                df_overtime = pd.DataFrame(table_data)
                st.dataframe(df_overtime, use_container_width=True, hide_index=True)
                
                # Export option
                if st.button("📊 Export Overtime Data"):
                    csv = df_overtime.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"overtime_requests_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No requests match the selected filters.")

    with tab3:
        st.subheader("📊 Overtime Payroll Reports")
        st.info("👑 **Admin Tool:** Generate reports for payroll processing")
        
        # Month selection for payroll
        current_month = datetime.now().strftime("%Y-%m")
        available_months = []
        
        # Generate last 12 months
        for i in range(12):
            month_date = datetime.now() - timedelta(days=30*i)
            available_months.append(month_date.strftime("%Y-%m"))
        
        selected_month = st.selectbox(
            "Select Month for Payroll Report",
            options=available_months,
            format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%B %Y"),
            index=0
        )
        
        # Division filter for payroll
        division_filter_payroll = st.selectbox(
            "Filter by Division",
            options=["All Divisions"] + list(set([r.get("employee_division", "Unknown") for r in get_all_overtime_requests_admin()])),
            key="payroll_division_filter"
        )
        
        # Generate payroll report
        if st.button("📋 Generate Payroll Report", type="primary"):
            division_id = None if division_filter_payroll == "All Divisions" else division_filter_payroll
            
            report_data = get_overtime_report_data(selected_month, division_id)
            
            if not report_data:
                st.info(f"📊 No overtime data found for {datetime.strptime(selected_month, '%Y-%m').strftime('%B %Y')}")
            else:
                st.success(f"📊 Generated report for {len(report_data)} employees")
                
                # Summary statistics
                total_employees = len(report_data)
                total_approved_hours = sum([emp.get("approved_hours", 0) for emp in report_data])
                total_balance_hours = sum([emp.get("balance_hours", 0) for emp in report_data])
                total_calculated_pay = sum([emp.get("calculated_pay", 0) for emp in report_data])
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Employees", total_employees)
                with col2:
                    st.metric("Approved Hours", f"{total_approved_hours:.1f}h")
                with col3:
                    st.metric("Payable Hours", f"{total_balance_hours:.1f}h")
                with col4:
                    st.metric("Total Pay", f"${total_calculated_pay:,.2f}")
                
                # Detailed payroll table
                st.markdown("### 💰 Detailed Payroll Report")
                
                payroll_df_data = []
                for emp in report_data:
                    payroll_df_data.append({
                        "Employee ID": emp.get("employee_id"),
                        "Employee Name": emp.get("employee_name"),
                        "Division": emp.get("division"),
                        "Role": emp.get("role"),
                        "Approved Hours": f"{emp.get('approved_hours', 0):.1f}h",
                        "Paid Hours": f"{emp.get('paid_hours', 0):.1f}h",
                        "Balance Hours": f"{emp.get('balance_hours', 0):.1f}h",
                        "Overtime Rate": f"${emp.get('overtime_rate', 0):.2f}",
                        "Calculated Pay": f"${emp.get('calculated_pay', 0):.2f}"
                    })
                
                payroll_df = pd.DataFrame(payroll_df_data)
                st.dataframe(payroll_df, use_container_width=True, hide_index=True)
                
                # Export payroll report
                col_export1, col_export2 = st.columns(2)
                
                with col_export1:
                    csv_payroll = payroll_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Payroll CSV",
                        data=csv_payroll,
                        file_name=f"overtime_payroll_{selected_month}.csv",
                        mime="text/csv"
                    )
                
                with col_export2:
                    # Summary for HR
                    summary_text = f"""
Overtime Payroll Summary - {datetime.strptime(selected_month, '%Y-%m').strftime('%B %Y')}

Total Employees with Overtime: {total_employees}
Total Approved Hours: {total_approved_hours:.1f}h
Total Payable Hours: {total_balance_hours:.1f}h
Total Calculated Pay: ${total_calculated_pay:,.2f}

Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Generated by: {user_data.get('name')} (Admin)
                    """
                    
                    st.download_button(
                        label="📋 Download Summary",
                        data=summary_text,
                        file_name=f"overtime_summary_{selected_month}.txt",
                        mime="text/plain"
                    )

    with tab4:
        st.subheader("⚙️ Admin Overtime Controls")
        st.info("👑 **Admin Tools:** System management and maintenance")
        
        # Reset overtime balances after payroll
        st.markdown("### 🔄 Payroll Processing")
        
        st.warning("""
        **⚠️ Important:** Only reset overtime balances AFTER payroll has been processed!
        
        This action will:
        - Mark all balance hours as "paid"
        - Reset balance hours to 0 for all employees
        - Keep approved hours for historical records
        """)
        
        reset_month = st.selectbox(
            "Select Month to Reset",
            options=available_months,
            format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%B %Y"),
            key="reset_month_selector"
        )
        
        if st.button("🔄 Reset Overtime Balances", type="primary"):
            if "confirm_reset_overtime" not in st.session_state:
                st.session_state.confirm_reset_overtime = True
                st.rerun()
        
        if st.session_state.get("confirm_reset_overtime"):
            st.error("⚠️ **DANGER ZONE - CONFIRM RESET**")
            st.write(f"This will reset overtime balances for ALL employees in {datetime.strptime(reset_month, '%Y-%m').strftime('%B %Y')}")
            st.write("**This action cannot be undone!**")
            
            reset_confirmation = st.text_input(
                "Type 'RESET OVERTIME' to confirm:",
                key="reset_confirmation_text"
            )
            
            col_confirm, col_cancel = st.columns(2)
            
            with col_confirm:
                if st.button("🔴 CONFIRM RESET", type="primary"):
                    if reset_confirmation == "RESET OVERTIME":
                        result = reset_overtime_balances(reset_month)
                        
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.balloons()
                            
                            # Log the reset action
                            st.info(f"Reset performed by: {user_data.get('name')} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        else:
                            st.error(f"❌ {result['message']}")
                        
                        st.session_state.confirm_reset_overtime = False
                        st.rerun()
                    else:
                        st.error("Please type 'RESET OVERTIME' exactly to confirm")
            
            with col_cancel:
                if st.button("❌ Cancel Reset"):
                    st.session_state.confirm_reset_overtime = False
                    st.rerun()
        
        st.markdown("---")
        
        # System statistics
        st.markdown("### 📊 System Statistics")
        
        all_requests = get_all_overtime_requests_admin()
        current_year = datetime.now().year
        
        if all_requests:
            year_requests = [r for r in all_requests if r.get("week_start", "").startswith(str(current_year))]
            
            total_requests = len(year_requests)
            total_hours = sum([r.get("total_hours", 0) for r in year_requests])
            approved_requests = len([r for r in year_requests if r.get("status") == "approved"])
            pending_requests = len([r for r in year_requests if r.get("status") == "pending"])
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(f"{current_year} Requests", total_requests)
            with col2:
                st.metric("Total Hours", f"{total_hours:.1f}h")
            with col3:
                st.metric("Approved", approved_requests)
            with col4:
                st.metric("Pending", pending_requests)
            
            # Division breakdown
            division_stats = {}
            for req in year_requests:
                division = req.get("employee_division", "Unknown")
                if division not in division_stats:
                    division_stats[division] = {"requests": 0, "hours": 0}
                division_stats[division]["requests"] += 1
                division_stats[division]["hours"] += req.get("total_hours", 0)
            
            if division_stats:
                st.markdown("### 🏢 Division Breakdown")
                
                division_chart_data = []
                for division, stats in division_stats.items():
                    division_chart_data.append({
                        "Division": division,
                        "Requests": stats["requests"],
                        "Hours": stats["hours"]
                    })
                
                df_divisions = pd.DataFrame(division_chart_data)
                st.dataframe(df_divisions, use_container_width=True, hide_index=True)

# Non-admin tab
if access_level != 1:
    with tab2:
        st.subheader("📊 My Approval History")
        
        # Get processed requests where this user was the approver
        try:
            all_processed = []
            query = db.db.collection("overtime_requests").where("approver_id", "==", employee_id).where("status", "in", ["approved", "rejected"])
            
            for doc in query.stream():
                request_data = doc.to_dict()
                request_data["id"] = doc.id
                
                # Enrich with employee data
                employee_data = db.db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
                if employee_data:
                    # Get division and role names
                    division_data = db.db.collection("divisions").document(employee_data.get("division_id", "")).get().to_dict()
                    role_data = db.db.collection("roles").document(employee_data.get("role_id", "")).get().to_dict()
                    
                    request_data["employee_name"] = employee_data.get("name")
                    request_data["employee_division"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                    request_data["employee_role"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
                
                all_processed.append(request_data)
            
            if not all_processed:
                st.info("📊 No approval history found.")
            else:
                # Summary statistics
                total_processed = len(all_processed)
                total_approved = len([r for r in all_processed if r.get("status") == "approved"])
                total_rejected = len([r for r in all_processed if r.get("status") == "rejected"])
                total_hours_approved = sum([r.get("total_hours", 0) for r in all_processed if r.get("status") == "approved"])
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Processed", total_processed)
                with col2:
                    st.metric("Approved", total_approved)
                with col3:
                    st.metric("Rejected", total_rejected)
                with col4:
                    st.metric("Hours Approved", f"{total_hours_approved:.1f}h")
                
                # Display history
                st.markdown("### 📋 Recent Approvals")
                
                # Sort by processing date
                all_processed.sort(key=lambda x: x.get("approved_at") or x.get("rejected_at") or 0, reverse=True)
                
                for request in all_processed[:10]:  # Show last 10
                    with st.container():
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**{request.get('employee_name', 'Unknown')}**")
                            st.caption(f"Week: {request.get('week_start')} to {request.get('week_end')}")
                        
                        with col2:
                            st.write(f"**{request.get('total_hours', 0):.1f}h**")
                        
                        with col3:
                            status = request.get("status")
                            if status == "approved":
                                st.success("✅ Approved")
                            else:
                                st.error("❌ Rejected")
                        
                        # Processing date
                        process_date = request.get("approved_at") or request.get("rejected_at")
                        if hasattr(process_date, "timestamp"):
                            process_str = datetime.fromtimestamp(process_date.timestamp()).strftime("%d %b %Y")
                            st.caption(f"Processed: {process_str}")
                        
                        if request.get("approver_comments"):
                            st.caption(f"Comment: {request['approver_comments']}")
                        
                        st.divider()
        
        except Exception as e:
            st.error(f"Error loading approval history: {e}")

# Sidebar with information
st.sidebar.markdown("### ⏰ Overtime Guidelines")

st.sidebar.markdown("""
**Approval Criteria:**
- ✅ Valid business justification
- ✅ Reasonable hours (max 12h/day)
- ✅ Detailed work descriptions
- ✅ Budget considerations

**Before Approving:**
- Check employee's current balance
- Review work descriptions
- Consider team workload
- Confirm budget availability

**Quick Actions:**
- Use checkboxes for bulk actions
- Click 🔍 View Details for employee info
- Use ✅/❌ for quick approve/reject
""")

if access_level == 1:
    st.sidebar.markdown("### 👑 Admin Privileges")
    st.sidebar.success("✅ Override any request")
    st.sidebar.success("✅ Bulk approve/reject")
    st.sidebar.success("✅ Generate payroll reports")
    st.sidebar.success("✅ Reset balances")
    st.sidebar.success("✅ System statistics")

st.sidebar.markdown("### 📊 Quick Stats")

# Show pending count in sidebar
pending_approvals = get_pending_overtime_approvals_for_approver(employee_id) if employee_id else []
if pending_approvals:
    st.sidebar.metric("Pending Approvals", len(pending_approvals))
    
    # Show selection count
    if st.session_state.selected_requests:
        st.sidebar.metric("Selected", len(st.session_state.selected_requests))
else:
    st.sidebar.success("All caught up! ✅")

# Show system stats for admin
if access_level == 1:
    try:
        all_pending = [r for r in get_all_overtime_requests_admin() if r.get("status") == "pending"]
        st.sidebar.metric("System Pending", len(all_pending))
    except:
        pass

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if st.button("⏰ My Overtime", use_container_width=True):
        st.switch_page("pages/overtime_management.py")

with col3:
    if st.button("📝 Leave Requests", use_container_width=True):
        st.switch_page("pages/leave_request.py")

if access_level == 1:
    st.caption("🔑 Enhanced Admin Overtime System | Complete organizational access")
else:
    st.caption("⏰ Enhanced Overtime Approval System | Team-based access")

st.caption(f"Session: {user_data.get('name')} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
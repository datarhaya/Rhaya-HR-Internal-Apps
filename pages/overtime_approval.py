# pages/overtime_approval.py - Complete version
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

        # Process each pending request
        for i, request in enumerate(pending_approvals):
            with st.container():
                # Request header
                col_header1, col_header2 = st.columns([3, 1])
                
                with col_header1:
                    week_start = request.get('week_start', '')
                    week_end = request.get('week_end', '')
                    st.markdown(f"#### ⏰ Request #{i+1} - {request.get('employee_name', 'Unknown')}")
                    st.markdown(f"**Week:** {week_start} to {week_end}")
                
                with col_header2:
                    # Show total hours prominently
                    total_hours = request.get('total_hours', 0)
                    st.metric("Total Hours", f"{total_hours:.1f}h")

                # Employee and request info
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**👤 Employee:** {request.get('employee_name', 'Unknown')}")
                    st.markdown(f"**📧 Email:** {request.get('employee_email', 'N/A')}")
                    st.markdown(f"**🏢 Division:** {request.get('employee_division', 'Unknown')}")
                    st.markdown(f"**💼 Role:** {request.get('employee_role', 'Unknown')}")
                
                with col2:
                    st.markdown(f"**📅 Days:** {len(request.get('overtime_entries', []))}")
                    st.markdown(f"**⏰ Hours:** {total_hours:.1f}")
                    
                    # Show employee's current balance
                    current_month = datetime.now().strftime("%Y-%m")
                    employee_balance = get_employee_overtime_balance(request.get('employee_id'), current_month)
                    if employee_balance:
                        balance_hours = employee_balance.get('balance_hours', 0)
                        st.markdown(f"**💰 Current Balance:** {balance_hours:.1f}h")
                
                with col3:
                    submitted_date = request.get('submitted_at')
                    if hasattr(submitted_date, 'timestamp'):
                        submitted_str = datetime.fromtimestamp(submitted_date.timestamp()).strftime('%d %b %Y')
                    else:
                        submitted_str = 'Unknown'
                    st.markdown(f"**📤 Submitted:** {submitted_str}")
                    st.markdown(f"**⏰ Status:** 🕐 Pending")

                # Overtime entries details
                st.markdown("**📋 Overtime Details:**")
                
                for entry in request.get('overtime_entries', []):
                    entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                    day_name = entry_date.strftime('%A')
                    date_str = entry_date.strftime('%d %b')
                    
                    with st.expander(f"{day_name}, {date_str} - {entry['hours']}h"):
                        st.write(f"**Hours:** {entry['hours']}")
                        st.write(f"**Description:** {entry['description']}")
                        
                        # Validate it's weekend
                        if entry_date.weekday() in [5, 6]:  # Saturday or Sunday
                            st.success("✅ Valid overtime day (Weekend)")
                        else:
                            st.warning("⚠️ Not a weekend - may be holiday")

                # Overall reason
                if request.get('reason'):
                    st.markdown("**💭 Overall Reason:**")
                    st.write(request['reason'])

                st.markdown("---")
                
                # Approval actions
                st.markdown("**🎯 Action Required:**")
                
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
                    
                    # Handle bulk actions
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
- ✅ Only weekends & holidays
- ✅ Valid business justification
- ✅ Reasonable hours (max 12h/day)
- ✅ Detailed work descriptions
- ✅ Budget considerations

**Before Approving:**
- Check employee's current balance
- Verify overtime dates are valid
- Review work descriptions
- Consider team workload
- Confirm budget availability
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
if pending_approvals:
    st.sidebar.metric("Pending Approvals", len(pending_approvals))
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

st.caption(f"Session: {user_data.get('name')} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")# pages/overtime_approval.py


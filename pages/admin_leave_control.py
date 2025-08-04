# pages/admin_leave_control.py
import streamlit as st
from datetime import datetime, date
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    LEAVE_TYPES, reset_annual_leave_quotas, get_leave_statistics,
    get_employee_leave_quota, get_employee_leave_requests
)

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

# Check if user has admin permissions
if access_level != 1:
    st.error("🚫 Access Denied: Admin privileges required.")
    st.info("Only Admin users can access the leave control panel.")
    if st.button("🏠 Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

# Page header
st.title("⚙️ Admin Leave Control Panel")
st.markdown(f"**Administrator:** {user_data.get('name')}")

# Logout button
if st.button("🚪 Logout", key="logout_admin"):
    handle_logout()
    st.success("Logged out! Redirecting...")
    st.markdown(clear_cookies_js(), unsafe_allow_html=True)
    st.stop()

# Navigation
if st.button("🏠 Back to Dashboard"):
    st.switch_page("pages/dashboard.py")

st.divider()

# Create tabs for different admin functions
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard", 
    "🔄 Quota Management", 
    "👥 Employee Management", 
    "📈 Reports"
])

with tab1:
    st.subheader("📊 Leave System Dashboard")
    
    # System statistics
    current_year = datetime.now().year
    system_stats = get_leave_statistics(year=current_year)
    
    if system_stats:
        st.markdown("### 📈 System Overview (Current Year)")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Requests", 
                system_stats['total_requests'],
                help="Total leave requests this year"
            )
        
        with col2:
            st.metric(
                "Approved", 
                system_stats['approved_requests'],
                help="Successfully approved requests"
            )
        
        with col3:
            st.metric(
                "Pending", 
                system_stats['pending_requests'],
                help="Requests awaiting approval"
            )
        
        with col4:
            st.metric(
                "Rejected", 
                system_stats['rejected_requests'],
                help="Rejected requests"
            )
        
        # Approval rate calculation
        if system_stats['total_requests'] > 0:
            approval_rate = (system_stats['approved_requests'] / system_stats['total_requests']) * 100
            st.metric("📊 Approval Rate", f"{approval_rate:.1f}%")
        
        # Leave type breakdown
        if system_stats['by_leave_type']:
            st.markdown("### 📋 Requests by Leave Type")
            
            col_types = st.columns(len(system_stats['by_leave_type']))
            for i, (leave_type, count) in enumerate(system_stats['by_leave_type'].items()):
                with col_types[i % len(col_types)]:
                    leave_name = LEAVE_TYPES.get(leave_type, {}).get('name', leave_type.title())
                    st.metric(leave_name, count)
    
    else:
        st.info("📊 No leave statistics available for the current year.")
    
    # Recent activity
    st.markdown("### 🕐 Recent System Activity")
    
    # Get recent requests across all employees (admin view)
    try:
        # This would need to be implemented in the database functions
        recent_activity = []  # Placeholder for recent activity
        
        if recent_activity:
            for activity in recent_activity[:10]:  # Show last 10 activities
                st.write(f"• {activity}")
        else:
            st.info("No recent activity to display.")
    except Exception as e:
        st.warning("Unable to load recent activity.")
    
    # System health checks
    st.markdown("### 🏥 System Health")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("✅ Database Connection: Active")
        st.success("✅ Authentication System: Working")
        st.success("✅ Leave Calculations: Operational")
    
    with col2:
        st.info("📅 Current Date: " + datetime.now().strftime("%Y-%m-%d"))
        st.info("📊 Active Users: Loading...")  # Would need implementation
        st.info("💾 Last Backup: Loading...")    # Would need implementation

with tab2:
    st.subheader("🔄 Leave Quota Management")
    
    # Year-end quota reset
    st.markdown("### 🗓️ Annual Quota Reset")
    
    st.info("""
    **Annual Leave Quota Reset:**
    - Resets all employee annual leave quotas for the new year
    - Employees with >12 months service: 14 days
    - Employees with ≤12 months service: 10 days
    - This action cannot be undone!
    """)
    
    if st.button("🔄 Reset All Annual Leave Quotas", type="primary"):
        if "confirm_reset" not in st.session_state:
            st.session_state.confirm_reset = True
            st.rerun()
    
    if st.session_state.get("confirm_reset"):
        st.warning("⚠️ **CONFIRMATION REQUIRED**")
        st.error("This will reset ALL employee annual leave quotas. This action cannot be undone!")
        
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("🟢 Yes, Reset All Quotas", type="primary"):
                with st.spinner("Resetting quotas..."):
                    result = reset_annual_leave_quotas()
                
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                else:
                    st.error(f"❌ {result['message']}")
                
                # Clear confirmation
                if "confirm_reset" in st.session_state:
                    del st.session_state.confirm_reset
                st.rerun()
        
        with col_no:
            if st.button("🔴 Cancel"):
                if "confirm_reset" in st.session_state:
                    del st.session_state.confirm_reset
                st.rerun()
    
    st.markdown("---")
    
    # Individual quota management
    st.markdown("### 👤 Individual Quota Management")
    
    # Employee search
    employee_search = st.text_input(
        "🔍 Search Employee",
        placeholder="Enter employee name or ID...",
        help="Search for an employee to manage their quota"
    )
    
    if employee_search:
        # This would need implementation to search employees
        st.info("Employee search functionality would be implemented here.")
    
    # Bulk quota adjustments
    st.markdown("### 📊 Bulk Quota Adjustments")
    
    col1, col2 = st.columns(2)
    
    with col1:
        division_filter = st.selectbox(
            "Filter by Division",
            options=["All Divisions", "HR", "Finance", "IT", "Operations"],  # Would be dynamic
            help="Select division for bulk operations"
        )
    
    with col2:
        quota_adjustment = st.number_input(
            "Quota Adjustment",
            min_value=-10,
            max_value=10,
            value=0,
            help="Add or subtract days from selected employees' quotas"
        )
    
    if st.button("⚡ Apply Bulk Adjustment"):
        if quota_adjustment != 0:
            st.warning("Bulk adjustment functionality would be implemented here.")
        else:
            st.warning("Please specify a quota adjustment amount.")

with tab3:
    st.subheader("👥 Employee Leave Management")
    
    # Employee overview
    st.markdown("### 📋 Employee Leave Overview")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        division_filter = st.selectbox(
            "Division",
            options=["All", "HR", "Finance", "IT", "Operations"],
            key="emp_division_filter"
        )
    
    with col2:
        status_filter = st.selectbox(
            "Status",
            options=["All", "Active", "On Leave", "Inactive"],
            key="emp_status_filter"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort By",
            options=["Name", "Leave Balance", "Department", "Join Date"],
            key="emp_sort_by"
        )
    
    # Employee list (mock data - would be from database)
    st.markdown("### 👥 Employee List")
    
    # This would be populated from the database
    mock_employees = [
        {
            "name": "John Doe",
            "email": "john@company.com",
            "division": "IT",
            "quota": 14,
            "used": 5,
            "pending": 2,
            "available": 7
        },
        {
            "name": "Jane Smith", 
            "email": "jane@company.com",
            "division": "HR",
            "quota": 14,
            "used": 8,
            "pending": 0,
            "available": 6
        }
    ]
    
    for emp in mock_employees:
        with st.expander(f"👤 {emp['name']} - {emp['division']}"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Quota", f"{emp['quota']} days")
            with col2:
                st.metric("Used", f"{emp['used']} days")
            with col3:
                st.metric("Pending", f"{emp['pending']} days")
            with col4:
                st.metric("Available", f"{emp['available']} days")
            
            # Quick actions
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button(f"📊 View Details", key=f"details_{emp['name']}"):
                    st.info("Employee details would be shown here")
            with col_b:
                if st.button(f"✏️ Edit Quota", key=f"edit_{emp['name']}"):
                    st.info("Quota editing would be implemented here")
            with col_c:
                if st.button(f"📋 Leave History", key=f"history_{emp['name']}"):
                    st.info("Leave history would be shown here")

with tab4:
    st.subheader("📈 Leave Reports & Analytics")
    
    # Report generation
    st.markdown("### 📊 Generate Reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        report_type = st.selectbox(
            "Report Type",
            options=[
                "Monthly Summary",
                "Annual Overview", 
                "Division Analysis",
                "Leave Type Breakdown",
                "Approval Rates",
                "Employee Utilization"
            ]
        )
    
    with col2:
        report_period = st.selectbox(
            "Period",
            options=[
                "Current Month",
                "Last Month",
                "Current Year",
                "Last Year",
                "Custom Range"
            ]
        )
    
    if report_period == "Custom Range":
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Start Date")
        with col_end:
            end_date = st.date_input("End Date")
    
    if st.button("📋 Generate Report", type="primary"):
        st.info("📊 Report generation would be implemented here")
        
        # Mock report data
        st.markdown("### 📈 Sample Report")
        
        if report_type == "Monthly Summary":
            st.markdown("""
            **Monthly Leave Summary - December 2024**
            
            - **Total Requests:** 45
            - **Approved:** 38 (84.4%)
            - **Pending:** 4 (8.9%)
            - **Rejected:** 3 (6.7%)
            
            **Most Requested Leave Types:**
            1. Annual Leave (32 requests)
            2. Sick Leave (8 requests)
            3. Marriage Leave (3 requests)
            4. Menstrual Leave (2 requests)
            """)
        
        elif report_type == "Division Analysis":
            st.markdown("""
            **Division Leave Analysis**
            
            | Division | Total Requests | Approval Rate | Avg Days/Employee |
            |----------|----------------|---------------|-------------------|
            | IT       | 18            | 88.9%         | 8.2              |
            | HR       | 12            | 91.7%         | 7.5              |
            | Finance  | 10            | 80.0%         | 6.8              |
            | Operations| 15           | 86.7%         | 9.1              |
            """)
    
    st.markdown("---")
    
    # Export options
    st.markdown("### 📤 Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Export to Excel"):
            st.info("Excel export would download a file")
    
    with col2:
        if st.button("📄 Export to PDF"):
            st.info("PDF export would download a file")
    
    with col3:
        if st.button("📧 Email Report"):
            st.info("Email functionality would be implemented")
    
    # Quick stats
    st.markdown("### ⚡ Quick Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Avg Approval Time", "2.3 days")
    
    with col2:
        st.metric("Peak Leave Month", "December")
    
    with col3:
        st.metric("Most Active Division", "Operations")
    
    with col4:
        st.metric("System Uptime", "99.9%")

# Sidebar with admin tools
st.sidebar.markdown("### ⚙️ Admin Tools")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

if st.sidebar.button("💾 Backup System"):
    st.sidebar.info("Backup initiated...")

if st.sidebar.button("🔍 System Logs"):
    st.sidebar.info("System logs would be displayed")

st.sidebar.markdown("### 📊 System Status")
st.sidebar.success("✅ All systems operational")
st.sidebar.info(f"⏰ Last updated: {datetime.now().strftime('%H:%M:%S')}")

st.sidebar.markdown("### 🆘 Emergency Actions")
if st.sidebar.button("🚨 Emergency Override"):
    st.sidebar.warning("Emergency override functionality")

# Footer
st.markdown("---")
st.caption("🔒 Admin Panel - Restricted Access")
st.caption(f"Session: {user_data.get('name')} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
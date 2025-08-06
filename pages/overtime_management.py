# pages/overtime_management.py - Enhanced with simplified date selection and individual date entry
import streamlit as st
from datetime import datetime, date, timedelta
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    submit_overtime_request, get_employee_overtime_requests,
    get_employee_overtime_balance
)
import pandas as pd
import calendar

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

def get_last_overtime_reset_date():
    """Get the last overtime balance reset date to set minimum date for overtime submission"""
    try:
        # Check system settings or overtime_balances for last reset
        # This would be stored when admin resets balances
        settings_ref = db.collection("system_settings").document("overtime_reset")
        settings_data = settings_ref.get().to_dict()
        
        if settings_data and settings_data.get("last_reset_date"):
            reset_date = settings_data["last_reset_date"]
            if hasattr(reset_date, 'timestamp'):
                return datetime.fromtimestamp(reset_date.timestamp()).date()
            else:
                return datetime.strptime(reset_date, "%Y-%m-%d").date()
        
        # If no reset date found, default to beginning of current year
        return date(datetime.now().year, 1, 1)
        
    except Exception as e:
        print(f"Error getting last reset date: {e}")
        # Fallback to beginning of current year
        return date(datetime.now().year, 1, 1)

def get_week_dates(selected_date):
    """Get the start and end dates of the week containing the selected date"""
    # Find Monday of the week (weekday() returns 0 for Monday)
    days_since_monday = selected_date.weekday()
    week_start = selected_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)  # Sunday
    return week_start, week_end
    """Get the start and end dates of the week containing the selected date"""
    # Find Monday of the week (weekday() returns 0 for Monday)
    days_since_monday = selected_date.weekday()
    week_start = selected_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)  # Sunday
    return week_start, week_end

# Page header
st.title("⏰ Overtime Management")
st.markdown(f"**Employee:** {user_data.get('name')} | **Division:** {user_data.get('division_name', 'Unknown')}")

# Logout button
if st.button("🚪 Logout", key="logout_overtime"):
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
    # Show approval button for managers
    if access_level in [1, 2, 3]:
        if st.button("✅ Approve Overtime"):
            st.switch_page("pages/overtime_approval.py")

st.divider()

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Submit Overtime", 
    "📊 My Overtime Balance", 
    "📋 My Overtime History",
    "📈 Statistics"
])

with tab1:
    st.subheader("📝 Submit Overtime Request")
    
    st.info("""
    **Overtime Submission:**
    - Select specific dates and enter overtime hours
    - Maximum 12 hours per day
    - Include detailed description for each overtime day
    - Submit for approval once completed
    """)
    
    # Initialize overtime entries in session state
    if "overtime_entries" not in st.session_state:
        st.session_state.overtime_entries = []
    
    # Get minimum date from last reset
    min_date = get_last_overtime_reset_date()
    
    # Date and hours input form
    st.markdown("### ➕ Add Overtime Entry")
    
    with st.form("add_overtime_entry", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 1, 3])
        
        with col1:
            overtime_date = st.date_input(
                "Date",
                value=date.today() - timedelta(days=1),  # Default to yesterday
                min_value=min_date,  # Set minimum date from last reset
                max_value=date.today(),
                help=f"Select the date you worked overtime (earliest: {min_date.strftime('%d %b %Y')})"
            )
        
        with col2:
            hours = st.number_input(
                "Hours",
                min_value=0.5,
                max_value=12.0,
                step=0.5,
                value=1.0,
                help="Overtime hours (0.5 - 12 hours)"
            )
        
        with col3:
            description = st.text_input(
                "Work Description",
                placeholder="e.g., Project completion, System maintenance, Client meeting",
                help="Describe the work performed during overtime"
            )
        
        add_entry = st.form_submit_button("➕ Add Entry", type="primary")
        
        if add_entry:
            if hours <= 0:
                st.error("Please enter valid overtime hours")
            elif not description.strip():
                st.error("Please provide a description of the work performed")
            else:
                # Check if date already exists
                existing_dates = [entry["date"] for entry in st.session_state.overtime_entries]
                if overtime_date.strftime("%Y-%m-%d") in existing_dates:
                    st.error("Entry for this date already exists. Please edit or remove the existing entry.")
                else:
                    # Add new entry
                    new_entry = {
                        "date": overtime_date.strftime("%Y-%m-%d"),
                        "date_display": overtime_date.strftime("%A, %d %B %Y"),
                        "hours": hours,
                        "description": description.strip()
                    }
                    st.session_state.overtime_entries.append(new_entry)
                    st.success(f"Added {hours}h overtime for {overtime_date.strftime('%d %B %Y')}")
                    st.rerun()
    
    # Display current entries
    if st.session_state.overtime_entries:
        st.markdown("### 📋 Current Overtime Entries")
        
        # Sort entries by date
        st.session_state.overtime_entries.sort(key=lambda x: x["date"])
        
        total_hours = sum(entry["hours"] for entry in st.session_state.overtime_entries)
        total_days = len(st.session_state.overtime_entries)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Days", total_days)
        with col2:
            st.metric("Total Hours", f"{total_hours:.1f}h")
        with col3:
            avg_hours = total_hours / total_days if total_days > 0 else 0
            st.metric("Avg Hours/Day", f"{avg_hours:.1f}h")
        
        st.markdown("---")
        
        # Display entries in a clean format
        for i, entry in enumerate(st.session_state.overtime_entries):
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 3, 1])
                
                with col1:
                    st.write(f"📅 **{entry['date_display']}**")
                
                with col2:
                    st.write(f"⏰ **{entry['hours']}h**")
                
                with col3:
                    st.write(f"📝 {entry['description']}")
                
                with col4:
                    if st.button("🗑️", key=f"remove_{i}", help="Remove entry"):
                        st.session_state.overtime_entries.pop(i)
                        st.rerun()
                
                st.markdown("---")
        
        # Overall reason and submit
        st.markdown("### 📄 Submit Request")
        
        overall_reason = st.text_area(
            "Overall Reason for Overtime *",
            placeholder="Explain the overall context for this overtime (e.g., project deadline, urgent maintenance, client emergency)",
            help="Provide context for why overtime was necessary",
            max_chars=500
        )
        
        # Submit button
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("🚀 Submit Overtime Request", type="primary", use_container_width=True):
                if not overall_reason.strip():
                    st.error("❌ Please provide an overall reason for overtime")
                else:
                    # Calculate week range for the entries
                    dates = [datetime.strptime(entry["date"], "%Y-%m-%d").date() for entry in st.session_state.overtime_entries]
                    week_start = min(dates)
                    week_end = max(dates)
                    
                    # Prepare overtime data
                    overtime_data = {
                        "week_start": week_start.strftime("%Y-%m-%d"),
                        "week_end": week_end.strftime("%Y-%m-%d"),
                        "overtime_entries": st.session_state.overtime_entries,
                        "total_hours": total_hours,
                        "reason": overall_reason.strip()
                    }
                    
                    # Submit overtime request
                    result = submit_overtime_request(employee_id, overtime_data)
                    
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        st.balloons()
                        st.info("Your overtime request has been sent to your supervisor for approval.")
                        
                        # Clear entries
                        st.session_state.overtime_entries = []
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")
        
        with col2:
            if st.button("🗑️ Clear All Entries", type="secondary", use_container_width=True):
                st.session_state.overtime_entries = []
                st.rerun()
    
    else:
        st.info("📝 No overtime entries added yet. Use the form above to add your overtime hours.")
        
        # Check if user has pending requests and show them
        recent_requests = get_employee_overtime_requests(employee_id, limit=3)
        if recent_requests:
            st.markdown("### 📋 Recent Requests")
            
            for request in recent_requests:
                status = request.get("status", "unknown")
                status_icon = "🕐" if status == "pending" else "✅" if status == "approved" else "❌"
                
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        week_start = request.get("week_start", "")
                        week_end = request.get("week_end", "")
                        st.write(f"**Week:** {week_start} to {week_end}")
                    
                    with col2:
                        st.write(f"**{request.get('total_hours', 0):.1f}h**")
                    
                    with col3:
                        st.write(f"{status_icon} {status.title()}")
                    
                    st.caption(f"Submitted: {datetime.fromtimestamp(request.get('submitted_at').timestamp()).strftime('%d %b %Y') if hasattr(request.get('submitted_at', 0), 'timestamp') else 'Unknown'}")
                    st.divider()

with tab2:
    st.subheader("📊 My Overtime Balance")
    
    # Current month balance
    current_month = datetime.now().strftime("%Y-%m")
    balance_data = get_employee_overtime_balance(employee_id, current_month)
    
    if balance_data:
        # Main metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Approved Hours", f"{balance_data.get('approved_hours', 0):.1f}h")
        
        with col2:
            st.metric("Paid Hours", f"{balance_data.get('paid_hours', 0):.1f}h")
        
        with col3:
            balance_hours = balance_data.get('balance_hours', 0)
            st.metric("Balance Hours", f"{balance_hours:.1f}h")
        
        with col4:
            # Estimated pay (assuming overtime rate exists in user data)
            overtime_rate = user_data.get('overtime_rate', 0)
            estimated_pay = balance_hours * overtime_rate
            st.metric("Estimated Pay", f"${estimated_pay:,.2f}" if overtime_rate > 0 else "N/A")
        
        # Balance history chart
        st.markdown("### 📈 Monthly Balance History")
        
        # Get last 6 months of balance data
        balance_history = []
        for i in range(6):
            month_date = datetime.now() - timedelta(days=30*i)
            month_str = month_date.strftime("%Y-%m")
            month_balance = get_employee_overtime_balance(employee_id, month_str)
            
            if month_balance:
                balance_history.append({
                    "Month": month_date.strftime("%b %Y"),
                    "Approved": month_balance.get('approved_hours', 0),
                    "Paid": month_balance.get('paid_hours', 0),
                    "Balance": month_balance.get('balance_hours', 0)
                })
        
        if balance_history:
            balance_history.reverse()  # Show oldest to newest
            df_balance = pd.DataFrame(balance_history)
            
            st.line_chart(df_balance.set_index("Month")[["Approved", "Paid", "Balance"]])
            
            # Show detailed table
            st.markdown("### 📋 Balance Details")
            st.dataframe(df_balance, use_container_width=True, hide_index=True)
        
        # Overtime rate info
        if overtime_rate > 0:
            st.markdown("### 💰 Rate Information")
            st.info(f"**Your Overtime Rate:** ${overtime_rate:.2f} per hour")
        else:
            st.warning("⚠️ Overtime rate not set. Please contact HR.")
    
    else:
        st.info("📊 No overtime balance data available for this month.")
        st.write("Submit your first overtime request to start tracking your balance!")

with tab3:
    st.subheader("📋 My Overtime Request History")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "Pending", "Approved", "Rejected"],
            index=0
        )
    
    with col2:
        # Get unique months from requests
        all_requests = get_employee_overtime_requests(employee_id)
        months = set()
        for req in all_requests:
            try:
                week_start = datetime.strptime(req.get("week_start", ""), "%Y-%m-%d")
                months.add(week_start.strftime("%Y-%m"))
            except:
                pass
        
        month_options = ["All"] + sorted(list(months), reverse=True)
        month_filter = st.selectbox(
            "Filter by Month",
            options=month_options,
            index=0
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=["Newest First", "Oldest First", "Hours (High-Low)", "Hours (Low-High)"],
            index=0
        )
    
    # Get overtime requests
    overtime_requests = get_employee_overtime_requests(employee_id)
    
    # Apply filters
    filtered_requests = []
    for request in overtime_requests:
        # Status filter
        if status_filter != "All":
            if request.get("status") != status_filter.lower():
                continue
        
        # Month filter
        if month_filter != "All":
            try:
                week_start = datetime.strptime(request.get("week_start", ""), "%Y-%m-%d")
                request_month = week_start.strftime("%Y-%m")
                if request_month != month_filter:
                    continue
            except:
                continue
        
        filtered_requests.append(request)
    
    # Apply sorting
    if sort_by == "Newest First":
        filtered_requests.sort(key=lambda x: x.get("submitted_at", 0), reverse=True)
    elif sort_by == "Oldest First":
        filtered_requests.sort(key=lambda x: x.get("submitted_at", 0))
    elif sort_by == "Hours (High-Low)":
        filtered_requests.sort(key=lambda x: x.get("total_hours", 0), reverse=True)
    elif sort_by == "Hours (Low-High)":
        filtered_requests.sort(key=lambda x: x.get("total_hours", 0))
    
    if not filtered_requests:
        st.info("📋 No overtime requests found matching the selected filters.")
    else:
        st.write(f"📊 **Total Requests:** {len(filtered_requests)}")
        
        # Summary statistics
        total_hours = sum([req.get("total_hours", 0) for req in filtered_requests])
        approved_hours = sum([req.get("total_hours", 0) for req in filtered_requests if req.get("status") == "approved"])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Hours Requested", f"{total_hours:.1f}h")
        with col2:
            st.metric("Approved Hours", f"{approved_hours:.1f}h")
        with col3:
            approval_rate = (approved_hours / total_hours * 100) if total_hours > 0 else 0
            st.metric("Approval Rate", f"{approval_rate:.1f}%")
        
        st.markdown("---")
        
        # Display requests
        for i, request in enumerate(filtered_requests):
            with st.container():
                # Request header
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    week_start = request.get("week_start", "")
                    week_end = request.get("week_end", "")
                    st.write(f"**Week: {week_start} to {week_end}**")
                
                with col2:
                    st.write(f"**{request.get('total_hours', 0):.1f} hours**")
                
                with col3:
                    status = request.get("status", "unknown")
                    if status == "pending":
                        st.warning("🕐 Pending")
                    elif status == "approved":
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
                
                # Show details in expander
                with st.expander(f"Details - Week {week_start}"):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.write("**Request Information:**")
                        st.write(f"• **Total Hours:** {request.get('total_hours', 0):.1f}")
                        st.write(f"• **Number of Days:** {len(request.get('overtime_entries', []))}")
                        st.write(f"• **Status:** {status.title()}")
                        
                        # Show overtime entries
                        st.write("**Overtime Days:**")
                        for entry in request.get("overtime_entries", []):
                            entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                            st.write(f"• {entry_date.strftime('%A, %d %b')}: {entry['hours']}h - {entry['description']}")
                    
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
                        
                        # Show who processed it
                        processor_name = request.get("approved_by_name") or request.get("rejected_by_name")
                        if processor_name:
                            st.write(f"• **Processed by:** {processor_name}")
                    
                    # Full reason
                    if request.get("reason"):
                        st.write("**Overall Reason:**")
                        st.write(request["reason"])
                
                st.divider()

with tab4:
    st.subheader("📈 My Overtime Statistics")
    
    # Year selection
    current_year = datetime.now().year
    selected_year = st.selectbox(
        "Select Year",
        options=[current_year, current_year - 1, current_year - 2],
        index=0
    )
    
    # Get year statistics
    year_requests = []
    for request in get_employee_overtime_requests(employee_id):
        try:
            week_start = datetime.strptime(request.get("week_start", ""), "%Y-%m-%d")
            if week_start.year == selected_year:
                year_requests.append(request)
        except:
            continue
    
    if not year_requests:
        st.info(f"📊 No overtime data found for {selected_year}")
    else:
        # Year summary
        total_requests = len(year_requests)
        total_hours_requested = sum([req.get("total_hours", 0) for req in year_requests])
        approved_requests = [req for req in year_requests if req.get("status") == "approved"]
        total_hours_approved = sum([req.get("total_hours", 0) for req in approved_requests])
        
        st.markdown(f"### 📊 {selected_year} Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Requests", total_requests)
        
        with col2:
            st.metric("Hours Requested", f"{total_hours_requested:.1f}h")
        
        with col3:
            st.metric("Hours Approved", f"{total_hours_approved:.1f}h")
        
        with col4:
            approval_rate = (len(approved_requests) / total_requests * 100) if total_requests > 0 else 0
            st.metric("Approval Rate", f"{approval_rate:.1f}%")
        
        # Monthly breakdown
        st.markdown("### 📅 Monthly Breakdown")
        
        monthly_data = {}
        for request in year_requests:
            try:
                week_start = datetime.strptime(request.get("week_start", ""), "%Y-%m-%d")
                month_key = week_start.strftime("%Y-%m")
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "requests": 0,
                        "hours_requested": 0,
                        "hours_approved": 0
                    }
                
                monthly_data[month_key]["requests"] += 1
                monthly_data[month_key]["hours_requested"] += request.get("total_hours", 0)
                
                if request.get("status") == "approved":
                    monthly_data[month_key]["hours_approved"] += request.get("total_hours", 0)
            except:
                continue
        
        if monthly_data:
            # Create chart data
            chart_data = []
            for month, data in sorted(monthly_data.items()):
                month_name = datetime.strptime(month, "%Y-%m").strftime("%b %Y")
                chart_data.append({
                    "Month": month_name,
                    "Requests": data["requests"],
                    "Hours Requested": data["hours_requested"],  
                    "Hours Approved": data["hours_approved"]
                })
            
            df_monthly = pd.DataFrame(chart_data)
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Monthly Requests**")
                st.bar_chart(df_monthly.set_index("Month")["Requests"])
            
            with col2:
                st.write("**Monthly Hours**")
                st.bar_chart(df_monthly.set_index("Month")[["Hours Requested", "Hours Approved"]])
            
            # Detailed table
            st.markdown("### 📋 Monthly Details")
            st.dataframe(df_monthly, use_container_width=True, hide_index=True)

# Footer with navigation
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if access_level in [1, 2, 3]:
        if st.button("✅ Approve Overtime", use_container_width=True):
            st.switch_page("pages/overtime_approval.py")

with col3:
    if st.button("📝 Leave Requests", use_container_width=True):
        st.switch_page("pages/leave_request.py")

# Sidebar with helpful information
st.sidebar.markdown("### ⏰ Overtime Guidelines")

st.sidebar.markdown("""
**Overtime Rules:**
- ✅ Select any date to enter overtime
- ✅ Maximum 12 hours per day
- ✅ Detailed descriptions required
- ✅ Supervisor approval needed

**Submission Tips:**
- Add each overtime day individually
- Be specific in descriptions
- Include project/task context
- Check balance regularly
- Submit multiple days together
""")

st.sidebar.markdown("### 📊 Quick Stats")
if balance_data:
    st.sidebar.metric("Current Balance", f"{balance_data.get('balance_hours', 0):.1f}h")
    st.sidebar.metric("This Month Approved", f"{balance_data.get('approved_hours', 0):.1f}h")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
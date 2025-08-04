# pages/overtime_management.py
import streamlit as st
from datetime import datetime, date, timedelta
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.leave_system_db import (
    submit_overtime_request, get_employee_overtime_requests,
    get_employee_overtime_balance, validate_overtime_request
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

def get_week_dates(selected_date):
    """Get the start and end dates of the week containing the selected date"""
    # Find Monday of the week (weekday() returns 0 for Monday)
    days_since_monday = selected_date.weekday()
    week_start = selected_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)  # Sunday
    return week_start, week_end

def is_weekend_or_holiday(date_obj):
    """Check if date is weekend (Saturday=5, Sunday=6)"""
    return date_obj.weekday() in [5, 6]

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
    st.subheader("📝 Submit Weekly Overtime Request")
    
    st.info("""
    **Overtime Rules:**
    - Overtime is only allowed on weekends (Saturday & Sunday) and public holidays
    - Submit weekly overtime requests (Monday to Sunday)
    - Maximum 12 hours per day
    - Include detailed description for each overtime day
    """)
    
    # Week selection
    col1, col2 = st.columns(2)
    
    with col1:
        selected_date = st.date_input(
            "Select any date in the week",
            value=date.today() - timedelta(days=7),  # Default to last week
            max_value=date.today(),
            help="Select any date in the week you want to submit overtime for"
        )
    
    with col2:
        week_start, week_end = get_week_dates(selected_date)
        st.info(f"**Week Period:**\n{week_start.strftime('%d %b %Y')} - {week_end.strftime('%d %b %Y')}")
    
    # Check if week is in the past
    if week_end > date.today():
        st.warning("⚠️ Cannot submit overtime for future dates")
    else:
        # Show week calendar
        st.markdown("### 📅 Week Overview")
        
        week_days = []
        current_date = week_start
        
        for i in range(7):
            day_name = current_date.strftime("%A")
            is_overtime_eligible = is_weekend_or_holiday(current_date)
            
            week_days.append({
                "Date": current_date.strftime("%d %b"),
                "Day": day_name,
                "Eligible": "✅ Yes" if is_overtime_eligible else "❌ No",
                "Type": "Weekend" if is_overtime_eligible else "Weekday"
            })
            
            current_date += timedelta(days=1)
        
        df_week = pd.DataFrame(week_days)
        st.dataframe(df_week, use_container_width=True, hide_index=True)
        
        # Overtime entry form
        st.markdown("### ⏰ Enter Overtime Hours")
        
        with st.form("overtime_form"):
            overtime_entries = []
            total_hours = 0
            
            # Create inputs for each eligible day
            eligible_days = [day for day in week_days if "✅ Yes" in day["Eligible"]]
            
            if not eligible_days:
                st.warning("No eligible overtime days in this week (weekends/holidays only)")
            else:
                st.markdown("**Enter overtime hours for eligible days:**")
                
                for day in eligible_days:
                    day_date = datetime.strptime(f"{day['Date']} {week_start.year}", "%d %b %Y").date()
                    
                    col_day, col_hours, col_desc = st.columns([1, 1, 2])
                    
                    with col_day:
                        st.write(f"**{day['Day']}**")
                        st.write(f"{day['Date']}")
                    
                    with col_hours:
                        hours = st.number_input(
                            "Hours",
                            min_value=0.0,
                            max_value=12.0,
                            step=0.5,
                            key=f"hours_{day_date}",
                            help="Maximum 12 hours per day"
                        )
                    
                    with col_desc:
                        description = st.text_input(
                            "Description",
                            key=f"desc_{day_date}",
                            placeholder="e.g., Project X completion, System maintenance",
                            help="Describe the work performed"
                        )
                    
                    if hours > 0:
                        if not description.strip():
                            st.error(f"Please provide description for {day['Day']} overtime")
                        else:
                            overtime_entries.append({
                                "date": day_date.strftime("%Y-%m-%d"),
                                "hours": hours,
                                "description": description
                            })
                            total_hours += hours
                
                # Overall reason
                st.markdown("---")
                overall_reason = st.text_area(
                    "Overall Reason for Overtime *",
                    placeholder="Explain the overall reason for this overtime week...",
                    help="Provide context for why overtime was necessary this week",
                    max_chars=500
                )
                
                # Summary
                if overtime_entries:
                    st.markdown("### 📊 Overtime Summary")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total Days", len(overtime_entries))
                    with col2:
                        st.metric("Total Hours", f"{total_hours:.1f}")
                    with col3:
                        avg_hours = total_hours / len(overtime_entries) if overtime_entries else 0
                        st.metric("Avg Hours/Day", f"{avg_hours:.1f}")
                    
                    # Show entry details
                    st.markdown("**Overtime Entries:**")
                    for entry in overtime_entries:
                        entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                        st.write(f"• **{entry_date.strftime('%A, %d %B')}:** {entry['hours']} hours - {entry['description']}")
                
                # Submit button
                submit_overtime = st.form_submit_button("🚀 Submit Overtime Request", type="primary")
                
                if submit_overtime:
                    if not overtime_entries:
                        st.error("❌ Please enter overtime hours for at least one day")
                    elif not overall_reason.strip():
                        st.error("❌ Please provide an overall reason for overtime")
                    else:
                        # Prepare overtime data
                        overtime_data = {
                            "week_start": week_start.strftime("%Y-%m-%d"),
                            "week_end": week_end.strftime("%Y-%m-%d"),
                            "overtime_entries": overtime_entries,
                            "total_hours": total_hours,
                            "reason": overall_reason.strip()
                        }
                        
                        # Submit overtime request
                        result = submit_overtime_request(employee_id, overtime_data)
                        
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.balloons()
                            st.info("Your overtime request has been sent to your supervisor for approval.")
                            
                            # Clear form by rerunning
                            st.rerun()
                        else:
                            st.error(f"❌ {result['message']}")

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
        
        # Top overtime days
        st.markdown("### 🏆 Most Productive Overtime Days")
        
        day_stats = {}
        for request in approved_requests:
            for entry in request.get("overtime_entries", []):
                entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                day_name = entry_date.strftime("%A")
                
                if day_name not in day_stats:
                    day_stats[day_name] = {"hours": 0, "count": 0}
                
                day_stats[day_name]["hours"] += entry["hours"]
                day_stats[day_name]["count"] += 1
        
        if day_stats:
            day_chart_data = []
            for day, stats in day_stats.items():
                day_chart_data.append({
                    "Day": day,
                    "Total Hours": stats["hours"],
                    "Sessions": stats["count"],
                    "Avg Hours": stats["hours"] / stats["count"]
                })
            
            df_days = pd.DataFrame(day_chart_data)
            df_days = df_days.sort_values("Total Hours", ascending=False)
            
            st.dataframe(df_days, use_container_width=True, hide_index=True)

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
- ✅ Only weekends and holidays
- ✅ Maximum 12 hours per day
- ✅ Submit weekly (Mon-Sun)
- ✅ Detailed descriptions required
- ✅ Supervisor approval needed

**Submission Tips:**
- Submit by end of following week
- Be specific in descriptions
- Include project/task context
- Check balance regularly
""")

st.sidebar.markdown("### 📊 Quick Stats")
if balance_data:
    st.sidebar.metric("Current Balance", f"{balance_data.get('balance_hours', 0):.1f}h")
    st.sidebar.metric("This Month Approved", f"{balance_data.get('approved_hours', 0):.1f}h")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
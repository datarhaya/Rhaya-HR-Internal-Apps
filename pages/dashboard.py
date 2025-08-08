# Enhanced dashboard.py with overtime management integration
import streamlit as st
from datetime import datetime
import pathlib
import utils.database as db
from utils.auth import get_authenticator, check_authentication, logout_user
from utils.logout_handler import handle_logout, clear_cookies_js, check_logout_status, is_authenticated
from utils.leave_system_db import (
    get_employee_leave_quota, get_employee_leave_requests, get_pending_approvals_for_approver,
    get_employee_overtime_balance, get_employee_overtime_requests, get_pending_overtime_approvals_for_approver
)

# Check if user just logged out
if check_logout_status():
    st.success("Anda Berhasil Log out dari akun Anda!")
    st.info("Mengarahkan ke laman login...")
    # Automatic redirect without button
    import time
    time.sleep(1)
    st.switch_page("pages/login.py")

# Initialize authentication check with error handling
try:
    authenticator = check_authentication()
except Exception as e:
    st.error(f"Authentication system error: {e}")
    st.info("Coba refresh laman ini atau pergi ke laman login.")
    if st.button("Go to Login Page"):
        st.session_state.clear()
        st.switch_page("pages/login.py")
    st.stop()

# Use the logout handler's authentication check
if not is_authenticated():
    st.warning("Anda harus masuk terlebih dahulu.")
    if st.button("Go to Login Page"):
        st.switch_page("pages/login.py")
    st.stop()

# Get user data
username = st.session_state.get("username")

# Ensure user data is loaded
if "user_data" not in st.session_state and username:
    user_data = db.fetch_user_by_username(username)
    if user_data:
        from utils.database import enrich_user_data
        user_data = enrich_user_data(user_data)
        st.session_state.user_data = user_data
    else:
        st.error("Pengguna tidak ditemukan. Jika menurut Anda ini adalah kesalahan, silakan hubungi tim IT (data@rhayaflicks.com)")
        st.switch_page("pages/login.py")
        st.stop()

# Final check for user data
if "user_data" not in st.session_state:
    st.error("Session expired. Silakan masuk lagi.")
    st.switch_page("pages/login.py")
    st.stop()

# -- Display User Data --
user_data = st.session_state["user_data"]
employee_id = user_data.get("employee_id")

# --- Helper functions ---
def format_date(dt):
    try:
        return dt.strftime("%d %B %Y")
    except Exception:
        return str(dt)

def service_duration(start_date):
    today = datetime.utcnow()
    if hasattr(start_date, "timestamp"):
        start_date = datetime.fromtimestamp(start_date.timestamp())
    delta = today - start_date
    return f"{delta.days} days"

# === UI Components ===
st.subheader(f"Selamat datang, {user_data.get('name', 'Unknown')}!")

# -- Handle Logout --
if st.sidebar.button("🚪 Logout", key="logout_main"):
    # Use logout handler
    handle_logout()
    st.success("Anda Berhasil Log out dari akun Anda!")

    # Execute JavaScript cookie clearing
    st.markdown(clear_cookies_js(), unsafe_allow_html=True)
    
    # Don't redirect immediately, let JS handle it
    st.stop()

col1, col2 = st.columns([0.2, 0.8])

with col1:
    st.image("assets/profile-placeholder-square.jpg", use_container_width=True)

with col2:
    st.markdown(f"""
        <div style="font-size: 0.75rem; color: gray;">Nama</div>
        <div style="font-size: 1rem; margin-bottom: 4px;">{user_data['name']}</div>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 8px 0;" />

        <div style="font-size: 0.75rem; color: gray;">Posisi</div>
        <div style="font-size: 1rem; margin-bottom: 4px;">{user_data['role_name']} ({user_data['division_name']})</div>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 8px 0;" />

        <div style="font-size: 0.75rem; color: gray;">Email</div>
        <div style="font-size: 1rem; margin-bottom: 4px;">{user_data['email']}</div>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 8px 0;" />

        <div style="font-size: 0.75rem; color: gray;">Bergabung Sejak</div>
        <div style="font-size: 1rem; margin-bottom: 4px;">{format_date(user_data['start_joining_date'])} ({service_duration(user_data['start_joining_date'])})</div>

    """, unsafe_allow_html=True)

st.divider()

# -- Enhanced Quick Stats with Leave and Overtime Information --
access_level = user_data.get("access_level", 4)

# Get leave data
leave_quota = get_employee_leave_quota(employee_id) if employee_id else None
recent_leave_requests = get_employee_leave_requests(employee_id, limit=5) if employee_id else []
pending_leave_requests = len([r for r in recent_leave_requests if r.get("status") == "pending"])

# Get overtime data
current_month = datetime.now().strftime("%Y-%m")
overtime_balance = get_employee_overtime_balance(employee_id, current_month) if employee_id else None
recent_overtime_requests = get_employee_overtime_requests(employee_id, limit=5) if employee_id else []
pending_overtime_requests = len([r for r in recent_overtime_requests if r.get("status") == "pending"])

# For managers, get pending approvals
pending_leave_approvals = 0
pending_overtime_approvals = 0
if access_level in [1, 2, 3]:  # Admin, HR Staff, Division Head
    pending_leave_approvals_list = get_pending_approvals_for_approver(employee_id) if employee_id else []
    pending_leave_approvals = len(pending_leave_approvals_list)
    
    pending_overtime_approvals_list = get_pending_overtime_approvals_for_approver(employee_id) if employee_id else []
    pending_overtime_approvals = len(pending_overtime_approvals_list)

# Calculate leave stats
if leave_quota:
    leave_used = leave_quota.get("annual_used", 0)
    leave_remaining = leave_quota.get("annual_quota", 14) - leave_used - leave_quota.get("annual_pending", 0)
else:
    leave_used = 0
    leave_remaining = 14

# Calculate overtime stats
if overtime_balance:
    overtime_balance_hours = overtime_balance.get("balance_hours", 0)
    overtime_approved_hours = overtime_balance.get("approved_hours", 0)
else:
    overtime_balance_hours = 0
    overtime_approved_hours = 0

# -- Enhanced Navigation Sidebar --
st.sidebar.title("🧭 Navigation")

# Add to sidebar navigation
st.sidebar.markdown("### 🔐 Akun")
if st.sidebar.button("🔑 Ubah Kata Sandi"):
    st.switch_page("pages/password_management.py")

# Leave Management Section
st.sidebar.markdown("### 📋 Cuti")
if st.sidebar.button("📝 Ajukan Cuti"):
    st.switch_page("pages/leave_request.py")

if access_level in [1, 2, 3]:
    if st.sidebar.button("✅ Persetujuan Cuti"):
        st.switch_page("pages/leave_approval.py")

if access_level == 1:
    if st.sidebar.button("⚙️ Cuti Admin Control"):
        st.switch_page("pages/admin_leave_control.py")

# NEW: Overtime Management Section
st.sidebar.markdown("### ⏰ Lembur")
if st.sidebar.button("⏰ Ajukan Lembur"):
    st.switch_page("pages/overtime_management.py")

if access_level in [1, 2, 3]:
    if st.sidebar.button("✅ Persetujuan Lembur"):
        st.switch_page("pages/overtime_approval.py")

# Other Navigation
st.sidebar.markdown("### 👤 Profile & Settings")
if access_level == 1:  # Admin
    if st.sidebar.button("Admin Control Panel"):
        st.switch_page("pages/admin_control.py")

st.sidebar.button("My Profile")

# Sidebar logout as backup
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
    handle_logout()
    st.markdown(clear_cookies_js(), unsafe_allow_html=True)

# -- Enhanced Quick Actions --
st.subheader("🚀 Quick Actions")

# Enhanced layout with overtime actions
col1, col2, = st.columns(2)

with col1:
    if st.button("📝 Ajukan Cuti", use_container_width=True):
        st.switch_page("pages/leave_request.py")

with col2:
    if st.button("⏰ Ajukan Lembur", use_container_width=True):
        st.switch_page("pages/overtime_management.py")

# -- Enhanced Status Overview with Leave and Overtime --
st.subheader("📊 My Status Overview")

# Create tabs for better organization
tab1, tab2 = st.tabs(["📋 Status Cuti", "⏰ Status Lembur"])

with tab1:
    st.markdown("### 📋 Leave Balance")
    
    if leave_quota:
        # Progress bars for leave usage
        total_quota = leave_quota.get("annual_quota", 14)
        used = leave_quota.get("annual_used", 0)
        pending = leave_quota.get("annual_pending", 0)
        available = total_quota - used - pending
        
        col1, col2, col3 = st.columns([0.33, 0.33, 0.34])
        # col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Used", f"{used}/{total_quota}")
            if total_quota > 0:
                st.progress(used / total_quota)
        
        with col2:
            st.metric("Pending", f"{pending}/{total_quota}")
            if total_quota > 0:
                st.progress(pending / total_quota if pending > 0 else 0.0)
        
        with col3:
            st.metric("Available", f"{available}/{total_quota}")
            if total_quota > 0:
                st.progress(available / total_quota if available > 0 else 0.0)
    else:
        st.info("📊 Leave quota information not available.")
    
    # Recent Leave Requests
    if recent_leave_requests:
        st.markdown("### 📋 Recent Leave Requests")
        
        for request in recent_leave_requests[:3]:  # Show only last 3
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    leave_type_name = request.get('leave_type', 'Unknown').title()
                    st.write(f"**{leave_type_name} Leave**")
                    st.caption(f"{request.get('start_date')} to {request.get('end_date')}")
                
                with col2:
                    st.write(f"{request.get('working_days', 0)} days")
                
                with col3:
                    status = request.get('status', 'unknown')
                    if status == 'pending':
                        st.warning("🕐 Pending")
                    elif status == 'approved_final':
                        st.success("✅ Approved")
                    elif status == 'rejected':
                        st.error("❌ Rejected")
                    else:
                        st.info("📋 Processing")
        
        if len(recent_leave_requests) > 3:
            st.info(f"... and {len(recent_leave_requests) - 3} more requests")

with tab2:
    st.markdown("### ⏰ Overtime Balance")
    
    if overtime_balance:
        # Overtime metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Approved Hours", f"{overtime_approved_hours:.1f}h")
        
        with col2:
            st.metric("Balance Hours", f"{overtime_balance_hours:.1f}h")
        
        with col3:
            # Estimated pay (if overtime rate exists)
            overtime_rate = user_data.get('overtime_rate', 0)
            if overtime_rate > 0:
                estimated_pay = overtime_balance_hours * overtime_rate
                st.metric("Est. Pay", f"${estimated_pay:.2f}")
            else:
                st.metric("Overtime Rate", "Not Set")
    else:
        st.info("📊 No overtime data for this month.")
    
    # Recent Overtime Requests
    if recent_overtime_requests:
        st.markdown("### ⏰ Recent Overtime Requests")
        
        for request in recent_overtime_requests[:3]:  # Show only last 3
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    week_start = request.get('week_start', '')
                    week_end = request.get('week_end', '')
                    st.write(f"**Week Overtime**")
                    st.caption(f"{week_start} to {week_end}")
                
                with col2:
                    st.write(f"{request.get('total_hours', 0):.1f}h")
                
                with col3:
                    status = request.get('status', 'unknown')
                    if status == 'pending':
                        st.warning("🕐 Pending")
                    elif status == 'approved':
                        st.success("✅ Approved")
                    elif status == 'rejected':
                        st.error("❌ Rejected")
                    else:
                        st.info("📋 Processing")
        
        if len(recent_overtime_requests) > 3:
            st.info(f"... and {len(recent_overtime_requests) - 3} more requests")

# -- Enhanced Manager Dashboard (for access levels 1-3) --
if access_level in [1, 2, 3]:
    st.subheader("⚡ Pending Approvals")
    
    total_pending = pending_leave_approvals + pending_overtime_approvals
    
    if total_pending > 0:
        st.warning(f"You have **{total_pending}** requests waiting for your approval.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if pending_leave_approvals > 0:
                st.error(f"📋 **{pending_leave_approvals}** leave requests pending")
                if st.button("📋 Review Leave Requests", type="primary"):
                    st.switch_page("pages/leave_approval.py")
        
        with col2:
            if pending_overtime_approvals > 0:
                st.error(f"⏰ **{pending_overtime_approvals}** overtime requests pending")
                if st.button("⏰ Review Overtime Requests", type="primary"):
                    st.switch_page("pages/overtime_approval.py")
    else:
        st.success("✅ All caught up! No pending approvals.")

# -- Enhanced Important Notices --
st.subheader("📢 Important Notices")

# Show important leave and overtime related notices
notices = []

# Check if leave quota is running low
if leave_quota and leave_remaining <= 3:
    notices.append({
        "type": "warning",
        "message": f"⚠️ Low leave balance: Only {leave_remaining} days remaining this year"
    })

# Check for pending leave requests
if pending_leave_requests > 0:
    notices.append({
        "type": "info", 
        "message": f"📋 You have {pending_leave_requests} leave request(s) pending approval"
    })

# Check for pending overtime requests
if pending_overtime_requests > 0:
    notices.append({
        "type": "info", 
        "message": f"⏰ You have {pending_overtime_requests} overtime request(s) pending approval"
    })

# Check overtime balance
if overtime_balance and overtime_balance_hours > 20:
    notices.append({
        "type": "info",
        "message": f"💰 High overtime balance: {overtime_balance_hours:.1f} hours ready for payroll"
    })

# Overtime rate warning
if user_data.get('overtime_rate', 0) <= 0:
    notices.append({
        "type": "warning",
        "message": "⚠️ Overtime rate not set. Contact HR to set your overtime rate."
    })

# Manager notices
if access_level in [1, 2, 3] and (pending_leave_approvals > 0 or pending_overtime_approvals > 0):
    notices.append({
        "type": "warning",
        "message": f"👥 Manager Alert: {pending_leave_approvals + pending_overtime_approvals} requests need your approval"
    })

# Display notices
if notices:
    for notice in notices:
        if notice["type"] == "warning":
            st.warning(notice["message"])
        elif notice["type"] == "error":
            st.error(notice["message"])
        else:
            st.info(notice["message"])
else:
    st.success("✅ No important notices at this time")

# Year-end quota reset reminder (for admins)
if access_level == 1 and datetime.now().month == 12:
    st.info("🗓️ **Admin Reminder:** Don't forget to reset annual leave quotas and process overtime payments for the new year!")

# -- Enhanced Stats Summary --
st.subheader("📈 My Activity Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Leave Used (YTD)", 
        f"{leave_used} days",
        help="Leave days used this year"
    )

with col2:
    st.metric(
        "Leave Available", 
        f"{leave_remaining} days",
        help="Remaining leave balance"
    )

with col3:
    st.metric(
        "Overtime Balance", 
        f"{overtime_balance_hours:.1f}h",
        help="Current overtime hours pending payment"
    )

with col4:
    if access_level in [1, 2, 3]:
        st.metric(
            "Pending Approvals", 
            f"{total_pending}",
            help="Total requests awaiting your approval"
        )
    else:
        st.metric(
            "Pending Requests", 
            f"{pending_leave_requests + pending_overtime_requests}",
            help="Your requests awaiting approval"
        )

st.markdown("---")

# -- Enhanced Sidebar Information --
st.sidebar.markdown("### 📊 Quick Stats")

# Leave stats
if leave_quota:
    st.sidebar.metric("Leave Balance", f"{leave_remaining}/{leave_quota.get('annual_quota', 14)} days")

# Overtime stats
if overtime_balance:
    st.sidebar.metric("Overtime Balance", f"{overtime_balance_hours:.1f}h")
    if user_data.get('overtime_rate', 0) > 0:
        estimated_pay = overtime_balance_hours * user_data['overtime_rate']
        st.sidebar.metric("Est. Overtime Pay", f"${estimated_pay:.2f}")

# Manager stats
if access_level in [1, 2, 3]:
    st.sidebar.metric("Pending Approvals", f"{total_pending}")

# System info for admin
if access_level == 1:
    st.sidebar.markdown("### 🔧 System Status")
    st.sidebar.success("✅ All systems operational")
    
    # Show system-wide pending counts
    try:
        from utils.leave_system_db import get_all_leave_requests_admin, get_all_overtime_requests_admin
        
        all_leave = get_all_leave_requests_admin()
        all_overtime = get_all_overtime_requests_admin()
        
        system_pending_leave = len([r for r in all_leave if r.get("status") == "pending"])
        system_pending_overtime = len([r for r in all_overtime if r.get("status") == "pending"])
        
        st.sidebar.metric("System Leave Pending", system_pending_leave)
        st.sidebar.metric("System Overtime Pending", system_pending_overtime)
    except:
        st.sidebar.info("Loading system stats...")

st.sidebar.markdown("### 💡 Quick Tips")
st.sidebar.info("""
**Leave Tips:**
- Plan leave in advance
- Check team calendar
- Submit before deadlines

**Overtime Tips:**
- Only weekends/holidays
- Detailed descriptions
- Submit weekly
- Check balance regularly
""")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Footer
st.markdown("---")
st.caption("🏢 Enhanced Employee Management System | Leave & Overtime Management")
st.caption(f"Session: {user_data.get('name')} | Access Level: {access_level} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Show different footer messages based on access level
if access_level == 1:
    st.caption("👑 Administrator: Full system access with override capabilities")
elif access_level in [2, 3]:
    st.caption("👥 Manager: Team approval and oversight responsibilities") 
else:
    st.caption("👤 Employee: Submit requests and track your leave & overtime")
# pages/profile.py - Employee Profile Management
import streamlit as st
from datetime import datetime, date
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.database import enrich_user_data
from firebase_admin.firestore import SERVER_TIMESTAMP
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

# Import Firebase Storage utilities
try:
    from utils.firebase_storage import (
        FirebaseStorageManager, 
        display_file_attachment,
        get_storage_config
    )
    STORAGE_AVAILABLE = True
except ImportError:
    st.warning("⚠️ Firebase Storage not configured. Payslip downloads will be disabled.")
    STORAGE_AVAILABLE = False

def get_employee_payslips(employee_id):
    """Get all payslips for an employee"""
    try:
        payslips_query = db.db.collection("payslips").where("employee_id", "==", employee_id).order_by("pay_period", direction=db.firestore.Query.DESCENDING)
        
        payslips = []
        for doc in payslips_query.stream():
            payslip_data = doc.to_dict()
            payslip_data["id"] = doc.id
            payslips.append(payslip_data)
        
        return payslips
        
    except Exception as e:
        print(f"Error getting payslips: {e}")
        return []

def update_employee_profile(employee_id, updated_data):
    """Update employee profile data"""
    try:
        # Get current data first
        employee_ref = db.db.collection("users_db").document(employee_id)
        current_data = employee_ref.get().to_dict()
        
        if not current_data:
            return {"success": False, "message": "Employee not found"}
        
        # Prepare update data
        update_data = {
            "updated_at": SERVER_TIMESTAMP
        }
        
        # Only update allowed fields for employees
        allowed_fields = [
            "phone_number", "address", "bpjs_kesehatan_number", 
            "bpjs_ketenagakerjaan_number"
        ]
        
        for field in allowed_fields:
            if field in updated_data and updated_data[field] != current_data.get(field):
                update_data[field] = updated_data[field]
        
        # Apply updates
        if len(update_data) > 1:  # More than just updated_at
            employee_ref.update(update_data)
            return {"success": True, "message": "Profile updated successfully"}
        else:
            return {"success": False, "message": "No changes detected"}
        
    except Exception as e:
        print(f"Error updating profile: {e}")
        return {"success": False, "message": f"Error updating profile: {str(e)}"}

def format_currency(amount):
    """Format currency for display"""
    try:
        return f"Rp {amount:,.0f}" if amount else "Rp 0"
    except:
        return "Rp 0"

# Page header
st.title("👤 My Profile")
st.markdown(f"**Employee:** {user_data.get('name')} | **ID:** {employee_id}")

# Logout button
if st.button("🚪 Logout", key="logout_profile"):
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
    if access_level == 1:
        if st.button("⚙️ Admin Panel"):
            st.switch_page("pages/admin_control.py")

st.divider()

# Create tabs
tab1, tab2, tab3 = st.tabs(["📋 Profile Information", "✏️ Edit Profile", "💰 My Payslips"])

with tab1:
    st.subheader("📋 Profile Information")
    
    # Display profile information in a clean format
    col1, col2 = st.columns([0.3, 0.7])
    
    with col1:
        st.image("assets/profile-placeholder-square.jpg", use_container_width=True)
        
        # Quick stats
        st.markdown("### 📊 Quick Stats")
        
        # Calculate service duration
        join_date = user_data.get('start_joining_date')
        if hasattr(join_date, 'timestamp'):
            join_datetime = datetime.fromtimestamp(join_date.timestamp())
            service_days = (datetime.now() - join_datetime).days
            service_years = service_days // 365
            service_months = (service_days % 365) // 30
            
            st.metric("Service Duration", f"{service_years}y {service_months}m")
        
        st.metric("Access Level", f"Level {access_level}")
        st.metric("Status", user_data.get('employee_status', 'Active'))
    
    with col2:
        st.markdown("### 👤 Personal Information")
        
        info_data = [
            ("Full Name", user_data.get('name', 'Unknown')),
            ("Email", user_data.get('email', 'Unknown')),
            ("Phone Number", user_data.get('phone_number', 'Not provided')),
            ("Address", user_data.get('address', 'Not provided')),
            ("Date of Birth", user_data.get('date_of_birth', 'Unknown')),
            ("Place of Birth", user_data.get('place_of_birth', 'Unknown')),
        ]
        
        for label, value in info_data:
            st.markdown(f"**{label}:** {value}")
        
        st.markdown("---")
        
        st.markdown("### 🏢 Work Information")
        
        work_data = [
            ("Employee ID", employee_id),
            ("NIP", user_data.get('NIP', 'Not assigned')),
            ("Role", user_data.get('role_name', 'Unknown')),
            ("Division", user_data.get('division_name', 'Unknown')),
            ("Join Date", join_date.strftime('%d %B %Y') if hasattr(join_date, 'timestamp') else 'Unknown'),
            ("Employee Status", user_data.get('employee_status', 'Unknown')),
            ("Direct Supervisor", user_data.get('supervisor_name', 'No direct supervisor')),
        ]
        
        for label, value in work_data:
            st.markdown(f"**{label}:** {value}")
        
        st.markdown("---")
        
        st.markdown("### 🏥 Benefits Information")
        
        benefits_data = [
            ("BPJS Kesehatan", user_data.get('bpjs_kesehatan_number', 'Not provided')),
            ("BPJS Ketenagakerjaan", user_data.get('bpjs_ketenagakerjaan_number', 'Not provided')),
            ("Overtime Rate", f"${user_data.get('overtime_rate', 0):.2f}/hour" if user_data.get('overtime_rate') else 'Not set'),
        ]
        
        for label, value in benefits_data:
            st.markdown(f"**{label}:** {value}")

with tab2:
    st.subheader("✏️ Edit Profile")
    
    st.info("You can update the following information. Other details require admin approval.")
    
    with st.form("update_profile_form"):
        st.markdown("### 📞 Contact Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_phone = st.text_input(
                "Phone Number",
                value=user_data.get('phone_number', ''),
                placeholder="+62 812 3456 7890",
                help="Update your phone number"
            )
        
        with col2:
            new_address = st.text_area(
                "Address",
                value=user_data.get('address', ''),
                placeholder="Your complete address",
                help="Update your current address"
            )
        
        st.markdown("### 🏥 BPJS Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_bpjs_kesehatan = st.text_input(
                "BPJS Kesehatan Number",
                value=user_data.get('bpjs_kesehatan_number', ''),
                placeholder="1234567890123",
                help="13-digit BPJS Kesehatan number"
            )
        
        with col2:
            new_bpjs_tk = st.text_input(
                "BPJS Ketenagakerjaan Number",
                value=user_data.get('bpjs_ketenagakerjaan_number', ''),
                placeholder="1234567890",
                help="BPJS Ketenagakerjaan number"
            )
        
        submitted = st.form_submit_button("💾 Update Profile", type="primary")
        
        if submitted:
            # Prepare update data
            updated_data = {
                "phone_number": new_phone.strip() if new_phone.strip() else None,
                "address": new_address.strip() if new_address.strip() else None,
                "bpjs_kesehatan_number": new_bpjs_kesehatan.strip() if new_bpjs_kesehatan.strip() else None,
                "bpjs_ketenagakerjaan_number": new_bpjs_tk.strip() if new_bpjs_tk.strip() else None,
            }
            
            # Update profile
            result = update_employee_profile(employee_id, updated_data)
            
            if result["success"]:
                st.success("✅ Profile updated successfully!")
                st.balloons()
                
                # Refresh user data
                user_data_new = db.fetch_user_by_username(st.session_state.get("username"))
                if user_data_new:
                    user_data_new = enrich_user_data(user_data_new)
                    st.session_state.user_data = user_data_new
                
                st.info("Refreshing page...")
                st.rerun()
            else:
                st.error(f"❌ {result['message']}")
    
    st.markdown("---")
    
    st.markdown("### 📝 Request Changes")
    st.info("""
    **Need to update other information?**
    
    The following information requires admin approval:
    - Name, Email, Date of Birth
    - Role, Division, Employee Status
    - NIP, Join Date
    - Bank account information
    
    Please contact your HR department or system administrator to request these changes.
    """)
    
    if st.button("📧 Contact HR", type="secondary"):
        st.info("Please send an email to hr@company.com with your change request.")

with tab3:
    st.subheader("💰 My Payslips")
    
    # Get payslips
    payslips = get_employee_payslips(employee_id)
    
    if not payslips:
        st.info("📄 No payslips available yet.")
        st.write("Payslips will appear here once they are processed by HR.")
    else:
        st.success(f"📊 Found {len(payslips)} payslip(s)")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Get unique years
            years = list(set([p.get("pay_period", "")[:4] for p in payslips if p.get("pay_period")]))
            years.sort(reverse=True)
            
            year_filter = st.selectbox(
                "Filter by Year",
                options=["All"] + years,
                index=0
            )
        
        with col2:
            # Get unique months
            months = []
            for p in payslips:
                if p.get("pay_period"):
                    try:
                        month_name = datetime.strptime(p["pay_period"], "%Y-%m").strftime("%B")
                        if month_name not in months:
                            months.append(month_name)
                    except:
                        pass
            
            month_filter = st.selectbox(
                "Filter by Month",
                options=["All"] + months,
                index=0
            )
        
        with col3:
            sort_order = st.selectbox(
                "Sort by",
                options=["Newest First", "Oldest First"],
                index=0
            )
        
        # Apply filters
        filtered_payslips = payslips
        
        if year_filter != "All":
            filtered_payslips = [p for p in filtered_payslips if p.get("pay_period", "").startswith(year_filter)]
        
        if month_filter != "All":
            filtered_payslips = [p for p in filtered_payslips if datetime.strptime(p.get("pay_period", "2000-01"), "%Y-%m").strftime("%B") == month_filter]
        
        # Sort payslips
        if sort_order == "Newest First":
            filtered_payslips.sort(key=lambda x: x.get("pay_period", ""), reverse=True)
        else:
            filtered_payslips.sort(key=lambda x: x.get("pay_period", ""))
        
        if not filtered_payslips:
            st.info("No payslips match the selected filters.")
        else:
            # Display payslips
            for payslip in filtered_payslips:
                with st.container():
                    # Payslip header
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    
                    with col1:
                        pay_period = payslip.get("pay_period", "Unknown")
                        try:
                            period_display = datetime.strptime(pay_period, "%Y-%m").strftime("%B %Y")
                        except:
                            period_display = pay_period
                        
                        st.markdown(f"### 💰 {period_display}")
                    
                    with col2:
                        gross_salary = payslip.get("gross_salary", 0)
                        st.metric("Gross Salary", format_currency(gross_salary))
                    
                    with col3:
                        net_salary = payslip.get("net_salary", 0)
                        st.metric("Net Salary", format_currency(net_salary))
                    
                    with col4:
                        status = payslip.get("status", "unknown")
                        if status == "paid":
                            st.success("✅ Paid")
                        elif status == "pending":
                            st.warning("🕐 Pending")
                        else:
                            st.info("📋 Processing")
                    
                    # Payslip details in expander
                    with st.expander(f"📋 Details - {period_display}"):
                        col_left, col_right = st.columns(2)
                        
                        with col_left:
                            st.markdown("**💰 Earnings**")
                            
                            earnings_data = [
                                ("Basic Salary", payslip.get("basic_salary", 0)),
                                ("Overtime Pay", payslip.get("overtime_pay", 0)),
                                ("Allowances", payslip.get("allowances", 0)),
                                ("Bonus", payslip.get("bonus", 0)),
                                ("Other Earnings", payslip.get("other_earnings", 0)),
                            ]
                            
                            total_earnings = 0
                            for label, amount in earnings_data:
                                if amount > 0:
                                    st.write(f"• **{label}:** {format_currency(amount)}")
                                    total_earnings += amount
                            
                            st.markdown(f"**Total Earnings:** {format_currency(total_earnings)}")
                        
                        with col_right:
                            st.markdown("**📉 Deductions**")
                            
                            deductions_data = [
                                ("Income Tax", payslip.get("income_tax", 0)),
                                ("BPJS Kesehatan", payslip.get("bpjs_kesehatan", 0)),
                                ("BPJS Ketenagakerjaan", payslip.get("bpjs_ketenagakerjaan", 0)),
                                ("Loan Deduction", payslip.get("loan_deduction", 0)),
                                ("Other Deductions", payslip.get("other_deductions", 0)),
                            ]
                            
                            total_deductions = 0
                            for label, amount in deductions_data:
                                if amount > 0:
                                    st.write(f"• **{label}:** {format_currency(amount)}")
                                    total_deductions += amount
                            
                            st.markdown(f"**Total Deductions:** {format_currency(total_deductions)}")
                        
                        # Summary
                        st.markdown("---")
                        col_summary1, col_summary2, col_summary3 = st.columns(3)
                        
                        with col_summary1:
                            st.metric("Gross Salary", format_currency(gross_salary))
                        
                        with col_summary2:
                            st.metric("Total Deductions", format_currency(total_deductions))
                        
                        with col_summary3:
                            st.metric("Net Salary", format_currency(net_salary))
                        
                        # Additional info
                        if payslip.get("notes"):
                            st.markdown("**📝 Notes:**")
                            st.write(payslip["notes"])
                        
                        # Payment info
                        if payslip.get("paid_date"):
                            paid_date = payslip["paid_date"]
                            if hasattr(paid_date, 'timestamp'):
                                paid_str = datetime.fromtimestamp(paid_date.timestamp()).strftime('%d %B %Y')
                                st.info(f"💳 Paid on: {paid_str}")
                        
                        # Download button with Firebase Storage support
                        col_download1, col_download2 = st.columns(2)
                        
                        with col_download1:
                            # Check if payslip PDF exists in Firebase Storage
                            payslip_pdf_path = payslip.get("pdf_file_path")
                            
                            if payslip_pdf_path and STORAGE_AVAILABLE:
                                # Display Firebase Storage download
                                try:
                                    storage_manager = FirebaseStorageManager()
                                    if storage_manager.bucket:
                                        download_url = storage_manager.get_download_url(payslip_pdf_path, expiration_hours=24)
                                        if download_url:
                                            st.link_button("📄 Download PDF", download_url, use_container_width=True)
                                        else:
                                            st.error("PDF temporarily unavailable")
                                    else:
                                        st.error("Storage not available")
                                except Exception as e:
                                    st.error(f"Download error: {e}")
                            else:
                                if st.button(f"📄 Generate PDF", key=f"generate_pdf_{payslip.get('id')}"):
                                    st.info("PDF generation will be implemented soon.")
                        
                        with col_download2:
                            if st.button(f"📧 Email Payslip", key=f"email_{payslip.get('id')}"):
                                st.info("Email feature will be implemented soon.")
                    
                    st.divider()
        
        # Summary statistics
        if filtered_payslips:
            st.markdown("### 📊 Summary")
            
            total_gross = sum([p.get("gross_salary", 0) for p in filtered_payslips])
            total_net = sum([p.get("net_salary", 0) for p in filtered_payslips])
            total_deductions = total_gross - total_net
            avg_gross = total_gross / len(filtered_payslips) if filtered_payslips else 0
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Payslips", len(filtered_payslips))
            
            with col2:
                st.metric("Total Gross", format_currency(total_gross))
            
            with col3:
                st.metric("Total Net", format_currency(total_net))
            
            with col4:
                st.metric("Average Gross", format_currency(avg_gross))

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if st.button("🔑 Change Password", use_container_width=True):
        st.switch_page("pages/password_management.py")

with col3:
    if access_level == 1:
        if st.button("⚙️ Admin Panel", use_container_width=True):
            st.switch_page("pages/admin_control.py")

# Sidebar with helpful information
st.sidebar.markdown("### 👤 Profile Help")

st.sidebar.markdown("""
**What you can do:**
- ✅ View your complete profile
- ✅ Update contact information
- ✅ Update BPJS numbers
- ✅ View all your payslips
- ✅ Download payslip documents

**Need to change other info?**
- Contact HR for role/division changes
- Contact admin for email changes
- Use password management for security
""")

st.sidebar.markdown("### 📊 Profile Completion")

# Calculate profile completion
completion_fields = [
    user_data.get('phone_number'),
    user_data.get('address'),
    user_data.get('bpjs_kesehatan_number'),
    user_data.get('bpjs_ketenagakerjaan_number'),
    user_data.get('date_of_birth'),
]

completed = sum([1 for field in completion_fields if field])
completion_rate = (completed / len(completion_fields)) * 100

st.sidebar.progress(completion_rate / 100)
st.sidebar.caption(f"Profile {completion_rate:.0f}% complete")

if completion_rate < 100:
    st.sidebar.warning("Complete your profile for better experience!")

st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
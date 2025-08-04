# Enhanced admin_control.py with direct supervisor selection
import streamlit as st
from datetime import datetime, timedelta
from utils.auth import get_authenticator, check_authentication
from utils.logout_handler import check_logout_status, is_authenticated
from utils.database import add_user_to_firestore, get_all_roles, get_all_divisions, db, get_or_create_role, get_or_create_division
from utils.leave_system_db import reset_annual_leave_quotas, LEAVE_TYPES
import pandas as pd
from firebase_admin.firestore import SERVER_TIMESTAMP

# Check authentication
if check_logout_status():
    st.switch_page("pages/login.py")

authenticator = check_authentication()

if not is_authenticated():
    st.warning("You must log in first.")
    if st.button("Go to Login Page"):
        st.switch_page("pages/login.py")
    st.stop()

# Get user data and check admin access
if "user_data" not in st.session_state:
    st.error("Session expired. Please log in again.")
    st.switch_page("pages/login.py")

user_data = st.session_state["user_data"]
access_level = user_data.get("access_level")

# Check if user is admin
if access_level != 1:
    st.error("🚫 Access Denied: Administrator privileges required.")
    st.info("This page is only accessible to system administrators.")
    if st.button("← Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

def get_potential_supervisors():
    """Get all users who can be supervisors (access levels 1-3)"""
    try:
        users_query = db.collection("users_db").where("access_level", "in", [1, 2, 3]).where("is_active", "==", True).stream()
        supervisors = []
        
        for doc in users_query:
            user_info = doc.to_dict()
            user_info["employee_id"] = doc.id
            supervisors.append(user_info)
        
        return supervisors
    except Exception as e:
        st.error(f"Error loading supervisors: {e}")
        return []

def add_user_with_supervisor(user_data_new):
    """Enhanced user creation with direct supervisor assignment"""
    try:
        # Create user using existing function
        user_id, employee_id = add_user_to_firestore(user_data_new)
        
        if user_id and employee_id:
            # Update with direct supervisor if provided
            if user_data_new.get("direct_supervisor_id"):
                employee_ref = db.collection("users_db").document(employee_id)
                employee_ref.update({
                    "direct_supervisor_id": user_data_new["direct_supervisor_id"],
                    "updated_at": SERVER_TIMESTAMP
                })
            
            return user_id, employee_id
        else:
            return None, None
            
    except Exception as e:
        st.error(f"Error creating user with supervisor: {e}")
        return None, None

st.title("⚙️ Admin Control Panel")
st.info(f"👤 Logged in as: **{user_data.get('name')}** (Administrator)")

# Create tabs for different admin functions
tab1, tab2, tab3, tab4 = st.tabs(["User Management", "Leave System", "Reports", "System Settings"])

with tab1:
    st.header("👥 User Management")
    
    # Add new user section
    with st.expander("➕ Add New User", expanded=False):
        st.subheader("Create New Employee Account")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Nama Lengkap*", placeholder="John Doe")
                email = st.text_input("Email*", placeholder="john.doe@company.com")
                username = st.text_input("Username*", placeholder="john.doe")
                password = st.text_input("Password*", type="password", placeholder="Temporary password")
                phone_number = st.text_input("Nomor Telepon", placeholder="+1234567890")
                address = st.text_area("Alamat", placeholder="Employee address")
                access_level = st.selectbox(
                    "Access Level*",
                    options=[1, 2, 3, 4],
                    format_func=lambda x: {1: "Admin / BOD / Head HR", 2: "HR Staff / Head of Subsidiary ", 3: "Division Head", 4: "Staff"}[x],
                    index=3  # Default to Staff
                )
                
                is_active = st.checkbox("Pegawai Aktif", value=True)
                
            with col2:
                date_of_birth = st.date_input("Tanggal Lahir", min_value=datetime(1900, 1, 1), max_value=datetime.now(), value=datetime.now() - timedelta(days=365 * 30))
                place_of_birth = st.text_input("Tempat Lahir", placeholder="Kota Kelahiran")
                join_date = st.date_input("Tanggal Bergabung", value=datetime.now().date())
                bpjs_number = st.text_input("Nomor BPJS Kesehatan", placeholder="1234567890")
                bpjs_tk_number = st.text_input("Nomor BPJS Ketenagakerjaan", placeholder="1234567890")

                roles = get_all_roles()
                role_names = [role_data["role_name"] for role_data in roles.values()]

                selected_role_name = st.selectbox(
                    "Role*",
                    options=role_names,
                    placeholder="Select or type a new role",
                    key="role_input",
                    accept_new_options=True
                )

                divisions = get_all_divisions()

                division_names = [div_data["division_name"] for div_data in divisions.values()]

                selected_division = st.selectbox(
                    "Division*",
                    options=division_names,
                    placeholder="Select or type a new division",
                    key="division_input",
                    accept_new_options=True
                )
                
                nip = st.text_input("NIP (Employee ID)", placeholder="1234567890")

                employee_status = st.selectbox(
                    "Employee Status*",
                    options=["Full Time", "Part Time", "Contract", "Intern", "Probation", "Freelance", "Inactive"],
                    index=0  # Default to Full Time
                )
                
                # NEW: Direct Supervisor Selection
                st.markdown("---")
                st.markdown("**👥 Reporting Structure**")
                
                # Get potential supervisors
                potential_supervisors = get_potential_supervisors()
                
                if potential_supervisors:
                    supervisor_options = ["No Direct Supervisor"] + [
                        f"{sup['name']} ({sup.get('role_name', 'Unknown Role')}) - {sup.get('division_name', 'Unknown Division')}"
                        for sup in potential_supervisors
                    ]
                    
                    selected_supervisor_index = st.selectbox(
                        "Direct Supervisor (Optional)",
                        options=range(len(supervisor_options)),
                        format_func=lambda x: supervisor_options[x],
                        help="Select the direct supervisor for this employee. Leave as 'No Direct Supervisor' if they report to division head."
                    )
                    
                    # Get the actual supervisor ID
                    direct_supervisor_id = None
                    if selected_supervisor_index > 0:  # Not "No Direct Supervisor"
                        direct_supervisor_id = potential_supervisors[selected_supervisor_index - 1]["employee_id"]
                        
                        # Show supervisor details
                        selected_sup = potential_supervisors[selected_supervisor_index - 1]
                        st.info(f"📧 Supervisor Email: {selected_sup.get('email', 'N/A')}")
                        st.info(f"🏢 Supervisor Division: {selected_sup.get('division_name', 'Unknown')}")
                else:
                    st.warning("⚠️ No potential supervisors found. Only users with access levels 1-3 can be supervisors.")
                    direct_supervisor_id = None
            
            submitted = st.form_submit_button("Create User Account", type="primary")
            
            if submitted:
                # Validate required fields
                if not all([name, email, username, password]):
                    st.error("Please fill in all required fields marked with *")
                else:
                    # Prepare user data
                    user_data_new = {
                        "name": name,
                        "email": email,
                        "username": username,
                        "password": password,
                        "phone_number": phone_number,
                        "address": address,
                        "date_of_birth": date_of_birth,
                        "role_name": selected_role_name,
                        "division_name": selected_division,
                        "join_date": join_date,
                        "access_level": access_level,
                        "bpjs_kesehatan_number": bpjs_number,
                        "bpjs_ketenagakerjaan_number": bpjs_tk_number,
                        "is_active": is_active,
                        "NIP": nip,
                        "employee_status": employee_status,
                        "place_of_birth": place_of_birth,
                        "start_joining_date": join_date,
                        "direct_supervisor_id": direct_supervisor_id  # NEW: Add supervisor ID
                    }
                    
                    # Add user to database with supervisor
                    user_id, employee_id = add_user_with_supervisor(user_data_new)
                    # if user_id and employee_id:
                    #     st.success(f"✅ User created successfully!")
                    #     st.info(f"User ID: {user_id}, Employee ID: {employee_id}")
                    #     existing_role_names = set(role_names)
                    #     if selected_role_name not in existing_role_names:
                    #         get_or_create_role(selected_role_name)

                    #     if selected_division not in division_names:
                    #         get_or_create_division(selected_division)

                    #     st.balloons()
                    # else:
                    #     st.error("❌ Failed to create user. Please check the logs for details.")

                    if user_id and employee_id:
                        st.success(f"✅ User created successfully!")
                        st.info(f"User ID: {user_id}, Employee ID: {employee_id}")
                        
                        if direct_supervisor_id:
                            supervisor_name = potential_supervisors[selected_supervisor_index - 1]["name"]
                            st.success(f"👥 Direct supervisor assigned: {supervisor_name}")
                        
                        # Create roles/divisions if new
                        existing_role_names = set(role_names)
                        if selected_role_name not in existing_role_names:
                            get_or_create_role(selected_role_name)

                        if selected_division not in division_names:
                            get_or_create_division(selected_division)

                        st.balloons()
                    else:
                        st.error("❌ Failed to create user. Please check the logs for details.")
    
    # Enhanced User list with supervisor information
    st.subheader("📋 Existing Users")
    
    try:
        # Get all users with enriched data
        users_query = db.collection("users_db").stream()
        users_list = []
        
        # Create supervisor lookup
        supervisor_lookup = {}
        for doc in users_query:
            user_info = doc.to_dict()
            user_info["employee_id"] = doc.id
            users_list.append(user_info)
            supervisor_lookup[doc.id] = user_info.get("name", "Unknown")
        
        if users_list:
            # Enhance user data with supervisor names
            for user in users_list:
                supervisor_id = user.get("direct_supervisor_id")
                if supervisor_id and supervisor_id in supervisor_lookup:
                    user["supervisor_name"] = supervisor_lookup[supervisor_id]
                else:
                    user["supervisor_name"] = "No Direct Supervisor"
            
            # Convert to DataFrame for better display
            df = pd.DataFrame(users_list)
            
            # Select columns to display including supervisor
            display_columns = ["name", "email", "role_name", "division_name", "supervisor_name", "access_level", "is_active", "start_joining_date"]
            available_columns = [col for col in display_columns if col in df.columns]
            
            st.dataframe(
                df[available_columns],
                use_container_width=True,
                hide_index=True
            )
            
            st.info(f"Total users: {len(users_list)}")
            
            # Show supervisor statistics
            supervisor_stats = df["supervisor_name"].value_counts()
            if len(supervisor_stats) > 1:
                st.markdown("### 👥 Reporting Structure Overview")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Direct Reports Count:**")
                    for supervisor, count in supervisor_stats.head(10).items():
                        if supervisor != "No Direct Supervisor":
                            st.write(f"• {supervisor}: {count} direct reports")
                
                with col2:
                    no_supervisor_count = supervisor_stats.get("No Direct Supervisor", 0)
                    st.metric("Employees without Direct Supervisor", no_supervisor_count)
        else:
            st.info("No users found in the database.")
    
    except Exception as e:
        st.error(f"Error loading users: {str(e)}")

with tab2:
    st.header("🏖️ Leave System Management")
    
    # Annual quota reset
    st.subheader("📅 Annual Leave Quota Management")
    
    current_year = datetime.now().year
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write(f"**Current Year:** {current_year}")
        st.write("Reset all employees' annual leave quotas for the new year.")
        st.warning("⚠️ This action will create new quota records for all active employees.")
    
    with col2:
        if st.button("🔄 Reset All Quotas", type="primary"):
            with st.spinner("Resetting leave quotas..."):
                result = reset_annual_leave_quotas()
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                else:
                    st.error(f"❌ {result['message']}")
    
    st.divider()
    
    # Leave type configuration
    st.subheader("⚙️ Leave Type Configuration")
    
    for leave_type, config in LEAVE_TYPES.items():
        with st.expander(f"{config['name']} Configuration"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Type:** {leave_type}")
                st.write(f"**Name:** {config['name']}")
                st.write(f"**Has Quota:** {'Yes' if config.get('has_quota') else 'No'}")
                st.write(f"**Requires Approval:** {'Yes' if config.get('requires_approval') else 'No'}")
            
            with col2:
                if config.get('default_quota'):
                    st.write(f"**Default Quota:** {config['default_quota']} days")
                if config.get('new_employee_quota'):
                    st.write(f"**New Employee Quota:** {config['new_employee_quota']} days")
                if config.get('max_days'):
                    st.write(f"**Maximum Days:** {config['max_days']} days")
                if config.get('max_days_per_month'):
                    st.write(f"**Max per Month:** {config['max_days_per_month']} days")
            
            st.info("Leave type configuration is currently read-only. Contact system administrator to modify.")

with tab3:
    st.header("📊 System Reports")
    
    # Leave statistics
    st.subheader("📈 Leave Request Statistics")
    
    try:
        # Get current year statistics
        current_year = datetime.now().year
        year_start = datetime(current_year, 1, 1)
        
        # Total requests this year
        requests_query = db.collection("leave_requests").where("created_at", ">=", year_start).stream()
        requests_list = [doc.to_dict() for doc in requests_query]
        
        if requests_list:
            total_requests = len(requests_list)
            approved_requests = len([r for r in requests_list if r.get("status") == "approved_final"])
            pending_requests = len([r for r in requests_list if r.get("status") == "pending"])
            rejected_requests = len([r for r in requests_list if r.get("status") == "rejected"])
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Requests", total_requests)
            
            with col2:
                st.metric("Approved", approved_requests, f"{(approved_requests/total_requests*100):.1f}%")
            
            with col3:
                st.metric("Pending", pending_requests, f"{(pending_requests/total_requests*100):.1f}%")
            
            with col4:
                st.metric("Rejected", rejected_requests, f"{(rejected_requests/total_requests*100):.1f}%")
            
            # Leave type breakdown
            st.subheader("📋 Leave Type Breakdown")
            
            leave_type_counts = {}
            for request in requests_list:
                leave_type = request.get("leave_type", "unknown")
                leave_type_counts[leave_type] = leave_type_counts.get(leave_type, 0) + 1
            
            if leave_type_counts:
                df_leave_types = pd.DataFrame(
                    list(leave_type_counts.items()),
                    columns=["Leave Type", "Count"]
                )
                df_leave_types["Leave Type"] = df_leave_types["Leave Type"].map(
                    lambda x: LEAVE_TYPES.get(x, {}).get("name", x.title())
                )
                
                st.bar_chart(df_leave_types.set_index("Leave Type"))
        
        else:
            st.info(f"No leave requests found for {current_year}")
    
    except Exception as e:
        st.error(f"Error loading statistics: {str(e)}")
    
    st.divider()
    
    # User statistics with supervisor information
    st.subheader("👥 User Statistics")
    
    try:
        # Get user counts by access level and supervisor status
        users_query = db.collection("users_db").stream()
        users_by_level = {1: 0, 2: 0, 3: 0, 4: 0}
        active_users = 0
        users_with_supervisors = 0
        
        for doc in users_query:
            user_data_stat = doc.to_dict()
            access_level = user_data_stat.get("access_level", 4)
            users_by_level[access_level] = users_by_level.get(access_level, 0) + 1
            
            if user_data_stat.get("is_active", True):
                active_users += 1
            
            if user_data_stat.get("direct_supervisor_id"):
                users_with_supervisors += 1
        
        total_users = sum(users_by_level.values())
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Users", total_users)
        
        with col2:
            st.metric("Active Users", active_users)
        
        with col3:
            st.metric("With Direct Supervisors", users_with_supervisors)
        
        with col4:
            st.metric("Without Direct Supervisors", total_users - users_with_supervisors)
        
        # Access level breakdown
        access_level_names = {1: "Admin", 2: "HR Staff", 3: "Division Head", 4: "Staff"}
        
        col1, col2, col3, col4 = st.columns(4)
        
        for i, (level, count) in enumerate(users_by_level.items()):
            with [col1, col2, col3, col4][i]:
                st.metric(access_level_names[level], count)
    
    except Exception as e:
        st.error(f"Error loading user statistics: {str(e)}")

with tab4:
    st.header("🔧 System Settings")
    
    st.subheader("🗄️ Database Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Collections Status**")
        try:
            collections = ["users_auth", "users_db", "leave_requests", "leave_quotas", "roles", "divisions"]
            
            for collection_name in collections:
                try:
                    doc_count = len(list(db.collection(collection_name).limit(1).stream()))
                    if doc_count > 0:
                        st.success(f"✅ {collection_name}")
                    else:
                        st.warning(f"⚠️ {collection_name} (empty)")
                except:
                    st.error(f"❌ {collection_name} (error)")
        
        except Exception as e:
            st.error(f"Error checking collections: {str(e)}")
    
    with col2:
        st.write("**System Information**")
        st.info(f"**Current Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.info(f"**Current Year:** {datetime.now().year}")
        st.info(f"**Environment:** Production")  # You can make this dynamic
    
    st.divider()
    
    st.subheader("⚠️ Maintenance Actions")
    
    st.warning("These actions are for system maintenance and should be used with caution.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Cache", help="Clear system cache and reload data"):
            # Clear Streamlit cache
            st.cache_resource.clear()
            st.success("Cache cleared successfully!")
    
    with col2:
        if st.button("📊 Generate Reports", help="Generate system reports"):
            st.info("Advanced reporting features coming soon!")

# Navigation
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("← Back to Dashboard"):
        st.switch_page("pages/dashboard.py")

with col2:
    if st.button("View Leave Approvals →"):
        st.switch_page("pages/leave_approval.py")
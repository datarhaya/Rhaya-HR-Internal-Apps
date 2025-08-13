# pages/admin_user_management.py - Simplified Admin User Management with Basic Payslip Data Only
import streamlit as st
from datetime import datetime, date, timedelta
import utils.database as db
from utils.auth import check_authentication
from utils.logout_handler import is_authenticated, handle_logout, clear_cookies_js
from utils.database import enrich_user_data, get_all_roles, get_all_divisions
from firebase_admin.firestore import SERVER_TIMESTAMP
import pandas as pd
from pathlib import Path

# Import Firebase Storage utilities
try:
    from utils.firebase_storage import (
        FirebaseStorageManager, 
        get_storage_config
    )
    STORAGE_AVAILABLE = True
except ImportError:
    st.warning("⚠️ Firebase Storage not configured. PDF payslips will not be stored.")
    STORAGE_AVAILABLE = False

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

# Check if user is admin
if access_level != 1:
    st.error("🚫 Access Denied: Administrator privileges required.")
    st.info("This page is only accessible to system administrators.")
    if st.button("← Back to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

# Initialize session state
if "selected_employee_id" not in st.session_state:
    st.session_state.selected_employee_id = None

if "show_delete_confirmation" not in st.session_state:
    st.session_state.show_delete_confirmation = False

def get_all_employees():
    """Get all employees with enriched data"""
    try:
        employees = []
        query = db.db.collection("users_db").stream()
        
        for doc in query:
            employee_data = doc.to_dict()
            employee_data["employee_id"] = doc.id
            employee_data = enrich_user_data(employee_data)
            employees.append(employee_data)
        
        return employees
        
    except Exception as e:
        print(f"Error getting employees: {e}")
        return []

def update_employee_data(employee_id, updated_data):
    """Update employee data (admin function)"""
    try:
        employee_ref = db.db.collection("users_db").document(employee_id)
        current_data = employee_ref.get().to_dict()
        
        if not current_data:
            return {"success": False, "message": "Employee not found"}
        
        # Prepare update data
        update_data = {
            "updated_at": SERVER_TIMESTAMP
        }
        
        # List of fields that can be updated by admin
        updatable_fields = [
            "name", "email", "phone_number", "address", "date_of_birth",
            "place_of_birth", "role_name", "division_name", "access_level",
            "employee_status", "NIP", "bpjs_kesehatan_number", 
            "bpjs_ketenagakerjaan_number", "overtime_rate", "is_active",
            "start_joining_date", "direct_supervisor_id"
        ]
        
        # Track changes for role/division updates
        for field in updatable_fields:
            if field in updated_data:
                new_value = updated_data[field]
                
                # Handle role name change
                if field == "role_name" and new_value != current_data.get("role_name"):
                    from utils.database import get_or_create_role
                    role_id = get_or_create_role(new_value)
                    update_data["role_id"] = role_id
                    update_data["role_name"] = new_value
                
                # Handle division name change
                elif field == "division_name" and new_value != current_data.get("division_name"):
                    from utils.database import get_or_create_division
                    division_id = get_or_create_division(new_value)
                    update_data["division_id"] = division_id
                    update_data["division_name"] = new_value
                
                # Handle other fields
                elif new_value != current_data.get(field):
                    update_data[field] = new_value
        
        # Apply updates if there are changes
        if len(update_data) > 1:  # More than just updated_at
            employee_ref.update(update_data)
            
            # Update auth collection if name or email changed
            if "name" in update_data or "email" in update_data:
                try:
                    # Find auth record
                    auth_query = db.db.collection("users_auth").where("employee_id", "==", employee_id).limit(1)
                    for auth_doc in auth_query.stream():
                        auth_update = {"updated_at": SERVER_TIMESTAMP}
                        if "name" in update_data:
                            auth_update["name"] = update_data["name"]
                        auth_doc.reference.update(auth_update)
                except Exception as e:
                    print(f"Warning: Could not update auth record: {e}")
            
            return {"success": True, "message": "Employee data updated successfully"}
        else:
            return {"success": False, "message": "No changes detected"}
        
    except Exception as e:
        print(f"Error updating employee data: {e}")
        return {"success": False, "message": f"Error updating employee: {str(e)}"}

def delete_employee(employee_id):
    """Delete employee (admin function)"""
    try:
        # Get employee data first
        employee_ref = db.db.collection("users_db").document(employee_id)
        employee_data = employee_ref.get().to_dict()
        
        if not employee_data:
            return {"success": False, "message": "Employee not found"}
        
        employee_name = employee_data.get("name", "Unknown")
        
        # Delete from users_db
        employee_ref.delete()
        
        # Delete from users_auth
        auth_query = db.db.collection("users_auth").where("employee_id", "==", employee_id)
        for auth_doc in auth_query.stream():
            auth_doc.reference.delete()
        
        return {"success": True, "message": f"Employee {employee_name} deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting employee: {e}")
        return {"success": False, "message": f"Error deleting employee: {str(e)}"}

def upload_payslip_pdf_to_storage(uploaded_file, payslip_id, employee_id, pay_period):
    """Upload manually prepared PDF to Firebase Storage"""
    try:
        if not STORAGE_AVAILABLE:
            return {"success": False, "message": "Firebase Storage not available"}
        
        storage_manager = FirebaseStorageManager()
        
        if not storage_manager.bucket:
            return {"success": False, "message": "Storage bucket not initialized"}
        
        # Validate file
        if not uploaded_file.name.lower().endswith('.pdf'):
            return {"success": False, "message": "Only PDF files are allowed"}
        
        # Generate storage path
        storage_path = f"payslips/{employee_id}/{pay_period}/payslip_{payslip_id}.pdf"
        
        # Upload to Firebase Storage
        blob = storage_manager.bucket.blob(storage_path)
        
        # Set metadata
        blob.metadata = {
            "payslip_id": payslip_id,
            "employee_id": employee_id,
            "pay_period": pay_period,
            "uploaded_at": datetime.now().isoformat(),
            "file_type": "payslip_pdf",
            "original_filename": uploaded_file.name
        }
        
        # Upload file
        blob.upload_from_string(
            uploaded_file.getvalue(),
            content_type='application/pdf'
        )
        
        return {
            "success": True,
            "message": "PDF uploaded to storage successfully",
            "storage_path": storage_path
        }
        
    except Exception as e:
        print(f"Error uploading PDF to storage: {e}")
        return {"success": False, "message": f"Upload failed: {str(e)}"}

def create_payslip_with_pdf(payslip_data, pdf_file):
    """Create a new payslip with basic data and PDF upload"""
    try:
        # Validate required fields
        required_fields = ["employee_id", "pay_period"]
        for field in required_fields:
            if field not in payslip_data or not payslip_data[field]:
                return {"success": False, "message": f"Missing required field: {field}"}
        
        # Check if PDF file is provided
        if not pdf_file:
            return {"success": False, "message": "PDF file is required"}
        
        # Check if payslip already exists for this period
        existing_query = db.db.collection("payslips").where("employee_id", "==", payslip_data["employee_id"]).where("pay_period", "==", payslip_data["pay_period"]).limit(1)
        
        if len(list(existing_query.stream())) > 0:
            return {"success": False, "message": "Payslip already exists for this period"}
        
        # Create payslip document
        payslip_ref = db.db.collection("payslips").document()
        
        # Upload PDF first
        if STORAGE_AVAILABLE:
            upload_result = upload_payslip_pdf_to_storage(
                pdf_file, 
                payslip_ref.id, 
                payslip_data["employee_id"], 
                payslip_data["pay_period"]
            )
            
            if not upload_result["success"]:
                return {"success": False, "message": f"PDF upload failed: {upload_result['message']}"}
        else:
            return {"success": False, "message": "Firebase Storage not available"}
        
        # Create payslip document with only basic data
        payslip_document = {
            "payslip_id": payslip_ref.id,
            "employee_id": payslip_data["employee_id"],
            "pay_period": payslip_data["pay_period"],
            "pdf_file_path": upload_result["storage_path"],
            "pdf_filename": pdf_file.name,
            "status": payslip_data.get("status", "pending"),
            "notes": payslip_data.get("notes", ""),
            "created_by": payslip_data.get("created_by"),
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP
        }
        
        # Save payslip to database
        payslip_ref.set(payslip_document)
        
        return {
            "success": True, 
            "message": "Payslip created successfully with PDF uploaded to cloud storage", 
            "payslip_id": payslip_ref.id
        }
        
    except Exception as e:
        print(f"Error creating payslip: {e}")
        return {"success": False, "message": f"Error creating payslip: {str(e)}"}

def get_employee_payslips(employee_id):
    """Get all payslips for a specific employee"""
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

def update_payslip_status(payslip_id, new_status, notes=None):
    """Update payslip status"""
    try:
        payslip_ref = db.db.collection("payslips").document(payslip_id)
        
        update_data = {
            "status": new_status,
            "updated_at": SERVER_TIMESTAMP
        }
        
        if notes:
            update_data["notes"] = notes
        
        payslip_ref.update(update_data)
        
        return {"success": True, "message": "Payslip status updated successfully"}
        
    except Exception as e:
        print(f"Error updating payslip status: {e}")
        return {"success": False, "message": f"Error updating status: {str(e)}"}

def delete_payslip(payslip_id):
    """Delete a payslip"""
    try:
        payslip_ref = db.db.collection("payslips").document(payslip_id)
        payslip_data = payslip_ref.get().to_dict()
        
        if not payslip_data:
            return {"success": False, "message": "Payslip not found"}
        
        # Delete from database
        payslip_ref.delete()
        
        # Note: PDF file in storage will remain for audit purposes
        # In production, you might want to move it to an archive folder
        
        return {"success": True, "message": "Payslip deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting payslip: {e}")
        return {"success": False, "message": f"Error deleting payslip: {str(e)}"}

# Page header
st.title("👥 User Management (Admin)")
st.markdown(f"**Administrator:** {user_data.get('name')}")

# Logout button
if st.button("🚪 Logout", key="logout_admin_users"):
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
    if st.button("⚙️ Main Admin Panel"):
        st.switch_page("pages/admin_control.py")

st.divider()

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "👥 User Management", 
    "✏️ Edit Employee", 
    "💰 Payslip Management",
    "🗑️ Delete Users"
])

with tab1:
    st.subheader("👥 Employee Directory")
    
    # Get all employees
    employees = get_all_employees()
    
    if not employees:
        st.warning("No employees found in the system.")
    else:
        st.success(f"📊 Total employees: {len(employees)}")
        
        # Search and filter
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input("🔍 Search by name or email", placeholder="Enter name or email...")
        
        with col2:
            # Get unique divisions
            divisions = list(set([emp.get("division_name", "Unknown") for emp in employees]))
            division_filter = st.selectbox("Filter by Division", options=["All"] + sorted(divisions))
        
        with col3:
            status_filter = st.selectbox("Filter by Status", options=["All", "Active", "Inactive"])
        
        # Apply filters
        filtered_employees = employees
        
        if search_term:
            filtered_employees = [
                emp for emp in filtered_employees 
                if search_term.lower() in emp.get("name", "").lower() or 
                   search_term.lower() in emp.get("email", "").lower()
            ]
        
        if division_filter != "All":
            filtered_employees = [emp for emp in filtered_employees if emp.get("division_name") == division_filter]
        
        if status_filter != "All":
            is_active = status_filter == "Active"
            filtered_employees = [emp for emp in filtered_employees if emp.get("is_active", True) == is_active]
        
        st.info(f"Showing {len(filtered_employees)} of {len(employees)} employees")
        
        # Display employees in a table format
        if filtered_employees:
            # Create dataframe for better display
            display_data = []
            for emp in filtered_employees:
                join_date = emp.get('start_joining_date')
                join_str = "Unknown"
                if hasattr(join_date, 'timestamp'):
                    join_str = datetime.fromtimestamp(join_date.timestamp()).strftime('%d %b %Y')
                
                display_data.append({
                    "Name": emp.get("name", "Unknown"),
                    "Email": emp.get("email", "Unknown"),
                    "Role": emp.get("role_name", "Unknown"),
                    "Division": emp.get("division_name", "Unknown"),
                    "Access Level": emp.get("access_level", 4),
                    "Status": "Active" if emp.get("is_active", True) else "Inactive",
                    "Join Date": join_str,
                    "Employee ID": emp.get("employee_id", "")
                })
            
            df = pd.DataFrame(display_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Select employee for editing
            st.markdown("### 🎯 Select Employee for Actions")
            
            employee_options = [f"{emp.get('name', 'Unknown')} ({emp.get('email', 'Unknown')})" for emp in filtered_employees]
            
            if employee_options:
                selected_index = st.selectbox(
                    "Choose employee:",
                    options=range(len(employee_options)),
                    format_func=lambda x: employee_options[x],
                    key="employee_selector_main"
                )
                
                st.session_state.selected_employee_id = filtered_employees[selected_index]["employee_id"]
                
                # Quick actions
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("✏️ Edit Employee", type="primary"):
                        st.info("Switch to 'Edit Employee' tab to modify this employee's data.")
                
                with col2:
                    if st.button("💰 Manage Payslips"):
                        st.info("Switch to 'Payslip Management' tab to add payslips.")
                
                with col3:
                    if st.button("🔍 View Profile"):
                        selected_emp = filtered_employees[selected_index]
                        st.json(selected_emp)
        
        else:
            st.info("No employees match the current filters.")

with tab2:
    st.subheader("✏️ Edit Employee Data")
    
    if not st.session_state.selected_employee_id:
        st.warning("Please select an employee from the 'User Management' tab first.")
    else:
        # Get selected employee data
        try:
            employee_ref = db.db.collection("users_db").document(st.session_state.selected_employee_id)
            employee_data = employee_ref.get().to_dict()
            
            if not employee_data:
                st.error("Employee not found.")
            else:
                employee_data = enrich_user_data(employee_data)
                
                st.info(f"Editing: **{employee_data.get('name', 'Unknown')}** ({employee_data.get('email', 'Unknown')})")
                
                with st.form("edit_employee_form"):
                    st.markdown("### 👤 Personal Information")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_name = st.text_input("Full Name", value=employee_data.get("name", ""))
                        new_email = st.text_input("Email", value=employee_data.get("email", ""))
                        new_phone = st.text_input("Phone Number", value=employee_data.get("phone_number", ""))
                        new_address = st.text_area("Address", value=employee_data.get("address", ""))
                    
                    with col2:
                        current_dob = employee_data.get("date_of_birth")
                        if hasattr(current_dob, 'timestamp'):
                            dob_date = datetime.fromtimestamp(current_dob.timestamp()).date()
                        else:
                            dob_date = date(1990, 1, 1)
                        
                        new_dob = st.date_input("Date of Birth", value=dob_date)
                        new_pob = st.text_input("Place of Birth", value=employee_data.get("place_of_birth", ""))
                        new_nip = st.text_input("NIP", value=employee_data.get("NIP", ""))
                    
                    st.markdown("### 🏢 Work Information")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Role selection
                        roles = get_all_roles()
                        role_names = [role_data["role_name"] for role_data in roles.values()]
                        current_role = employee_data.get("role_name", "")
                        
                        new_role = st.selectbox(
                            "Role",
                            options=role_names,
                            index=role_names.index(current_role) if current_role in role_names else 0
                        )
                        
                        # Division selection
                        divisions = get_all_divisions()
                        division_names = [div_data["division_name"] for div_data in divisions.values()]
                        current_division = employee_data.get("division_name", "")
                        
                        new_division = st.selectbox(
                            "Division",
                            options=division_names,
                            index=division_names.index(current_division) if current_division in division_names else 0
                        )
                        
                        new_access_level = st.selectbox(
                            "Access Level",
                            options=[1, 2, 3, 4],
                            format_func=lambda x: {1: "Admin", 2: "HR Staff", 3: "Division Head", 4: "Staff"}[x],
                            index=[1, 2, 3, 4].index(employee_data.get("access_level", 4))
                        )
                    
                    with col2:
                        new_status = st.selectbox(
                            "Employee Status",
                            options=["Full Time", "Part Time", "Contract", "Intern", "Probation", "Freelance", "Inactive"],
                            index=["Full Time", "Part Time", "Contract", "Intern", "Probation", "Freelance", "Inactive"].index(employee_data.get("employee_status", "Full Time"))
                        )
                        
                        current_join_date = employee_data.get("start_joining_date")
                        if hasattr(current_join_date, 'timestamp'):
                            join_date = datetime.fromtimestamp(current_join_date.timestamp()).date()
                        else:
                            join_date = date.today()
                        
                        new_join_date = st.date_input("Join Date", value=join_date)
                        
                        new_is_active = st.checkbox("Active Employee", value=employee_data.get("is_active", True))
                        new_overtime_rate = st.number_input("Overtime Rate ($/hour)", value=float(employee_data.get("overtime_rate", 0)), min_value=0.0, step=0.5)
                    
                    st.markdown("### 🏥 Benefits Information")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_bpjs_kesehatan = st.text_input("BPJS Kesehatan", value=employee_data.get("bpjs_kesehatan_number", ""))
                    
                    with col2:
                        new_bpjs_tk = st.text_input("BPJS Ketenagakerjaan", value=employee_data.get("bpjs_ketenagakerjaan_number", ""))
                    
                    submitted = st.form_submit_button("💾 Update Employee", type="primary")
                    
                    if submitted:
                        # Prepare update data
                        updated_data = {
                            "name": new_name.strip(),
                            "email": new_email.strip(),
                            "phone_number": new_phone.strip() if new_phone.strip() else None,
                            "address": new_address.strip() if new_address.strip() else None,
                            "date_of_birth": datetime.combine(new_dob, datetime.min.time()),
                            "place_of_birth": new_pob.strip() if new_pob.strip() else None,
                            "NIP": new_nip.strip() if new_nip.strip() else None,
                            "role_name": new_role,
                            "division_name": new_division,
                            "access_level": new_access_level,
                            "employee_status": new_status,
                            "start_joining_date": datetime.combine(new_join_date, datetime.min.time()),
                            "is_active": new_is_active,
                            "overtime_rate": new_overtime_rate,
                            "bpjs_kesehatan_number": new_bpjs_kesehatan.strip() if new_bpjs_kesehatan.strip() else None,
                            "bpjs_ketenagakerjaan_number": new_bpjs_tk.strip() if new_bpjs_tk.strip() else None
                        }
                        
                        # Validate required fields
                        if not all([new_name.strip(), new_email.strip()]):
                            st.error("Name and email are required fields.")
                        else:
                            # Update employee
                            result = update_employee_data(st.session_state.selected_employee_id, updated_data)
                            
                            if result["success"]:
                                st.success("✅ Employee updated successfully!")
                                st.balloons()
                                st.info("Refreshing data...")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['message']}")
        
        except Exception as e:
            st.error(f"Error loading employee data: {e}")

with tab3:
    st.subheader("💰 Payslip Management")
    
    if not st.session_state.selected_employee_id:
        st.warning("Please select an employee from the 'User Management' tab first.")
    else:
        # Get employee data
        try:
            employee_ref = db.db.collection("users_db").document(st.session_state.selected_employee_id)
            employee_data = employee_ref.get().to_dict()
            
            if employee_data:
                st.info(f"Managing payslips for: **{employee_data.get('name', 'Unknown')}**")
                
                # Create new payslip
                with st.expander("➕ Upload New Payslip", expanded=True):
                    with st.form("upload_payslip_form"):
                        st.markdown("### 📄 Upload Payslip")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Pay period
                            current_month = datetime.now().replace(day=1)
                            pay_period = st.date_input(
                                "Pay Period (Month/Year) *",
                                value=current_month,
                                help="Select the month for this payslip"
                            )
                            pay_period_str = pay_period.strftime("%Y-%m")
                        
                        with col2:
                            payslip_status = st.selectbox("Status *", options=["pending", "paid"], index=0)
                        
                        notes = st.text_area("Notes (Optional)", placeholder="Additional notes for this payslip...")
                        
                        # PDF Upload Section (Required)
                        st.markdown("### 📄 Upload Payslip PDF *")
                        st.info("📋 **Required:** Upload the prepared payslip PDF file")
                        
                        if STORAGE_AVAILABLE:
                            payslip_pdf = st.file_uploader(
                                "Choose PDF file",
                                type=["pdf"],
                                help="Upload the prepared payslip PDF (max 10 MB)"
                            )
                            
                            if payslip_pdf:
                                # Show file preview
                                st.success(f"📄 **Selected:** {payslip_pdf.name}")
                                file_size_mb = payslip_pdf.size / (1024 * 1024)
                                st.write(f"**📊 Size:** {file_size_mb:.2f} MB")
                                
                                if file_size_mb > 10:
                                    st.error("File size exceeds 10 MB limit")
                                    payslip_pdf = None
                            else:
                                st.warning("⚠️ Please select a PDF file to upload")
                        else:
                            st.error("📁 PDF upload not available - Firebase Storage not configured")
                            payslip_pdf = None
                        
                        upload_payslip_submitted = st.form_submit_button("📤 Upload Payslip", type="primary")
                        
                        if upload_payslip_submitted:
                            if not payslip_pdf:
                                st.error("❌ Please select a PDF file to upload")
                            else:
                                # Prepare payslip data (simplified with basic fields only)
                                payslip_data = {
                                    "employee_id": st.session_state.selected_employee_id,
                                    "pay_period": pay_period_str,
                                    "status": payslip_status,
                                    "notes": notes.strip(),
                                    "created_by": employee_id
                                }
                                
                                # Create payslip with PDF
                                with st.spinner("Uploading payslip..."):
                                    result = create_payslip_with_pdf(payslip_data, payslip_pdf)
                                
                                if result["success"]:
                                    st.success("✅ Payslip uploaded successfully!")
                                    st.success("📄 PDF stored in cloud storage!")
                                    st.balloons()
                                    st.info("Refreshing payslip list...")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                
                # Display existing payslips
                st.markdown("### 📋 Existing Payslips")
                
                payslips = get_employee_payslips(st.session_state.selected_employee_id)
                
                if not payslips:
                    st.info("No payslips found for this employee.")
                else:
                    st.success(f"Found {len(payslips)} payslip(s)")
                    
                    for payslip in payslips:
                        with st.container():
                            # Payslip header
                            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                            
                            with col1:
                                pay_period = payslip.get("pay_period", "Unknown")
                                try:
                                    period_display = datetime.strptime(pay_period, "%Y-%m").strftime("%B %Y")
                                except:
                                    period_display = pay_period
                                
                                st.markdown(f"#### 💰 {period_display}")
                                
                                # Show PDF filename
                                pdf_filename = payslip.get("pdf_filename", "No file")
                                st.caption(f"📄 {pdf_filename}")
                            
                            with col2:
                                # Created date
                                created_at = payslip.get("created_at")
                                if hasattr(created_at, 'timestamp'):
                                    created_str = datetime.fromtimestamp(created_at.timestamp()).strftime('%d %b %Y')
                                    st.metric("Created", created_str)
                                else:
                                    st.metric("Created", "Unknown")
                            
                            with col3:
                                # Status
                                status = payslip.get("status", "unknown")
                                if status == "paid":
                                    st.success("✅ Paid")
                                elif status == "pending":
                                    st.warning("🕐 Pending")
                                else:
                                    st.info("📋 Processing")
                            
                            with col4:
                                # Actions menu
                                with st.popover("⚙️ Actions"):
                                    st.markdown("**Payslip Actions**")
                                    
                                    # Update status
                                    new_status = st.selectbox(
                                        "Change Status",
                                        options=["pending", "paid", "cancelled"],
                                        index=["pending", "paid", "cancelled"].index(status) if status in ["pending", "paid", "cancelled"] else 0,
                                        key=f"status_{payslip['payslip_id']}"
                                    )
                                    
                                    status_notes = st.text_area(
                                        "Update Notes",
                                        value=payslip.get("notes", ""),
                                        key=f"notes_{payslip['payslip_id']}"
                                    )
                                    
                                    if st.button("💾 Update Status", key=f"update_{payslip['payslip_id']}"):
                                        update_result = update_payslip_status(
                                            payslip["payslip_id"],
                                            new_status,
                                            status_notes.strip()
                                        )
                                        
                                        if update_result["success"]:
                                            st.success("Status updated!")
                                            st.rerun()
                                        else:
                                            st.error(update_result["message"])
                                    
                                    st.divider()
                                    
                                    # Delete payslip
                                    if st.button("🗑️ Delete Payslip", key=f"delete_{payslip['payslip_id']}", type="secondary"):
                                        delete_result = delete_payslip(payslip["payslip_id"])
                                        
                                        if delete_result["success"]:
                                            st.success("Payslip deleted!")
                                            st.rerun()
                                        else:
                                            st.error(delete_result["message"])
                            
                            # Payslip details
                            with st.expander(f"📋 Details - {period_display}"):
                                col_left, col_right = st.columns(2)
                                
                                with col_left:
                                    st.markdown("**📄 File Information**")
                                    st.write(f"• PDF File: {payslip.get('pdf_filename', 'No file')}")
                                    st.write(f"• File Path: {payslip.get('pdf_file_path', 'No path')}")
                                    st.write(f"• Payslip ID: {payslip.get('payslip_id', 'Unknown')}")
                                    
                                    created_by = payslip.get('created_by', 'Unknown')
                                    st.write(f"• Created By: {created_by}")
                                
                                with col_right:
                                    st.markdown("**📅 Dates**")
                                    
                                    created_at = payslip.get("created_at")
                                    if hasattr(created_at, 'timestamp'):
                                        created_str = datetime.fromtimestamp(created_at.timestamp()).strftime('%d %B %Y at %H:%M')
                                        st.write(f"• Created: {created_str}")
                                    
                                    updated_at = payslip.get("updated_at")
                                    if hasattr(updated_at, 'timestamp'):
                                        updated_str = datetime.fromtimestamp(updated_at.timestamp()).strftime('%d %B %Y at %H:%M')
                                        st.write(f"• Updated: {updated_str}")
                                
                                if payslip.get("notes"):
                                    st.markdown("**📝 Notes:**")
                                    st.write(payslip["notes"])
                                
                                # PDF download link (if storage is available)
                                if STORAGE_AVAILABLE and payslip.get("pdf_file_path"):
                                    st.info("💡 PDF file is stored in cloud storage")
                                    # In a real implementation, you would generate a download URL here
                                    st.caption("PDF download functionality requires additional Firebase Storage setup")
                            
                            st.divider()
            
        except Exception as e:
            st.error(f"Error managing payslips: {e}")

with tab4:
    st.subheader("🗑️ Delete Users")
    
    st.warning("⚠️ **DANGER ZONE** - User deletion is permanent and cannot be undone!")
    
    if not st.session_state.selected_employee_id:
        st.warning("Please select an employee from the 'User Management' tab first.")
    else:
        # Get employee data
        try:
            employee_ref = db.db.collection("users_db").document(st.session_state.selected_employee_id)
            employee_data = employee_ref.get().to_dict()
            
            if employee_data:
                st.error(f"**Selected for deletion:** {employee_data.get('name', 'Unknown')} ({employee_data.get('email', 'Unknown')})")
                
                # Show employee details
                with st.expander("📋 Employee Details"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Name:** {employee_data.get('name', 'Unknown')}")
                        st.write(f"**Email:** {employee_data.get('email', 'Unknown')}")
                        st.write(f"**Role:** {employee_data.get('role_name', 'Unknown')}")
                        st.write(f"**Division:** {employee_data.get('division_name', 'Unknown')}")
                    
                    with col2:
                        st.write(f"**Employee ID:** {st.session_state.selected_employee_id}")
                        st.write(f"**Access Level:** {employee_data.get('access_level', 4)}")
                        st.write(f"**Status:** {'Active' if employee_data.get('is_active', True) else 'Inactive'}")
                        
                        join_date = employee_data.get('start_joining_date')
                        if hasattr(join_date, 'timestamp'):
                            join_str = datetime.fromtimestamp(join_date.timestamp()).strftime('%d %B %Y')
                            st.write(f"**Join Date:** {join_str}")
                
                # Deletion warnings
                st.markdown("### ⚠️ Deletion Impact")
                
                st.error("""
                **This action will:**
                - ✅ Delete user from authentication system
                - ✅ Delete user from employee database
                - ✅ Remove all access permissions
                
                **Related data (will be preserved for audit):**
                - 📋 Leave requests (marked as deleted user)
                - ⏰ Overtime requests (marked as deleted user)
                - 💰 Payslips (kept for legal compliance)
                """)
                
                # Confirmation process
                if not st.session_state.show_delete_confirmation:
                    if st.button("🗑️ I Want to Delete This User", type="primary"):
                        st.session_state.show_delete_confirmation = True
                        st.rerun()
                
                else:
                    st.error("⚠️ **FINAL CONFIRMATION REQUIRED**")
                    
                    confirmation_text = st.text_input(
                        f"Type 'DELETE {employee_data.get('name', 'Unknown').upper()}' to confirm:",
                        placeholder=f"DELETE {employee_data.get('name', 'Unknown').upper()}"
                    )
                    
                    expected_text = f"DELETE {employee_data.get('name', 'Unknown').upper()}"
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🔴 CONFIRM DELETE", type="primary", disabled=(confirmation_text != expected_text)):
                            if confirmation_text == expected_text:
                                # Perform deletion
                                result = delete_employee(st.session_state.selected_employee_id)
                                
                                if result["success"]:
                                    st.success(f"✅ {result['message']}")
                                    st.balloons()
                                    
                                    # Clear selection
                                    st.session_state.selected_employee_id = None
                                    st.session_state.show_delete_confirmation = False
                                    
                                    st.info("Redirecting to user management...")
                                    import time
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['message']}")
                    
                    with col2:
                        if st.button("❌ Cancel Deletion"):
                            st.session_state.show_delete_confirmation = False
                            st.rerun()
                    
                    if confirmation_text != expected_text and confirmation_text:
                        st.error("Confirmation text does not match. Please type exactly as shown.")
            
        except Exception as e:
            st.error(f"Error loading employee data: {e}")

# Sidebar with admin tools and statistics
st.sidebar.markdown("### 👑 Admin Tools")

# Quick stats
try:
    all_employees = get_all_employees()
    active_employees = [emp for emp in all_employees if emp.get("is_active", True)]
    admin_count = len([emp for emp in all_employees if emp.get("access_level") == 1])
    
    st.sidebar.metric("Total Employees", len(all_employees))
    st.sidebar.metric("Active Employees", len(active_employees))
    st.sidebar.metric("Administrators", admin_count)
    
    # Division breakdown
    if all_employees:
        division_counts = {}
        for emp in all_employees:
            div = emp.get("division_name", "Unknown")
            division_counts[div] = division_counts.get(div, 0) + 1
        
        st.sidebar.markdown("### 🏢 Division Overview")
        for div, count in sorted(division_counts.items()):
            st.sidebar.write(f"• {div}: {count}")

except Exception as e:
    st.sidebar.error("Error loading statistics")

st.sidebar.markdown("### 🛠️ Quick Actions")

if st.sidebar.button("📊 Export User Data"):
    # Export functionality
    try:
        employees = get_all_employees()
        if employees:
            # Prepare export data
            export_data = []
            for emp in employees:
                join_date = emp.get('start_joining_date')
                join_str = "Unknown"
                if hasattr(join_date, 'timestamp'):
                    join_str = datetime.fromtimestamp(join_date.timestamp()).strftime('%Y-%m-%d')
                
                export_data.append({
                    "Employee ID": emp.get("employee_id", ""),
                    "Name": emp.get("name", ""),
                    "Email": emp.get("email", ""),
                    "Role": emp.get("role_name", ""),
                    "Division": emp.get("division_name", ""),
                    "Access Level": emp.get("access_level", 4),
                    "Status": "Active" if emp.get("is_active", True) else "Inactive",
                    "Join Date": join_str,
                    "Phone": emp.get("phone_number", ""),
                    "NIP": emp.get("NIP", "")
                })
            
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False)
            
            st.sidebar.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"employees_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.sidebar.warning("No data to export")
    except Exception as e:
        st.sidebar.error(f"Export error: {e}")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

st.sidebar.markdown("### 💰 Payslip Statistics")

try:
    # Get payslip statistics
    total_payslips = 0
    pending_payslips = 0
    paid_payslips = 0
    
    payslips_query = db.db.collection("payslips").stream()
    for doc in payslips_query:
        total_payslips += 1
        status = doc.to_dict().get("status", "unknown")
        if status == "pending":
            pending_payslips += 1
        elif status == "paid":
            paid_payslips += 1
    
    st.sidebar.metric("Total Payslips", total_payslips)
    st.sidebar.metric("Pending", pending_payslips)
    st.sidebar.metric("Paid", paid_payslips)
    
except Exception as e:
    st.sidebar.error("Error loading payslip stats")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔒 Security Notice")
st.sidebar.caption("""
Admin actions are logged and monitored.
Only perform actions you are authorized to do.
Contact IT security for any concerns.
""")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if st.button("⚙️ Main Admin Panel", use_container_width=True):
        st.switch_page("pages/admin_control.py")

with col3:
    if st.button("📝 Leave Management", use_container_width=True):
        st.switch_page("pages/leave_approval.py")

st.caption("👑 Simplified Admin User Management System | Basic Payslip Data with PDF Upload")
st.caption(f"Session: {user_data.get('name')} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
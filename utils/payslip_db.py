# utils/payslip_db.py - Database functions for payslip management
import streamlit as st
from google.cloud import firestore
from firebase_admin.firestore import SERVER_TIMESTAMP
from google.oauth2 import service_account
from datetime import datetime, timedelta, date
from utils.secrets_manager import secrets

@st.cache_resource
def get_db():
    firebase_credentials = secrets.get_firebase_credentials()
    project_id = secrets.get_nested("firebase_auth", "project_id")
    
    db = firestore.Client(credentials=firebase_credentials, project=project_id)
    return db

db = get_db()

def create_payslip(payslip_data):
    """Create a new payslip for an employee"""
    try:
        # Validate required fields
        required_fields = ["employee_id", "pay_period", "basic_salary", "gross_salary", "net_salary"]
        for field in required_fields:
            if field not in payslip_data or payslip_data[field] is None:
                return {"success": False, "message": f"Missing required field: {field}"}
        
        # Check if payslip already exists for this period
        existing_query = db.collection("payslips").where("employee_id", "==", payslip_data["employee_id"]).where("pay_period", "==", payslip_data["pay_period"]).limit(1)
        
        if len(list(existing_query.stream())) > 0:
            return {"success": False, "message": "Payslip already exists for this period"}
        
        # Create payslip document
        payslip_ref = db.collection("payslips").document()
        
        payslip_document = {
            "payslip_id": payslip_ref.id,
            "employee_id": payslip_data["employee_id"],
            "pay_period": payslip_data["pay_period"],
            "basic_salary": float(payslip_data["basic_salary"]),
            "overtime_pay": float(payslip_data.get("overtime_pay", 0)),
            "allowances": float(payslip_data.get("allowances", 0)),
            "bonus": float(payslip_data.get("bonus", 0)),
            "other_earnings": float(payslip_data.get("other_earnings", 0)),
            "gross_salary": float(payslip_data["gross_salary"]),
            "income_tax": float(payslip_data.get("income_tax", 0)),
            "bpjs_kesehatan": float(payslip_data.get("bpjs_kesehatan", 0)),
            "bpjs_ketenagakerjaan": float(payslip_data.get("bpjs_ketenagakerjaan", 0)),
            "loan_deduction": float(payslip_data.get("loan_deduction", 0)),
            "other_deductions": float(payslip_data.get("other_deductions", 0)),
            "net_salary": float(payslip_data["net_salary"]),
            "status": payslip_data.get("status", "pending"),
            "notes": payslip_data.get("notes", ""),
            "created_by": payslip_data.get("created_by"),
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP
        }
        
        # Add paid date if status is paid
        if payslip_data.get("status") == "paid" and payslip_data.get("paid_date"):
            payslip_document["paid_date"] = payslip_data["paid_date"]
        
        payslip_ref.set(payslip_document)
        
        return {"success": True, "message": "Payslip created successfully", "payslip_id": payslip_ref.id}
        
    except Exception as e:
        print(f"Error creating payslip: {e}")
        return {"success": False, "message": f"Error creating payslip: {str(e)}"}

def get_employee_payslips(employee_id, limit=None):
    """Get all payslips for a specific employee"""
    try:
        query = db.collection("payslips").where("employee_id", "==", employee_id).order_by("pay_period", direction=firestore.Query.DESCENDING)
        
        if limit:
            query = query.limit(limit)
        
        payslips = []
        for doc in query.stream():
            payslip_data = doc.to_dict()
            payslip_data["id"] = doc.id
            payslips.append(payslip_data)
        
        return payslips
        
    except Exception as e:
        print(f"Error getting payslips: {e}")
        return []

def get_payslip_by_id(payslip_id):
    """Get a specific payslip by ID"""
    try:
        payslip_ref = db.collection("payslips").document(payslip_id)
        payslip_doc = payslip_ref.get()
        
        if payslip_doc.exists:
            payslip_data = payslip_doc.to_dict()
            payslip_data["id"] = payslip_doc.id
            return payslip_data
        else:
            return None
            
    except Exception as e:
        print(f"Error getting payslip: {e}")
        return None

def update_payslip(payslip_id, updated_data):
    """Update an existing payslip"""
    try:
        payslip_ref = db.collection("payslips").document(payslip_id)
        current_data = payslip_ref.get().to_dict()
        
        if not current_data:
            return {"success": False, "message": "Payslip not found"}
        
        # Prepare update data
        update_data = {
            "updated_at": SERVER_TIMESTAMP
        }
        
        # List of fields that can be updated
        updatable_fields = [
            "basic_salary", "overtime_pay", "allowances", "bonus", "other_earnings",
            "gross_salary", "income_tax", "bpjs_kesehatan", "bpjs_ketenagakerjaan",
            "loan_deduction", "other_deductions", "net_salary", "status", "notes", "paid_date"
        ]
        
        for field in updatable_fields:
            if field in updated_data:
                if field in ["basic_salary", "overtime_pay", "allowances", "bonus", "other_earnings",
                           "gross_salary", "income_tax", "bpjs_kesehatan", "bpjs_ketenagakerjaan",
                           "loan_deduction", "other_deductions", "net_salary"]:
                    update_data[field] = float(updated_data[field])
                else:
                    update_data[field] = updated_data[field]
        
        # Apply updates
        if len(update_data) > 1:  # More than just updated_at
            payslip_ref.update(update_data)
            return {"success": True, "message": "Payslip updated successfully"}
        else:
            return {"success": False, "message": "No changes detected"}
        
    except Exception as e:
        print(f"Error updating payslip: {e}")
        return {"success": False, "message": f"Error updating payslip: {str(e)}"}

def delete_payslip(payslip_id):
    """Delete a payslip (admin function - use with caution)"""
    try:
        payslip_ref = db.collection("payslips").document(payslip_id)
        payslip_data = payslip_ref.get().to_dict()
        
        if not payslip_data:
            return {"success": False, "message": "Payslip not found"}
        
        # Instead of deleting, mark as deleted for audit purposes
        payslip_ref.update({
            "status": "deleted",
            "deleted_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP
        })
        
        return {"success": True, "message": "Payslip marked as deleted"}
        
    except Exception as e:
        print(f"Error deleting payslip: {e}")
        return {"success": False, "message": f"Error deleting payslip: {str(e)}"}

def get_payslip_statistics(employee_id=None, year=None, division_id=None):
    """Get payslip statistics for reporting"""
    try:
        if not year:
            year = datetime.now().year
        
        query = db.collection("payslips")
        
        if employee_id:
            query = query.where("employee_id", "==", employee_id)
        
        # Get all payslips and filter by year
        payslips = []
        for doc in query.stream():
            payslip_data = doc.to_dict()
            
            # Filter by year
            try:
                payslip_year = int(payslip_data.get("pay_period", "2000-01")[:4])
                if payslip_year == year:
                    payslips.append(payslip_data)
            except:
                continue
        
        # Filter by division if specified
        if division_id and not employee_id:
            filtered_payslips = []
            for payslip in payslips:
                try:
                    emp_ref = db.collection("users_db").document(payslip["employee_id"])
                    emp_data = emp_ref.get().to_dict()
                    if emp_data and emp_data.get("division_id") == division_id:
                        filtered_payslips.append(payslip)
                except:
                    continue
            payslips = filtered_payslips
        
        # Calculate statistics
        stats = {
            "total_payslips": len(payslips),
            "total_gross_salary": sum([p.get("gross_salary", 0) for p in payslips]),
            "total_net_salary": sum([p.get("net_salary", 0) for p in payslips]),
            "total_deductions": 0,
            "average_gross_salary": 0,
            "average_net_salary": 0,
            "paid_payslips": len([p for p in payslips if p.get("status") == "paid"]),
            "pending_payslips": len([p for p in payslips if p.get("status") == "pending"])
        }
        
        stats["total_deductions"] = stats["total_gross_salary"] - stats["total_net_salary"]
        
        if stats["total_payslips"] > 0:
            stats["average_gross_salary"] = stats["total_gross_salary"] / stats["total_payslips"]
            stats["average_net_salary"] = stats["total_net_salary"] / stats["total_payslips"]
        
        return stats
        
    except Exception as e:
        print(f"Error getting payslip statistics: {e}")
        return None

def generate_payslip_report(year=None, month=None, division_id=None):
    """Generate comprehensive payslip report"""
    try:
        if not year:
            year = datetime.now().year
        
        query = db.collection("payslips")
        
        # Build filter conditions
        filter_conditions = []
        if month:
            pay_period = f"{year}-{month:02d}"
            filter_conditions.append(("pay_period", "==", pay_period))
        else:
            # Filter by year (need to get all and filter manually due to Firestore limitations)
            pass
        
        # Get payslips
        payslips = []
        for doc in query.stream():
            payslip_data = doc.to_dict()
            payslip_data["id"] = doc.id
            
            # Apply year filter
            try:
                payslip_year = int(payslip_data.get("pay_period", "2000-01")[:4])
                if payslip_year != year:
                    continue
                
                # Apply month filter if specified
                if month:
                    payslip_month = int(payslip_data.get("pay_period", "2000-01")[5:7])
                    if payslip_month != month:
                        continue
            except:
                continue
            
            # Enrich with employee data
            try:
                emp_ref = db.collection("users_db").document(payslip_data["employee_id"])
                emp_data = emp_ref.get().to_dict()
                
                if emp_data:
                    # Apply division filter if specified
                    if division_id and emp_data.get("division_id") != division_id:
                        continue
                    
                    # Get division and role names
                    division_data = db.collection("divisions").document(emp_data.get("division_id", "")).get().to_dict()
                    role_data = db.collection("roles").document(emp_data.get("role_id", "")).get().to_dict()
                    
                    payslip_data["employee_name"] = emp_data.get("name", "Unknown")
                    payslip_data["employee_email"] = emp_data.get("email", "Unknown")
                    payslip_data["division_name"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                    payslip_data["role_name"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
                    
                    payslips.append(payslip_data)
            except Exception as e:
                print(f"Error enriching payslip data: {e}")
                continue
        
        return payslips
        
    except Exception as e:
        print(f"Error generating payslip report: {e}")
        return []

def calculate_payroll_summary(payslips):
    """Calculate payroll summary from a list of payslips"""
    try:
        summary = {
            "total_employees": len(payslips),
            "total_gross_amount": 0,
            "total_net_amount": 0,
            "total_deductions": 0,
            "breakdown": {
                "basic_salary": 0,
                "overtime_pay": 0,
                "allowances": 0,
                "bonus": 0,
                "other_earnings": 0,
                "income_tax": 0,
                "bpjs_kesehatan": 0,
                "bpjs_ketenagakerjaan": 0,
                "loan_deduction": 0,
                "other_deductions": 0
            },
            "by_division": {},
            "by_status": {"paid": 0, "pending": 0, "other": 0}
        }
        
        for payslip in payslips:
            # Totals
            summary["total_gross_amount"] += payslip.get("gross_salary", 0)
            summary["total_net_amount"] += payslip.get("net_salary", 0)
            
            # Breakdown
            for field in summary["breakdown"]:
                summary["breakdown"][field] += payslip.get(field, 0)
            
            # By division
            division = payslip.get("division_name", "Unknown")
            if division not in summary["by_division"]:
                summary["by_division"][division] = {
                    "count": 0,
                    "gross_amount": 0,
                    "net_amount": 0
                }
            
            summary["by_division"][division]["count"] += 1
            summary["by_division"][division]["gross_amount"] += payslip.get("gross_salary", 0)
            summary["by_division"][division]["net_amount"] += payslip.get("net_salary", 0)
            
            # By status
            status = payslip.get("status", "other")
            if status in summary["by_status"]:
                summary["by_status"][status] += 1
            else:
                summary["by_status"]["other"] += 1
        
        summary["total_deductions"] = summary["total_gross_amount"] - summary["total_net_amount"]
        
        return summary
        
    except Exception as e:
        print(f"Error calculating payroll summary: {e}")
        return None

def bulk_update_payslip_status(payslip_ids, new_status, admin_id, paid_date=None):
    """Bulk update payslip status (admin function)"""
    try:
        updated_count = 0
        errors = []
        
        for payslip_id in payslip_ids:
            try:
                payslip_ref = db.collection("payslips").document(payslip_id)
                update_data = {
                    "status": new_status,
                    "updated_at": SERVER_TIMESTAMP,
                    "updated_by": admin_id
                }
                
                if new_status == "paid" and paid_date:
                    update_data["paid_date"] = paid_date
                
                payslip_ref.update(update_data)
                updated_count += 1
                
            except Exception as e:
                errors.append(f"Error updating {payslip_id}: {str(e)}")
        
        if errors:
            return {
                "success": False,
                "message": f"Updated {updated_count} payslips, but encountered {len(errors)} errors",
                "errors": errors
            }
        else:
            return {
                "success": True,
                "message": f"Successfully updated {updated_count} payslips",
                "updated_count": updated_count
            }
        
    except Exception as e:
        print(f"Error bulk updating payslips: {e}")
# utils/payslip_db.py - Database functions for payslip management
import streamlit as st
from google.cloud import firestore
from firebase_admin.firestore import SERVER_TIMESTAMP
from google.oauth2 import service_account
from datetime import datetime, timedelta, date

def get_db():
    """Get Firestore database instance"""
    firebase_credentials = service_account.Credentials.from_service_account_info(
        st.secrets["firebase_auth"]
    )
    db = firestore.Client(credentials=firebase_credentials, project=st.secrets["firebase_auth"]["project_id"])
    return db

db = get_db()
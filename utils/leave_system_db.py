# Enhanced leave_system_db.py with admin control and overtime system
import streamlit as st
from google.cloud import firestore
from firebase_admin.firestore import SERVER_TIMESTAMP
from google.oauth2 import service_account
from datetime import datetime, timedelta, date


def get_db():
    """Get Firestore database instance"""
    # db = firestore.Client.from_service_account_json("firebase_key.json")
    
    # Access credentials from st.secrets
    firebase_credentials = service_account.Credentials.from_service_account_info(
        st.secrets["firebase_auth"]
    )

    # Initialize Firestore client
    db = firestore.Client(credentials=firebase_credentials, project=st.secrets["firebase_auth"]["project_id"])
    return db

db = get_db()

DIVISIONS = {
    "strategic": "Strategic",
    "admin": "Admin", 
    "btn": "BTN (Barudak Top Notch)",
    "finance": "Finance",
    "hr": "HR"
}

# Leave Types Configuration
LEAVE_TYPES = {
    "annual": {
        "name": "Annual Leave",
        "has_quota": True,
        "max_days": 14,
        "requires_approval": True,
        "description": "Paid annual leave"
    },
    "sick": {
        "name": "Sick Leave", 
        "has_quota": False,
        "max_consecutive": 2,
        "requires_approval": True,
        "description": "Sick leave without quota (max 2 days consecutive)"
    },
    "menstrual": {
        "name": "Menstrual Leave",
        "has_quota": False,
        "max_per_month": 1,
        "requires_approval": True,
        "gender_specific": "female",
        "description": "Monthly menstrual leave for female employees"
    },
    "marriage": {
        "name": "Marriage Leave",
        "has_quota": False,
        "fixed_days": 3,
        "requires_approval": True,
        "once_per_marriage": True,
        "description": "3 days leave for marriage"
    },
    "maternity": {
        "name": "Maternity Leave",
        "has_quota": False,
        "fixed_days": 45,
        "requires_approval": True,
        "gender_specific": "female",
        "description": "45 days maternity leave"
    },
    "paternity": {
        "name": "Paternity Leave",
        "has_quota": False,
        "fixed_days": 2,
        "requires_approval": True,
        "gender_specific": "male",
        "description": "2 days paternity leave"
    }
}

# OVERTIME SYSTEM FUNCTIONS

# Updated submit_overtime_request function with better date handling
def submit_overtime_request(employee_id, overtime_data):
    """
    Submit overtime request - Updated to handle individual date entries
    overtime_data = {
        "week_start": "2024-01-01",  # Can be calculated from entries
        "week_end": "2024-01-07",    # Can be calculated from entries
        "overtime_entries": [
            {"date": "2024-01-06", "hours": 4.0, "description": "Project X completion"},
            {"date": "2024-01-07", "hours": 3.5, "description": "System maintenance"}
        ],
        "total_hours": 7.5,
        "reason": "Project deadline and maintenance"
    }
    """
    try:
        # Validate overtime request
        validation_result = validate_overtime_request(employee_id, overtime_data)
        if not validation_result["valid"]:
            return {"success": False, "message": validation_result["message"]}
        
        # Get approver using existing logic
        approver_id = get_employee_approver(employee_id)
        if not approver_id:
            return {"success": False, "message": "No approver found. Please contact HR."}
        
        # Get approver info
        approver_data = db.collection("users_db").document(approver_id).get().to_dict()
        approver_name = approver_data.get("name", "Unknown") if approver_data else "Unknown"
        
        # Create overtime request
        overtime_request_data = {
            "employee_id": employee_id,
            "week_start": overtime_data["week_start"],
            "week_end": overtime_data["week_end"],
            "overtime_entries": overtime_data["overtime_entries"],
            "total_hours": float(overtime_data["total_hours"]),  # Ensure it's a float
            "reason": overtime_data.get("reason", ""),
            "status": "pending",
            "approver_id": approver_id,
            "approver_name": approver_name,
            "approval_type": get_approver_type(employee_id, approver_id),
            "submitted_at": SERVER_TIMESTAMP,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP
        }
        
        # Save to database
        request_ref = db.collection("overtime_requests").document()
        overtime_request_data["request_id"] = request_ref.id
        request_ref.set(overtime_request_data)
        
        return {
            "success": True,
            "message": f"Overtime request submitted successfully. Sent to {approver_name} for approval.",
            "request_id": request_ref.id,
            "approver_name": approver_name
        }
        
    except Exception as e:
        print(f"Error submitting overtime request: {e}")
        return {"success": False, "message": f"Error submitting request: {str(e)}"}

# Updated function to check for overlapping requests by date
def get_employee_overtime_requests_by_date_range(employee_id, start_date, end_date):
    """Get existing overtime requests that overlap with the given date range"""
    try:
        query = db.collection("overtime_requests").where("employee_id", "==", employee_id)
        
        overlapping_requests = []
        
        for doc in query.stream():
            request_data = doc.to_dict()
            request_start = datetime.strptime(request_data.get("week_start", ""), "%Y-%m-%d").date()
            request_end = datetime.strptime(request_data.get("week_end", ""), "%Y-%m-%d").date()
            
            # Check for overlap
            if not (end_date < request_start or start_date > request_end):
                request_data["id"] = doc.id
                overlapping_requests.append(request_data)
        
        return overlapping_requests
        
    except Exception as e:
        print(f"Error getting overtime requests by date range: {e}")
        return []


# Enhanced validation to check for date conflicts
def validate_overtime_dates(employee_id, overtime_entries):
    """Check if any of the overtime dates conflict with existing requests"""
    try:
        request_dates = [datetime.strptime(entry["date"], "%Y-%m-%d").date() for entry in overtime_entries]
        
        if not request_dates:
            return {"valid": False, "message": "No overtime dates provided"}
        
        start_date = min(request_dates)
        end_date = max(request_dates)
        
        # Check for overlapping requests
        existing_requests = get_employee_overtime_requests_by_date_range(employee_id, start_date, end_date)
        
        if existing_requests:
            conflicting_dates = []
            for existing in existing_requests:
                for entry in existing.get("overtime_entries", []):
                    existing_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                    if existing_date in request_dates:
                        conflicting_dates.append(existing_date.strftime("%Y-%m-%d"))
            
            if conflicting_dates:
                return {
                    "valid": False, 
                    "message": f"Overtime already submitted for dates: {', '.join(conflicting_dates)}"
                }
        
        return {"valid": True, "message": "No date conflicts found"}
        
    except Exception as e:
        return {"valid": False, "message": f"Error validating dates: {str(e)}"}


# Helper function to get week range from individual dates
def calculate_week_range_from_entries(overtime_entries):
    """Calculate week start and end from overtime entries"""
    try:
        dates = [datetime.strptime(entry["date"], "%Y-%m-%d").date() for entry in overtime_entries]
        week_start = min(dates)
        week_end = max(dates)
        return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error calculating week range: {e}")
        return None, None

def validate_overtime_request(employee_id, overtime_data):
    """Validate overtime request against business rules - REMOVED weekend/holiday validation"""
    try:
        # Check if dates are valid
        week_start = datetime.strptime(overtime_data["week_start"], "%Y-%m-%d").date()
        week_end = datetime.strptime(overtime_data["week_end"], "%Y-%m-%d").date()
        
        if week_start > week_end:
            return {"valid": False, "message": "Week start cannot be after week end"}
        
        if week_end > date.today():
            return {"valid": False, "message": "Cannot submit overtime for future dates"}
        
        # Validate hours for each entry
        for entry in overtime_data["overtime_entries"]:
            overtime_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            
            # REMOVED: Weekend/holiday validation - now allows any date
            
            # Validate hours
            if entry["hours"] <= 0 or entry["hours"] > 12:
                return {"valid": False, "message": f"Invalid overtime hours: {entry['hours']}. Must be between 0.5-12 hours per day."}
        
        # Check total hours
        calculated_total = sum([entry["hours"] for entry in overtime_data["overtime_entries"]])
        if abs(calculated_total - overtime_data["total_hours"]) > 0.01:  # Allow small floating point differences
            return {"valid": False, "message": "Total hours mismatch with individual entries"}
        
        # Check for duplicate submissions (same date range)
        existing_requests = get_employee_overtime_requests_by_week(
            employee_id, overtime_data["week_start"], overtime_data["week_end"]
        )
        if existing_requests:
            return {"valid": False, "message": "Overtime request already exists for this period"}
        
        return {"valid": True, "message": "Valid overtime request"}
        
    except Exception as e:
        return {"valid": False, "message": f"Validation error: {str(e)}"}

# Updated get_employee_overtime_requests_by_week to handle flexible date ranges
def get_employee_overtime_requests_by_week(employee_id, week_start, week_end):
    """Get existing overtime requests for a specific date range"""
    try:
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        end_date = datetime.strptime(week_end, "%Y-%m-%d").date()
        
        return get_employee_overtime_requests_by_date_range(employee_id, start_date, end_date)
        
    except Exception as e:
        print(f"Error getting overtime requests by week: {e}")
        return []

def get_employee_overtime_requests(employee_id, limit=None, status=None):
    """Get employee's overtime requests"""
    try:
        query = db.collection("overtime_requests").where("employee_id", "==", employee_id)
        
        if status:
            query = query.where("status", "==", status)
        
        query = query.order_by("submitted_at", direction=firestore.Query.DESCENDING)
        
        if limit:
            query = query.limit(limit)
        
        requests = []
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            requests.append(request_data)
        
        return requests
        
    except Exception as e:
        print(f"Error getting overtime requests: {e}")
        return []

def get_pending_overtime_approvals_for_approver(approver_id):
    """Get pending overtime requests for approval"""
    try:
        query = db.collection("overtime_requests").where("approver_id", "==", approver_id).where("status", "==", "pending")
        
        requests = []
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Enrich with employee data
            employee_data = db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
            if employee_data:
                # Get division and role names from their collections
                division_data = db.collection("divisions").document(employee_data.get("division_id", "")).get().to_dict()
                role_data = db.collection("roles").document(employee_data.get("role_id", "")).get().to_dict()
                
                request_data["employee_name"] = employee_data.get("name")
                request_data["employee_email"] = employee_data.get("email")
                request_data["employee_division"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                request_data["employee_role"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
            
            requests.append(request_data)
        
        requests.sort(key=lambda x: x.get("submitted_at", 0), reverse=True)
        return requests
        
    except Exception as e:
        print(f"Error getting pending overtime approvals: {e}")
        return []

def approve_overtime_request(request_id, approver_id, comments=""):
    """Approve overtime request"""
    try:
        request_ref = db.collection("overtime_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Overtime request not found"}
        
        if request_data["approver_id"] != approver_id:
            return {"success": False, "message": "Unauthorized to approve this request"}
        
        if request_data["status"] != "pending":
            return {"success": False, "message": "Request is not pending approval"}
        
        # Get approver info
        approver_data = db.collection("users_db").document(approver_id).get().to_dict()
        approver_name = approver_data.get("name", "Unknown") if approver_data else "Unknown"
        
        # Update request status
        request_ref.update({
            "status": "approved",
            "approved_by": approver_id,
            "approved_by_name": approver_name,
            "approved_at": SERVER_TIMESTAMP,
            "approver_comments": comments,
            "updated_at": SERVER_TIMESTAMP
        })
        
        # Add to employee's approved overtime balance
        update_employee_overtime_balance(request_data["employee_id"], request_data["total_hours"], "add")
        
        return {"success": True, "message": "Overtime request approved successfully"}
        
    except Exception as e:
        print(f"Error approving overtime request: {e}")
        return {"success": False, "message": f"Error approving request: {str(e)}"}

def reject_overtime_request(request_id, approver_id, comments=""):
    """Reject overtime request"""
    try:
        request_ref = db.collection("overtime_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Overtime request not found"}
        
        if request_data["approver_id"] != approver_id:
            return {"success": False, "message": "Unauthorized to reject this request"}
        
        if request_data["status"] != "pending":
            return {"success": False, "message": "Request is not pending approval"}
        
        # Get approver info
        approver_data = db.collection("users_db").document(approver_id).get().to_dict()
        approver_name = approver_data.get("name", "Unknown") if approver_data else "Unknown"
        
        # Update request status
        request_ref.update({
            "status": "rejected",
            "rejected_by": approver_id,
            "rejected_by_name": approver_name,
            "rejected_at": SERVER_TIMESTAMP,
            "approver_comments": comments,
            "updated_at": SERVER_TIMESTAMP
        })
        
        return {"success": True, "message": "Overtime request rejected"}
        
    except Exception as e:
        print(f"Error rejecting overtime request: {e}")
        return {"success": False, "message": f"Error rejecting request: {str(e)}"}

def update_employee_overtime_balance(employee_id, hours, operation):
    """Update employee's overtime balance"""
    try:
        current_month = datetime.now().strftime("%Y-%m")
        balance_ref = db.collection("overtime_balances").document(f"{employee_id}_{current_month}")
        balance_data = balance_ref.get().to_dict()
        
        if not balance_data:
            # Create new balance record
            balance_data = {
                "employee_id": employee_id,
                "month": current_month,
                "approved_hours": 0,
                "paid_hours": 0,
                "balance_hours": 0,
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP
            }
        
        current_approved = balance_data.get("approved_hours", 0)
        current_balance = balance_data.get("balance_hours", 0)
        
        if operation == "add":
            new_approved = current_approved + hours
            new_balance = current_balance + hours
        else:  # remove
            new_approved = max(0, current_approved - hours)
            new_balance = max(0, current_balance - hours)
        
        balance_data.update({
            "approved_hours": new_approved,
            "balance_hours": new_balance,
            "updated_at": SERVER_TIMESTAMP
        })
        
        balance_ref.set(balance_data)
        
    except Exception as e:
        print(f"Error updating overtime balance: {e}")

def get_employee_overtime_balance(employee_id, month=None):
    """Get employee's overtime balance for a specific month"""
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")
        
        balance_ref = db.collection("overtime_balances").document(f"{employee_id}_{month}")
        balance_data = balance_ref.get().to_dict()
        
        if not balance_data:
            return {
                "employee_id": employee_id,
                "month": month,
                "approved_hours": 0,
                "paid_hours": 0,
                "balance_hours": 0
            }
        
        return balance_data
        
    except Exception as e:
        print(f"Error getting overtime balance: {e}")
        return None

def get_overtime_report_data(month=None, division_id=None):
    """Get overtime report data for payroll processing"""
    try:
        if not month:
            month = datetime.now().strftime("%Y-%m")
        
        query = db.collection("overtime_balances").where("month", "==", month)
        
        report_data = []
        for doc in query.stream():
            balance_data = doc.to_dict()
            employee_id = balance_data["employee_id"]
            
            # Get employee info
            employee_data = db.collection("users_db").document(employee_id).get().to_dict()
            if not employee_data:
                continue
            
            # Filter by division if specified
            if division_id and employee_data.get("division_id") != division_id:
                continue
            
            # Get division and role names
            division_data = db.collection("divisions").document(employee_data.get("division_id", "")).get().to_dict()
            role_data = db.collection("roles").document(employee_data.get("role_id", "")).get().to_dict()
            
            report_entry = {
                "employee_id": employee_id,
                "employee_name": employee_data.get("name", "Unknown"),
                "employee_email": employee_data.get("email", "Unknown"),
                "division": division_data.get("division_name", "Unknown") if division_data else "Unknown",
                "role": role_data.get("role_name", "Unknown") if role_data else "Unknown",
                "approved_hours": balance_data.get("approved_hours", 0),
                "paid_hours": balance_data.get("paid_hours", 0),
                "balance_hours": balance_data.get("balance_hours", 0),
                "overtime_rate": employee_data.get("overtime_rate", 0),  # Assuming this exists
                "calculated_pay": balance_data.get("balance_hours", 0) * employee_data.get("overtime_rate", 0)
            }
            
            report_data.append(report_entry)
        
        return report_data
        
    except Exception as e:
        print(f"Error getting overtime report data: {e}")
        return []

# Updated reset_overtime_balances function to store reset date
def reset_overtime_balances(month):
    """Reset overtime balances after payroll processing and store reset date"""
    try:
        query = db.collection("overtime_balances").where("month", "==", month)
        
        reset_count = 0
        for doc in query.stream():
            balance_data = doc.to_dict()
            
            # Mark hours as paid and reset balance
            doc.reference.update({
                "paid_hours": balance_data.get("balance_hours", 0),
                "balance_hours": 0,
                "reset_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP
            })
            
            reset_count += 1
        
        # Store the reset date in system settings
        reset_date = datetime.now()
        settings_ref = db.collection("system_settings").document("overtime_reset")
        settings_ref.set({
            "last_reset_date": reset_date,
            "last_reset_month": month,
            "reset_count": reset_count,
            "updated_at": SERVER_TIMESTAMP
        })
        
        return {"success": True, "message": f"Reset overtime balances for {reset_count} employees in {month}"}
        
    except Exception as e:
        print(f"Error resetting overtime balances: {e}")
        return {"success": False, "message": f"Error resetting balances: {str(e)}"}


# ENHANCED LEAVE SYSTEM WITH ADMIN CONTROL

def admin_approve_leave_request(request_id, admin_id, comments=""):
    """Admin override approval for leave request"""
    try:
        request_ref = db.collection("leave_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Leave request not found"}
        
        # Verify admin access
        admin_data = db.collection("users_db").document(admin_id).get().to_dict()
        if not admin_data or admin_data.get("access_level") != 1:
            return {"success": False, "message": "Admin privileges required"}
        
        admin_name = admin_data.get("name", "Unknown")
        
        # Update request status
        request_ref.update({
            "status": "approved_final",
            "approved_by": admin_id,
            "approved_by_name": admin_name,
            "approved_at": SERVER_TIMESTAMP,
            "approver_comments": comments,
            "admin_override": True,
            "updated_at": SERVER_TIMESTAMP
        })
        
        # Update leave quota for annual leave
        if request_data["leave_type"] == "annual":
            employee_id = request_data["employee_id"]
            working_days = request_data["working_days"]
            
            # Move from pending to used
            update_leave_quota_pending(employee_id, working_days, "remove")
            update_leave_quota_used(employee_id, working_days, "add")
        
        return {"success": True, "message": f"Leave request approved by admin ({admin_name})"}
        
    except Exception as e:
        print(f"Error admin approving leave request: {e}")
        return {"success": False, "message": f"Error approving request: {str(e)}"}

def admin_reject_leave_request(request_id, admin_id, comments=""):
    """Admin override rejection for leave request"""
    try:
        request_ref = db.collection("leave_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Leave request not found"}
        
        # Verify admin access
        admin_data = db.collection("users_db").document(admin_id).get().to_dict()
        if not admin_data or admin_data.get("access_level") != 1:
            return {"success": False, "message": "Admin privileges required"}
        
        admin_name = admin_data.get("name", "Unknown")
        
        # Update request status
        request_ref.update({
            "status": "rejected",
            "rejected_by": admin_id,
            "rejected_by_name": admin_name,
            "rejected_at": SERVER_TIMESTAMP,
            "approver_comments": comments,
            "admin_override": True,
            "updated_at": SERVER_TIMESTAMP
        })
        
        # Remove from pending quota for annual leave
        if request_data["leave_type"] == "annual":
            employee_id = request_data["employee_id"]
            working_days = request_data["working_days"]
            update_leave_quota_pending(employee_id, working_days, "remove")
        
        return {"success": True, "message": f"Leave request rejected by admin ({admin_name})"}
        
    except Exception as e:
        print(f"Error admin rejecting leave request: {e}")
        return {"success": False, "message": f"Error rejecting request: {str(e)}"}

def admin_override_overtime_request(request_id, admin_id, action, comments=""):
    """Admin override for overtime requests"""
    try:
        request_ref = db.collection("overtime_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Overtime request not found"}
        
        # Verify admin access
        admin_data = db.collection("users_db").document(admin_id).get().to_dict()
        if not admin_data or admin_data.get("access_level") != 1:
            return {"success": False, "message": "Admin privileges required"}
        
        admin_name = admin_data.get("name", "Unknown")
        
        if action == "approve":
            request_ref.update({
                "status": "approved",
                "approved_by": admin_id,
                "approved_by_name": admin_name,
                "approved_at": SERVER_TIMESTAMP,
                "approver_comments": comments,
                "admin_override": True,
                "updated_at": SERVER_TIMESTAMP
            })
            
            # Add to employee's overtime balance
            update_employee_overtime_balance(request_data["employee_id"], request_data["total_hours"], "add")
            
            return {"success": True, "message": f"Overtime request approved by admin ({admin_name})"}
        
        elif action == "reject":
            request_ref.update({
                "status": "rejected",
                "rejected_by": admin_id,
                "rejected_by_name": admin_name,
                "rejected_at": SERVER_TIMESTAMP,
                "approver_comments": comments,
                "admin_override": True,
                "updated_at": SERVER_TIMESTAMP
            })
            
            return {"success": True, "message": f"Overtime request rejected by admin ({admin_name})"}
        
        else:
            return {"success": False, "message": "Invalid action. Use 'approve' or 'reject'"}
        
    except Exception as e:
        print(f"Error admin overriding overtime request: {e}")
        return {"success": False, "message": f"Error processing request: {str(e)}"}

def get_all_leave_requests_admin():
    """Get all leave requests with enhanced admin info"""
    try:
        requests = []
        query = db.collection("leave_requests").order_by("submitted_at", direction=firestore.Query.DESCENDING)
        
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Enrich with employee data
            try:
                employee_data = db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
                if employee_data:
                    # Get division and role names
                    division_data = db.collection("divisions").document(employee_data.get("division_id", "")).get().to_dict()
                    role_data = db.collection("roles").document(employee_data.get("role_id", "")).get().to_dict()
                    
                    request_data["employee_name"] = employee_data.get("name")
                    request_data["employee_email"] = employee_data.get("email")
                    request_data["employee_division"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                    request_data["employee_role"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
                    request_data["employee_access_level"] = employee_data.get("access_level", 4)
            except Exception as e:
                print(f"Error enriching employee data: {e}")
            
            # Enrich with approver data
            if request_data.get("approver_id"):
                try:
                    approver_data = db.collection("users_db").document(request_data["approver_id"]).get().to_dict()
                    if approver_data:
                        approver_division_data = db.collection("divisions").document(approver_data.get("division_id", "")).get().to_dict()
                        approver_role_data = db.collection("roles").document(approver_data.get("role_id", "")).get().to_dict()
                        
                        request_data["approver_name"] = approver_data.get("name", "Unknown")
                        request_data["approver_role"] = approver_role_data.get("role_name", "Unknown") if approver_role_data else "Unknown"
                        request_data["approver_division"] = approver_division_data.get("division_name", "Unknown") if approver_division_data else "Unknown"
                        request_data["approver_access_level"] = approver_data.get("access_level", 4)
                except Exception as e:
                    print(f"Error enriching approver data: {e}")
            
            # Add final processor info (who actually approved/rejected)
            final_processor_id = request_data.get("approved_by") or request_data.get("rejected_by")
            if final_processor_id:
                try:
                    processor_data = db.collection("users_db").document(final_processor_id).get().to_dict()
                    if processor_data:
                        processor_role_data = db.collection("roles").document(processor_data.get("role_id", "")).get().to_dict()
                        request_data["final_processor_name"] = processor_data.get("name", "Unknown")
                        request_data["final_processor_role"] = processor_role_data.get("role_name", "Unknown") if processor_role_data else "Unknown"
                        request_data["is_admin_override"] = request_data.get("admin_override", False)
                except Exception as e:
                    print(f"Error enriching processor data: {e}")
            
            requests.append(request_data)
        
        return requests
        
    except Exception as e:
        print(f"Error getting all leave requests: {e}")
        return []

def get_all_overtime_requests_admin():
    """Get all overtime requests for admin view"""
    try:
        requests = []
        query = db.collection("overtime_requests").order_by("submitted_at", direction=firestore.Query.DESCENDING)
        
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Enrich with employee data
            try:
                employee_data = db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
                if employee_data:
                    division_data = db.collection("divisions").document(employee_data.get("division_id", "")).get().to_dict()
                    role_data = db.collection("roles").document(employee_data.get("role_id", "")).get().to_dict()
                    
                    request_data["employee_name"] = employee_data.get("name")
                    request_data["employee_email"] = employee_data.get("email")
                    request_data["employee_division"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                    request_data["employee_role"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
            except Exception as e:
                print(f"Error enriching employee data: {e}")
            
            # Enrich with approver data
            if request_data.get("approver_id"):
                try:
                    approver_data = db.collection("users_db").document(request_data["approver_id"]).get().to_dict()
                    if approver_data:
                        approver_role_data = db.collection("roles").document(approver_data.get("role_id", "")).get().to_dict()
                        request_data["approver_name"] = approver_data.get("name", "Unknown")
                        request_data["approver_role"] = approver_role_data.get("role_name", "Unknown") if approver_role_data else "Unknown"
                except Exception as e:
                    print(f"Error enriching approver data: {e}")
            
            # Add final processor info
            final_processor_id = request_data.get("approved_by") or request_data.get("rejected_by")
            if final_processor_id:
                try:
                    processor_data = db.collection("users_db").document(final_processor_id).get().to_dict()
                    if processor_data:
                        request_data["final_processor_name"] = processor_data.get("name", "Unknown")
                        request_data["is_admin_override"] = request_data.get("admin_override", False)
                except Exception as e:
                    print(f"Error enriching processor data: {e}")
            
            requests.append(request_data)
        
        return requests
        
    except Exception as e:
        print(f"Error getting all overtime requests: {e}")
        return []

# EXISTING FUNCTIONS (kept for backward compatibility with enhancements)

def get_employee_approver(employee_id):
    """
    Get the approver for an employee with improved logic:
    1. Check if employee has a direct_supervisor_id
    2. If yes, use that as approver
    3. If no, fall back to division head
    4. Handle special cases and escalation
    """
    try:
        # Get employee data
        employee_ref = db.collection("users_db").document(employee_id)
        employee_data = employee_ref.get().to_dict()
        
        if not employee_data:
            return None
        
        # Priority 1: Direct Supervisor
        direct_supervisor_id = employee_data.get("direct_supervisor_id")
        if direct_supervisor_id:
            # Verify the supervisor is active and has appropriate access level
            supervisor_ref = db.collection("users_db").document(direct_supervisor_id)
            supervisor_data = supervisor_ref.get().to_dict()
            
            if supervisor_data and supervisor_data.get("is_active", True):
                supervisor_access = supervisor_data.get("access_level", 4)
                # Only allow supervisors with access level 1-3 to approve
                if supervisor_access in [1, 2, 3]:
                    return direct_supervisor_id
        
        # Priority 2: Division Head (traditional hierarchy)
        division_id = employee_data.get("division_id")
        if division_id:
            division_ref = db.collection("divisions").document(division_id)
            division_data = division_ref.get().to_dict()
            
            division_head_id = division_data.get("head_employee_id")
            if division_head_id:
                # Verify division head is active
                head_ref = db.collection("users_db").document(division_head_id)
                head_data = head_ref.get().to_dict()
                
                if head_data and head_data.get("is_active", True):
                    return division_head_id
        
        # Priority 3: Escalation to HR/Admin (fallback)
        fallback_approver = get_fallback_approver()
        return fallback_approver
        
    except Exception as e:
        print(f"Error getting approver: {e}")
        return None

def get_fallback_approver():
    """Get fallback approver (HR head or admin) when no direct approver is found"""
    try:
        # Look for HR division head first
        hr_division = db.collection("divisions").where("division_name", "==", "HR").limit(1).stream()
        for div_doc in hr_division:
            div_data = div_doc.to_dict()
            hr_head_id = div_data.get("head_employee_id")
            if hr_head_id:
                return hr_head_id
        
        # If no HR head, look for any admin (access level 1)
        admin_query = db.collection("users_db").where("access_level", "==", 1).where("is_active", "==", True).limit(1).stream()
        for admin_doc in admin_query:
            return admin_doc.id
        
        return None
        
    except Exception as e:
        print(f"Error getting fallback approver: {e}")
        return None

def get_approver_type(employee_id, approver_id):
    """Determine if the approver is direct supervisor or division head"""
    try:
        employee_data = db.collection("users_db").document(employee_id).get().to_dict()
        if not employee_data:
            return "unknown"
        
        # Check if approver is direct supervisor
        if employee_data.get("direct_supervisor_id") == approver_id:
            return "direct_supervisor"
        
        # Check if approver is division head
        division_id = employee_data.get("division_id")
        if division_id:
            division_data = db.collection("divisions").document(division_id).get().to_dict()
            if division_data and division_data.get("head_employee_id") == approver_id:
                return "division_head"
        
        return "fallback_approver"
        
    except Exception as e:
        print(f"Error determining approver type: {e}")
        return "unknown"

def calculate_working_days(start_date, end_date):
    """Calculate working days between two dates (excluding weekends)"""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    working_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday = 0, Sunday = 6
        if current_date.weekday() < 5:  # Monday to Friday
            working_days += 1
        current_date += timedelta(days=1)
    
    return working_days

def get_employee_leave_quota(employee_id):
    """Get employee's current leave quota and usage"""
    try:
        current_year = datetime.now().year
        
        # Get employee data to determine service duration
        employee_ref = db.collection("users_db").document(employee_id)
        employee_data = employee_ref.get().to_dict()
        
        if not employee_data:
            return None
            
        # Calculate annual leave quota based on service duration
        start_date = employee_data.get("start_joining_date")
        if hasattr(start_date, "timestamp"):
            start_date = datetime.fromtimestamp(start_date.timestamp())
        
        service_months = (datetime.now() - start_date).days // 30
        annual_quota = 14 if service_months > 12 else 10
        
        # Get or create leave quota record
        quota_ref = db.collection("leave_quotas").document(f"{employee_id}_{current_year}")
        quota_doc = quota_ref.get()
        
        if not quota_doc.exists:
            # Create initial quota record
            quota_data = {
                "employee_id": employee_id,
                "year": current_year,
                "annual_quota": annual_quota,
                "annual_used": 0,
                "annual_pending": 0,
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP
            }
            quota_ref.set(quota_data)
            return quota_data
        else:
            return quota_doc.to_dict()
            
    except Exception as e:
        print(f"Error getting leave quota: {e}")
        return None

def submit_leave_request(employee_id, leave_data):
    """Submit a new leave request with improved approver logic"""
    try:
        # Validate leave request
        validation_result = validate_leave_request(employee_id, leave_data)
        if not validation_result["valid"]:
            return {"success": False, "message": validation_result["message"]}
        
        # Calculate working days
        working_days = calculate_working_days(leave_data["start_date"], leave_data["end_date"])
        
        # Get approver using improved logic
        approver_id = get_employee_approver(employee_id)
        if not approver_id:
            return {"success": False, "message": "No approver found. Please contact HR."}
        
        # Get approver info for confirmation
        approver_data = db.collection("users_db").document(approver_id).get().to_dict()
        approver_name = approver_data.get("name", "Unknown") if approver_data else "Unknown"
        
        # Create leave request
        leave_request_data = {
            "employee_id": employee_id,
            "leave_type": leave_data["leave_type"],
            "start_date": leave_data["start_date"],
            "end_date": leave_data["end_date"],
            "working_days": working_days,
            "reason": leave_data.get("reason", ""),
            "status": "pending",
            "approver_id": approver_id,
            "approver_name": approver_name,
            "approval_type": get_approver_type(employee_id, approver_id),
            "submitted_at": SERVER_TIMESTAMP,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP
        }
        
        # Add additional fields for certain leave types
        if leave_data["leave_type"] in ["maternity", "marriage"]:
            leave_request_data["emergency_contact"] = leave_data.get("emergency_contact")
        
        if leave_data.get("attachment"):
            leave_request_data["attachment"] = leave_data["attachment"]
        
        # Save to database
        request_ref = db.collection("leave_requests").document()
        leave_request_data["request_id"] = request_ref.id
        request_ref.set(leave_request_data)
        
        # Update pending quota for annual leave
        if leave_data["leave_type"] == "annual":
            update_leave_quota_pending(employee_id, working_days, "add")
        
        return {
            "success": True, 
            "message": f"Leave request submitted successfully. Sent to {approver_name} for approval.",
            "request_id": request_ref.id,
            "approver_name": approver_name
        }
        
    except Exception as e:
        print(f"Error submitting leave request: {e}")
        return {"success": False, "message": f"Error submitting request: {str(e)}"}

def get_pending_approvals_for_approver(approver_id):
    """Get pending leave requests for approval by a specific approver"""
    try:
        query = db.collection("leave_requests").where("approver_id", "==", approver_id).where("status", "==", "pending")
        
        requests = []
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            
            # Enrich with employee data
            employee_data = db.collection("users_db").document(request_data["employee_id"]).get().to_dict()
            if employee_data:
                # Get division and role names from their collections
                division_data = db.collection("divisions").document(employee_data.get("division_id", "")).get().to_dict()
                role_data = db.collection("roles").document(employee_data.get("role_id", "")).get().to_dict()
                
                request_data["employee_name"] = employee_data.get("name")
                request_data["employee_email"] = employee_data.get("email")
                request_data["employee_division"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                request_data["employee_role"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
            
            requests.append(request_data)
        
        # Sort by submission date (newest first)
        requests.sort(key=lambda x: x.get("submitted_at", 0), reverse=True)
        
        return requests
        
    except Exception as e:
        print(f"Error getting pending approvals: {e}")
        return []

def approve_leave_request(request_id, approver_id, comments=""):
    """Approve a leave request"""
    try:
        request_ref = db.collection("leave_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Leave request not found"}
        
        if request_data["approver_id"] != approver_id:
            return {"success": False, "message": "Unauthorized to approve this request"}
        
        if request_data["status"] != "pending":
            return {"success": False, "message": "Request is not pending approval"}
        
        # Get approver info
        approver_data = db.collection("users_db").document(approver_id).get().to_dict()
        approver_name = approver_data.get("name", "Unknown") if approver_data else "Unknown"
        
        # Update request status
        request_ref.update({
            "status": "approved_final",
            "approved_by": approver_id,
            "approved_by_name": approver_name,
            "approved_at": SERVER_TIMESTAMP,
            "approver_comments": comments,
            "updated_at": SERVER_TIMESTAMP
        })
        
        # Update leave quota for annual leave
        if request_data["leave_type"] == "annual":
            employee_id = request_data["employee_id"]
            working_days = request_data["working_days"]
            
            # Move from pending to used
            update_leave_quota_pending(employee_id, working_days, "remove")
            update_leave_quota_used(employee_id, working_days, "add")
        
        return {"success": True, "message": "Leave request approved successfully"}
        
    except Exception as e:
        print(f"Error approving leave request: {e}")
        return {"success": False, "message": f"Error approving request: {str(e)}"}

def reject_leave_request(request_id, approver_id, comments=""):
    """Reject a leave request"""
    try:
        request_ref = db.collection("leave_requests").document(request_id)
        request_data = request_ref.get().to_dict()
        
        if not request_data:
            return {"success": False, "message": "Leave request not found"}
        
        if request_data["approver_id"] != approver_id:
            return {"success": False, "message": "Unauthorized to reject this request"}
        
        if request_data["status"] != "pending":
            return {"success": False, "message": "Request is not pending approval"}
        
        # Get approver info
        approver_data = db.collection("users_db").document(approver_id).get().to_dict()
        approver_name = approver_data.get("name", "Unknown") if approver_data else "Unknown"
        
        # Update request status
        request_ref.update({
            "status": "rejected",
            "rejected_by": approver_id,
            "rejected_by_name": approver_name,
            "rejected_at": SERVER_TIMESTAMP,
            "approver_comments": comments,
            "updated_at": SERVER_TIMESTAMP
        })
        
        # Remove from pending quota for annual leave
        if request_data["leave_type"] == "annual":
            employee_id = request_data["employee_id"]
            working_days = request_data["working_days"]
            update_leave_quota_pending(employee_id, working_days, "remove")
        
        return {"success": True, "message": "Leave request rejected"}
        
    except Exception as e:
        print(f"Error rejecting leave request: {e}")
        return {"success": False, "message": f"Error rejecting request: {str(e)}"}

def validate_leave_request(employee_id, leave_data):
    """Validate leave request against business rules"""
    leave_type = leave_data["leave_type"]
    start_date = datetime.strptime(leave_data["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(leave_data["end_date"], "%Y-%m-%d").date()
    
    # Basic validations
    if start_date > end_date:
        return {"valid": False, "message": "Start date cannot be after end date"}
    
    if start_date < date.today():
        return {"valid": False, "message": "Cannot request leave for past dates"}
    
    working_days = calculate_working_days(start_date, end_date)
    leave_config = LEAVE_TYPES.get(leave_type)
    
    if not leave_config:
        return {"valid": False, "message": "Invalid leave type"}
    
    # Annual leave quota validation
    if leave_type == "annual":
        quota_data = get_employee_leave_quota(employee_id)
        if not quota_data:
            return {"valid": False, "message": "Unable to fetch leave quota"}
        
        available = quota_data["annual_quota"] - quota_data["annual_used"] - quota_data["annual_pending"]
        if working_days > available:
            return {"valid": False, "message": f"Insufficient leave balance. Available: {available} days"}
    
    # Sick leave validation
    elif leave_type == "sick" and working_days > 2:
        return {"valid": False, "message": "Sick leave without medical certificate limited to 2 consecutive days"}
    
    # Menstrual leave validation
    elif leave_type == "menstrual":
        if working_days > 1:
            return {"valid": False, "message": "Menstrual leave is limited to 1 day per request"}
        
        # Check monthly limit
        month_start = start_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        existing_requests = get_employee_leave_requests_by_period(
            employee_id, month_start, month_end, leave_type="menstrual"
        )
        if len(existing_requests) >= 1:
            return {"valid": False, "message": "Maximum 1 menstrual leave per month"}
    
    # Fixed days validation
    elif leave_config.get("fixed_days"):
        fixed_days = leave_config["fixed_days"]
        if working_days != fixed_days:
            return {"valid": False, "message": f"{leave_config['name']} must be exactly {fixed_days} days"}
    
    return {"valid": True, "message": "Valid request"}

def get_employee_leave_requests(employee_id, limit=None, status=None):
    """Get employee's leave requests"""
    try:
        query = db.collection("leave_requests").where("employee_id", "==", employee_id)
        
        if status:
            query = query.where("status", "==", status)
        
        query = query.order_by("submitted_at", direction=firestore.Query.DESCENDING)
        
        if limit:
            query = query.limit(limit)
        
        requests = []
        for doc in query.stream():
            request_data = doc.to_dict()
            request_data["id"] = doc.id
            requests.append(request_data)
        
        return requests
        
    except Exception as e:
        print(f"Error getting leave requests: {e}")
        return []

def get_employee_leave_requests_by_period(employee_id, start_date, end_date, leave_type=None):
    """Get employee leave requests within a specific period"""
    try:
        query = db.collection("leave_requests").where("employee_id", "==", employee_id)
        
        if leave_type:
            query = query.where("leave_type", "==", leave_type)
        
        requests = []
        for doc in query.stream():
            request_data = doc.to_dict()
            request_start = datetime.strptime(request_data["start_date"], "%Y-%m-%d").date()
            
            if start_date <= request_start <= end_date:
                requests.append(request_data)
        
        return requests
        
    except Exception as e:
        print(f"Error getting leave requests by period: {e}")
        return []

def update_leave_quota_pending(employee_id, days, operation):
    """Update pending leave quota"""
    try:
        current_year = datetime.now().year
        quota_ref = db.collection("leave_quotas").document(f"{employee_id}_{current_year}")
        quota_data = quota_ref.get().to_dict()
        
        if quota_data:
            current_pending = quota_data.get("annual_pending", 0)
            
            if operation == "add":
                new_pending = current_pending + days
            else:  # remove
                new_pending = max(0, current_pending - days)
            
            quota_ref.update({
                "annual_pending": new_pending,
                "updated_at": SERVER_TIMESTAMP
            })
            
    except Exception as e:
        print(f"Error updating pending quota: {e}")

def update_leave_quota_used(employee_id, days, operation):
    """Update used leave quota"""
    try:
        current_year = datetime.now().year
        quota_ref = db.collection("leave_quotas").document(f"{employee_id}_{current_year}")
        quota_data = quota_ref.get().to_dict()
        
        if quota_data:
            current_used = quota_data.get("annual_used", 0)
            
            if operation == "add":
                new_used = current_used + days
            else:  # remove
                new_used = max(0, current_used - days)
            
            quota_ref.update({
                "annual_used": new_used,
                "updated_at": SERVER_TIMESTAMP
            })
            
    except Exception as e:
        print(f"Error updating used quota: {e}")

def reset_annual_leave_quotas():
    """Reset annual leave quotas for new year (Admin function)"""
    try:
        current_year = datetime.now().year
        
        # Get all employees
        employees = db.collection("users_db").where("is_active", "==", True).stream()
        
        reset_count = 0
        for employee_doc in employees:
            employee_data = employee_doc.to_dict()
            employee_id = employee_doc.id
            
            # Calculate new quota based on service duration
            start_date = employee_data.get("start_joining_date")
            if hasattr(start_date, "timestamp"):
                start_date = datetime.fromtimestamp(start_date.timestamp())
            
            service_months = (datetime.now() - start_date).days // 30
            annual_quota = 14 if service_months > 12 else 10
            
            # Create new quota record
            quota_ref = db.collection("leave_quotas").document(f"{employee_id}_{current_year}")
            quota_data = {
                "employee_id": employee_id,
                "year": current_year,
                "annual_quota": annual_quota,
                "annual_used": 0,
                "annual_pending": 0,
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP
            }
            quota_ref.set(quota_data)
            reset_count += 1
        
        return {"success": True, "message": f"Reset quotas for {reset_count} employees"}
        
    except Exception as e:
        print(f"Error resetting annual quotas: {e}")
        return {"success": False, "message": f"Error resetting quotas: {str(e)}"}

def get_leave_statistics(employee_id=None, division_id=None, year=None):
    """Get leave statistics for reporting"""
    try:
        if not year:
            year = datetime.now().year
        
        stats = {
            "total_requests": 0,
            "approved_requests": 0,
            "pending_requests": 0,
            "rejected_requests": 0,
            "by_leave_type": {},
            "total_days_taken": 0
        }
        
        query = db.collection("leave_requests")
        
        if employee_id:
            query = query.where("employee_id", "==", employee_id)
        
        # Filter by year
        for doc in query.stream():
            request_data = doc.to_dict()
            request_year = datetime.strptime(request_data["start_date"], "%Y-%m-%d").year
            
            if request_year != year:
                continue
            
            stats["total_requests"] += 1
            
            status = request_data.get("status", "pending")
            if status == "approved_final":
                stats["approved_requests"] += 1
                stats["total_days_taken"] += request_data.get("working_days", 0)
            elif status == "pending":
                stats["pending_requests"] += 1
            elif status == "rejected":
                stats["rejected_requests"] += 1
            
            # By leave type
            leave_type = request_data.get("leave_type", "unknown")
            if leave_type not in stats["by_leave_type"]:
                stats["by_leave_type"][leave_type] = 0
            stats["by_leave_type"][leave_type] += 1
        
        return stats
        
    except Exception as e:
        print(f"Error getting leave statistics: {e}")
        return None

def get_team_members(supervisor_id):
    """Get all team members who report to a specific supervisor"""
    try:
        # Get employees where direct_supervisor_id equals supervisor_id
        direct_reports = []
        direct_query = db.collection("users_db").where("direct_supervisor_id", "==", supervisor_id).stream()
        
        for doc in direct_query:
            employee_data = doc.to_dict()
            employee_data["employee_id"] = doc.id
            
            # Get division and role names
            if employee_data.get("division_id"):
                division_data = db.collection("divisions").document(employee_data["division_id"]).get().to_dict()
                employee_data["division_name"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
            
            if employee_data.get("role_id"):
                role_data = db.collection("roles").document(employee_data["role_id"]).get().to_dict()
                employee_data["role_name"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
            
            direct_reports.append(employee_data)
        
        # Also get employees from divisions where this person is head
        division_reports = []
        division_query = db.collection("divisions").where("head_employee_id", "==", supervisor_id).stream()
        
        for div_doc in division_query:
            division_id = div_doc.id
            # Get all employees in this division who don't have a direct supervisor
            emp_query = db.collection("users_db").where("division_id", "==", division_id).stream()
            
            for emp_doc in emp_query:
                emp_data = emp_doc.to_dict()
                # Only include if they don't have a direct supervisor or if supervisor is this person
                if not emp_data.get("direct_supervisor_id") or emp_data.get("direct_supervisor_id") == supervisor_id:
                    emp_data["employee_id"] = emp_doc.id
                    
                    # Get division and role names
                    if emp_data.get("division_id"):
                        division_data = db.collection("divisions").document(emp_data["division_id"]).get().to_dict()
                        emp_data["division_name"] = division_data.get("division_name", "Unknown") if division_data else "Unknown"
                    
                    if emp_data.get("role_id"):
                        role_data = db.collection("roles").document(emp_data["role_id"]).get().to_dict()
                        emp_data["role_name"] = role_data.get("role_name", "Unknown") if role_data else "Unknown"
                    
                    # Avoid duplicates from direct reports
                    if emp_data["employee_id"] not in [dr["employee_id"] for dr in direct_reports]:
                        division_reports.append(emp_data)
        
        return {
            "direct_reports": direct_reports,
            "division_reports": division_reports,
            "total_count": len(direct_reports) + len(division_reports)
        }
        
    except Exception as e:
        print(f"Error getting team members: {e}")
        return {"direct_reports": [], "division_reports": [], "total_count": 0}

def get_approval_chain(employee_id):
    """Get the complete approval chain for an employee"""
    try:
        employee_ref = db.collection("users_db").document(employee_id)
        employee_data = employee_ref.get().to_dict()
        
        if not employee_data:
            return []
        
        approval_chain = []
        
        # Level 1: Direct Supervisor
        direct_supervisor_id = employee_data.get("direct_supervisor_id")
        if direct_supervisor_id:
            supervisor_data = db.collection("users_db").document(direct_supervisor_id).get().to_dict()
            if supervisor_data:
                # Get role name
                role_data = db.collection("roles").document(supervisor_data.get("role_id", "")).get().to_dict()
                role_name = role_data.get("role_name", "Unknown") if role_data else "Unknown"
                
                approval_chain.append({
                    "level": 1,
                    "type": "direct_supervisor",
                    "employee_id": direct_supervisor_id,
                    "name": supervisor_data.get("name"),
                    "role": role_name,
                    "access_level": supervisor_data.get("access_level")
                })
        
        # Level 2: Division Head (if different from direct supervisor)
        division_id = employee_data.get("division_id")
        if division_id:
            division_data = db.collection("divisions").document(division_id).get().to_dict()
            division_head_id = division_data.get("head_employee_id")
            
            if division_head_id and division_head_id != direct_supervisor_id:
                head_data = db.collection("users_db").document(division_head_id).get().to_dict()
                if head_data:
                    # Get role name
                    role_data = db.collection("roles").document(head_data.get("role_id", "")).get().to_dict()
                    role_name = role_data.get("role_name", "Unknown") if role_data else "Unknown"
                    
                    approval_chain.append({
                        "level": 2,
                        "type": "division_head",
                        "employee_id": division_head_id,
                        "name": head_data.get("name"),
                        "role": role_name,
                        "access_level": head_data.get("access_level")
                    })
        
        return approval_chain
        
    except Exception as e:
        print(f"Error getting approval chain: {e}")
        return []
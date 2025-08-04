# Enhanced database.py with direct supervisor support
import streamlit as st
import streamlit_authenticator as stauth

from google.cloud import firestore
from firebase_admin import firestore, credentials, initialize_app
from google.oauth2 import service_account
from firebase_admin.firestore import SERVER_TIMESTAMP
import firebase_admin

from datetime import datetime, time, date

@st.cache_resource
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

def get_all_auth():
    users_auth = db.collection("users_auth") # Dont forget to change db name after normalization
    return users_auth

def fetch_user_by_username(username):
    """
    Fetch a user's data from Firestore based on their username.

    Args:
        username: The username to search for.

    Returns:
        A dictionary containing the user's data, or None if not found.
    """
    users_auth = get_all_auth()
    
    query = users_auth.where("username", "==", username).get()
    employee_id = query[0].to_dict()['employee_id']

    user = db.collection("users_db").document(employee_id).get()
    # query = users.where("user_id", "==", user_id).get()
    print('user data is :', user)
    try:
        return user.to_dict()
    except:
        return None

# Check if the same name and username exist
def is_duplicate_user(name, username):
    users_ref = db.collection("users_auth")
    query = users_ref.where("name", "==", name).where("username", "==", username).get()

    # If any document matches the query, it's a duplicate
    if query:
        return True
    return False

def add_user(user_data):
    """
    Adds a user to Firestore with data normalized across two collections: `users_auth` and `users_db`.

    Parameters:
        user_data (dict): A dictionary containing user data to be added.

    Returns:
        tuple: (auth_doc_id, user_doc_id) - The auto-generated document IDs for `users_auth` and `users_db`.
    """
    if is_duplicate_user(user_data["name"], user_data["username"]):
        print("Registration failed: Name and username already exist!")
    else:
        try:
            # Reference Firestore collections
            users_auth_collection = db.collection("users_auth")
            users_db_collection = db.collection("users_db")
            
            # Step 1: Save data to `users_db` and get the auto-generated document ID
            user_db_data = {
                "email": user_data["email"],
                "phone_number": user_data["phone_number"],
                "profile_picture": user_data["profile_picture"],
                "role": user_data["role"],
                "access_level": user_data["access_level"],
                "status": user_data["status"],
                "division": user_data["division"],
                "position": user_data["position"],
                "join_date": user_data["join_date"],
                "bpjs_number": user_data["bpjs_number"],
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP,
                "default_wfh_schedule": user_data["default_wfh_schedule"]
            }
            
            user_doc_ref = users_db_collection.document()
            user_db_data["user_id"] = user_doc_ref.id  # Auto-generated `user_id`
            user_doc_ref.set(user_db_data)
            
            # Step 2: Save authentication data to `users_auth` with hashed password
            if "password" in user_data:
                hasher = stauth.Hasher()
                hashed_password = hasher.generate([user_data["password"]])[0]

                # hashed_password = stauth.Hasher(user_data["password"].split()).generate()[0]
            else:
                raise ValueError("Password field is required for authentication.")

            auth_data = {
                "auth_id": None,  # This will be set to the auto-generated document ID
                "user_id": user_doc_ref.id,
                "username": user_data["username"],
                "name": user_data["name"],
                "password": hashed_password,
                "last_login": None  # Set to `None` initially, update later upon user login
            }
            auth_doc_ref = users_auth_collection.document()
            auth_data["auth_id"] = auth_doc_ref.id  # Auto-generated `auth_id`
            auth_doc_ref.set(auth_data)
            
            print(f"User added successfully with auth_id: {auth_doc_ref.id}, user_id: {user_doc_ref.id}")
            return auth_doc_ref.id, user_doc_ref.id

        except Exception as e:
            # print(f"Error adding user: {e}")
            # print(f"User data pass: {user_data["password"]}")
            return None, None

def to_datetime(d):
    if isinstance(d, date):
        return datetime.combine(d, time())
    return d

def get_or_create_role(role_name, description=None):
    roles_ref = db.collection("roles")
    query = roles_ref.where("role_name", "==", role_name).limit(1).stream()
    for doc in query:
        return doc.id  # Already exists

    # Add new role
    doc_ref = roles_ref.document()  # Create a new doc with an auto-generated ID
    doc_id = doc_ref.id
    doc_ref.set({
        "role_id": doc_id,
        "role_name": role_name,
    })
    return doc_id

def get_or_create_division(division_name, head_employee_id=None):
    divisions_ref = db.collection("divisions")
    query = divisions_ref.where("division_name", "==", division_name).limit(1).stream()
    for doc in query:
        return doc.id  # Already exists

    # Add new division
    doc_ref = divisions_ref.document()
    doc_id = doc_ref.id
    doc_ref.set({
        "division_id": doc_id,
        "division_name": division_name,
        "head_employee_id": head_employee_id
    })
    return doc_id

def is_duplicate_user(username, email):
    users_ref = db.collection("users")
    employees_ref = db.collection("employees")
    user_query = users_ref.where("username", "==", username).limit(1).stream()
    if any(user_query):
        return True
    employee_query = employees_ref.where("email", "==", email).limit(1).stream()
    return any(employee_query)

def add_user_to_firestore(user_data):
    """
    Enhanced user creation function with direct supervisor support
    """
    name = user_data.get("name")
    email = user_data.get("email")
    username = user_data.get("username")
    password = user_data.get("password")
    role_name = user_data.get("role_name")
    division_name = user_data.get("division_name")
    join_date = user_data.get("join_date")
    access_level = user_data.get("access_level")
    direct_supervisor_id = user_data.get("direct_supervisor_id")  # NEW: Direct supervisor support

    if not all([name, email, username, password, role_name, division_name, join_date]):
        print("Missing required user data fields.")
        return None, None

    if is_duplicate_user(username, email):
        print("Duplicate username or email.")
        return None, None

    try:
        role_doc_id = get_or_create_role(role_name)
        division_doc_id = get_or_create_division(division_name)

        employees_ref = db.collection("users_db")
        employee_data = {
            "name": name,
            "email": email,
            "phone_number": user_data.get("phone_number"),
            "address": user_data.get("address"),
            "date_of_birth": to_datetime(user_data.get("date_of_birth")),
            "start_joining_date": to_datetime(join_date),
            "role_id": role_doc_id,
            "role_name": role_name,  # Store role name for easy access
            "division_id": division_doc_id,
            "division_name": division_name,  # Store division name for easy access
            "access_level": access_level,
            "NIP": str(user_data.get("NIP")) if user_data.get("NIP") else None,
            "employee_status": user_data.get("employee_status", "Unknown"),
            "place_of_birth": str(user_data.get("place_of_birth")) if user_data.get("place_of_birth") else "Unknown",
            "start_joining_date": to_datetime(user_data.get("start_joining_date", join_date)),
            "bpjs_kesehatan_number": str(user_data.get("bpjs_kesehatan_number")) if user_data.get("bpjs_kesehatan_number") else None,
            "bpjs_ketenagakerjaan_number": str(user_data.get("bpjs_ketenagakerjaan_number")) if user_data.get("bpjs_ketenagakerjaan_number") else None,
            "loan_eligibility_score": user_data.get("loan_eligibility_score", 0.00),
            "default_wfh_days": ", ".join(user_data.get("default_wfh_days", [])) if isinstance(user_data.get("default_wfh_days"), list) else user_data.get("default_wfh_days"),
            "is_active": user_data.get("is_active", True),
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        }
        
        # NEW: Add direct supervisor if provided
        if direct_supervisor_id:
            employee_data["direct_supervisor_id"] = direct_supervisor_id
            
            # Optionally, also store supervisor name for easy reference
            try:
                supervisor_data = db.collection("users_db").document(direct_supervisor_id).get().to_dict()
                if supervisor_data:
                    employee_data["direct_supervisor_name"] = supervisor_data.get("name", "Unknown")
            except Exception as e:
                print(f"Warning: Could not fetch supervisor name: {e}")
        
        employee_doc_ref = employees_ref.document()
        employee_id = employee_doc_ref.id
        employee_data["employee_id"] = employee_id  # Auto-generated `user_id`

        employee_doc_ref.set(employee_data)

        users_ref = db.collection("users_auth")

        # Create a dictionary for the user credentials so we can use stauth.Hasher
        # to hash the password
        credentials_dict = {
            "usernames": {
                username: {
                    "name": name,
                    "email": email,
                    "password": password
                }
            }
        }

        hashed_credentials = stauth.Hasher.hash_passwords(credentials_dict)
        _user_cred = hashed_credentials['usernames'][username]
        hashed_password = _user_cred['password']

        user_auth_data = {
            "auth_id": None,  # This will be set to the auto-generated document ID
            "username": username,
            "name": name,
            "password": hashed_password,
            "employee_id": employee_id,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        }
        user_doc_ref = users_ref.document()
        user_id = user_doc_ref.id
        user_auth_data["auth_id"] = user_id  # Auto-generated `auth_id`
        
        user_doc_ref.set(user_auth_data)

        print(f"User '{username}' added. User ID: {user_id}, Employee ID: {employee_id}")
        if direct_supervisor_id:
            print(f"Direct supervisor assigned: {direct_supervisor_id}")
        
        return user_id, employee_id

    except Exception as e:
        print(f"Error adding user (add_user_to_firestore): {e}")
        print(f"User data pass: {password}")
        return None, None

def get_potential_supervisors():
    """
    Get all users who can be supervisors (access levels 1-3) and are active
    """
    try:
        supervisors_query = db.collection("users_db").where("access_level", "in", [1, 2, 3]).where("is_active", "==", True).stream()
        supervisors = []
        
        for doc in supervisors_query:
            supervisor_data = doc.to_dict()
            supervisor_data["employee_id"] = doc.id
            supervisors.append(supervisor_data)
        
        # Sort by name for better UX
        supervisors.sort(key=lambda x: x.get("name", ""))
        return supervisors
        
    except Exception as e:
        print(f"Error getting potential supervisors: {e}")
        return []

def get_direct_reports(supervisor_id):
    """
    Get all employees who report directly to a specific supervisor
    """
    try:
        reports_query = db.collection("users_db").where("direct_supervisor_id", "==", supervisor_id).where("is_active", "==", True).stream()
        reports = []
        
        for doc in reports_query:
            report_data = doc.to_dict()
            report_data["employee_id"] = doc.id
            reports.append(report_data)
        
        return reports
        
    except Exception as e:
        print(f"Error getting direct reports: {e}")
        return []

def update_employee_supervisor(employee_id, new_supervisor_id):
    """
    Update an employee's direct supervisor
    """
    try:
        employee_ref = db.collection("users_db").document(employee_id)
        
        update_data = {
            "updated_at": SERVER_TIMESTAMP
        }
        
        if new_supervisor_id:
            # Get supervisor name for easy reference
            supervisor_data = db.collection("users_db").document(new_supervisor_id).get().to_dict()
            supervisor_name = supervisor_data.get("name", "Unknown") if supervisor_data else "Unknown"
            
            update_data["direct_supervisor_id"] = new_supervisor_id
            update_data["direct_supervisor_name"] = supervisor_name
        else:
            # Remove supervisor assignment
            update_data["direct_supervisor_id"] = None
            update_data["direct_supervisor_name"] = None
        
        employee_ref.update(update_data)
        return True
        
    except Exception as e:
        print(f"Error updating employee supervisor: {e}")
        return False

def get_employee_hierarchy(employee_id):
    """
    Get the complete reporting hierarchy for an employee
    Returns: {
        "employee": employee_data,
        "direct_supervisor": supervisor_data or None,
        "division_head": division_head_data or None,
        "direct_reports": [list of direct reports]
    }
    """
    try:
        # Get employee data
        employee_data = db.collection("users_db").document(employee_id).get().to_dict()
        if not employee_data:
            return None
        
        employee_data["employee_id"] = employee_id
        hierarchy = {
            "employee": employee_data,
            "direct_supervisor": None,
            "division_head": None,
            "direct_reports": []
        }
        
        # Get direct supervisor
        supervisor_id = employee_data.get("direct_supervisor_id")
        if supervisor_id:
            supervisor_data = db.collection("users_db").document(supervisor_id).get().to_dict()
            if supervisor_data:
                supervisor_data["employee_id"] = supervisor_id
                hierarchy["direct_supervisor"] = supervisor_data
        
        # Get division head
        division_id = employee_data.get("division_id")
        if division_id:
            division_data = db.collection("divisions").document(division_id).get().to_dict()
            if division_data and division_data.get("head_employee_id"):
                head_id = division_data["head_employee_id"]
                if head_id != supervisor_id:  # Only if different from direct supervisor
                    head_data = db.collection("users_db").document(head_id).get().to_dict()
                    if head_data:
                        head_data["employee_id"] = head_id
                        hierarchy["division_head"] = head_data
        
        # Get direct reports
        hierarchy["direct_reports"] = get_direct_reports(employee_id)
        
        return hierarchy
        
    except Exception as e:
        print(f"Error getting employee hierarchy: {e}")
        return None

def validate_supervisor_assignment(employee_id, supervisor_id):
    """
    Validate that a supervisor assignment is valid
    - Supervisor must exist and be active
    - Supervisor must have appropriate access level (1-3)
    - Cannot create circular reporting (employee supervising their own supervisor)
    """
    try:
        if not supervisor_id:
            return True, "No supervisor assignment"
        
        # Check if supervisor exists and is active
        supervisor_data = db.collection("users_db").document(supervisor_id).get().to_dict()
        if not supervisor_data:
            return False, "Supervisor not found"
        
        if not supervisor_data.get("is_active", True):
            return False, "Supervisor is not active"
        
        # Check access level
        supervisor_access = supervisor_data.get("access_level", 4)
        if supervisor_access not in [1, 2, 3]:
            return False, "Supervisor must have access level 1, 2, or 3"
        
        # Check for circular reporting
        def check_circular_reporting(current_id, target_id, depth=0):
            if depth > 10:  # Prevent infinite loops
                return True
            
            if current_id == target_id:
                return True
            
            current_data = db.collection("users_db").document(current_id).get().to_dict()
            if not current_data:
                return False
            
            next_supervisor = current_data.get("direct_supervisor_id")
            if not next_supervisor:
                return False
            
            return check_circular_reporting(next_supervisor, target_id, depth + 1)
        
        if check_circular_reporting(supervisor_id, employee_id):
            return False, "Circular reporting relationship detected"
        
        return True, "Valid supervisor assignment"
        
    except Exception as e:
        return False, f"Error validating supervisor assignment: {e}"

@st.cache_resource(ttl=300)  # refresh every 5 minutes (optional)
def get_all_roles():
    roles_ref = db.collection("roles").stream()
    return {doc.id: doc.to_dict() for doc in roles_ref}

@st.cache_resource(ttl=300)
def get_all_divisions():
    divisions_ref = db.collection("divisions").stream()
    return {doc.id: doc.to_dict() for doc in divisions_ref}

def enrich_user_data(user_data):
    """
    Enhanced user data enrichment with supervisor information
    """
    roles = get_all_roles()
    divisions = get_all_divisions()

    role = roles.get(user_data.get("role_id"), {}).get("role_name", "Unknown")
    division = divisions.get(user_data.get("division_id"), {}).get("division_name", "Unknown")

    enriched = {
        **user_data,
        "role_name": role,
        "division_name": division,
    }
    
    # Add supervisor information if available
    supervisor_id = user_data.get("direct_supervisor_id")
    if supervisor_id:
        try:
            supervisor_data = db.collection("users_db").document(supervisor_id).get().to_dict()
            if supervisor_data:
                enriched["supervisor_name"] = supervisor_data.get("name", "Unknown")
                enriched["supervisor_email"] = supervisor_data.get("email", "Unknown")
                enriched["supervisor_role"] = supervisor_data.get("role_name", "Unknown")
        except:
            enriched["supervisor_name"] = "Unknown"
    
    return enriched

def get_organizational_stats():
    """
    Get organizational statistics for admin dashboard
    """
    try:
        stats = {
            "total_employees": 0,
            "active_employees": 0,
            "employees_with_supervisors": 0,
            "supervisors_count": 0,
            "divisions_count": 0,
            "by_access_level": {1: 0, 2: 0, 3: 0, 4: 0},
            "by_division": {}
        }
        
        # Get employee stats
        employees_query = db.collection("users_db").stream()
        
        for doc in employees_query:
            employee_data = doc.to_dict()
            stats["total_employees"] += 1
            
            if employee_data.get("is_active", True):
                stats["active_employees"] += 1
            
            if employee_data.get("direct_supervisor_id"):
                stats["employees_with_supervisors"] += 1
            
            access_level = employee_data.get("access_level", 4)
            stats["by_access_level"][access_level] = stats["by_access_level"].get(access_level, 0) + 1
            
            if access_level in [1, 2, 3]:
                stats["supervisors_count"] += 1
            
            division = employee_data.get("division_name", "Unknown")
            stats["by_division"][division] = stats["by_division"].get(division, 0) + 1
        
        # Get divisions count
        divisions_query = db.collection("divisions").stream()
        stats["divisions_count"] = len(list(divisions_query))
        
        return stats
        
    except Exception as e:
        print(f"Error getting organizational stats: {e}")
        return None

def update_user():
    pass

def delete_user():
    pass

# Initialize database connection
db = get_db()
# utils/firebase_storage.py - FIXED version with proper credential handling
import streamlit as st
from google.cloud import storage
from firebase_admin import storage as admin_storage
import firebase_admin
from firebase_admin import credentials
import os
import uuid
from datetime import datetime, timedelta
import mimetypes
import tempfile
from pathlib import Path
import json

class FirebaseStorageManager:
    """Manage file uploads and downloads with Firebase Cloud Storage - FIXED VERSION"""
    
    def __init__(self):
        self.bucket_name = st.secrets.get("firebase_storage", {}).get("bucket_name")
        self.max_file_size = st.secrets.get("firebase_storage", {}).get("max_file_size_mb", 10) * 1024 * 1024  # Convert to bytes
        self.allowed_extensions = st.secrets.get("firebase_storage", {}).get("allowed_extensions", [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"])
        
        # Initialize Firebase Admin if not already done
        self._init_firebase_admin()
        
        # Get storage bucket
        try:
            if self.bucket_name:
                self.bucket = admin_storage.bucket(self.bucket_name)
            else:
                st.error("Firebase Storage bucket name not configured in secrets")
                self.bucket = None
        except Exception as e:
            st.error(f"Failed to initialize Firebase Storage bucket: {e}")
            self.bucket = None
    
    def _init_firebase_admin(self):
        """Initialize Firebase Admin SDK if not already initialized - FIXED VERSION"""
        try:
            # Check if Firebase Admin is already initialized
            firebase_admin.get_app()
            st.info("Firebase Admin already initialized")
        except ValueError:
            # Initialize Firebase Admin with service account
            try:
                # FIXED: Get credentials from secrets and handle them properly
                firebase_credentials_dict = dict(st.secrets["firebase_auth"])
                
                # Create credentials object from dictionary
                cred = credentials.Certificate(firebase_credentials_dict)
                
                # Initialize Firebase Admin
                firebase_admin.initialize_app(cred, {
                    'storageBucket': self.bucket_name
                })
                
                st.success("✅ Firebase Admin initialized successfully")
                
            except Exception as e:
                st.error(f"Failed to initialize Firebase Admin: {e}")
                st.error("Please check your firebase_auth configuration in secrets.toml")
                
                # Show debug info (remove in production)
                if st.secrets.get("environment") == "development":
                    st.write("Debug - Available secrets keys:", list(st.secrets.keys()))
                    if "firebase_auth" in st.secrets:
                        auth_keys = [k for k in st.secrets["firebase_auth"].keys() if k != "private_key"]
                        st.write("Debug - firebase_auth keys:", auth_keys)
    
    def validate_file(self, uploaded_file):
        """Validate uploaded file"""
        errors = []
        
        if not uploaded_file:
            return False, ["No file provided"]
        
        # Check file size
        if uploaded_file.size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            errors.append(f"File size ({uploaded_file.size / (1024 * 1024):.1f} MB) exceeds maximum allowed size ({max_mb} MB)")
        
        # Check file extension
        file_extension = Path(uploaded_file.name).suffix.lower()
        if file_extension not in self.allowed_extensions:
            errors.append(f"File type '{file_extension}' not allowed. Allowed types: {', '.join(self.allowed_extensions)}")
        
        # Check file name
        if len(uploaded_file.name) > 255:
            errors.append("File name too long (maximum 255 characters)")
        
        # Check for invalid characters in filename
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        if any(char in uploaded_file.name for char in invalid_chars):
            errors.append("File name contains invalid characters")
        
        return len(errors) == 0, errors
    
    def generate_secure_filename(self, original_filename, employee_id, request_type="leave"):
        """Generate a secure, unique filename"""
        # Get file extension
        file_extension = Path(original_filename).suffix.lower()
        
        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate unique ID
        unique_id = str(uuid.uuid4())[:8]
        
        # Clean original filename (remove extension and invalid chars)
        clean_name = Path(original_filename).stem
        clean_name = "".join(c for c in clean_name if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_name = clean_name[:50]  # Limit length
        
        # Create secure filename
        secure_filename = f"{request_type}_{employee_id}_{timestamp}_{unique_id}_{clean_name}{file_extension}"
        
        return secure_filename
    
    def upload_file(self, uploaded_file, employee_id, request_type="leave", folder="documents"):
        """
        Upload file to Firebase Cloud Storage - FIXED VERSION
        
        Args:
            uploaded_file: Streamlit uploaded file object
            employee_id: Employee ID for organizing files
            request_type: Type of request (leave, overtime, etc.)
            folder: Folder structure in storage
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "file_url": str or None,
                "file_path": str or None,
                "file_metadata": dict or None
            }
        """
        try:
            if not self.bucket:
                return {
                    "success": False,
                    "message": "Firebase Storage not properly initialized. Check your configuration.",
                    "file_url": None,
                    "file_path": None,
                    "file_metadata": None
                }
            
            # Validate file
            is_valid, validation_errors = self.validate_file(uploaded_file)
            if not is_valid:
                return {
                    "success": False,
                    "message": f"File validation failed: {'; '.join(validation_errors)}",
                    "file_url": None,
                    "file_path": None,
                    "file_metadata": None
                }
            
            # Generate secure filename and path
            secure_filename = self.generate_secure_filename(uploaded_file.name, employee_id, request_type)
            file_path = f"{folder}/{request_type}/{employee_id}/{secure_filename}"
            
            # Get file content
            file_content = uploaded_file.getvalue()
            
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(uploaded_file.name)
            if not mime_type:
                # Default MIME types for common extensions
                mime_defaults = {
                    '.pdf': 'application/pdf',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                }
                file_ext = Path(uploaded_file.name).suffix.lower()
                mime_type = mime_defaults.get(file_ext, "application/octet-stream")
            
            # Create blob and upload
            blob = self.bucket.blob(file_path)
            
            # Set metadata
            blob.metadata = {
                "original_filename": uploaded_file.name,
                "uploaded_by": employee_id,
                "upload_timestamp": datetime.now().isoformat(),
                "request_type": request_type,
                "file_size": str(uploaded_file.size),
                "mime_type": mime_type
            }
            
            # Upload file with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    blob.upload_from_string(
                        file_content,
                        content_type=mime_type
                    )
                    break  # Success, exit retry loop
                except Exception as upload_error:
                    if attempt == max_retries - 1:  # Last attempt
                        raise upload_error
                    st.warning(f"Upload attempt {attempt + 1} failed, retrying...")
            
            # Get download URL (signed URL valid for 24 hours)
            download_url = self.get_download_url(file_path)
            
            file_metadata = {
                "original_filename": uploaded_file.name,
                "secure_filename": secure_filename,
                "file_size": uploaded_file.size,
                "mime_type": mime_type,
                "upload_timestamp": datetime.now().isoformat(),
                "uploaded_by": employee_id,
                "request_type": request_type
            }
            
            return {
                "success": True,
                "message": f"File '{uploaded_file.name}' uploaded successfully",
                "file_url": download_url,
                "file_path": file_path,
                "file_metadata": file_metadata
            }
            
        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            st.error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "file_url": None,
                "file_path": None,
                "file_metadata": None
            }
    
    def get_download_url(self, file_path, expiration_hours=24):
        """
        Generate a signed URL for downloading a file - FIXED VERSION
        
        Args:
            file_path: Path to file in storage
            expiration_hours: How long the URL should be valid
            
        Returns:
            str: Signed download URL or None
        """
        try:
            if not self.bucket:
                st.warning("Storage bucket not available for generating download URL")
                return None
            
            blob = self.bucket.blob(file_path)
            
            # Check if file exists
            if not blob.exists():
                st.warning(f"File not found: {file_path}")
                return None
            
            # Generate signed URL
            expiration = datetime.utcnow() + timedelta(hours=expiration_hours)
            signed_url = blob.generate_signed_url(
                expiration=expiration,
                method='GET'
            )
            
            return signed_url
            
        except Exception as e:
            st.error(f"Error generating download URL: {e}")
            return None
    
    def delete_file(self, file_path):
        """
        Delete a file from Firebase Cloud Storage
        
        Args:
            file_path: Path to file in storage
            
        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            if not self.bucket:
                return {"success": False, "message": "Firebase Storage not initialized"}
            
            blob = self.bucket.blob(file_path)
            
            if blob.exists():
                blob.delete()
                return {"success": True, "message": "File deleted successfully"}
            else:
                return {"success": False, "message": "File not found"}
                
        except Exception as e:
            return {"success": False, "message": f"Delete failed: {str(e)}"}
    
    def get_file_info(self, file_path):
        """
        Get information about a specific file
        
        Args:
            file_path: Path to file in storage
            
        Returns:
            dict: File information or None
        """
        try:
            if not self.bucket:
                return None
            
            blob = self.bucket.blob(file_path)
            
            if not blob.exists():
                return None
            
            # Reload blob to get latest metadata
            blob.reload()
            
            return {
                "name": blob.name,
                "size": blob.size,
                "created": blob.time_created,
                "updated": blob.updated,
                "metadata": blob.metadata or {},
                "content_type": blob.content_type,
                "download_url": self.get_download_url(file_path, expiration_hours=1)
            }
            
        except Exception as e:
            st.error(f"Error getting file info: {e}")
            return None

# Storage configuration helper
def get_storage_config():
    """Get storage configuration from secrets"""
    try:
        return {
            "bucket_name": st.secrets.get("firebase_storage", {}).get("bucket_name"),
            "max_file_size_mb": st.secrets.get("firebase_storage", {}).get("max_file_size_mb", 10),
            "allowed_extensions": st.secrets.get("firebase_storage", {}).get("allowed_extensions", [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]),
            "auto_delete_days": st.secrets.get("firebase_storage", {}).get("auto_delete_days", 365)
        }
    except Exception as e:
        st.error(f"Error loading storage configuration: {e}")
        return {
            "bucket_name": None,
            "max_file_size_mb": 10,
            "allowed_extensions": [".pdf", ".jpg", ".jpeg", ".png"],
            "auto_delete_days": 365
        }

# UI Components for file handling
def file_upload_component(employee_id, request_type="leave", allowed_types=None):
    """
    Streamlit component for file upload with Firebase Storage - FIXED VERSION
    
    Args:
        employee_id: Employee ID
        request_type: Type of request
        allowed_types: List of allowed file extensions
        
    Returns:
        dict: Upload result
    """
    # Get config first
    config = get_storage_config()
    
    if not config["bucket_name"]:
        st.error("📁 File upload not available - Firebase Storage not configured")
        st.info("Contact your administrator to enable file uploads")
        return None
    
    # Try to initialize storage manager
    try:
        storage_manager = FirebaseStorageManager()
        
        if not storage_manager.bucket:
            st.error("📁 File upload not available - Storage initialization failed")
            return None
            
    except Exception as e:
        st.error(f"📁 File upload error: {e}")
        return None
    
    max_size_mb = config["max_file_size_mb"]
    
    if allowed_types is None:
        allowed_types = config["allowed_extensions"]
    
    # File upload widget
    st.markdown("### 📎 Attach Supporting Documents")
    st.info(f"📋 **Allowed formats:** {', '.join(allowed_types)} | **Max size:** {max_size_mb} MB")
    
    uploaded_file = st.file_uploader(
        "Choose file",
        type=[ext.replace(".", "") for ext in allowed_types],
        help=f"Upload supporting documents (max {max_size_mb} MB)",
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        # Show file preview
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**📄 Selected:** {uploaded_file.name}")
            st.write(f"**📊 Size:** {uploaded_file.size / (1024 * 1024):.2f} MB")
            st.write(f"**🏷️ Type:** {Path(uploaded_file.name).suffix.upper()}")
        
        with col2:
            if st.button("🚀 Upload File", type="primary"):
                with st.spinner("Uploading file..."):
                    result = storage_manager.upload_file(
                        uploaded_file, 
                        employee_id, 
                        request_type
                    )
                    
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        return result
                    else:
                        st.error(f"❌ {result['message']}")
                        return None
    
    return None

def display_file_attachment(file_path, file_metadata=None):
    """
    Display file attachment information with download link - FIXED VERSION
    
    Args:
        file_path: Path to file in storage
        file_metadata: Optional metadata dictionary
    """
    if not file_path:
        return
    
    try:
        storage_manager = FirebaseStorageManager()
        
        if not storage_manager.bucket:
            st.error("📁 File storage not available")
            return
        
        # Get file info
        file_info = storage_manager.get_file_info(file_path)
        
        if not file_info:
            st.error("📁 File not found or no longer available")
            return
        
        # Display file information
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Use metadata filename if available, otherwise use the original
            display_name = file_metadata.get("original_filename") if file_metadata else Path(file_path).name
            
            st.write(f"📎 **Attachment:** {display_name}")
            
            # File size and date
            if file_info.get('size'):
                size_kb = file_info['size'] / 1024
                st.caption(f"Size: {size_kb:.1f} KB")
            
            if file_info.get('created'):
                upload_date = file_info['created'].strftime('%d %b %Y, %H:%M')
                st.caption(f"Uploaded: {upload_date}")
        
        with col2:
            download_url = file_info.get("download_url")
            if download_url:
                st.link_button("📥 Download", download_url, use_container_width=True)
            else:
                st.error("Download unavailable")
                
    except Exception as e:
        st.error(f"Error displaying attachment: {e}")

# Test function to verify setup
def test_firebase_storage_connection():
    """Test Firebase Storage connection - FIXED VERSION"""
    st.markdown("### 🧪 Firebase Storage Connection Test")
    
    try:
        # Test configuration
        config = get_storage_config()
        
        if config["bucket_name"]:
            st.success(f"✅ Bucket configured: {config['bucket_name']}")
        else:
            st.error("❌ Bucket name not configured")
            return False
        
        # Test Firebase Admin initialization
        storage_manager = FirebaseStorageManager()
        
        if storage_manager.bucket:
            st.success("✅ Firebase Storage initialized successfully")
            
            # Test listing files (this will verify permissions)
            try:
                # Try to list a few files to test connection
                blobs = list(storage_manager.bucket.list_blobs(max_results=1))
                st.success("✅ Storage access verified")
                return True
                
            except Exception as e:
                st.error(f"❌ Storage access failed: {e}")
                return False
        else:
            st.error("❌ Failed to initialize storage bucket")
            return False
            
    except Exception as e:
        st.error(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Run connection test
    test_firebase_storage_connection()
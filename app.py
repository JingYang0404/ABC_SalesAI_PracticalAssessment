"""
Flask API for Lead Management - ABC Sales AI Assessment
Endpoints:
- POST /leads - Create a new lead
- GET /leads - Retrieve leads (with optional filtering)
"""

# ============================================================================
# IMPORTS
# ============================================================================

from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text
from datetime import datetime
import phonenumbers
import re
from config import DB_CONNECTION, CLASSIFICATION_RULES, PHONE_DEFAULT_REGION

# ============================================================================
# FLASK APP SETUP
# ============================================================================

app = Flask(__name__)

# ============================================================================
# DATABASE SETUP - create_engine
# ============================================================================

# Build the database URL from config dictionary
# Note: Database is NOT specified here, will be specified in each query
DATABASE_URL = (
    f"mysql+pymysql://{DB_CONNECTION['user']}:{DB_CONNECTION['password']}"
    f"@{DB_CONNECTION['host']}:{DB_CONNECTION['port']}"
)

# Create the engine - this is your connection to MySQL
engine = create_engine(DATABASE_URL, echo=False)

# ============================================================================
# DATABASE CONNECTION CHECK - FAIL FAST
# ============================================================================

def test_database_connection() -> bool:
    """
    Test database connection at startup
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return True
    except Exception as e:
        return False

# Check connection at startup - STOP if it fails
if not test_database_connection():
    print("\n" + "="*60)
    print("✗ CRITICAL ERROR: Database Connection Failed")
    print("="*60)
    print("\nReason: Cannot connect to MySQL database")
    print("Please check:")
    print("  1. MySQL server is running")
    print("  2. Database 'leads_db' exists")
    print("  3. Username/password in config.py are correct")
    print("  4. Host/port in config.py are correct")
    print("\nConnection Details:")
    print(f"  Host: {DB_CONNECTION['host']}")
    print(f"  Port: {DB_CONNECTION['port']}")
    print(f"  User: {DB_CONNECTION['user']}")
    print(f"  Database: leads_db (checked in queries)")
    print("="*60 + "\n")
    exit(1)  # ← STOP the app, exit with error code 1

print("✓ Database connection successful!")

# ============================================================================
# HELPER FUNCTIONS - VALIDATION, PHONE NORMALIZATION, CLASSIFICATION
# ============================================================================

def normalize_phone(phone: str, region: str = PHONE_DEFAULT_REGION) -> tuple[str | None, str | None]:
    """
    Normalize phone number to E.164 format
    
    Args:
        phone (str): Raw phone number (e.g., "0123456789" or "+60123456789")
        region (str): Default region code (e.g., "MY" for Malaysia)
    
    Returns:
        tuple: (e164_phone, error_message)
        - e164_phone: Normalized phone in E.164 format (e.g., "+60123456789")
        - error_message: Error message if parsing failed, None if success
    """
    try:
        # Parse the phone number with the given region
        parsed_phone = phonenumbers.parse(phone, region)
        
        # Check if it's a valid number
        if not phonenumbers.is_valid_number(parsed_phone):
            return None, "Invalid phone number for region"
        
        # Format to E.164 (e.g., +60123456789)
        e164_phone = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
        return e164_phone, None
        
    except phonenumbers.NumberParseException as e:
        return None, f"Phone parse error: {str(e)}"

def validate_lead_input(data: any) -> tuple[bool, str | None, str | None]:
    """
    Validate incoming lead data
    
    Args:
        data (dict): JSON data from request
    
    Returns:
        tuple: (is_valid, error_message, error_code)
        - is_valid (bool): True if valid, False otherwise
        - error_message (str): Description of what's wrong
        - error_code (str): Code for the error (e.g., "MISSING_FIELD")
    """
    
    # Check if data is a dictionary
    if not isinstance(data, dict):
        return False, "Request body must be JSON", "INVALID_JSON"
    
    # Check for required fields
    required_fields = ['name', 'phone', 'message']
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}", "MISSING_FIELD"
        
        if data[field] is None:
            return False, f"Field '{field}' cannot be null", "NULL_FIELD"
    
    # Validate name
    if not isinstance(data['name'], str) or len(data['name'].strip()) == 0:
        return False, "Name must be a non-empty string", "INVALID_NAME"
    
    if len(data['name']) > 255:
        return False, "Name is too long (max 255 characters)", "NAME_TOO_LONG"
    
    # Validate name: only letters, spaces, hyphens, apostrophes (no numbers or special symbols)
    # Pattern: letters, spaces, hyphens, apostrophes only
    name_pattern = r"^[a-zA-Z\s\-']+$"
    if not re.match(name_pattern, data['name']):
        return False, "Name can only contain letters, spaces, hyphens, and apostrophes (no numbers or symbols)", "INVALID_NAME_FORMAT"
    
    # Validate phone
    if not isinstance(data['phone'], str) or len(data['phone'].strip()) == 0:
        return False, "Phone must be a non-empty string", "INVALID_PHONE"
    
    # Validate phone: only digits, spaces, +, -, (), . (no letters)
    # Pattern: digits, spaces, +, -, (), . only
    phone_pattern = r"^[\d\s\+\-\(\)\.]+$"
    if not re.match(phone_pattern, data['phone']):
        return False, "Phone can only contain digits, spaces, +, -, (), and . (no letters or other symbols)", "INVALID_PHONE_FORMAT"
    
    # Validate message
    if not isinstance(data['message'], str) or len(data['message'].strip()) == 0:
        return False, "Message must be a non-empty string", "INVALID_MESSAGE"
    
    # Validate message: cannot be all symbols (must have at least one letter or digit)
    # Check if message has at least one alphanumeric character
    if not re.search(r"[a-zA-Z0-9]", data['message']):
        return False, "Message must contain at least some words or numbers (cannot be all symbols)", "INVALID_MESSAGE_FORMAT"
    
    return True, None, None

def classify_lead(message: str) -> str:
    """
    Classify a lead as hot, warm, or cold based on message content
    Uses configurable rules from config.py
    
    Args:
        message (str): Lead's message
    
    Returns:
        str: Classification - "hot", "warm", or "cold"
    """
    
    message_lower = message.lower()
    
    # Check hot keywords first (highest priority)
    for keyword in CLASSIFICATION_RULES['hot']['keywords']:
        if keyword.lower() in message_lower:
            return 'hot'
    
    # Check warm keywords
    for keyword in CLASSIFICATION_RULES['warm']['keywords']:
        if keyword.lower() in message_lower:
            return 'warm'
    
    # Everything else is cold
    return 'cold'

# ============================================================================
# DATABASE OPERATIONS - CRUD Functions
# ============================================================================

def check_database_connection() -> bool:
    """
    Check if database connection is available
    
    Returns:
        bool: True if connected, False if connection failed
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"✗ Database connection check failed: {e}")
        return False

def insert_lead(name: str, phone_e164: str, original_phone: str, message: str, classification: str) -> int | None:
    """
    Insert a successful lead into the leads table
    
    Args:
        name (str): Lead's name
        phone_e164 (str): Normalized phone in E.164 format
        original_phone (str): Original phone number (for reference)
        message (str): Lead's message
        classification (str): Classification - "hot", "warm", or "cold"
    
    Returns:
        int: The auto-generated lead ID if successful, None if failed
    """
    try:
        with engine.connect() as connection:
            # SQL INSERT query - specify database.table
            query = text("""
                INSERT INTO leads_db.leads (name, phone_e164, original_phone, message, classification, created_at)
                VALUES (:name, :phone_e164, :original_phone, :message, :classification, NOW())
            """)
            
            # Execute the query with parameters
            result = connection.execute(query, {
                'name': name,
                'phone_e164': phone_e164,
                'original_phone': original_phone,
                'message': message,
                'classification': classification
            })
            
            # Commit the transaction
            connection.commit()
            
            # Get the last inserted ID
            lead_id = result.lastrowid
            print(f"✓ Lead created with ID: {lead_id}")
            return lead_id
            
    except Exception as e:
        print(f"✗ Error inserting lead: {e}")
        return None

def lead_exists(phone_e164: str) -> bool | None:
    """
    Check if a lead with this phone number already exists
    
    Args:
        phone_e164 (str): Phone number in E.164 format
    
    Returns:
        bool: True if exists, False if doesn't exist, None if error
    """
    try:
        with engine.connect() as connection:
            # SQL SELECT query - specify database.table
            query = text("""
                SELECT id FROM leads_db.leads WHERE phone_e164 = :phone_e164
            """)
            
            # Execute the query
            result = connection.execute(query, {'phone_e164': phone_e164})
            
            # Check if any row was found
            existing_lead = result.fetchone()
            
            if existing_lead:
                print(f"✓ Lead exists with phone: {phone_e164}")
                return True
            else:
                print(f"✓ Lead does NOT exist with phone: {phone_e164}")
                return False
                
    except Exception as e:
        print(f"✗ Error checking lead existence: {e}")
        return None

def get_all_leads(classification_filter: str | None = None) -> list[dict[str, any]] | None:
    """
    Fetch all leads from the database, optionally filtered by classification
    
    Args:
        classification_filter (str): Optional filter - "hot", "warm", or "cold"
    
    Returns:
        list: List of lead dictionaries, None if error
    """
    try:
        with engine.connect() as connection:
            # Build query based on filter - specify database.table
            if classification_filter:
                query = text("""
                    SELECT id, name, phone_e164, original_phone, message, classification, created_at
                    FROM leads_db.leads
                    WHERE classification = :classification
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {'classification': classification_filter})
            else:
                query = text("""
                    SELECT id, name, phone_e164, original_phone, message, classification, created_at
                    FROM leads_db.leads
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query)
            
            # Fetch all rows
            rows = result.fetchall()
            
            # Convert rows to list of dictionaries
            leads = []
            for row in rows:
                leads.append({
                    'id': row[0],
                    'name': row[1],
                    'phone_e164': row[2],
                    'original_phone': row[3],
                    'message': row[4],
                    'classification': row[5],
                    'created_at': row[6].isoformat() if row[6] else None
                })
            
            print(f"✓ Retrieved {len(leads)} leads from database")
            return leads
            
    except Exception as e:
        print(f"✗ Error fetching leads: {e}")
        return None

def insert_failed_lead(name: str | None, phone: str | None, message: str | None, error_reason: str, error_code: str) -> bool:
    """
    Insert a failed lead into the failed_leads table (for logging)
    
    Args:
        name (str): Lead's name (might be None/empty if validation failed early)
        phone (str): Phone number (raw, not normalized)
        message (str): Lead's message (might be None/empty)
        error_reason (str): Description of what went wrong
        error_code (str): Error code (e.g., "MISSING_FIELD", "DUPLICATE_LEAD")
    
    Returns:
        bool: True if successful, False if failed
    """
    try:
        with engine.connect() as connection:
            # SQL INSERT query - specify database.table
            query = text("""
                INSERT INTO leads_db.failed_leads (name, phone, message, error_reason, error_code, attempted_at)
                VALUES (:name, :phone, :message, :error_reason, :error_code, NOW())
            """)
            
            # Execute the query
            connection.execute(query, {
                'name': name,
                'phone': phone,
                'message': message,
                'error_reason': error_reason,
                'error_code': error_code
            })
            
            # Commit the transaction
            connection.commit()
            
            print(f"✓ Failed lead logged with code: {error_code}")
            return True
            
    except Exception as e:
        print(f"✗ Error inserting failed lead: {e}")
        return False


def get_failed_leads() -> list[dict[str, any]] | None:
    """
    Retrieve all failed leads from the database
    
    Returns:
        List of failed lead dictionaries or None if error
    """
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT id, name, phone, message, error_reason, error_code, attempted_at
                FROM leads_db.failed_leads
                ORDER BY attempted_at DESC
            """)
            result = connection.execute(query)
            failed_leads = []
            
            for row in result:
                failed_leads.append({
                    "id": row[0],
                    "name": row[1],
                    "phone": row[2],
                    "message": row[3],
                    "error_reason": row[4],
                    "error_code": row[5],
                    "attempted_at": row[6].isoformat() if row[6] else None
                })
            
            return failed_leads
    except Exception as e:
        print(f"Error retrieving failed leads: {e}")
        return None
    

# ============================================================================
# FLASK ENDPOINTS
# ============================================================================

@app.route('/leads', methods=['POST'])
def create_lead():
    """
    POST /leads - Create a new lead
    
    Request body:
    {
        "name": "Aisyah Binti Rahman",
        "phone": "0123456789",
        "message": "Hi, I'm interested in your premium plan. What's the pricing? Need it urgently."
    }
    
    Returns:
        201 Created - Lead successfully created
        400 Bad Request - Missing or invalid required fields
        409 Conflict - Lead with this phone already exists
        422 Unprocessable Entity - Phone cannot be parsed to E.164
        500 Internal Server Error - Database error
    """
    
    # Step 0: Check if database is available (FIRST check!)
    if not check_database_connection():
        return jsonify({
            "error": "Database service is unavailable",
            "code": "DATABASE_UNAVAILABLE"
        }), 500
    
    # Step 1: Get JSON data from request
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    
    # Step 2: Validate input
    is_valid, error_msg, error_code = validate_lead_input(data)
    if not is_valid:
        insert_failed_lead(data.get('name'), data.get('phone'), data.get('message'), error_msg, error_code)
        return jsonify({"error": error_msg, "code": error_code}), 400
    
    # Step 3: Normalize phone number
    phone_e164, phone_error = normalize_phone(data['phone'])
    if phone_error:
        insert_failed_lead(data['name'], data['phone'], data['message'], phone_error, "INVALID_PHONE_FORMAT")
        return jsonify({"error": f"Phone normalization failed: {phone_error}", "code": "INVALID_PHONE_FORMAT"}), 422
    
    # Step 4: Check for duplicate
    duplicate_exists = lead_exists(phone_e164)
    if duplicate_exists is None:
        # Database error
        insert_failed_lead(data['name'], phone_e164, data['message'], "Database error checking duplicates", "DATABASE_ERROR")
        return jsonify({"error": "Failed to check for duplicates", "code": "DATABASE_ERROR"}), 500
    elif duplicate_exists:
        insert_failed_lead(data['name'], phone_e164, data['message'], "Lead with this phone already exists", "DUPLICATE_LEAD")
        return jsonify({"error": "Lead with this phone number already exists", "code": "DUPLICATE_LEAD"}), 409
    
    # Step 5: Classify the lead
    classification = classify_lead(data['message'])
    
    # Step 6: Insert into database
    lead_id = insert_lead(data['name'], phone_e164, data['phone'], data['message'], classification)
    if lead_id is None:
        insert_failed_lead(data['name'], phone_e164, data['message'], "Failed to insert into database", "DATABASE_ERROR")
        return jsonify({"error": "Failed to create lead", "code": "DATABASE_ERROR"}), 500
    
    # Step 7: Return created lead with REAL ID from database
    return jsonify({
        "id": lead_id,
        "name": data['name'],
        "phone_e164": phone_e164,
        "original_phone": data['phone'],
        "message": data['message'],
        "classification": classification,
        "created_at": datetime.now().isoformat()
    }), 201

@app.route('/leads', methods=['GET'])
def get_leads():
    """
    GET /leads - Retrieve all leads
    
    Query parameters:
        status (optional): Filter by classification - "hot", "warm", or "cold"
    
    Examples:
        GET /leads                  (all leads)
        GET /leads?status=hot       (only hot leads)
        GET /leads?status=warm      (only warm leads)
        GET /leads?status=cold      (only cold leads)
    
    Returns:
        200 OK - List of leads
        400 Bad Request - Invalid status parameter
        500 Internal Server Error - Database error
    """
    
    # Step 0: Check if database is available (FIRST check!)
    if not check_database_connection():
        return jsonify({
            "error": "Database service is unavailable",
            "code": "DATABASE_UNAVAILABLE"
        }), 500
    
    # Step 1: Get optional status filter from query parameters
    status_filter = request.args.get('status')
    
    # Step 2: Validate status filter
    if status_filter and status_filter not in ['hot', 'warm', 'cold']:
        return jsonify({"error": "Status must be one of: hot, warm, cold"}), 400
    
    # Step 3: Fetch leads from database
    leads = get_all_leads(status_filter)
    if leads is None:
        return jsonify({"error": "Failed to retrieve leads", "code": "DATABASE_ERROR"}), 500
    
    # Step 4: Return leads
    return jsonify({
        "count": len(leads),
        "leads": leads
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """
    GET /health - Simple health check endpoint
    
    Returns:
        200 OK - Service is running
    """
    return jsonify({
        "status": "ok",
        "service": "leads-api",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/failed_leads', methods=['GET'])
def get_failed_leads_endpoint() -> tuple[dict, int]:
    """
    Retrieve all failed leads (validation errors)
    
    Returns:
        JSON list of failed leads with error details
        Status 200 if successful, 500 if database error
    """
    # 1. Check database connection
    if not check_database_connection():
        return jsonify({
            "error": "Database unavailable",
            "error_code": "DATABASE_UNAVAILABLE"
        }), 500
    
    # 2. Get failed leads from database
    failed_leads = get_failed_leads()
    
    if failed_leads is None:
        return jsonify({
            "error": "Failed to retrieve failed leads",
            "error_code": "DATABASE_ERROR"
        }), 500
    
    # 3. Return jsonify results
    # 200 is success status code
    return jsonify({
        "count": len(failed_leads),
        "failed_leads": failed_leads
    }), 200


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors (wrong HTTP method)"""
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error"}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Starting Flask Leads API - ABC Sales AI Assessment")
    print("="*60)
    print("\nAvailable Endpoints:")
    print("  POST /leads              - Create a new lead")
    print("  GET /leads               - List all leads")
    print("  GET /leads?status=hot    - List only hot leads")
    print("  GET /health              - Health check")
    print("\nRunning on http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, host='localhost', port=5000)
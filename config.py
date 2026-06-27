"""
Configuration for the leads API
Database setup using SQLAlchemy create_engine
"""

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Database connection dictionary - Easy to modify
DB_CONNECTION = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'majingyang',
    'database': None,  # Database specified in each query instead
    'port': 3306
}

# This tells SQLAlchemy not to track modifications (performance improvement)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ============================================================================
# CLASSIFICATION RULES - Data-driven configuration
# ============================================================================

CLASSIFICATION_RULES = {
    'hot': {
        'keywords': ['urgent', 'asap', 'buy now', 'pricing', 'ready to pay', 'demo'],
        'priority': 1  # Highest priority
    },
    'warm': {
        'keywords': ['interested', 'tell me more', 'how does it work'],
        'priority': 2
    },
    'cold': {
        'keywords': [],  # Everything else falls here
        'priority': 3
    }
}

# ============================================================================
# PHONE CONFIGURATION
# ============================================================================

# Default region for phone number normalization
PHONE_DEFAULT_REGION = 'MY'
"""
Firebase configuration and initialization for ASGCN.
Architectural Choice: Firebase provides real-time synchronization across agents,
automatic scaling, and built-in security rules. Using Firestore for structured
state management and Realtime Database for streaming events.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore, db
from google.cloud.firestore_v1 import Client as FirestoreClient
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FirebaseConfig(BaseModel):
    """Configuration model for Firebase initialization."""
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    cert_url: str


class FirebaseManager:
    """Singleton manager for Firebase connections."""
    
    _instance: Optional['FirebaseManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._firestore_client: Optional[FirestoreClient] = None
            self._realtime_db = None
            self._initialized = True
    
    def initialize(self, config_path: Optional[str] = None) -> None:
        """
        Initialize Firebase with explicit error handling for missing credentials.
        
        Args:
            config_path: Path to service account JSON file. If None, uses environment variables.
            
        Raises:
            ValueError: If Firebase credentials are missing or invalid.
            firebase_admin.exceptions.FirebaseError: For Firebase-specific errors.
        """
        try:
            if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
                logger.warning("Firebase already initialized")
                return
            
            creds = self._get_credentials(config_path)
            firebase_admin.initialize_app(creds, {
                'databaseURL': f'https://{creds.project_id}.firebaseio.com'
            })
            
            self._firestore_client = firestore.client()
            self._realtime_db = db.reference('/')
            
            # Test connection
            self._test_connections()
            
            logger.info("Firebase initialized successfully")
            
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {e}")
            raise ValueError(f"Firebase credentials file not found: {config_path}")
        except ValueError as e:
            logger.error(f"Invalid Firebase configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def _get_credentials(self, config_path: Optional[str]) -> credentials.Certificate:
        """Extract credentials from env vars or config file with validation."""
        if config_path and os.path.exists(config_path):
            return credentials.Certificate(config_path)
        
        # Try environment variables
        required_vars = [
            'FIREBASE_PROJECT_ID',
            'FIREBASE_PRIVATE_KEY_ID',
            'FIREBASE_PRIVATE_KEY',
            'FIREBASE_CLIENT_EMAIL',
            'FIREBASE_CLIENT_ID',
            'FIREBASE_CERT_URL'
        ]
        
        missing_vars = [var for var in required_vars if var not in os.environ]
        if missing_vars:
            raise ValueError(f"Missing environment variables: {missing_vars}")
        
        # Clean private key (remove escaped newlines)
        private_key = os.environ['FIREBASE_PRIVATE_KEY'].replace('\\n', '\n')
        
        config_dict = {
            "type": "service_account",
            "project_id": os.environ['FIREBASE_PROJECT
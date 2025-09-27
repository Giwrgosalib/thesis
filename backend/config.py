"""
Configuration management for the eBay AI Chatbot backend.
Handles environment variables, validation, and application settings.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    mongo_uri: str
    db_name: str = "ebay_extension_prefs"
    pref_collection: str = "user_preferences"
    session_collection: str = "auth_sessions"
    connection_timeout: int = 5000
    max_pool_size: int = 10

@dataclass
class EBayConfig:
    """eBay API configuration settings."""
    client_id: str
    client_secret: str
    dev_id: str
    runame: str
    environment: str = "PRODUCTION"
    scopes: Optional[list] = None
    base_url: str = "https://api.ebay.com"
    sandbox_url: str = "https://api.sandbox.ebay.com"
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = [
                "https://api.ebay.com/oauth/api_scope",
                "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly"
            ]

@dataclass
class AppConfig:
    """Application configuration settings."""
    app_base_url: str
    frontend_url: str
    frontend_build_dir: str
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    session_expiry: int = 86400  # 24 hours
    max_request_size: int = 16 * 1024 * 1024  # 16MB
    rate_limit_per_minute: int = 60

@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

@dataclass
class ModelConfig:
    """ML model configuration settings."""
    models_dir: str = "models"
    intent_model_path: str = "models/intent_model.pkl"
    ner_model_path: str = "models/ner_model.pth"
    ner_vocab_path: str = "models/ner_vocab.pkl"
    embedding_dim: int = 128
    hidden_dim: int = 256
    max_sequence_length: int = 512

class Config:
    """Main configuration class that validates and loads all settings."""
    
    def __init__(self):
        self._validate_environment()
        self.database = self._load_database_config()
        self.ebay = self._load_ebay_config()
        self.app = self._load_app_config()
        self.logging = self._load_logging_config()
        self.model = self._load_model_config()
        
    def _validate_environment(self) -> None:
        """Validate that all required environment variables are set."""
        required_vars = [
            "MONGO_URI",
            "EBAY_CLIENT_ID", 
            "EBAY_CLIENT_SECRET",
            "EBAY_DEV_ID",
            "EBAY_RUNAME"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                "Please check your .env file or environment configuration."
            )
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load and validate database configuration."""
        return DatabaseConfig(
            mongo_uri=os.environ["MONGO_URI"],
            db_name=os.environ.get("DB_NAME", "ebay_extension_prefs"),
            pref_collection=os.environ.get("PREF_COLLECTION", "user_preferences"),
            session_collection=os.environ.get("SESSION_COLLECTION", "auth_sessions"),
            connection_timeout=int(os.environ.get("DB_CONNECTION_TIMEOUT", "5000")),
            max_pool_size=int(os.environ.get("DB_MAX_POOL_SIZE", "10"))
        )
    
    def _load_ebay_config(self) -> EBayConfig:
        """Load and validate eBay API configuration."""
        return EBayConfig(
            client_id=os.environ["EBAY_CLIENT_ID"],
            client_secret=os.environ["EBAY_CLIENT_SECRET"],
            dev_id=os.environ["EBAY_DEV_ID"],
            runame=os.environ["EBAY_RUNAME"],
            environment=os.environ.get("EBAY_API_ENVIRONMENT", "PRODUCTION").upper(),
            scopes=os.environ.get("EBAY_SCOPES", "").split() if os.environ.get("EBAY_SCOPES") else None
        )
    
    def _load_app_config(self) -> AppConfig:
        """Load and validate application configuration."""
        return AppConfig(
            app_base_url=os.environ.get("APP_BACKEND_URL", "http://localhost:5000"),
            frontend_url=os.environ.get("FRONTEND_URL", "http://localhost:3000"),
            frontend_build_dir=os.environ.get("FRONTEND_BUILD_DIR", "../frontend/dist"),
            debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true",
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "5000")),
            session_expiry=int(os.environ.get("SESSION_EXPIRY", "86400")),
            max_request_size=int(os.environ.get("MAX_REQUEST_SIZE", str(16 * 1024 * 1024))),
            rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
        )
    
    def _load_logging_config(self) -> LoggingConfig:
        """Load and validate logging configuration."""
        return LoggingConfig(
            level=os.environ.get("LOG_LEVEL", "INFO"),
            format=os.environ.get("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=os.environ.get("LOG_FILE_PATH"),
            max_file_size=int(os.environ.get("LOG_MAX_FILE_SIZE", str(10 * 1024 * 1024))),
            backup_count=int(os.environ.get("LOG_BACKUP_COUNT", "5"))
        )
    
    def _load_model_config(self) -> ModelConfig:
        """Load and validate model configuration."""
        return ModelConfig(
            models_dir=os.environ.get("MODELS_DIR", "models"),
            intent_model_path=os.environ.get("INTENT_MODEL_PATH", "models/intent_model.pkl"),
            ner_model_path=os.environ.get("NER_MODEL_PATH", "models/ner_model.pth"),
            ner_vocab_path=os.environ.get("NER_VOCAB_PATH", "models/ner_vocab.pkl"),
            embedding_dim=int(os.environ.get("EMBEDDING_DIM", "128")),
            hidden_dim=int(os.environ.get("HIDDEN_DIM", "256")),
            max_sequence_length=int(os.environ.get("MAX_SEQUENCE_LENGTH", "512"))
        )
    
    def get_ebay_environment(self) -> str:
        """Get the eBay environment (SANDBOX or PRODUCTION)."""
        return self.ebay.environment
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ebay.environment == "PRODUCTION"
    
    def get_ebay_base_url(self) -> str:
        """Get the appropriate eBay API base URL based on environment."""
        if self.ebay.environment == "SANDBOX":
            return self.ebay.sandbox_url
        return self.ebay.base_url

# Global configuration instance
config = Config()

def get_config() -> Config:
    """Get the global configuration instance."""
    return config

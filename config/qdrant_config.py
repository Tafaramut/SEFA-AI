# config/qdrant_config.py
"""
Configuration file for Qdrant integration
"""

import os
from typing import Dict, Any


class QdrantConfig:
    """Configuration class for Qdrant settings"""

    # Qdrant Connection Settings
    QDRANT_URL = "https://23e86f8b-af40-41c7-8e42-aa67f17ac110.us-east4-0.gcp.cloud.qdrant.io:6333"
    QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.0hvxGIdcsV56Bn9jLCrxhDw_2KVjIFyINDxFw9xxAR4"

    # Collection Settings
    COLLECTION_NAME = "whatsapp_conversations"
    VECTOR_SIZE = 384  # all-MiniLM-L6-v2 embedding size
    DISTANCE_METRIC = "Cosine"  # Options: Cosine, Dot, Euclid, Manhattan

    # Embedding Model Settings
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Options: all-MiniLM-L6-v2, all-mpnet-base-v2, etc.

    # Search Settings
    DEFAULT_SEARCH_LIMIT = 5
    SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score for results
    USER_CONTEXT_LIMIT = 3  # Max conversations to include from user's history
    GLOBAL_CONTEXT_LIMIT = 3  # Max conversations to include from all users

    # Context Settings
    MAX_CONTEXT_LENGTH = 2000  # Maximum characters in context
    MAX_CONVERSATION_HISTORY = 10  # Maximum conversation turns to keep

    # Response Settings
    INCLUDE_GLOBAL_CONTEXT = True
    INCLUDE_USER_CONTEXT = True
    INCLUDE_KNOWLEDGE_BASE = True

    @classmethod
    def get_qdrant_settings(cls) -> Dict[str, Any]:
        """Get Qdrant connection settings"""
        return {
            "url": cls.QDRANT_URL,
            "api_key": cls.QDRANT_API_KEY,
        }

    @classmethod
    def get_collection_config(cls) -> Dict[str, Any]:
        """Get collection configuration"""
        return {
            "name": cls.COLLECTION_NAME,
            "vector_size": cls.VECTOR_SIZE,
            "distance": cls.DISTANCE_METRIC,
        }

    @classmethod
    def get_search_config(cls) -> Dict[str, Any]:
        """Get search configuration"""
        return {
            "limit": cls.DEFAULT_SEARCH_LIMIT,
            "threshold": cls.SIMILARITY_THRESHOLD,
            "user_context_limit": cls.USER_CONTEXT_LIMIT,
            "global_context_limit": cls.GLOBAL_CONTEXT_LIMIT,
        }

    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration settings"""
        required_settings = [
            cls.QDRANT_URL,
            cls.QDRANT_API_KEY,
            cls.COLLECTION_NAME,
        ]

        return all(setting for setting in required_settings)


# Environment-based configuration
class EnvironmentConfig:
    """Load configuration from environment variables with fallbacks"""

    @staticmethod
    def get_qdrant_url() -> str:
        return os.getenv('QDRANT_URL', QdrantConfig.QDRANT_URL)

    @staticmethod
    def get_qdrant_api_key() -> str:
        return os.getenv('QDRANT_API_KEY', QdrantConfig.QDRANT_API_KEY)

    @staticmethod
    def get_collection_name() -> str:
        return os.getenv('QDRANT_COLLECTION', QdrantConfig.COLLECTION_NAME)

    @staticmethod
    def get_embedding_model() -> str:
        return os.getenv('EMBEDDING_MODEL', QdrantConfig.EMBEDDING_MODEL)

    @staticmethod
    def get_gemini_api_key() -> str:
        return os.getenv('GEMINI_API_KEY', '')

    @staticmethod
    def is_development() -> bool:
        return os.getenv('ENVIRONMENT', 'development').lower() == 'development'

    @staticmethod
    def get_all_settings() -> Dict[str, Any]:
        """Get all configuration settings"""
        return {
            'qdrant': {
                'url': EnvironmentConfig.get_qdrant_url(),
                'api_key': EnvironmentConfig.get_qdrant_api_key(),
                'collection': EnvironmentConfig.get_collection_name(),
            },
            'embedding': {
                'model': EnvironmentConfig.get_embedding_model(),
            },
            'gemini': {
                'api_key': EnvironmentConfig.get_gemini_api_key(),
            },
            'environment': {
                'is_development': EnvironmentConfig.is_development(),
            }
        }


# Conversation categories for better organization
class ConversationTypes:
    """Predefined conversation types for categorization"""

    WELCOME = "welcome"
    TEMPLATE_NAVIGATION = "template_navigation"
    AI_CONVERSATION = "ai_conversation"
    PAYMENT_TRIGGER = "payment_trigger"
    PAYMENT_FLOW = "payment_flow"
    END_OF_TREE = "end_of_tree_payment"
    KNOWLEDGE_BASE = "knowledge_base"
    NAVIGATION = "navigation"
    FALLBACK = "fallback"
    TEST = "test"

    @classmethod
    def get_all_types(cls) -> list:
        """Get all conversation types"""
        return [
            cls.WELCOME,
            cls.TEMPLATE_NAVIGATION,
            cls.AI_CONVERSATION,
            cls.PAYMENT_TRIGGER,
            cls.PAYMENT_FLOW,
            cls.END_OF_TREE,
            cls.KNOWLEDGE_BASE,
            cls.NAVIGATION,
            cls.FALLBACK,
            cls.TEST,
        ]


# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'logs/qdrant_integration.log',
            'mode': 'a',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default', 'file'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}
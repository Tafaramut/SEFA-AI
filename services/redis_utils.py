# services/redis_utils.py
import redis
from datetime import datetime, timedelta
import json
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self):
        """
        Production-ready Redis connection with:
        - Environment variable configuration
        - Connection pooling
        - Timeout settings
        - SSL/TLS support for Redis Cloud
        - Automatic reconnection
        """
        try:
            # Get Redis configuration from environment variables
            # Fallback to Redis Cloud if no env vars are set (for production)
            redis_host = os.getenv('REDIS_HOST', 'redis-11065.c327.europe-west1-2.gce.redns.redis-cloud.com')
            redis_port = int(os.getenv('REDIS_PORT', 11065))
            redis_password = os.getenv('REDIS_PASSWORD', 'CYeBkT1k99vrTWP6gtMClQynzgBlH1eL')
            redis_ssl = os.getenv('REDIS_SSL', 'true').lower() == 'true'

            logger.info(f"Connecting to Redis at {redis_host}:{redis_port} (SSL: {redis_ssl})")

            # Base connection parameters
            connection_params = {
                'host': redis_host,
                'port': redis_port,
                'password': redis_password,
                'db': 0,
                'decode_responses': True,
                'socket_timeout': 10,  # Socket operations timeout (seconds)
                'socket_connect_timeout': 5,  # Connection timeout (seconds)
                'retry_on_timeout': True,  # Retry on timeout errors
                'health_check_interval': 30,  # Check connection health (seconds)
                'max_connections': 100  # Connection pool size
            }

            # Add SSL parameters for Redis Cloud (redis-py 6.2.0 compatible)
            if redis_ssl:
                connection_params.update({
                    'ssl_cert_reqs': None,  # Disable SSL certificate verification
                    'ssl_check_hostname': False,  # Disable hostname checking
                })
                logger.info("Using SSL connection for Redis Cloud")

            self.redis_client = redis.Redis(**connection_params)

            # Test connection immediately
            if not self.redis_client.ping():
                raise ConnectionError("Redis ping failed")

            logger.info(f"✅ Redis connected successfully to {redis_host}:{redis_port}")

        except Exception as e:
            logger.error(f"❌ Redis connection failed: {str(e)}")
            self.redis_client = None
            raise  # Fail fast in production

    def _safe_operation(self, func, *args, **kwargs):
        """Wrapper for safe Redis operations with error handling"""
        if not self.redis_client:
            logger.warning("Redis client not available")
            return None

        try:
            return func(*args, **kwargs)
        except redis.RedisError as e:
            logger.error(f"Redis operation failed: {str(e)}")
            return None

    def get_user_session(self, user_id):
        """Retrieve complete user session from Redis with error handling"""

        def _get():
            session = self.redis_client.hgetall(f"user:{user_id}")
            if session:
                for field in ['history', 'current', 'payment_step']:
                    if field in session:
                        try:
                            session[field] = json.loads(session[field])
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to decode {field} for user {user_id}")
                            session[field] = None
            return session or None

        return self._safe_operation(_get)

    def save_user_session(self, user_id, session_data):
        """Store complete user session in Redis with atomic operations"""

        def _save():
            if not session_data:
                logger.warning(f"No session data provided for user {user_id}")
                return None

            # DEBUG: Log what we're trying to save
            logger.info(f"🔍 DEBUG - Attempting to save session for user {user_id}")
            logger.info(f"🔍 DEBUG - Session data keys: {list(session_data.keys())}")

            # Check each field for None values
            for key, value in session_data.items():
                if value is None:
                    logger.warning(f"🚨 DEBUG - Found None value in field '{key}' for user {user_id}")
                else:
                    logger.info(
                        f"✅ DEBUG - Field '{key}': type={type(value).__name__}, value_preview={str(value)[:100]}...")

            # Create a deep copy to avoid modifying the original
            data_to_store = session_data.copy()

            # Remove None values and convert others to proper types
            cleaned_data = {}
            for key, value in data_to_store.items():
                if value is None:
                    logger.warning(f"🚨 Skipping None value for field '{key}' (user: {user_id})")
                    continue

                # Convert specific fields to JSON strings
                if key in ['history', 'current', 'payment_step']:
                    try:
                        cleaned_data[key] = json.dumps(value)
                        logger.info(f"✅ Serialized field '{key}' to JSON")
                    except (TypeError, ValueError) as e:
                        logger.error(f"❌ Failed to serialize {key}: {str(e)}")
                        continue  # Skip this field
                else:
                    # Convert all other values to strings to ensure Redis compatibility
                    try:
                        cleaned_data[key] = str(value)
                        logger.info(f"✅ Converted field '{key}' to string")
                    except (TypeError, ValueError) as e:
                        logger.error(f"❌ Failed to convert {key} to string: {str(e)}")
                        continue  # Skip this field

            if not cleaned_data:
                logger.warning(f"🚨 No valid data to store for user {user_id} after cleaning")
                return None

            logger.info(f"✅ Cleaned data fields for user {user_id}: {list(cleaned_data.keys())}")

            # Set expiration if specified
            pipeline = self.redis_client.pipeline()
            if 'payment_expiry' in cleaned_data:
                try:
                    expiry = int((datetime.now() + timedelta(days=30)).timestamp())
                    cleaned_data['payment_expiry'] = str(expiry)
                    pipeline.expireat(f"user:{user_id}", expiry)
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid payment expiry: {str(e)}")
                    del cleaned_data['payment_expiry']

            pipeline.hset(f"user:{user_id}", mapping=cleaned_data)
            result = pipeline.execute()
            logger.info(f"✅ Successfully saved session for user {user_id}")
            return result

        return self._safe_operation(_save)

    def clear_user_session(self, user_id):
        """Clear user session from Redis with error handling"""
        return self._safe_operation(self.redis_client.delete, f"user:{user_id}")

    def check_payment_status(self, user_id):
        """Check payment status with proper error handling"""

        def _check():
            session = self.get_user_session(user_id)
            if not session or 'payment_expiry' not in session:
                return False
            try:
                expiry = float(session['payment_expiry'])
                return datetime.now().timestamp() < expiry
            except (ValueError, TypeError):
                logger.warning(f"Invalid payment expiry for user {user_id}")
                return False

        return self._safe_operation(_check)

    def add_to_conversation_history(self, user_id, role, message):
        """Atomic operation to add conversation history"""

        def _add():
            # DEBUG: Log what we're trying to add
            logger.info(f"🔍 DEBUG - Adding to conversation history:")
            logger.info(f"🔍 DEBUG - user_id: {user_id} (type: {type(user_id).__name__})")
            logger.info(f"🔍 DEBUG - role: {role} (type: {type(role).__name__})")
            logger.info(f"🔍 DEBUG - message: {str(message)[:200]}... (type: {type(message).__name__})")

            if not user_id or not role or not message:
                logger.warning(
                    f"🚨 Invalid parameters for conversation history: user_id={user_id}, role={role}, message={message}")
                return None

            # Check for None values specifically
            if user_id is None:
                logger.error(f"🚨 user_id is None!")
                return None
            if role is None:
                logger.error(f"🚨 role is None!")
                return None
            if message is None:
                logger.error(f"🚨 message is None!")
                return None

            history_key = f"conversation:{user_id}"
            message_entry = json.dumps({
                "role": str(role),
                "message": str(message),
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"✅ Adding conversation entry for user {user_id}")

            with self.redis_client.pipeline() as pipe:
                pipe.lpush(history_key, message_entry)
                pipe.ltrim(history_key, 0, 19)  # Keep last 20 messages
                result = pipe.execute()
                logger.info(f"✅ Successfully added conversation history for user {user_id}")
                return result

        return self._safe_operation(_add)

    def get_conversation_history(self, user_id):
        """Safe conversation history retrieval"""

        def _get():
            history_key = f"conversation:{user_id}"
            messages = self.redis_client.lrange(history_key, 0, -1)
            return [json.loads(msg) for msg in messages] if messages else []

        return self._safe_operation(_get)

    def is_healthy(self):
        """Check if Redis connection is healthy"""
        return self.redis_client and self._safe_operation(self.redis_client.ping)
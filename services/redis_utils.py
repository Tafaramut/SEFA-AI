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
        - SSL/TLS support
        - Automatic reconnection
        """
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('_REDIS_HOST', 'localhost'),
                port=int(os.getenv('_REDIS_PORT', 6379)),
                password=os.getenv('_REDIS_PASSWORD'),  # Required for production
                db=0,
                decode_responses=True,
                ssl=True if os.getenv('_REDIS_SSL', 'false').lower() == 'true' else False,
                socket_timeout=10,  # Socket operations timeout (seconds)
                socket_connect_timeout=5,  # Connection timeout (seconds)
                retry_on_timeout=True,  # Retry on timeout errors
                health_check_interval=30,  # Check connection health (seconds)
                max_connections=100  # Connection pool size
            )

            # Test connection immediately
            if not self.redis_client.ping():
                raise ConnectionError("Redis ping failed")

            logger.info("✅ Redis connected successfully")

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
            # Create a deep copy to avoid modifying the original
            data_to_store = session_data.copy()

            # Convert specific fields to JSON strings
            for field in ['history', 'current', 'payment_step']:
                if field in data_to_store and data_to_store[field] is not None:
                    try:
                        data_to_store[field] = json.dumps(data_to_store[field])
                    except (TypeError, ValueError) as e:
                        logger.error(f"Failed to serialize {field}: {str(e)}")
                        del data_to_store[field]  # Remove problematic field

            # Set expiration if specified
            pipeline = self.redis_client.pipeline()
            if 'payment_expiry' in data_to_store:
                try:
                    expiry = int((datetime.now() + timedelta(days=30)).timestamp())
                    data_to_store['payment_expiry'] = str(expiry)
                    pipeline.expireat(f"user:{user_id}", expiry)
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid payment expiry: {str(e)}")
                    del data_to_store['payment_expiry']

            pipeline.hset(f"user:{user_id}", mapping=data_to_store)
            return pipeline.execute()

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
            history_key = f"conversation:{user_id}"
            message_entry = json.dumps({
                "role": role,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            with self.redis_client.pipeline() as pipe:
                pipe.lpush(history_key, message_entry)
                pipe.ltrim(history_key, 0, 19)  # Keep last 20 messages
                pipe.execute()

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
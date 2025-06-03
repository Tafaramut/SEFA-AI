# services/redis_service.py
import redis
from datetime import datetime, timedelta
import json
import os


class RedisService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=os.getenv('REDIS_PORT', 6379),
            db=0,
            decode_responses=True
        )

    def get_user_session(self, user_id):
        """Retrieve complete user session from Redis"""
        session = self.redis_client.hgetall(f"user:{user_id}")
        if session:
            if 'history' in session:
                session['history'] = json.loads(session['history'])
            if 'current' in session:
                session['current'] = json.loads(session['current'])
            if 'payment_step' in session:
                session['payment_step'] = json.loads(session['payment_step'])
        return session or None

    def save_user_session(self, user_id, session_data):
        """Store complete user session in Redis"""
        session_data = session_data.copy()
        if 'history' in session_data:
            session_data['history'] = json.dumps(session_data['history'])
        if 'current' in session_data:
            session_data['current'] = json.dumps(session_data['current'])
        if 'payment_step' in session_data:
            session_data['payment_step'] = json.dumps(session_data['payment_step'])

        # Set expiration for payment sessions
        if 'payment_expiry' in session_data:
            expiry = int((datetime.now() + timedelta(days=30)).timestamp())
            session_data['payment_expiry'] = str(expiry)
            self.redis_client.expireat(f"user:{user_id}", expiry)

        return self.redis_client.hset(f"user:{user_id}", mapping=session_data)

    def clear_user_session(self, user_id):
        """Clear user session from Redis"""
        return self.redis_client.delete(f"user:{user_id}")

    def check_payment_status(self, user_id):
        """Check if user has active payment"""
        session = self.get_user_session(user_id)
        if not session or 'payment_expiry' not in session:
            return False

        expiry = float(session['payment_expiry'])
        return datetime.now().timestamp() < expiry

    def add_to_conversation_history(self, user_id, role, message):
        """Add message to conversation history for context"""
        history_key = f"conversation:{user_id}"
        message_entry = json.dumps({"role": role, "message": message, "timestamp": datetime.now().isoformat()})
        self.redis_client.lpush(history_key, message_entry)
        self.redis_client.ltrim(history_key, 0, 19)  # Keep last 20 messages

    def get_conversation_history(self, user_id):
        """Retrieve conversation history for context"""
        history_key = f"conversation:{user_id}"
        messages = self.redis_client.lrange(history_key, 0, -1)
        return [json.loads(msg) for msg in messages]
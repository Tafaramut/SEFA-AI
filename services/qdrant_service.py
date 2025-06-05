# services/qdrant_service.py
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
except ImportError as e:
    print(f"Error importing qdrant_client: {e}")
    print("Install with: pip install qdrant-client")
    raise

try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"Error importing sentence_transformers: {e}")
    print("Install with: pip install sentence-transformers")
    raise


class QdrantService:
    def __init__(self):
        try:
            self.client = QdrantClient(
                url="https://23e86f8b-af40-41c7-8e42-aa67f17ac110.us-east4-0.gcp.cloud.qdrant.io:6333",
                api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.0hvxGIdcsV56Bn9jLCrxhDw_2KVjIFyINDxFw9xxAR4",
            )
        except Exception as e:
            print(f"Error connecting to Qdrant: {e}")
            raise

        # Initialize sentence transformer for embeddings
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast and efficient model
        except Exception as e:
            print(f"Error loading SentenceTransformer model: {e}")
            raise

        # Collection name for conversations
        self.collection_name = "whatsapp_conversations"

        # Initialize logging
        self.logger = logging.getLogger(__name__)

        # Initialize collection
        self._initialize_collection()

    def _initialize_collection(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            collection_exists = any(col.name == self.collection_name for col in collections)

            if not collection_exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=384,  # all-MiniLM-L6-v2 produces 384-dim vectors
                        distance=Distance.COSINE
                    )
                )
                self.logger.info(f"Created collection: {self.collection_name}")
            else:
                self.logger.info(f"Collection {self.collection_name} already exists")

        except Exception as e:
            self.logger.error(f"Error initializing collection: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for given text"""
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            return []

    def store_conversation(self, user_number: str, message: str, response: str, message_type: str = "conversation"):
        """Store user message and bot response in Qdrant"""
        try:
            timestamp = datetime.now().isoformat()

            # Store user message
            user_embedding = self.generate_embedding(message)
            if user_embedding:
                user_point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=user_embedding,
                    payload={
                        "user_number": user_number,
                        "message": message,
                        "message_type": "user",
                        "conversation_type": message_type,
                        "timestamp": timestamp,
                        "response_to": None
                    }
                )

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[user_point]
                )

            # Store bot response
            bot_embedding = self.generate_embedding(response)
            if bot_embedding:
                bot_point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=bot_embedding,
                    payload={
                        "user_number": user_number,
                        "message": response,
                        "message_type": "bot",
                        "conversation_type": message_type,
                        "timestamp": timestamp,
                        "response_to": message
                    }
                )

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[bot_point]
                )

            self.logger.info(f"Stored conversation for user {user_number}")

        except Exception as e:
            self.logger.error(f"Error storing conversation: {e}")

    def search_similar_conversations(self, query: str, user_number: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """Search for similar conversations to provide context"""
        try:
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return []

            # Build filter for user-specific search if provided
            query_filter = None
            if user_number:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="user_number",
                            match=MatchValue(value=user_number)
                        )
                    ]
                )

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit,
                score_threshold=0.7  # Only return results with good similarity
            )

            results = []
            for point in search_result:
                results.append({
                    "message": point.payload.get("message", ""),
                    "message_type": point.payload.get("message_type", ""),
                    "timestamp": point.payload.get("timestamp", ""),
                    "score": point.score,
                    "response_to": point.payload.get("response_to", "")
                })

            return results

        except Exception as e:
            self.logger.error(f"Error searching conversations: {e}")
            return []

    def get_user_conversation_context(self, user_number: str, query: str, limit: int = 3) -> str:
        """Get relevant conversation context for the user"""
        try:
            # Search for similar conversations from this user
            similar_convs = self.search_similar_conversations(query, user_number, limit)

            if not similar_convs:
                return ""

            context_parts = []
            context_parts.append("Based on previous conversations:")

            for conv in similar_convs:
                if conv["message_type"] == "user" and conv.get("response_to"):
                    context_parts.append(f"User asked: {conv['message']}")
                elif conv["message_type"] == "bot":
                    context_parts.append(f"Bot replied: {conv['message'][:200]}...")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(f"Error getting user context: {e}")
            return ""

    def get_global_conversation_context(self, query: str, limit: int = 5) -> str:
        """Get relevant conversation context from all users (anonymized)"""
        try:
            # Search across all conversations without user filter
            similar_convs = self.search_similar_conversations(query, user_number=None, limit=limit)

            if not similar_convs:
                return ""

            context_parts = []
            context_parts.append("Similar questions from other users:")

            for conv in similar_convs:
                if conv["message_type"] == "bot":
                    # Only include bot responses to maintain privacy
                    context_parts.append(f"- {conv['message'][:150]}...")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(f"Error getting global context: {e}")
            return ""

    def store_knowledge_base(self, documents: List[Dict[str, str]]):
        """Store knowledge base documents for better context"""
        try:
            points = []
            for doc in documents:
                embedding = self.generate_embedding(doc["content"])
                if embedding:
                    point = PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload={
                            "content": doc["content"],
                            "title": doc.get("title", ""),
                            "category": doc.get("category", "knowledge_base"),
                            "message_type": "knowledge_base",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    points.append(point)

            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                self.logger.info(f"Stored {len(points)} knowledge base documents")

        except Exception as e:
            self.logger.error(f"Error storing knowledge base: {e}")

    def get_collection_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status
            }
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {e}")
            return {}


# Test function to verify imports
def test_imports():
    """Test function to check if all imports work"""
    try:
        service = QdrantService()
        print("✅ All imports successful!")
        print("✅ QdrantService initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_imports()
# scripts/setup_qdrant.py
"""
Setup script for Qdrant integration with WhatsApp chatbot
Run this script to initialize your Qdrant collection and test the integration
"""

import sys
import os
from datetime import datetime

# Add the parent directory to sys.path to import our services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.qdrant_service import QdrantService
from services.gemini_enhanced import EnhancedGeminiService


def test_qdrant_connection():
    """Test the Qdrant connection and collection setup"""
    print("🔗 Testing Qdrant connection...")

    try:
        qdrant_service = QdrantService()
        stats = qdrant_service.get_collection_stats()

        if stats:
            print("✅ Qdrant connection successful!")
            print(f"   - Collection: {qdrant_service.collection_name}")
            print(f"   - Points count: {stats.get('points_count', 0)}")
            print(f"   - Status: {stats.get('status', 'Unknown')}")
            return True
        else:
            print("❌ Failed to get collection stats")
            return False

    except Exception as e:
        print(f"❌ Qdrant connection failed: {e}")
        return False


def test_embedding_generation():
    """Test embedding generation"""
    print("\n🧠 Testing embedding generation...")

    try:
        qdrant_service = QdrantService()
        test_text = "Hello, how can I help you with your payment?"

        embedding = qdrant_service.generate_embedding(test_text)

        if embedding and len(embedding) == 384:
            print("✅ Embedding generation successful!")
            print(f"   - Text: '{test_text}'")
            print(f"   - Embedding dimensions: {len(embedding)}")
            print(f"   - First 5 values: {embedding[:5]}")
            return True
        else:
            print(f"❌ Embedding generation failed. Length: {len(embedding) if embedding else 0}")
            return False

    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        return False


def test_conversation_storage():
    """Test storing and retrieving conversations"""
    print("\n💾 Testing conversation storage...")

    try:
        qdrant_service = QdrantService()

        # Test data
        test_user = "whatsapp:+1234567890"
        test_message = "I need help with my payment issues"
        test_response = "I can help you with payment issues. What specific problem are you experiencing?"

        # Store conversation
        qdrant_service.store_conversation(
            user_number=test_user,
            message=test_message,
            response=test_response,
            message_type="test"
        )

        print("✅ Conversation stored successfully!")
        print(f"   - User: {test_user}")
        print(f"   - Message: {test_message}")
        print(f"   - Response: {test_response}")

        # Test search
        results = qdrant_service.search_similar_conversations(
            "payment problems",
            user_number=test_user,
            limit=3
        )

        if results:
            print("✅ Search functionality working!")
            print(f"   - Found {len(results)} similar conversations")
            for i, result in enumerate(results[:2]):
                print(f"   - Result {i + 1}: {result['message'][:50]}... (Score: {result['score']:.3f})")
        else:
            print("⚠️  No search results found (this might be normal for new collections)")

        return True

    except Exception as e:
        print(f"❌ Conversation storage test failed: {e}")
        return False


def test_enhanced_gemini():
    """Test enhanced Gemini integration"""
    print("\n🤖 Testing Enhanced Gemini integration...")

    try:
        # Check if GEMINI_API_KEY is set
        if not os.getenv('GEMINI_API_KEY'):
            print("⚠️  GEMINI_API_KEY environment variable not set")
            print("   Set it with: export GEMINI_API_KEY='your-api-key'")
            return False

        enhanced_gemini = EnhancedGeminiService()

        test_user = "whatsapp:+1234567890"
        test_message = "What payment methods do you accept?"

        response = enhanced_gemini.generate_enhanced_response(
            user_message=test_message,
            user_number=test_user,
            include_global_context=False
        )

        if response and len(response) > 10:
            print("✅ Enhanced Gemini integration working!")
            print(f"   - User message: {test_message}")
            print(f"   - Response: {response[:100]}...")
            return True
        else:
            print("❌ Enhanced Gemini integration failed")
            return False

    except Exception as e:
        print(f"❌ Enhanced Gemini test failed: {e}")
        return False


def populate_sample_knowledge_base():
    """Populate sample knowledge base for testing"""
    print("\n📚 Populating sample knowledge base...")

    try:
        qdrant_service = QdrantService()

        sample_documents = [
            {
                "title": "Payment Methods",
                "content": "We accept credit cards, debit cards, mobile money, and bank transfers. All payments are processed securely through our payment gateway.",
                "category": "payments"
            },
            {
                "title": "Account Issues",
                "content": "If you're having trouble accessing your account, try resetting your password or contact our support team for assistance.",
                "category": "account"
            },
            {
                "title": "Service Features",
                "content": "Our premium service includes 24/7 AI support, personalized responses, priority customer service, and advanced features.",
                "category": "features"
            },
            {
                "title": "Subscription Plans",
                "content": "We offer monthly and annual subscription plans. Monthly plans cost $9.99 and annual plans cost $99.99 with 2 months free.",
                "category": "pricing"
            },
            {
                "title": "Technical Support",
                "content": "For technical issues, please provide your error message, device type, and steps to reproduce the problem. Our team will help you quickly.",
                "category": "support"
            }
        ]

        qdrant_service.store_knowledge_base(sample_documents)

        print(f"✅ Successfully added {len(sample_documents)} knowledge base documents!")

        # Test searching the knowledge base
        search_results = qdrant_service.search_similar_conversations(
            "payment options",
            user_number=None,
            limit=3
        )

        if search_results:
            print(f"✅ Knowledge base search working! Found {len(search_results)} results")

        return True

    except Exception as e:
        print(f"❌ Knowledge base population failed: {e}")
        return False


def main():
    """Run all setup and tests"""
    print("🚀 Setting up Qdrant integration for WhatsApp chatbot")
    print("=" * 60)

    tests = [
        ("Qdrant Connection", test_qdrant_connection),
        ("Embedding Generation", test_embedding_generation),
        ("Conversation Storage", test_conversation_storage),
        ("Enhanced Gemini", test_enhanced_gemini),
        ("Knowledge Base", populate_sample_knowledge_base),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 60)
    print("📊 SETUP SUMMARY")
    print("=" * 60)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<25} {status}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Your Qdrant integration is ready to use.")
        print("\nNext steps:")
        print("1. Update your main app to import the enhanced services")
        print("2. Set up your environment variables (GEMINI_API_KEY)")
        print("3. Start your Flask application")
        print("4. Test with actual WhatsApp messages")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        print("\nCommon issues:")
        print("- Make sure GEMINI_API_KEY is set")
        print("- Check your Qdrant connection details")
        print("- Ensure all dependencies are installed")


if __name__ == "__main__":
    main()
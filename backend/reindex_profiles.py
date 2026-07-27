"""One-time script to re-index all active profiles into Qdrant.

Usage:
    cd backend
    .\venv\Scripts\python reindex_profiles.py

Requires:
    - Qdrant server running (set QDRANT_HOST in .env)
    - MySQL matrimony database accessible
    - BAAI/bge-m3 model downloaded (~2.2GB on first run)
"""
import asyncio
import sys
import os


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    print("=" * 60)
    print("  Profile Re-Index to Qdrant")
    print("=" * 60)

    from app.config import settings
    print(f"\n  Qdrant:      {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    print(f"  Model:       {settings.EMBEDDING_MODEL}")
    print(f"  MySQL DB:    {settings.DB_HOST}/{settings.DB_NAME}")
    print()

    confirm = input("  Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("  Aborted.")
        return

    print("\n  Connecting to Qdrant...")
    from app.services.vector_service import get_client
    try:
        get_client(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        print("  Qdrant connected.")
    except Exception as e:
        print(f"  ERROR: Cannot reach Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        print(f"  {e}")
        print("\n  Make sure Qdrant is running on your server.")
        print("  See: docs/qdrant-setup.md or .agents/HYBRID_RAG_SUMMARY.md")
        return

    print("\n  Fetching active profiles from MySQL...")
    from app.services.indexing_service import reindex_all
    await reindex_all()

    print("\n  Done!")


if __name__ == "__main__":
    asyncio.run(main())

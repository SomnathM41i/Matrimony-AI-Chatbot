"""Development server entrypoint.

Plain `uvicorn app.main:app --reload` watches the whole backend directory, which
includes venv/, site-packages/ and the HuggingFace/torch caches. Loading the
embedding model then touches thousands of watched files and restarts the server
mid-request, which in turn reloads the model again.

Here WatchFiles only ever walks backend/app, so venv/, site-packages/, model
caches and .git are never monitored. The excludes below additionally stop
bytecode and editor scratch files inside app/ from triggering a reload.

Usage:
    cd backend
    python run_dev.py
"""
import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # Only project source code is watched.
        reload_dirs=["app"],
        reload_excludes=["*/__pycache__/*", "*.pyc", "*.swp", "*.swx", "*~"],
    )

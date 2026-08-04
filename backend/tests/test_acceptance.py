"""Deployment acceptance smoke script (manual; not collected by pytest).

This file deliberately does NOT define a `test_`-prefixed function so pytest never
collects it. Run it manually against a running server:

    python -m tests.test_acceptance          # or: python tests/test_acceptance.py

Every check uses a real assertion (no swallowed exceptions, no boolean return),
so a failed acceptance run exits non-zero and pytest-style silent green is impossible.
"""
import sys

import httpx

from app.core.security import create_access_token

BASE_URL = "http://localhost:8000"


def _assert(resp, condition, name):
    if not condition:
        raise AssertionError(f"{name}: failed (status={resp.status_code}, body={resp.text[:200]})")


def run_acceptance(base_url: str = BASE_URL) -> bool:
    print("=" * 60)
    print("DEPLOYMENT ACCEPTANCE TESTS")
    print("=" * 60)

    token = create_access_token(data={"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=60) as client:
        resp = client.get("/health")
        _assert(resp, resp.status_code == 200 and "status" in resp.json(), "Health endpoint")
        print("  [PASS] Health endpoint")

        resp = client.post("/api/chat", json={"message": "Hello, how are you?"})
        body = resp.json()
        _assert(
            resp,
            resp.status_code == 200
            and isinstance(body.get("reply"), str)
            and len(body["reply"]) > 0
            and body.get("conversation_id") is not None,
            "General chat - greeting",
        )
        print("  [PASS] General chat - greeting")

        resp = client.post("/api/chat", json={"message": "Show me Maratha girls in Pune"})
        _assert(resp, resp.status_code == 200, "Profile search with no DB")
        print("  [PASS] Profile search with no DB")

        resp = client.post("/api/chat", json={"message": "\u092e\u0932\u093e \u092e\u0930\u093e\u0920\u093e \u092e\u0941\u0932\u0917\u0940 \u0939\u0935\u0940 \u0906\u0939\u0947"})
        _assert(resp, resp.status_code == 200, "Marathi profile query")
        print("  [PASS] Marathi profile query")

        resp = client.post("/api/chat", json={"message": ""})
        _assert(resp, resp.status_code == 400, "Empty message rejected")
        print("  [PASS] Empty message rejected")

        resp = client.post("/api/chat", json={"message": "Show me brides"})
        _assert(
            resp,
            resp.status_code == 200 and resp.json().get("conversation_id", 0) > 0,
            "Conversation ID returned",
        )
        print("  [PASS] Conversation ID returned")

    with httpx.Client(base_url=base_url, timeout=60) as anon:
        resp = anon.post("/api/chat", json={"message": "hi"})
        _assert(resp, resp.status_code == 401, "Auth failure without token")
    print("  [PASS] Auth failure without token")

    print("-" * 60)
    print("ALL ACCEPTANCE TESTS PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        run_acceptance()
    except AssertionError as e:
        print(f"\nACCEPTANCE FAILURE: {e}")
        sys.exit(1)

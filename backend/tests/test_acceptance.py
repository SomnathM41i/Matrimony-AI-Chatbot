import httpx
import traceback
from app.core.security import create_access_token


BASE_URL = "http://localhost:8000"


def test_acceptance():
    print("=" * 60)
    print("DEPLOYMENT ACCEPTANCE TESTS")
    print("=" * 60)

    token = create_access_token(data={"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}

    passed = 0
    failed = 0

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=60) as client:

        def check(name, method, path, json=None, assertions=None):
            nonlocal passed, failed
            try:
                if method == "GET":
                    resp = client.get(path)
                else:
                    resp = client.post(path, json=json)
                if assertions:
                    assertions(resp)
                print(f"  [PASS] {name}")
                passed += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                traceback.print_exc(limit=1)
                failed += 1

        check("Health endpoint", "GET", "/health",
              assertions=lambda r: (r.status_code == 200, "status" in r.json()))

        check("General chat - greeting", "POST", "/api/chat",
              json={"message": "Hello, how are you?"},
              assertions=lambda r: (
                  r.status_code == 200
                  and isinstance(r.json()["reply"], str)
                  and len(r.json()["reply"]) > 0
                  and r.json()["conversation_id"] is not None
              ))

        check("Profile search with no DB", "POST", "/api/chat",
              json={"message": "Show me Maratha girls in Pune"},
              assertions=lambda r: (
                  r.status_code == 200
              ))

        check("Marathi profile query", "POST", "/api/chat",
              json={"message": "\u092e\u0932\u093e \u092e\u0930\u093e\u0920\u093e \u092e\u0941\u0932\u0917\u0940 \u0939\u0935\u0940 \u0906\u0939\u0947"},
              assertions=lambda r: (
                  r.status_code == 200
              ))

        check("Empty message rejected", "POST", "/api/chat",
              json={"message": ""},
              assertions=lambda r: r.status_code == 400)

    try:
        with httpx.Client(base_url=BASE_URL, timeout=60) as anon:
            resp = anon.post("/api/chat", json={"message": "hi"})
        assert resp.status_code == 401
        print(f"  [PASS] Auth failure without token")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Auth failure: {e}")
        traceback.print_exc(limit=1)
        failed += 1

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=60) as client:
        check("Conversation ID returned", "POST", "/api/chat",
              json={"message": "Show me brides"},
              assertions=lambda r: (
                  r.status_code == 200
                  and r.json()["conversation_id"] > 0
              ))

    print("-" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
    if failed > 0:
        print("SOME TESTS FAILED")
    else:
        print("ALL ACCEPTANCE TESTS PASSED")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = test_acceptance()
    exit(0 if success else 1)

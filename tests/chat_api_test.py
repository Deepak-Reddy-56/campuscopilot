"""Full smoke-test for all smart chatbot scenarios."""
import sys, requests
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:5000/api/chat"

cases = [
    # Intent + entity routing
    ("what are the upcoming cs events",   "CS EVENTS"),
    ("what are the upcoming cse events",  "CS EVENTS"),
    ("show me mechanical events",         "ME EVENTS"),
    ("upcoming events",                   "which department"),
    ("CS events",                         "CS EVENTS"),      # chip click simulation
    ("all events",                        "ALL EVENTS"),

    # Fee routing
    ("fees",                              "what would you like"),
    ("CS fees",                           "CS TUITION"),
    ("IT fees",                           "IT TUITION"),
    ("3 sharing hostel fees",             "3-Sharing"),
    ("4 sharing fees",                    "4-Sharing"),
    ("hostel fees",                       "which room"),

    # Schedule
    ("exam schedule",                     "EXAM SCHEDULE"),
    ("show schedule",                     "EXAM SCHEDULE"),
]

passed = 0
failed = 0
for msg, expected_substr in cases:
    r = requests.post(BASE, json={"message": msg}).json()
    text = r["text"]
    chips = r.get("chips", [])
    ok = expected_substr.lower() in text.lower()
    status = "✓" if ok else "✗"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"{status}  {msg!r:45s} → chips={chips[:3]}")
    if not ok:
        print(f"   FAIL: expected {expected_substr!r} in: {text[:120]!r}")

print(f"\n{passed}/{passed+failed} tests passed")

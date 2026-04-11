
import os
import sys
# Add backend to path to allow imports
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.meta_api import _normalize_comp_placeholders
import json

def test_normalization():
    print("--- TESTING TEMPLATE NORMALIZATION ---")
    
    # Test case 1: Single variable re-indexing
    t1 = "Hello {{3}}"
    res1 = _normalize_comp_placeholders(t1)
    print(f"Case 1: '{t1}' -> '{res1}'")
    assert res1 == "Hello {{1}}"

    # Test case 2: Multiple variable re-indexing (sequential)
    t2 = "Hi {{2}}, your code is {{5}}"
    res2 = _normalize_comp_placeholders(t2)
    print(f"Case 2: '{t2}' -> '{res2}'")
    assert res2 == "Hi {{1}}, your code is {{2}}"

    # Test case 3: Mixed order
    t3 = "Variable {{2}} then {{1}}"
    res3 = _normalize_comp_placeholders(t3)
    print(f"Case 3: '{t3}' -> '{res3}'")
    assert res3 == "Variable {{1}} then {{2}}"

    # Test case 4: Repeated variables
    t4 = "Hey {{3}}, repeated {{3}} then {{1}}"
    res4 = _normalize_comp_placeholders(t4)
    print(f"Case 4: '{t4}' -> '{res4}'")
    assert res4 == "Hey {{1}}, repeated {{1}} then {{2}}"

    print("\nSUCCESS: Normalization logic verified.")

if __name__ == "__main__":
    test_normalization()

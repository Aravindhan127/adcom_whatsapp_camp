import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core import security
import bcrypt

def test_truncation():
    # Test a very long password (greater than 72 bytes)
    # Using special characters to ensure byte-safe truncation
    long_pwd = "a" * 50 + "🔥" * 20 # 🔥 is 4 bytes in UTF-8. 50 + 20*4 = 130 bytes.
    
    print(f"Testing with password length: {len(long_pwd)} chars")
    
    # This should NOT throw ValueError
    try:
        hashed = security.get_password_hash(long_pwd)
        print("Hashing successful.")
        
        # This should also NOT throw ValueError and return True
        verified = security.verify_password(long_pwd, hashed)
        print(f"Verification result: {verified}")
        
        if not verified:
            print("ERROR: Verification failed!")
            sys.exit(1)
            
    except ValueError as e:
        print(f"FAILED with ValueError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED with unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_truncation()
    print("All tests passed!")

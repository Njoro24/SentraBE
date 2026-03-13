"""
Generate Test Tokens
Standalone script to generate test JWT tokens for manual testing
"""

from jwt_handler import generate_token
from datetime import datetime, timedelta


def main():
    """Generate and print test tokens"""
    
    print("\n" + "="*70)
    print("PHASE 6 SECURITY - TEST TOKEN GENERATOR")
    print("="*70 + "\n")
    
    # Token 1: Valid admin token (1 hour expiry)
    admin_token = generate_token(
        sub="admin_user_001",
        role="admin",
        expires_in_hours=1
    )
    
    print("1. VALID ADMIN TOKEN (expires in 1 hour)")
    print("-" * 70)
    print(f"Token: {admin_token}")
    print(f"Subject: admin_user_001")
    print(f"Role: admin")
    print(f"Expiry: 1 hour from now")
    print()
    
    # Token 2: Valid analyst token (1 hour expiry)
    analyst_token = generate_token(
        sub="analyst_user_002",
        role="analyst",
        expires_in_hours=1
    )
    
    print("2. VALID ANALYST TOKEN (expires in 1 hour)")
    print("-" * 70)
    print(f"Token: {analyst_token}")
    print(f"Subject: analyst_user_002")
    print(f"Role: analyst")
    print(f"Expiry: 1 hour from now")
    print()
    
    # Token 3: Already expired token
    expired_token = generate_token(
        sub="expired_user_003",
        role="client",
        expires_in_hours=-1  # Negative means already expired
    )
    
    print("3. ALREADY EXPIRED TOKEN (for testing rejection)")
    print("-" * 70)
    print(f"Token: {expired_token}")
    print(f"Subject: expired_user_003")
    print(f"Role: client")
    print(f"Status: EXPIRED (use for testing 401 responses)")
    print()
    
    print("="*70)
    print("USAGE INSTRUCTIONS")
    print("="*70)
    print("""
To use these tokens in API requests, add them to the Authorization header:

    Authorization: Bearer <token>

Example with curl:
    curl -H "Authorization: Bearer <token>" http://localhost:8000/score

Example with Python requests:
    import requests
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://localhost:8000/score", headers=headers)

The expired token should return HTTP 401 Unauthorized.
The valid tokens should return HTTP 200 with the response.
    """)
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

# Test script to verify authentication
from spotify_handler import SpotifyHandler
import asyncio

async def test_auth():
    handler = SpotifyHandler()
    
    # Step 1: Get auth URL
    auth_url = handler.get_auth_url()
    print(f"Visit: {auth_url}")
    
    # Step 2: Get code from redirect URL
    code = input("Enter authorization code: ")
    
    # Step 3: Complete authentication
    success = handler.authenticate_with_code(code)
    print(f"Authentication: {'Success' if success else 'Failed'}")
    
    # Step 4: Test API call
    if success:
        user_data = await handler.fetch_all_user_data()
        print(f"User: {user_data.get('user_profile', {}).get('display_name', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(test_auth())
import requests
import sys
import json
import time
from datetime import datetime

class ChatAppAPITester:
    def __init__(self, base_url="https://d79f18f0-7fd9-4953-a9e9-4f43d526aef8.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.registered_users = []

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_user_registration(self, username):
        """Test user registration"""
        success, response = self.run_test(
            f"Register User '{username}'",
            "POST",
            "register",
            200,
            data={"username": username}
        )
        if success and 'id' in response:
            user_data = {
                'id': response['id'],
                'username': response['username']
            }
            self.registered_users.append(user_data)
            print(f"   Registered user: {user_data}")
            return user_data
        return None

    def test_duplicate_registration(self, username):
        """Test duplicate username registration (should fail)"""
        success, response = self.run_test(
            f"Duplicate Registration '{username}' (should fail)",
            "POST",
            "register",
            400,
            data={"username": username}
        )
        return success

    def test_get_online_users(self):
        """Test getting online users"""
        success, response = self.run_test(
            "Get Online Users",
            "GET",
            "users/online",
            200
        )
        if success and 'users' in response:
            print(f"   Online users count: {len(response['users'])}")
        return success, response

    def test_get_messages(self):
        """Test getting chat messages"""
        success, response = self.run_test(
            "Get Messages",
            "GET",
            "messages",
            200
        )
        if success and isinstance(response, list):
            print(f"   Messages count: {len(response)}")
        return success, response

    def test_relay_connection(self):
        """Test Flask relay server connection (expected to fail)"""
        success, response = self.run_test(
            "Test Relay Connection (expected to fail)",
            "POST",
            "test-relay",
            200
        )
        if success and 'relay_connection' in response:
            print(f"   Relay status: {response['relay_connection']}")
        return success, response

    def test_invalid_endpoints(self):
        """Test invalid endpoints"""
        invalid_tests = [
            ("Invalid endpoint", "GET", "invalid-endpoint", 404),
            ("Invalid method", "DELETE", "register", 405),
        ]
        
        for name, method, endpoint, expected_status in invalid_tests:
            self.run_test(name, method, endpoint, expected_status)

def main():
    print("🚀 Starting Chat App API Tests")
    print("=" * 50)
    
    tester = ChatAppAPITester()
    
    # Test user registration flow
    print("\n📝 Testing User Registration...")
    test_users = [f"test_user_{int(time.time())}", f"alice_{int(time.time())}", f"bob_{int(time.time())}"]
    
    for username in test_users:
        user = tester.test_user_registration(username)
        if not user:
            print(f"❌ Failed to register user {username}, stopping tests")
            return 1
    
    # Test duplicate registration
    if test_users:
        tester.test_duplicate_registration(test_users[0])
    
    # Test getting online users (will be empty since no WebSocket connections)
    print("\n👥 Testing Online Users...")
    tester.test_get_online_users()
    
    # Test getting messages
    print("\n💬 Testing Messages...")
    tester.test_get_messages()
    
    # Test relay connection (expected to fail)
    print("\n🔗 Testing Relay Connection...")
    tester.test_relay_connection()
    
    # Test invalid endpoints
    print("\n❌ Testing Invalid Endpoints...")
    tester.test_invalid_endpoints()
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.registered_users:
        print(f"\n👤 Registered Users for UI Testing:")
        for user in tester.registered_users:
            print(f"   - {user['username']} (ID: {user['id']})")
    
    success_rate = (tester.tests_passed / tester.tests_run) * 100
    print(f"✨ Success Rate: {success_rate:.1f}%")
    
    return 0 if success_rate >= 80 else 1

if __name__ == "__main__":
    sys.exit(main())
from jose import jwt
from backend import config

def test_update_user_status_requires_auth(client):
    """Test that updating user status requires authentication."""
    response = client.post('/api/me/status', json={"theme": "dark"})
    assert response.status_code == 401

def test_update_user_status_success(client, shop_client_auth_headers):
    """Test successful update of user status and JWT extension."""
    access_headers, _ = shop_client_auth_headers
    status_payload = {"theme": "dark", "notifications": True}
    
    response = client.post('/api/me/status', headers=access_headers, json=status_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    
    # Decode the new token and verify claims
    new_token = data['access_token']
    decoded_new_token = jwt.decode(new_token, config.JWT_SECRET_KEY, algorithms=["HS256"])
    
    assert decoded_new_token['sub'] == "client@example.com"
    assert decoded_new_token['role'] == "shop_client" # from models.Role enum
    assert decoded_new_token['client_status'] == status_payload
    assert decoded_new_token['exp'] > decoded_new_token['iat'] # Ensure expiration is extended
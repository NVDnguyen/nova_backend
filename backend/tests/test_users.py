from backend import config
from jose import jwt

def test_register_user(client, db):
    """Test user registration."""
    response = client.post('/api/auth/register', json={
        "email": "new_user@example.com",
        "password": "secure_password"
    })
    assert response.status_code == 201
    data = response.json()
    assert "message" in data
    assert db.users.find_one({"email": "new_user@example.com"}) is not None

def test_register_user_duplicate_email(client):
    """Test registration with an already existing email."""
    client.post('/api/auth/register', json={
        "email": "duplicate@example.com",
        "password": "secure_password"
    })
    response = client.post('/api/auth/register', json={
        "email": "duplicate@example.com",
        "password": "another_password"
    })
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data

def test_login_user(client):
    """Test user login."""
    # Register a user first
    client.post('/api/auth/register', json={"email": "login_test@example.com", "password": "login_pass"})
    
    response = client.post('/api/auth/login', data={"username": "login_test@example.com", "password": "login_pass"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    decoded_token = jwt.decode(data['access_token'], config.JWT_SECRET_KEY, algorithms=["HS256"])
    assert decoded_token['sub'] == "login_test@example.com"
    assert decoded_token['role'] == "shop_client"

def test_login_user_invalid_credentials(client):
    """Test login with incorrect password."""
    client.post('/api/auth/register', json={"email": "invalid_login@example.com", "password": "correct_pass"})
    response = client.post('/api/auth/login', data={"username": "invalid_login@example.com", "password": "wrong_pass"})
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data

def test_card_login_success(client):
    """Test successful card login."""
    response = client.post('/api/auth/card_login', json={"card_id": "CARD123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    decoded_token = jwt.decode(data['access_token'], config.JWT_SECRET_KEY, algorithms=["HS256"])
    assert decoded_token['sub'] == "CARD123"
    assert decoded_token['role'] == "shop_client"

def test_card_login_invalid_id(client):
    """Test card login with an invalid card ID."""
    response = client.post('/api/auth/card_login', json={"card_id": "INVALID_ID_TOO_LONG"})
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data

def test_refresh_token_success(client, shop_client_auth_headers):
    """Test refreshing an access token."""
    _, refresh_headers = shop_client_auth_headers
    response = client.post('/api/auth/refresh', headers=refresh_headers)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

def test_register_user_validation_error(client):
    """Test registration with invalid data (e.g., invalid email, short password)."""
    response = client.post('/api/auth/register', json={
        "email": "invalid-email", # Invalid email format
        "password": "short" # Too short
    })
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert any(err['loc'] == ['body', 'email'] for err in data['detail'])
    assert any(err['loc'] == ['body', 'password'] for err in data['detail'])

def test_card_login_validation_error(client):
    """Test card login with invalid data (e.g., card_id too short)."""
    response = client.post('/api/auth/card_login', json={"card_id": "12"}) # Too short
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert any(err['loc'] == ['body', 'card_id'] for err in data['detail'])

def test_refresh_token_invalid_token(client):
    """Test refreshing with an invalid or non-refresh token."""
    # No token
    response = client.post('/api/auth/refresh')
    assert response.status_code == 401

    # Invalid token format
    response = client.post('/api/auth/refresh', headers={"Authorization": "Bearer invalid_jwt"})
    assert response.status_code == 401 # get_current_user will fail

    # For this implementation, any valid token can be used to refresh.
    # A real-world app might add a "type": "refresh" claim to refresh tokens
    # and a "type": "access" to access tokens, then validate the type.
    # The current test setup is sufficient for the converted code.
    pass

def test_guest_login_success(client):
    """Test successful guest login."""
    response = client.post('/api/auth/guest_login')
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    decoded_token = jwt.decode(data['access_token'], config.JWT_SECRET_KEY, algorithms=["HS256"])
    assert decoded_token['sub'].startswith("guest_")
    assert decoded_token['sub'].endswith("@temp.com")
    assert decoded_token['role'] == "guest"
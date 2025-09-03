import pytest
from pymongo import MongoClient
from fastapi.testclient import TestClient
from backend.app import app
from backend import config
from backend.database import (
    get_products_collection,
    get_users_collection,
    get_orders_collection,
)
from backend.models import Role
import hmac
import hashlib

# Use a dedicated test database name
TEST_MONGO_URI = "mongodb://localhost:27017/test_shopping_cart_db"

@pytest.fixture(scope="session")
def test_db():
    """Creates a client to a test database and cleans it up after tests."""
    client = MongoClient(TEST_MONGO_URI)
    db = client.get_database("test_shopping_cart_db")
    yield db
    client.drop_database("test_shopping_cart_db")
    client.close()

@pytest.fixture(scope="function", autouse=True)
def setup_test_db(test_db):
    """
    - Overrides database dependencies to use the test database.
    - Cleans all collections and seeds products before each test.
    """
    def override_get_products(): return test_db["products"]
    def override_get_users(): return test_db["users"]
    def override_get_orders(): return test_db["order_history"]

    app.dependency_overrides[get_products_collection] = override_get_products
    app.dependency_overrides[get_users_collection] = override_get_users
    app.dependency_overrides[get_orders_collection] = override_get_orders

    for c in test_db.list_collection_names():
        test_db.drop_collection(c)

    # Seed initial products for tests that need them
    initial_products = [
        {'id': 1, 'name': 'Fifa 19', 'subtitle': 'PS4', 'price': 1500000, 'currency': 'VND', 'quantity': 10, 'unit': 'pack', 'product_img_url': 'https://via.placeholder.com/80/cccccc/000000?Text=Game'},
        {'id': 2, 'name': 'Glacier White 500GB', 'subtitle': 'PS4', 'price': 8000000, 'currency': 'VND', 'quantity': 5, 'unit': 'each', 'product_img_url': 'https://via.placeholder.com/80/f0f0f0/000000?Text=Console'},
        {'id': 3, 'name': 'Platinum Headset', 'subtitle': 'PS4', 'price': 2500000, 'currency': 'VND', 'quantity': 20, 'unit': 'each', 'product_img_url': 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory'},
    ]
    test_db.products.insert_many(initial_products)
    
    yield # Run the test
    
    # Clear overrides after test
    app.dependency_overrides = {}

@pytest.fixture(scope="session")
def client():
    """A test client for the app, created once per session."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def db(test_db):
    """Provides direct access to the test database instance for assertions."""
    return test_db

@pytest.fixture
def register_and_login_user(client):
    """Helper to register and log in a user, returning their tokens and identity."""
    def _register_and_login(email, password, is_admin=False):
        register_email = config.ADMIN_EMAIL if is_admin else email

        client.post('/api/auth/register', json={"email": register_email, "password": password})
        response = client.post(
            '/api/auth/login', 
            data={"username": register_email, "password": password}
        )
        data = response.json()
        return data['access_token'], data['refresh_token'], register_email
    return _register_and_login

@pytest.fixture
def admin_auth_headers(register_and_login_user):
    """Returns authorization headers for an admin user."""
    access_token, refresh_token, _ = register_and_login_user(
        config.ADMIN_EMAIL, "admin_pass", is_admin=True
    )
    return {"Authorization": f"Bearer {access_token}"}, {"Authorization": f"Bearer {refresh_token}"}

@pytest.fixture
def shop_client_auth_headers(register_and_login_user):
    """Returns authorization headers for a shop client user."""
    access_token, refresh_token, _ = register_and_login_user(
        "client@example.com", "client_pass"
    )
    return {"Authorization": f"Bearer {access_token}"}, {"Authorization": f"Bearer {refresh_token}"}

@pytest.fixture
def card_user_auth_headers(client):
    """Returns authorization headers for a card user."""
    card_id = "CARD123"
    response = client.post('/api/auth/card_login', json={"card_id": card_id})
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, {"Authorization": f"Bearer {data['refresh_token']}"}

@pytest.fixture
def mock_celery_process_order(monkeypatch):
    """Mocks the Celery process_order task."""
    mock_delay_called = []
    class MockProcessOrder:
        def delay(self, *args, **kwargs):
            mock_delay_called.append({"args": args, "kwargs": kwargs})
            # Mock a Celery AsyncResult object
            return type('obj', (object,), {'id': 'mock_task_id'})()
    monkeypatch.setattr("backend.orders.routes.process_order", MockProcessOrder())
    return mock_delay_called

@pytest.fixture
def generate_webhook_signature_helper():
    """Helper to generate VietQR webhook signatures for testing."""
    def _generate_signature(payload_data: dict, secret: str):
        # Reconstruct the string as per generate_vietqr_webhook_signature in routes.py
        payload_string = f"{payload_data['paymentRequestId']}{payload_data['state']}{payload_data['amount']}{payload_data['referenceId']}{payload_data['extraData']}"
        return hmac.new(secret.encode(), payload_string.encode(), hashlib.sha256).hexdigest()
    return _generate_signature
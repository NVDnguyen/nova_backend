from backend.models import OrderStatus
import time

def test_checkout_requires_auth(client):
    """Test that checkout requires authentication."""
    response = client.post('/api/orders/checkout', json={
        "items": [{"id": 1, "name": "Fifa 19", "subtitle": "PS4", "price": 64.0, "quantity": 1, "unit": "pack"}],
        "shipping_cost": 5.0,
        "subtotal": 64.0,
        "total_cost": 69.0
    })
    assert response.status_code == 401

def test_initiate_checkout_validation_error(client, shop_client_auth_headers):
    """Test checkout initiation with invalid data (e.g., negative price, empty items)."""
    access_headers, _ = shop_client_auth_headers
    
    # Test with negative price
    response = client.post('/api/orders/checkout', headers=access_headers, json={
        "items": [{"id": 1, "name": "Fifa 19", "subtitle": "PS4", "price": -64.0, "quantity": 1, "unit": "pack"}],
        "shipping_cost": 5.0, "subtotal": -64.0, "total_cost": -59.0
    })
    assert response.status_code == 422 # Unprocessable Entity
    data = response.json()
    assert any("Input should be a valid number, greater than or equal to 0" in err['msg'] for err in data['detail'])

    # Test with empty items list
    response = client.post('/api/orders/checkout', headers=access_headers, json={
        "items": [], "shipping_cost": 0.0, "subtotal": 0.0, "total_cost": 0.0
    })
    assert response.status_code == 400
    assert "Cannot checkout with an empty cart" in response.json()['detail']

def test_initiate_checkout_success(client, shop_client_auth_headers, db):
    """Test successful checkout initiation and QR generation."""
    access_headers, _ = shop_client_auth_headers
    checkout_payload = {
        "items": [{"id": 1, "name": "Fifa 19", "subtitle": "PS4", "price": 1500000, "currency": "VND", "quantity": 1, "unit": "pack"}],
        "shipping_cost": 5.0,
        "subtotal": 64.0,
        "total_cost": 69.0
    }
    response = client.post('/api/orders/checkout', headers=access_headers, json=checkout_payload)
    assert response.status_code == 200
    data = response.json()
    assert "order_id" in data
    assert "qr_svg" in data
    assert "message" in data
    
    # Verify order is in pending state in DB
    order_in_db = db.order_history.find_one({"order_id": data['order_id']})
    assert order_in_db is not None
    assert order_in_db['status'] == OrderStatus.PENDING.value
    assert order_in_db['total_cost'] == 69.0

def test_get_order_history_requires_auth(client):
    """Test that viewing order history requires authentication."""
    response = client.get('/api/orders/history')
    assert response.status_code == 401

def test_get_order_history_success(client, shop_client_auth_headers):
    """Test successful retrieval of order history."""
    access_headers, _ = shop_client_auth_headers
    
    # Initiate an order first
    checkout_payload = {
        "items": [{"id": 2, "name": "Glacier White 500GB", "subtitle": "PS4", "price": 8000000, "currency": "VND", "quantity": 1, "unit": "each"}],
        "shipping_cost": 10.0,
        "subtotal": 249.99,
        "total_cost": 259.99
    }
    response = client.post('/api/orders/checkout', headers=access_headers, json=checkout_payload)
    order_id = response.json()['order_id']

    # Simulate payment confirmation
    webhook_payload = {
        "paymentRequestId": "txn_mock_1",
        "state": "SUCCESS",
        "amount": 259.99,
        "description": "Payment for order",
        "referenceId": order_id,
        "merchantId": "MOCK_MERCHANT",
        "extraData": "extra",
        "signature": "mock_signature" # Signature is mocked for this test
    }
    client.post('/api/orders/webhook/payment_confirmation', json=webhook_payload)
    
    # Give Celery a moment to process (in a real test, you'd mock Celery)
    time.sleep(0.1) 

    response = client.get('/api/orders/history', headers=access_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(o['order_id'] == order_id for o in data)
    assert any(o['status'] == OrderStatus.COMPLETED.value for o in data)

def test_get_order_status_success(client, shop_client_auth_headers):
    """Test successful retrieval of order status from the public endpoint."""
    access_headers, _ = shop_client_auth_headers
    checkout_payload = {
        "items": [{"id": 3, "name": "Platinum Headset", "subtitle": "PS4", "price": 2500000, "currency": "VND", "quantity": 1, "unit": "each"}],
        "shipping_cost": 0.0,
        "subtotal": 119.99,
        "total_cost": 119.99
    }
    # An authenticated user creates an order
    response = client.post('/api/orders/checkout', headers=access_headers, json=checkout_payload)
    order_id = response.json()['order_id']

    # But anyone can check its status without authentication
    response = client.get(f'/api/orders/{order_id}/status')
    assert response.status_code == 200
    data = response.json()
    assert data['order_id'] == order_id
    assert data['status'] == OrderStatus.PENDING.value

def test_get_order_history_no_completed_orders(client, shop_client_auth_headers):
    """Test retrieving order history for a user with only pending orders or no orders."""
    access_headers, _ = shop_client_auth_headers
    
    # User has no orders yet
    response = client.get('/api/orders/history', headers=access_headers)
    assert response.status_code == 200
    assert response.json() == []

    # Initiate a pending order, but don't confirm it
    checkout_payload = {
        "items": [{"id": 1, "name": "Fifa 19", "subtitle": "PS4", "price": 1500000, "currency": "VND", "quantity": 1, "unit": "pack"}],
        "shipping_cost": 5.0, "subtotal": 64.0, "total_cost": 69.0
    }
    client.post('/api/orders/checkout', headers=access_headers, json=checkout_payload)
    response = client.get('/api/orders/history', headers=access_headers)
    assert response.json() == [] # Still empty as status is PENDING

def test_receive_payment_webhook_success(client, db, mock_celery_process_order, generate_webhook_signature_helper):
    """Test successful payment webhook processing."""
    # Create a pending order first
    client.post('/api/auth/register', json={"email": "webhook_test@example.com", "password": "pass"})
    login_res = client.post('/api/auth/login', data={"username": "webhook_test@example.com", "password": "pass"})
    access_token = login_res.json()['access_token']
    
    checkout_payload = {
        "items": [{"id": 1, "name": "Fifa 19", "subtitle": "PS4", "price": 1500000, "currency": "VND", "quantity": 1, "unit": "pack"}],
        "shipping_cost": 5.0,
        "subtotal": 64.0,
        "total_cost": 69.0
    }
    res = client.post('/api/orders/checkout', headers={"Authorization": f"Bearer {access_token}"}, json=checkout_payload)
    order_id = res.json()['order_id']

    webhook_payload_data = {
        "paymentRequestId": "txn_123",
        "state": "SUCCESS",
        "amount": 69,
        "description": "Payment for order",
        "referenceId": order_id,
        "merchantId": "MOCK_MERCHANT",
        "extraData": "extra",
        "signature": "" # Will be calculated
    }
    webhook_payload_data["signature"] = generate_webhook_signature_helper(webhook_payload_data, config.VIETQR_WEBHOOK_SECRET_KEY)

    response = client.post('/api/orders/webhook/payment_confirmation', json=webhook_payload_data)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert db.order_history.find_one({"order_id": order_id})['status'] == OrderStatus.PAID.value
    assert len(mock_celery_process_order) == 1 # Ensure Celery task was called
    assert mock_celery_process_order[0]['args'][0] == order_id

def test_receive_payment_webhook_invalid_signature(client):
    """Test webhook with invalid signature."""
    webhook_payload_data = {
        "paymentRequestId": "txn_invalid_sig", "state": "SUCCESS", "amount": 100,
        "description": "Test", "referenceId": "some_order_id", "merchantId": "MOCK",
        "extraData": "data", "signature": "wrong_signature"
    }
    response = client.post('/api/orders/webhook/payment_confirmation', json=webhook_payload_data)
    assert response.status_code == 400
    data = response.json()
    assert "Invalid signature" in data['detail']

def test_receive_payment_webhook_amount_mismatch(client, db, shop_client_auth_headers, generate_webhook_signature_helper):
    """Test webhook with amount mismatch."""
    access_headers, _ = shop_client_auth_headers
    checkout_payload = {
        "items": [{"id": 1, "name": "Fifa 19", "subtitle": "PS4", "price": 1500000, "currency": "VND", "quantity": 1, "unit": "pack"}],
        "shipping_cost": 5.0, "subtotal": 64.0, "total_cost": 69.0
    }
    res = client.post('/api/orders/checkout', headers=access_headers, json=checkout_payload)
    order_id = res.json()['order_id']

    webhook_payload_data = {
        "paymentRequestId": "txn_mismatch", "state": "SUCCESS", "amount": 60, # Mismatched amount
        "description": "Payment for order", "referenceId": order_id, "merchantId": "MOCK_MERCHANT",
        "extraData": "extra", "signature": ""
    }
    webhook_payload_data["signature"] = generate_webhook_signature_helper(webhook_payload_data, config.VIETQR_WEBHOOK_SECRET_KEY)

    response = client.post('/api/orders/webhook/payment_confirmation', json=webhook_payload_data)
    assert response.status_code == 400
    data = response.json()
    assert "Amount mismatch" in data['detail']
    assert db.order_history.find_one({"order_id": order_id})['status'] == OrderStatus.FAILED.value

def test_receive_payment_webhook_order_not_found(client, generate_webhook_signature_helper):
    """Test webhook for a non-existent order."""
    webhook_payload_data = {
        "paymentRequestId": "txn_not_found", "state": "SUCCESS", "amount": 100,
        "description": "Test", "referenceId": "non_existent_order", "merchantId": "MOCK",
        "extraData": "data", "signature": ""
    }
    webhook_payload_data["signature"] = generate_webhook_signature_helper(webhook_payload_data, config.VIETQR_WEBHOOK_SECRET_KEY)
    response = client.post('/api/orders/webhook/payment_confirmation', json=webhook_payload_data)
    assert response.status_code == 404
    data = response.json()
    assert "Order not found" in data['detail']

def test_receive_payment_webhook_validation_error(client):
    """Test webhook with invalid payload structure."""
    response = client.post('/api/orders/webhook/payment_confirmation', json={
        "paymentRequestId": "txn_invalid",
        "state": "SUCCESS",
        "amount": "not_an_int", # Invalid type
        "description": "Test",
        "referenceId": "some_order_id",
        "merchantId": "MOCK",
        "extraData": "data",
        "signature": "mock_sig"
    })
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert any(err['loc'] == ['body', 'amount'] for err in data['detail'])
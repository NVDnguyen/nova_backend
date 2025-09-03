from backend.models import Role

def test_get_products(client):
    """Test retrieving all products."""
    response = client.get('/api/products')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) and len(data) > 0
    assert any(p['id'] == 1 for p in data)

def test_get_product_by_id(client):
    """Test retrieving a single product by ID."""
    response = client.get('/api/products/1')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == 1
    assert data['name'] == 'Fifa 19'

def test_get_product_not_found(client):
    """Test retrieving a non-existent product."""
    response = client.get('/api/products/999')
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data

def test_create_product_admin_only(client, db, admin_auth_headers, shop_client_auth_headers):
    """Test that creating a product requires ADMIN role."""
    new_product_data = {
        "name": "Test Product",
        "subtitle": "Test Subtitle",
        "price": 99.99,
        "unit": "each"
    }
    
    # Test with no token
    response = client.post('/api/products', json=new_product_data)
    assert response.status_code == 401

    # Test with shop client token
    shop_client_access_headers, _ = shop_client_auth_headers
    response = client.post('/api/products', headers=shop_client_access_headers, json=new_product_data)
    assert response.status_code == 403

    # Test with admin token (successful creation)
    admin_access_headers, _ = admin_auth_headers
    response = client.post('/api/products', headers=admin_access_headers, json=new_product_data)
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == "Test Product"
    assert db.products.find_one({"name": "Test Product"}) is not None

def test_update_product_admin_only(client, admin_auth_headers, shop_client_auth_headers):
    """Test that updating a product requires ADMIN role."""
    update_data = {"price": 123.45}
    
    # Test with shop client token
    shop_client_access_headers, _ = shop_client_auth_headers
    response = client.put('/api/products/1', headers=shop_client_access_headers, json=update_data)
    assert response.status_code == 403

    # Test with admin token (successful update)
    admin_access_headers, _ = admin_auth_headers
    response = client.put('/api/products/1', headers=admin_access_headers, json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data['price'] == 123.45

def test_delete_product_admin_only(client, db, admin_auth_headers, shop_client_auth_headers):
    """Test that deleting a product requires ADMIN role."""
    # Test with shop client token
    shop_client_access_headers, _ = shop_client_auth_headers
    response = client.delete('/api/products/1', headers=shop_client_access_headers)
    assert response.status_code == 403

    # Test with admin token (successful deletion)
    admin_access_headers, _ = admin_auth_headers
    response = client.delete('/api/products/1', headers=admin_access_headers)
    assert response.status_code == 204
    assert db.products.find_one({"id": 1}) is None

def test_create_product_validation_error(client, admin_auth_headers):
    """Test creating a product with invalid data (e.g., missing name)."""
    admin_access_headers, _ = admin_auth_headers
    response = client.post('/api/products', headers=admin_access_headers, json={
        "subtitle": "Test Subtitle",
        "price": -10.0, # Invalid price
        "unit": "each"
    })
    assert response.status_code == 422 # Unprocessable Entity
    data = response.json()
    assert "detail" in data
    assert any("Input should be a valid number, greater than or equal to 0" in err['msg'] for err in data['detail'])

def test_update_product_validation_error(client, admin_auth_headers):
    """Test updating a product with invalid data (e.g., negative price)."""
    admin_access_headers, _ = admin_auth_headers
    response = client.put('/api/products/1', headers=admin_access_headers, json={
        "price": -50.0 # Invalid price
    })
    assert response.status_code == 422 # Unprocessable Entity
    data = response.json()
    assert "detail" in data
    assert any("Input should be a valid number, greater than or equal to 0" in err['msg'] for err in data['detail'])

def test_update_product_not_found(client, admin_auth_headers):
    """Test updating a non-existent product."""
    admin_access_headers, _ = admin_auth_headers
    response = client.put('/api/products/999', headers=admin_access_headers, json={"price": 100.0})
    assert response.status_code == 404
    data = response.json()
    assert "Product not found" in data['detail']

def test_delete_product_not_found(client, admin_auth_headers):
    """Test deleting a non-existent product."""
    admin_access_headers, _ = admin_auth_headers
    response = client.delete('/api/products/999', headers=admin_access_headers)
    assert response.status_code == 404
    data = response.json()
    assert "Product not found" in data['detail']
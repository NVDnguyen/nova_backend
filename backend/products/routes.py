# backend/products/routes.py
from fastapi import APIRouter, HTTPException, status, Depends
from pymongo import DESCENDING, collection
from typing import List
from fastapi_cache.decorator import cache

from ..database import get_products_collection
from ..models import Product, ProductCreate, ProductUpdate
from ..models import Role
from .. import auth

router = APIRouter(
    prefix="/api/products",
    tags=["Products"]
)

def get_next_product_id(products_collection: collection.Collection):
    """
    Finds the highest product 'id' and returns the next integer.
    NOTE: In a highly concurrent production environment, a more robust solution like
    a dedicated 'counters' collection with atomic increments should be used.
    """
    last_product = products_collection.find_one(sort=[("id", DESCENDING)])
    if last_product and 'id' in last_product:
        return last_product['id'] + 1
    return 1 # Start from 1 if collection is empty

@router.get('', response_model=List[Product])
@cache(expire=60)
async def get_products(
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """API endpoint to get all available products."""
    print("--- [DATABASE HIT] Fetching products from MongoDB ---")
    return list(products_collection.find({}, {'_id': 0}))

@router.post('', status_code=status.HTTP_201_CREATED, response_model=Product)
async def create_product(
    product_to_create: ProductCreate,
    current_user: auth.TokenData = Depends(auth.role_required([Role.ADMIN])),
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """Creates a new product in the database."""
    new_product_doc = product_to_create.model_dump()
    new_product_doc['id'] = get_next_product_id(products_collection)
    new_product = Product.model_validate(new_product_doc)
    products_collection.insert_one(new_product.model_dump())
    
    # In FastAPI, cache invalidation is often handled differently,
    # e.g., via a separate endpoint or event system. For simplicity, we'll skip explicit clearing.
    # await FastAPICache.clear(namespace="fastapi-cache") # This would clear everything
    print("--- Product created. Cache will expire naturally. ---")
    return new_product

@router.get('/{product_id}', response_model=Product)
async def get_product(
    product_id: int,
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """Retrieves a single product by its ID."""
    product = products_collection.find_one({"id": product_id}, {'_id': 0})
    if product:
        return product
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

@router.get('/barcode/{barcode}', response_model=Product)
async def get_product_by_barcode(
    barcode: str,
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """Retrieves a single product by its barcode."""
    product = products_collection.find_one({"barcode": barcode}, {'_id': 0})
    if product:
        return product
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found by barcode")

@router.put('/{product_id}', response_model=Product)
async def update_product(
    product_id: int,
    update_data: ProductUpdate,
    current_user: auth.TokenData = Depends(auth.role_required([Role.ADMIN])),
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """Updates an existing product."""
    update_fields = update_data.model_dump(exclude_unset=True)
    
    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided")
        
    result = products_collection.update_one({"id": product_id}, {"$set": update_fields})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
    print("--- Product updated. Cache will expire naturally. ---")
    updated_product = products_collection.find_one({"id": product_id}, {'_id': 0})
    return updated_product

@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: auth.TokenData = Depends(auth.role_required([Role.ADMIN])),
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """Deletes a product from the database."""
    result = products_collection.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    print("--- Product deleted. Cache will expire naturally. ---")
    return
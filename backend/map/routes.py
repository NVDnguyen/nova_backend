# backend/map/routes.py
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pymongo.collection import Collection
from typing import List, Optional
from io import BytesIO
from bson.binary import Binary
from ..database import get_products_collection, get_map_collection

router = APIRouter(
    prefix="/api/map",
    tags=["Map"]
)

@router.get("/search", response_model=List[str])
async def search_products(
    q: str = Query(..., min_length=1, description="Product search query"),
    products_collection: Collection = Depends(get_products_collection),
):
    """Return product name suggestions based on text search."""
    # MongoDB text search (ensure text index on 'name')
    results = products_collection.find({"$text": {"$search": q}}, {"name": 1, "_id": 0})
    names = [doc["name"] for doc in results]
    if not names:
        # fallback: partial match
        results = products_collection.find({"name": {"$regex": q, "$options": "i"}}, {"name": 1, "_id": 0})
        names = [doc["name"] for doc in results]
    return names

@router.get("/location")
async def get_product_location(
    name: str = Query(..., description="Product name"),
    products_collection: Collection = Depends(get_products_collection),
):
    """Return product location(s) and details. Case-insensitive name match."""
    # Use case-insensitive exact match for name
    product = products_collection.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}, {"location": 1, "name": 1, "subtitle": 1, "price": 1, "quantity": 1, "unit": 1, "product_img_url": 1, "_id": 0})
    if not product or "location" not in product:
        raise HTTPException(status_code=404, detail="Product or location not found")
    # Ensure location is always a list
    loc = product["location"]
    if not isinstance(loc, list):
        product["location"] = [loc]
    return product

@router.get("/map_image")
async def get_map_image(map_collection=Depends(get_map_collection)):
    """Return the shopping mall map image from MongoDB."""
    map_doc = map_collection.find_one({"name": "mall_map"})
    if not map_doc or "image" not in map_doc:
        raise HTTPException(status_code=404, detail="Map image not found")
    image_bytes = map_doc["image"]
    return StreamingResponse(BytesIO(image_bytes), media_type="image/png")

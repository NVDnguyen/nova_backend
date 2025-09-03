# cart/routes.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from ..models import Product, CartOpRequest, CartOpResponse
from ..auth import get_current_user, TokenData
from backend.database import get_carts_collection, get_products_collection

router = APIRouter(
    prefix="/api/cart",
    tags=["Cart"]
)


@router.post("/op", response_model=CartOpResponse)
async def cart_operation(
    request: CartOpRequest,
    user: TokenData = Depends(get_current_user)
):
    """
    Execute cart operation (add/remove items) with transactional safety.
    
    This endpoint handles cart modifications with:
    - Product existence validation
    - Stock availability checks
    - Atomic cart operations
    """
    try:
        # Get MongoDB collections
        products_collection = get_products_collection()
        carts_collection = get_carts_collection()
        
        # 1. Validate product exists
        product = products_collection.find_one({"barcode": request.barcode})
        if not product:
            return CartOpResponse(
                success=False,
                message=f"Unknown barcode: {request.barcode}",
                cart_total_items=0
            )
        
        # 2. Get current cart
        user_cart = carts_collection.find_one({"user_identity": user.identity})
        if not user_cart:
            user_cart = {"user_identity": user.identity, "items": []}
        
        # Find item in cart
        cart_item = None
        for item in user_cart.get("items", []):
            if item.get("barcode") == request.barcode:
                cart_item = item
                break
        
        # 3. Validate operation based on action
        if request.action == "add":
            # Check stock availability
            if product.get("quantity", 0) < request.quantity:
                return CartOpResponse(
                    success=False,
                    message=f"Insufficient stock. Available: {product.get('quantity', 0)}, Requested: {request.quantity}",
                    cart_total_items=sum(item.get("quantity", 0) for item in user_cart.get("items", []))
                )
        elif request.action == "remove":
            # Check if enough items in cart
            current_cart_quantity = cart_item.get("quantity", 0) if cart_item else 0
            if current_cart_quantity < request.quantity:
                return CartOpResponse(
                    success=False,
                    message=f"Not enough items in cart. Available: {current_cart_quantity}, Requested: {request.quantity}",
                    cart_total_items=sum(item.get("quantity", 0) for item in user_cart.get("items", []))
                )
        
        # 4. Execute operation atomically
        if request.action == "add":
            if cart_item:
                # Update existing item
                carts_collection.update_one(
                    {"user_identity": user.identity, "items.barcode": request.barcode},
                    {"$inc": {"items.$.quantity": request.quantity}}
                )
            else:
                # Add new item
                new_item = {
                    "barcode": request.barcode,
                    "name": product.get("name"),
                    "price": product.get("price"),
                    "quantity": request.quantity
                }
                carts_collection.update_one(
                    {"user_identity": user.identity},
                    {"$push": {"items": new_item}},
                    upsert=True
                )
        elif request.action == "remove":
            if cart_item.get("quantity", 0) == request.quantity:
                # Remove item completely
                carts_collection.update_one(
                    {"user_identity": user.identity},
                    {"$pull": {"items": {"barcode": request.barcode}}}
                )
            else:
                # Decrease quantity
                carts_collection.update_one(
                    {"user_identity": user.identity, "items.barcode": request.barcode},
                    {"$inc": {"items.$.quantity": -request.quantity}}
                )
        
        # 5. Get updated cart for response
        updated_cart = carts_collection.find_one({"user_identity": user.identity})
        total_items = sum(item.get("quantity", 0) for item in updated_cart.get("items", []))
        
        return CartOpResponse(
            success=True,
            message=f"Cart updated: {request.action} {request.quantity}x {product.get('name')}",
            cart_total_items=total_items
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Cart operation failed: {str(e)}")


from fastapi import Depends, HTTPException
from pymongo import collection
from ..auth import get_current_user, TokenData
from ..models import Product
from backend.database import get_carts_collection, get_products_collection

@router.get("/op", response_model=List[Product])
def get_cart(
    user: TokenData = Depends(get_current_user),
    carts_collection: collection.Collection = Depends(get_carts_collection),
    products_collection: collection.Collection = Depends(get_products_collection),
):
    """
    Get the current user's cart as a list of Product objects.
    Each returned Product includes full metadata from the products collection,
    with its `quantity` set to the quantity in the cart.
    """
    # Fetch the user's cart (only need items)
    user_cart = carts_collection.find_one(
        {"user_identity": user.identity},
        {"_id": 0, "items": 1}
    )
    cart_items = user_cart.get("items", []) if user_cart else []
    if not cart_items:
        return []

    # Collect barcodes from cart and fetch corresponding product docs
    barcodes = [it.get("barcode") for it in cart_items if it.get("barcode")]
    if not barcodes:
        return []

    products = list(
        products_collection.find(
            {"barcode": {"$in": barcodes}},
            {"_id": 0}  # strip Mongo _id for Pydantic compatibility
        )
    )

    # Index product metadata by barcode for quick merge
    by_barcode = {p.get("barcode"): p for p in products}

    # Build response: merge metadata + cart quantity
    result: List[Product] = []
    for it in cart_items:
        bc = it.get("barcode")
        qty = int(it.get("quantity", 0) or 0)
        meta = by_barcode.get(bc)
        if not meta:
            # Product no longer exists or barcode mismatch — skip silently
            # (alternatively, you could log or surface a warning)
            continue
        merged = dict(meta)
        merged["quantity"] = max(qty, 0)  # ensure non-negative
        result.append(Product(**merged))

    return result

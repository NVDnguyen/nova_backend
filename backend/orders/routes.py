# backend/orders/routes.py
from fastapi import APIRouter, HTTPException, status, Depends, Body
from pymongo import DESCENDING, collection
import uuid
from datetime import datetime
from typing import List, Optional
import io
import qrcode
import qrcode.image.svg
import httpx

import hmac
import hashlib
from ..models import (
    CheckoutPayload,
    OrderHistoryItem,
    OrderStatus,
    VietQRWebhookPayload,
    VietQRGenerateRequest,
    VietQRTransactionState,
    VietQRGenerateResponse,
    OrderStatusResponse,
)
from ..database import get_orders_collection
from .tasks import process_order
from ..models import Role
from .. import auth, config

router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"]
)
@router.post('/checkout')
async def initiate_checkout_and_generate_qr(
    cart_data: CheckoutPayload,
    current_user: auth.TokenData = Depends(auth.role_required([Role.SHOP_CLIENT, Role.GUEST])),
    orders_collection: collection.Collection = Depends(get_orders_collection),
):
    """API endpoint to handle checkout and generate QR code via VietQR API."""
    if not cart_data.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot checkout with an empty cart")

    user_identity = current_user.identity
    order_id = str(uuid.uuid4())
    print(f"--- [API] Initiating payment for order {order_id} by {user_identity} ---")
    
    # Create a pending order record in the database
    pending_order = OrderHistoryItem(
        **cart_data.model_dump(),
        order_id=order_id,
        user_identity=user_identity,
        created_at=datetime.utcnow(),
        status=OrderStatus.PENDING
    )
    orders_collection.insert_one(pending_order.model_dump())

    # --- Generate VietQR code via external API ---
    vietqr_request_data = VietQRGenerateRequest(
        acqId=int(config.settings.VIETQR_BANK_BIN),
        accountNo=config.settings.VIETQR_ACCOUNT_NO,
        accountName=config.settings.VIETQR_ACCOUNT_NAME,
        amount=int(pending_order.total_cost),
        addInfo=f"Thanh toan don hang {order_id}",
        template="compact2"
    )

    qr_svg_string = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.vietqr.io/v2/generate",
                json=vietqr_request_data.model_dump(),
                timeout=10.0 # It's good practice to set a timeout
            )
            response.raise_for_status()
            api_response = VietQRGenerateResponse.model_validate(response.json())

            if api_response.code != "00" or not api_response.data:
                print(f"--- [API] VietQR API error for order {order_id}: {api_response.desc} ---")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to generate QR code: {api_response.desc}"
                )
            
            # The VietQR API gives us the raw data for the QR code.
            # We can use this to generate our own SVG image.
            qr_code_data = api_response.data.qrCode
            
            # Generate SVG image in memory
            img = qrcode.make(qr_code_data, image_factory=qrcode.image.svg.SvgPathImage)
            stream = io.BytesIO()
            img.save(stream)
            qr_svg_string = stream.getvalue().decode('utf-8')
    except httpx.RequestError as e:
        print(f"--- [API] HTTP request to VietQR API failed for order {order_id}: {e} ---")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to the payment QR service."
        )

    return {
        "message": "Order created. Please scan the QR code to pay.",
        "order_id": order_id,
        "qr_svg": qr_svg_string
    }

@router.get('/history', response_model=List[OrderHistoryItem])
def get_order_history(
    current_user: auth.TokenData = Depends(auth.role_required([Role.SHOP_CLIENT, Role.GUEST])),
    orders_collection: collection.Collection = Depends(get_orders_collection),
):
    """Retrieves the order history for the currently logged-in user."""
    user_identity = current_user.identity
    try:
        history = list(orders_collection.find(
            {"user_identity": user_identity, "status": {"$ne": OrderStatus.PENDING}},
            {'_id': 0}
        ).sort("created_at", DESCENDING))
        return history
    except Exception as e:
        print(f"Error fetching order history for {user_identity}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while fetching order history.")

@router.get('/{order_id}/status', response_model=OrderStatusResponse)
def get_order_status(
    order_id: str,
    orders_collection: collection.Collection = Depends(get_orders_collection),
):
    """
    Allows a client to poll for the payment status of an order without authentication.
    This is a public endpoint.
    """
    order = orders_collection.find_one(
        {"order_id": order_id},
        {"_id": 0, "order_id": 1, "status": 1}
    )

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    
    return order

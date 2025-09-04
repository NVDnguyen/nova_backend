# models.py
from typing import List, Optional
from enum import Enum
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator, EmailStr
from datetime import datetime


class ProductBase(BaseModel):
    name: str
    subtitle: str
    price: float = Field(..., ge=0)
    currency: str = Field(default="VND", description="Currency code, e.g. 'VND'.")
    unit: str = Field(
        default="each",
        description="The unit of measurement (e.g., 'each', 'kg', 'pack').",
    )
    product_img_url: Optional[str] = Field(
        default=None, description="URL for the product's image."
    )
    barcode: Optional[str] = Field(
        default=None, description="Barcode for the product (EAN/UPC/other)."
    )


# Model for creating a new product. 'quantity' is the initial stock.
class ProductCreate(ProductBase):
    quantity: int = Field(
        default=1, ge=0, description="The initial stock quantity of the product."
    )


# Model for what is stored in/retrieved from the DB and used in the cart.
class Product(ProductBase):
    id: int
    quantity: int = Field(
        ..., ge=0, description="The stock quantity of the product, or quantity in cart."
    )


# Model for updating a product. All fields are optional.
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    subtitle: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, description="Currency code, e.g. 'VND'.")
    quantity: Optional[int] = Field(default=None, ge=0)
    unit: Optional[str] = None
    product_img_url: Optional[str] = None
    barcode: Optional[str] = None


# --- User and Auth Models ---


class Role(str, Enum):
    ADMIN = "admin"
    SHOP_CLIENT = "shop_client"
    GUEST = "guest"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class User(BaseModel):
    email: EmailStr
    hashed_password: str
    role: Role = Role.SHOP_CLIENT


class CardLogin(BaseModel):
    card_id: str = Field(..., min_length=4, max_length=16)  # Example length constraints


# --- Order History Models ---


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    COMPLETED = "completed"  # After inventory processing


class CheckoutPayload(BaseModel):
    """Data model for the entire checkout payload sent from the client."""

    items: List[Product]
    shipping_cost: float = Field(..., ge=0)
    subtotal: float = Field(..., ge=0)
    total_cost: float = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_and_recalculate_totals(self) -> "CheckoutPayload":
        """
        Validates that the subtotal and total_cost sent by the client are correct.
        This is a security measure to prevent price manipulation from the client-side.
        """
        # Use Decimal for precision with currency to avoid floating point errors
        calculated_subtotal = sum(
            Decimal(str(item.price)) * Decimal(item.quantity) for item in self.items
        )
        calculated_total = calculated_subtotal + Decimal(str(self.shipping_cost))

        # Compare with a small tolerance for floating point inaccuracies
        if not abs(Decimal(str(self.subtotal)) - calculated_subtotal) < Decimal(
            "0.01"
        ):
            raise ValueError(
                f"Subtotal mismatch. Client sent {self.subtotal}, server calculated {calculated_subtotal:.2f}"
            )

        if not abs(Decimal(str(self.total_cost)) - calculated_total) < Decimal(
            "0.01"
        ):
            raise ValueError(
                f"Total cost mismatch. Client sent {self.total_cost}, server calculated {calculated_total:.2f}"
            )

        return self


class OrderHistoryItem(CheckoutPayload):
    """Represents a single completed order in the user's history."""

    order_id: str
    user_identity: str
    created_at: datetime
    status: OrderStatus = OrderStatus.PENDING


class OrderStatusResponse(BaseModel):
    """Response model for checking an order's status."""

    order_id: str
    status: OrderStatus


class VietQRTransactionState(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class VietQRWebhookPayload(BaseModel):
    paymentRequestId: str
    state: VietQRTransactionState
    amount: int
    description: str
    referenceId: str  # This will be our order_id
    merchantId: str
    extraData: str
    signature: str


# --- VietQR API Models ---
class VietQRGenerateRequest(BaseModel):
    accountNo: str
    accountName: str
    acqId: int
    amount: int
    addInfo: str
    template: str = "compact2"

class VietQRGenerateResponseData(BaseModel):
    qrCode: str
    qrDataURL: str

class VietQRGenerateResponse(BaseModel):
    code: str
    desc: str
    data: Optional[VietQRGenerateResponseData] = None

# backend/users/routes.py
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pymongo import collection
import uuid

from .. import pwd_context, config
from ..database import get_users_collection
from ..models import UserCreate, User, CardLogin, Role
from .. import auth

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

@router.post('/register', status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserCreate,
    users_collection: collection.Collection = Depends(get_users_collection),
):
    """Registers a new user."""
    if users_collection.find_one({"email": user_data.email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Assign role based on email
    user_role = Role.ADMIN if user_data.email == config.ADMIN_EMAIL else Role.SHOP_CLIENT

    hashed_password = pwd_context.hash(user_data.password)
    new_user = User(
        email=user_data.email, 
        hashed_password=hashed_password, 
        role=user_role)
    
    users_collection.insert_one(new_user.model_dump())
    
    return {"message": f"User {user_data.email} created successfully"}

@router.post('/login')
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    users_collection: collection.Collection = Depends(get_users_collection),
):
    """Logs in a user and returns JWT access and refresh tokens."""
    user_doc = users_collection.find_one({"email": form_data.username})
    
    if user_doc and pwd_context.verify(form_data.password, user_doc["hashed_password"]):
        user_role = user_doc.get("role", Role.SHOP_CLIENT) # Default to SHOP_CLIENT if role not found
        token_data = {"sub": form_data.username, "role": user_role.value}
        access_token = auth.create_access_token(data=token_data)
        refresh_token = auth.create_refresh_token(data={"sub": form_data.username})
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post('/card_login')
def card_login(card_login_data: CardLogin):
    """
    Logs in a user with a card ID and returns a JWT access token with limited permissions.
    """
    card_id = card_login_data.card_id

    # --- DEMO VALIDATION ---
    # In a real application, you would look up the card_id in a database
    # and verify its validity, potentially linking it to a user account.
    VALID_CARD_IDS = ["CARD123", "GUEST456", "TEMP789"]
    if card_id not in VALID_CARD_IDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid card ID"
        )

    # Create a JWT with the card_id as identity and a custom 'role' claim
    token_data = {"sub": card_id, "role": Role.SHOP_CLIENT.value}
    access_token = auth.create_access_token(data=token_data)
    refresh_token = auth.create_refresh_token(data={"sub": card_id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post('/refresh')
def refresh_access_token(
    current_user: auth.TokenData = Depends(auth.get_current_user),
    users_collection: collection.Collection = Depends(get_users_collection),
):
    """
    Endpoint to refresh an expired access token using a valid refresh token.
    NOTE: In a real app, you'd check if the token is a refresh token (e.g., via a 'type' claim).
    For simplicity, we're allowing any valid token to generate a new access token.
    """
    # The role might not be in the refresh token, so we fetch it from the DB
    user_doc = users_collection.find_one({"email": current_user.identity})
    user_role = Role.SHOP_CLIENT # Default for card IDs or if not found
    if user_doc:
        user_role = user_doc.get("role", Role.SHOP_CLIENT)

    token_data = {"sub": current_user.identity, "role": user_role.value}
    new_access_token = auth.create_access_token(data=token_data)
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post('/guest_login')
def guest_login(
    users_collection: collection.Collection = Depends(get_users_collection),
):
    """
    Creates a temporary guest user and logs them in, returning JWT tokens.
    Each call creates a new guest user.
    """
    guest_id = str(uuid.uuid4())
    guest_email = f"guest_{guest_id}@temp.com"
    # Guests don't need a memorable password, but we hash one for consistency with User model
    hashed_password = pwd_context.hash(str(uuid.uuid4())) 

    new_guest_user = User(
        email=guest_email,
        hashed_password=hashed_password,
        role=Role.SHOP_CLIENT
    )
    users_collection.insert_one(new_guest_user.model_dump())

    token_data = {"sub": guest_email, "role": Role.SHOP_CLIENT.value}
    access_token = auth.create_access_token(data=token_data)
    refresh_token = auth.create_refresh_token(data={"sub": guest_email})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
# backend/database.py
from pymongo import MongoClient, ASCENDING, collection
from .config import settings
import random
import os
import json
# --- Database Connection ---
# This setup creates a single client that can be shared across the application.
# PyMongo's client is thread-safe and includes connection pooling.
client = MongoClient(settings.MONGO_URI)
db = client["shopping_cart_db"]

# --- Collection Getters (for Dependency Injection) ---
def get_products_collection() -> collection.Collection:
    return db["products"]

def get_users_collection() -> collection.Collection:
    return db["users"]

def get_orders_collection() -> collection.Collection:
    return db["order_history"]

def get_map_collection() -> collection.Collection:
    return db["map"]

# --- Database Helpers ---
def ensure_indexes():
    """Creates unique indexes for collections if they don't exist."""
    get_products_collection().create_index([("id", ASCENDING)], unique=True)
    get_users_collection().create_index([("email", ASCENDING)], unique=True)
    print("Database indexes ensured.")

PRODUCT_NAMES = [
    "Apple", "Banana", "Orange", "Milk", "Bread", "Eggs", "Cheese", "Chicken", "Rice", "Pasta",
    "Tomato", "Potato", "Onion", "Carrot", "Cucumber", "Lettuce", "Yogurt", "Butter", "Juice", "Coffee"
]
SUBTITLES = ["Fresh", "Organic", "Imported", "Local", "Premium", "Budget"]
UNITS = ["each", "kg", "pack", "bottle", "box"]
random.seed(42)

def random_location():
    return {"x": 5200, "y": 2400}
import string
def random_barcode(length=13):
    """Generate a random numeric barcode string (EAN-13 style)."""
    return ''.join(random.choices(string.digits, k=length))

def generate_products(n=20):
    products = []
    # Add original demo products (conform to ProductBase)
    demo_products = [
        {
            'id': 1,
            'name': 'Fifa 19',
            'subtitle': 'PS4',
            'price': 64.00,
            'currency': 'VND',
            'quantity': 1,
            'unit': 'pack',
            'product_img_url': 'https://via.placeholder.com/80/cccccc/000000?Text=Game',
            'barcode': random_barcode()
        },
        {
            'id': 2,
            'name': 'Glacier White 500GB',
            'subtitle': 'PS4',
            'price': 249.99,
            'currency': 'VND',
            'quantity': 1,
            'unit': 'each',
            'product_img_url': 'https://via.placeholder.com/80/f0f0f0/000000?Text=Console',
            'barcode': random_barcode()
        },
        {
            'id': 3,
            'name': 'Platinum Headset',
            'subtitle': 'PS4',
            'price': 119.99,
            'currency': 'VND',
            'quantity': 1,
            'unit': 'each',
            'product_img_url': 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory',
            'barcode': random_barcode()
        },
        {"id": 4, "name": "Lay stax original yellow 150g", "subtitle": "", "price": 10.0, "currency": "VND", "quantity": 1, "unit": "each", "product_img_url": 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory', "barcode": "8850718820634"},
        {"id": 5, "name": "swing red bo bit tet 55g", "subtitle": "", "price": 10.0, "currency": "VND", "quantity": 1, "unit": "each", "product_img_url": 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory', "barcode": "8936036021660"},
        {"id": 6, "name": "haohao  chua cay hop 67g", "subtitle": "", "price": 10.0, "currency": "VND", "quantity": 1, "unit": "each", "product_img_url": 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory', "barcode": "8934563651138"},
        {"id": 7, "name": "lau thai tom hop 67g", "subtitle": "", "price": 10.0, "currency": "VND", "quantity": 1, "unit": "each", "product_img_url": 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory', "barcode": "8934563619138"},
        {"id": 8, "name": "nuoc khoang thien nhien vivan 500ml", "subtitle": "", "price": 10.0, "currency": "VND", "quantity": 1, "unit": "each", "product_img_url": 'https://via.placeholder.com/80/e0e0e0/000000?Text=Accessory', "barcode": "8936136163185"}
    ]
    products.extend(demo_products)
    # Add random mock products
    for i in range(n):
        name = PRODUCT_NAMES[i % len(PRODUCT_NAMES)] + f" {i+1}"
        product = {
            "id": i+100,
            "name": name,
            "subtitle": random.choice(SUBTITLES),
            "price": round(random.uniform(1, 100), 2),
            "currency": "VND",
            "quantity": random.randint(1, 50),
            "unit": random.choice(UNITS),
            "product_img_url": "https://via.placeholder.com/80/cccccc/000000?Text=Product",
            "location": [random_location() for _ in range(random.randint(1, 3))],
            "barcode": None
        }
        products.append(product)
    return products

def seed_database_if_empty():
    """Clears and reseeds the products and map collections with initial data, only in development."""
    if getattr(settings, "APP_ENV", "development") != "development":
        print("Skipping database seeding: not in development environment.")
        return
    products_collection = get_products_collection()
    map_collection = get_map_collection()
    # Always ensure text index exists
    products_collection.create_index([("name", "text")])

    # Clear collections before reseeding
    products_collection.delete_many({})
    map_collection.delete_many({})

    # Try to load products from JSONL file
    
    seed_file = os.path.join(os.path.dirname(__file__), "tests", "database_seed.jsonl")
    loaded_products = []
    if os.path.exists(seed_file):
        with open(seed_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        prod = json.loads(line)
                        # Ensure all required fields exist, fill defaults if missing
                        prod.setdefault("currency", "VND")
                        prod.setdefault("barcode", random_barcode())
                        prod.setdefault("unit", "each")
                        prod.setdefault("product_img_url", None)
                        prod.setdefault("location", [random_location() for _ in range(random.randint(1, 3))])
                        loaded_products.append(prod)
                    except Exception as e:
                        print(f"Error loading product from JSONL: {e}")

    if not loaded_products:
        print("No products loaded from JSONL, generating random samples...")
        loaded_products = generate_products(20)
    else:
        print(f"Loaded {len(loaded_products)} products from JSONL.")

    print("Seeding database with products...")
    products_collection.insert_many(loaded_products)
    print("Database seeded.")

    # Seed default_map.png
    default_map_path = os.path.join(os.path.dirname(__file__), "default_map.png")
    with open(default_map_path, "rb") as f:
        image_bytes = f.read()
    map_doc = {"name": "mall_map", "image": image_bytes, "content_type": "image/png"}
    map_collection.insert_one(map_doc)
    print("Seeded mall map image from default_map.png.")
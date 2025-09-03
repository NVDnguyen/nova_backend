from pymongo import MongoClient
from config import settings  # Đảm bảo file này cùng cấp với database.py

def print_all_products():
    client = MongoClient(settings.MONGO_URI)
    db = client["shopping_cart_db"]
    products = db["products"].find()
    for prod in products:
        print(prod)

if __name__ == "__main__":
    print_all_products()
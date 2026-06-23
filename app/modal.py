from decimal import Decimal
import enum
from flask_login import UserMixin
from datetime import datetime, timedelta
from app import now_eat



# 1. Qeexidda Enum-ka
class UserRole(enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    user = "user"
    customer="customer"




class User(UserMixin):
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.username = self.data.get("username")
        self.fullname = self.data.get("fullname")
        self.email = self.data.get("email")
        self.password = self.data.get("password")

        # Role system (Mongo style)
        self.role = self.data.get("role", "user")
        self.role_id = self.data.get("role_id")  # ObjectId string if using reference

        # Basic info
        self.phone = self.data.get("phone")
        self.country = self.data.get("country")
        self.city = self.data.get("city")
        self.state = self.data.get("state")
        self.address = self.data.get("address")
        self.bio = self.data.get("bio")
        self.photo = self.data.get("photo")
        self.gender = self.data.get("gender")
        self.photo_visibility = self.data.get("photo_visibility", "everyone")

        self.status = self.data.get("status", True)

        # Device info
        self.device = self.data.get("device")
        self.browser = self.data.get("browser")
        self.platform = self.data.get("platform")
        self.device_name = self.data.get("device_name")
        self.interface_name = self.data.get("interface_name")

        # Security
        self.is_verified = self.data.get("is_verified", False)
        self.auth_status = self.data.get("auth_status", "logout")
        self.session_token = self.data.get("session_token")
        self.login_time = self.data.get("login_time")
        self.last_seen = self.data.get("last_seen")

        self.phone_verified = self.data.get("phone_verified", False)
        self.two_factor_enabled = self.data.get("two_factor_enabled", False)
        self.two_factor_code = self.data.get("two_factor_code")
        self.two_factor_expires_at = self.data.get("two_factor_expires_at")

        self.last_login_ip = self.data.get("last_login_ip")
        self.remember_token = self.data.get("remember_token")
        self.failed_login_attempts = self.data.get("failed_login_attempts", 0)

        self.auth_provider = self.data.get("auth_provider", "local")
        self.last_active = self.data.get("last_active")

        # Socials
        self.facebook = self.data.get("facebook")
        self.twitter = self.data.get("twitter")
        self.google = self.data.get("google")
        self.whatsapp = self.data.get("whatsapp")
        self.instagram = self.data.get("instagram")
        self.github = self.data.get("github")
        self.github_id = self.data.get("github_id")

        # Timestamps
        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")

        # Embedded relationships (Mongo style)
        self.user_logs = self.data.get("user_logs", [])
        self.sessions = self.data.get("sessions", [])
        self.user_permissions = self.data.get("user_permissions", [])

        self.patient_appointments = self.data.get("patient_appointments", [])
        self.doctor_appointments = self.data.get("doctor_appointments", [])

    # Flask-Login required
    def get_id(self):
        return self.id

    @property
    def is_active(self):
        return self.status is True

    @property
    def permissions(self):
        return [p.get("permission") for p in self.user_permissions]

    def to_dict(self):
        return self.data

    def __repr__(self):
        return f"<User {self.username}>"


class Category:
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.name = self.data.get("name")
        self.image = self.data.get("image")
        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")

    def to_dict(self):
        return {
            "_id": self.id,
            "name": self.name,
            "image": self.image,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def __repr__(self):
        return f"<Category {self.name}>"


class Product:
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.category_id = str(self.data.get("category_id"))

        self.name = self.data.get("name")
        self.description = self.data.get("description")
        self.price = self.data.get("price", 0)
        self.stock = self.data.get("stock", 0)
        self.image = self.data.get("image")

        # Optional advanced fields
        self.brand = self.data.get("brand")
        self.sku = self.data.get("sku")
        self.status = self.data.get("status", True)
        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")


    def is_in_stock(self):
        return self.stock > 0

    def reduce_stock(self, qty=1):
        if self.stock >= qty:
            self.stock -= qty

    def to_dict(self):
        return {
            "_id": self.id,
            "category_id": self.category_id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock": self.stock,
            "image": self.image,
            "brand": self.brand,
            "sku": self.sku,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at

        }

    def __repr__(self):
        return f"<Product {self.name}>"
    

class Cart:
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.user_id = str(self.data.get("user_id"))

        self.items = self.data.get("items", [])  
        # items = [{"product_id": "...", "qty": 2, "price": 25}]

        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")

    def total_price(self):
        return sum(item["qty"] * item["price"] for item in self.items)

    def total_items(self):
        return sum(item["qty"] for item in self.items)

    def to_dict(self):
        return {
            "_id": self.id,
            "user_id": self.user_id,
            "items": self.items,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def __repr__(self):
        return f"<Cart {self.user_id}>"
    

class Order:
    def __init__(self, data):
        self.data = data or {}
        self.id = str(self.data.get("_id"))
        self.user_id = str(self.data.get("user_id"))
        self.items = self.data.get("items", [])
        self.total = float(self.data.get("total", 0))
        
        # Lacagaha iyo Deynta
        self.paid_amount = float(self.data.get("paid_amount", 0))
        self.payment_history = self.data.get("payment_history", []) # List of dicts
        
        self.status = self.data.get("status", "pending")
        self.payment_status = self.data.get("payment_status", "unpaid")
        
        # Xusuusinta
        self.reminder_date = self.data.get("reminder_date") # Marka la filayo lacagta
        
        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")

    @property
    def remaining_balance(self):
        return self.total - self.paid_amount

    def add_payment(self, amount, note=""):
        """Habka ugu muhiimsan ee loo diiwaan galiyo lacagta cusub"""
        amount = float(amount)
        self.paid_amount += amount
        self.payment_history.append({
            "amount": amount,
            "date": datetime.now(),
            "note": note
        })
        
        # Update status-ka haddii la dhammaystiray
        if self.paid_amount >= self.total:
            self.payment_status = "paid"
        else:
            self.payment_status = "partial" # Status cusub oo muhiim ah

    def to_dict(self):
        return {
            "_id": self.id,
            "user_id": self.user_id,
            "total": self.total,
            "paid_amount": self.paid_amount,
            "payment_history": self.payment_history,
            "payment_status": self.payment_status,
            "remaining_balance": self.remaining_balance,
            "reminder_date": self.reminder_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class Session:
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.user_id = str(self.data.get("user_id"))

        self.session_token = self.data.get("session_token")
        self.ip = self.data.get("ip")
        self.device = self.data.get("device")

        self.created_at = self.data.get("created_at", datetime.utcnow())
        self.expires_at = self.data.get(
            "expires_at",
            datetime.utcnow() + timedelta(days=7)
        )

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def is_active(self):
        return not self.is_expired()

    def to_dict(self):
        return {
            "_id": self.id,
            "user_id": self.user_id,
            "session_token": self.session_token,
            "ip": self.ip,
            "device": self.device,
            "created_at": self.created_at,
            "expires_at": self.expires_at
        }

    def __repr__(self):
        return f"<Session {self.session_token}>"



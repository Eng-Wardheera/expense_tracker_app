from collections import defaultdict
import datetime
import math
import os
import random
import secrets
import traceback
import uuid

from bson import ObjectId
import cloudinary
from flask import Blueprint, abort, current_app, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app import ALLOWED_EXTENSIONS, google
from app.extensions import mongo
from datetime import datetime, timedelta

from app.modal import Category, Order, Product, User, UserRole


bp = Blueprint('main', __name__)

#------------------------------------------
#---- Function: 1 | Func Allowed Files  ---
#------------------------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
 
def create_guest_session(mongo):
    if not session.get("guest_token"):

        token = secrets.token_hex(24)

        session["guest_token"] = token

        mongo.db.sessions.insert_one({
            "session_token": token,
            "user_id": None,   # guest
            "ip": request.remote_addr,
            "device": request.user_agent.string,
            "created_at": datetime.utcnow(),
            "expires_at": None,
            "routes": []   # store visited pages
        })



# 1. Index route: Wuxuu soo bandhigayaa page-ka iyo data-da projects-ka
@bp.route('/', methods=['GET'])
def index():

    categories = [
        Category(cat)
        for cat in mongo.db.categories.find().sort("name", 1)
    ]

    return render_template(
        "frontend/home/index.html",
        categories=categories
    )


@bp.route('/category/<category_id>')
def single_category(category_id):

    category = mongo.db.categories.find_one({
        "_id": ObjectId(category_id)
    })

    if not category:
        return abort(404)

    products = [
        Product(p)
        for p in mongo.db.products.find({
            "category_id": ObjectId(category_id)
        })
    ]

    # Halkan ku dar tirada
    product_count = len(products)

    return render_template(
        "frontend/pages/single_category.html",
        category=Category(category),
        products=products,
        product_count=product_count
    )


@bp.route('/product/<product_id>')
def product_detail(product_id):

    product = mongo.db.products.find_one({
        "_id": ObjectId(product_id)
    })

    if not product:
        return abort(404)

    return render_template(
        "frontend/pages/product_detail.html",
        product=Product(product)
    )




@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('password_confirmation')

        # 1. Hubi haddii passwords-ku isku mid yihiin
        if password != confirm_password:
            flash("Passwords-ka isma laha!", "danger")
            return redirect(url_for('main.register'))

        # 2. Hubi haddii user-ku horey u jiray
        if mongo.db.users.find_one({"email": email}):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.register'))

        # 3. Role Logic
        user_count = mongo.db.users.count_documents({})
        role = UserRole.superadmin.value if user_count == 0 else UserRole.user.value

        # 4. Save
        new_user = {
            "fullname": fullname,
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "role": role,
            "status": False,
            "created_at": datetime.utcnow()
        }
        mongo.db.users.insert_one(new_user)
        
        flash("Diiwaangelinta way guulaysatay!", "success")
        return redirect(url_for('main.login'))

    # Wadada saxda ah ee faylkaaga:
    return render_template("backend/auth/auth-register.html")


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Haddi uu user-ku horay u soo galay, u dir dashboard-ka
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remembr_me') else False

        # 1. Ka raadi user-ka database-ka
        user_data = mongo.db.users.find_one({"email": email})

        # 2. Hubi haddii password-ku sax yahay
        if user_data and check_password_hash(user_data.get('password'), password):
            # Samee User object
            user = User(user_data) 
            
            # 3. Login u samee
            login_user(user, remember=remember)
            
            flash("Si guul leh ayaad u gashay dashboard-ka!", "success")
            return redirect(url_for('main.dashboard')) 
        else:
            flash("Email ama Password khaldan!", "danger")
            # Waxaan u beddelay 'auth.login' si uu ugu laabto isla boggaas
            return redirect(url_for('main.login')) 

    return render_template("backend/auth/auth-login.html")


@bp.app_errorhandler(403)
def forbidden(error):
    return render_template('frontend/errors/403.html'), 403

@bp.route("/login/google")
def login_google():
    redirect_uri = url_for("main.google_callback", _external=True)
    print("REDIRECT URI:", redirect_uri)
    return google.authorize_redirect(redirect_uri)



@bp.route("/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    email = user_info.get("email")

    # 1. Check if the user exists in your database
    raw_user = mongo.db.users.find_one({"email": email})

    # 2. If the user does not exist, block the login
    if not raw_user:
        flash("You do not have an account. Please register first.", "danger")
        return redirect(url_for("main.login"))

    # 3. Optional: Check if the account was registered via Google previously
    # This prevents users from trying to log in with Google to an email 
    # that was registered via standard email/password (if you prefer).
    if raw_user.get("auth_provider") != "google":
        # You could also choose to update their profile here instead of blocking
        pass

    # 4. Proceed with Login
    user_obj = User(raw_user)
    login_user(user_obj, remember=True)
    
    flash("Successfully logged in with Google!", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
@login_required
def dashboard():

    # ❌ role guard
    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    # ================= USERS =================
    total_users = mongo.db.users.count_documents({})
    total_admins = mongo.db.users.count_documents({"role": "admin"})
    total_customers = mongo.db.users.count_documents({"role": "user"})

    # ================= PRODUCTS =================
    total_products = mongo.db.products.count_documents({})

    total_stock_result = mongo.db.products.aggregate([
        {"$group": {"_id": None, "total_stock": {"$sum": "$stock"}}}
    ])
    total_stock_result = list(total_stock_result)
    total_stock = total_stock_result[0]["total_stock"] if total_stock_result else 0

    # ================= ORDERS =================

    # ✔️ use separate queries (IMPORTANT FIX)
    orders_cursor = mongo.db.orders.find()
    orders = [Order(o) for o in orders_cursor]

    total_income = sum(float(o.total or 0) for o in orders if o.payment_status == "paid")
    total_unpaid = sum(float(o.total or 0) for o in orders if o.payment_status != "paid")

    total_orders = len(orders)

    # ✔️ NEW CURSOR FOR RECENT (DO NOT reuse old one)
    recent_orders = list(
        mongo.db.orders.find().sort("created_at", -1).limit(5)
    )

    # ================= PRODUCTS =================
    # Xisaabinta: (stock * price) mid kasta oo la isku daray
    inventory_value_result = mongo.db.products.aggregate([
        {
            "$project": {
                "item_value": {"$multiply": ["$stock", "$price"]}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_inventory_value": {"$sum": "$item_value"}
            }
        }
    ])
    
    inventory_val_list = list(inventory_value_result)
    total_inventory_value = inventory_val_list[0]["total_inventory_value"] if inventory_val_list else 0

    return render_template(
        "backend/home/dashbaord.html",
        user=current_user,

        total_users=total_users,
        total_admins=total_admins,
        total_customers=total_customers,

        total_products=total_products,
        total_stock=total_stock,

        total_income=total_income,
        total_unpaid=total_unpaid,
        total_orders=total_orders,

        recent_orders=recent_orders,
        total_inventory_value=total_inventory_value
    )



@bp.route("/profile")
@login_required
def profile():
    return render_template(
        "backend/pages/components/users/profile.html",
        user=current_user
    )


@bp.route("/account-settings", methods=["GET", "POST"])
@login_required
def account_settings():

    if request.method == "POST":

        data = {
            "fullname": request.form.get("fullname"),
            "username": request.form.get("username"),
            "phone": request.form.get("phone"),
            "country": request.form.get("country"),
            "state": request.form.get("state"),
            "city": request.form.get("city"),
            "address": request.form.get("address"),
            "bio": request.form.get("bio"),
            "updated_at": datetime.utcnow()
        }

        file = request.files.get("photo")

        if file and file.filename:

            upload_result = cloudinary.uploader.upload(file, folder="users")

            data["photo"] = upload_result["secure_url"]  # 🔥 IMPORTANT

        mongo.db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": data}
        )

        flash("Account updated successfully.", "success")
        return redirect(url_for("main.account_settings"))

    return render_template(
        "backend/pages/components/users/account_settings.html",
        user=current_user
    )



@bp.route('/add-user', methods=['GET', 'POST'])
@login_required
def add_user():

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    countries = [
        {"code": "SO", "name": "Somalia", "flag_url": "https://flagcdn.com/so.svg"},
        {"code": "KE", "name": "Kenya", "flag_url": "https://flagcdn.com/ke.svg"},
    ]

    if request.method == 'POST':

        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role') or "user"
        country = request.form.get('country')
        phone = request.form.get('phone')
        state = request.form.get('state')
        city = request.form.get('city')
        address = request.form.get('address')
        status = True if request.form.get('status') == '1' else False

        # ================= VALIDATION =================
        if not email or not username or not fullname:
            flash("Fadlan buuxi fields-ka muhiimka ah!", "danger")
            return redirect(url_for('main.add_user'))

        if password != confirm_password:
            flash("Passwords-ka isma laha!", "danger")
            return redirect(url_for('main.add_user'))

        if mongo.db.users.find_one({"email": email}):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.add_user'))

        if mongo.db.users.find_one({"username": username}):
            flash("Username-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.add_user'))

        # ================= PHOTO UPLOAD =================
        photo_path = None

        file = request.files.get('photo')

        if file and file.filename:

            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                'static',
                'backend',
                'uploads',
                'users'
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file_path = os.path.join(upload_dir, filename)

            file.save(file_path)

            photo_path = f"backend/uploads/users/{filename}"

        # ================= CREATE USER =================
        new_user = {
            "fullname": fullname,
            "username": username,
            "email": email,
            "password": generate_password_hash(password),
            "role": role,
            "country": country,
            "phone": phone,
            "state": state,
            "city": city,
            "address": address,
            "status": status,
            "photo": photo_path,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        mongo.db.users.insert_one(new_user)

        flash(f"User {username} si guul leh ayaa loo diiwaangeliyey!", "success")
        return redirect(url_for('main.add_user'))

    return render_template(
        "backend/pages/components/users/add_user.html",
        countries=countries
    )


@bp.route('/edit-user/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    try:
        raw_user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        flash("Invalid user ID!", "danger")
        return redirect(url_for('main.index'))

    if not raw_user:
        flash("User-ka lama helin!", "danger")
        return redirect(url_for('main.index'))

    user = User(raw_user)

    if request.method == 'POST':

        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        country = request.form.get('country')
        phone = request.form.get('phone')
        address = request.form.get('address')
        bio = request.form.get('bio')
        status = True if request.form.get('status') == '1' else False

        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # ================= VALIDATION =================
        if mongo.db.users.find_one({
            "username": username,
            "_id": {"$ne": ObjectId(user_id)}
        }):
            flash("Username-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.edit_user', user_id=user_id))

        if mongo.db.users.find_one({
            "email": email,
            "_id": {"$ne": ObjectId(user_id)}
        }):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.edit_user', user_id=user_id))

        updated_data = {
            "fullname": fullname,
            "username": username,
            "email": email,
            "role": role,
            "country": country,
            "phone": phone,
            "address": address,
            "bio": bio,
            "status": status,
            "updated_at": datetime.utcnow()
        }

        # ================= PASSWORD =================
        if password:
            if password != confirm_password:
                flash("Passwords-ka isma laha!", "danger")
                return redirect(url_for('main.edit_user', user_id=user_id))

            updated_data["password"] = generate_password_hash(password)

        # ================= CLOUDINARY PHOTO =================
        file = request.files.get('photo')

        if file and file.filename:

            old_public_id = raw_user.get("photo_public_id")

            # delete old image
            if old_public_id:
                try:
                    cloudinary.uploader.destroy(old_public_id)
                except Exception:
                    pass

            # upload new image
            result = cloudinary.uploader.upload(
                file,
                folder="users"
            )

            updated_data["photo"] = result["secure_url"]
            updated_data["photo_public_id"] = result["public_id"]

        # ================= UPDATE DB =================
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updated_data}
        )

        flash("User si guul leh ayaa loo cusbooneysiiyey!", "success")
        return redirect(url_for('main.edit_user', user_id=user_id))

    return render_template(
        "backend/pages/components/users/edit_user.html",
        user=user
    )


@bp.route('/delete-user/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    try:
        user = mongo.db.users.find_one({
            "_id": ObjectId(user_id)
        })
    except Exception:
        flash("Invalid user ID!", "danger")
        return redirect(url_for('main.all_users'))

    if not user:
        flash("User-ka lama helin!", "danger")
        return redirect(url_for('main.all_users'))

    # ==========================================
    # DELETE USER PHOTO FROM CLOUDINARY
    # ==========================================

    photo_public_id = user.get("photo_public_id")

    if photo_public_id:
        try:
            cloudinary.uploader.destroy(photo_public_id)
        except Exception:
            pass

    # ==========================================
    # FIND ALL USER ORDERS
    # ==========================================

    orders = list(
        mongo.db.orders.find({
            "user_id": ObjectId(user_id)
        })
    )

    # ==========================================
    # RESTORE PRODUCT STOCK
    # ==========================================

    for order in orders:

        for item in order.get("items", []):

            try:
                mongo.db.products.update_one(
                    {
                        "_id": ObjectId(item["product_id"])
                    },
                    {
                        "$inc": {
                            "stock": int(item["qty"])
                        }
                    }
                )
            except Exception:
                pass

    # ==========================================
    # DELETE ALL CUSTOMER ORDERS
    # ==========================================

    mongo.db.orders.delete_many({
        "user_id": ObjectId(user_id)
    })

    # ==========================================
    # DELETE USER
    # ==========================================

    mongo.db.users.delete_one({
        "_id": ObjectId(user_id)
    })

    flash(
        "Customer, orders-kiisii iyo payments-kiisii si guul leh ayaa loo tirtiray!",
        "success"
    )

    return redirect(url_for('main.all_users'))



@bp.route('/all-users', methods=['GET'])
@login_required
def all_users():

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    if current_user.role == 'superadmin':
        # Superadmin sees everyone
        users_cursor = mongo.db.users.find().sort('created_at', -1)

    else:  # admin
        # Admin cannot see superadmins
        users_cursor = mongo.db.users.find(
            {"role": {"$ne": "superadmin"}}
        ).sort('created_at', -1)

    users = [User(user_data) for user_data in users_cursor]

    return render_template(
        'backend/pages/components/users/all_users.html',
        users=users
    )




@bp.route('/add-category', methods=['GET', 'POST'])
@login_required
def add_category():

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    if request.method == 'POST':

        name = request.form.get('name')

        # ================= VALIDATION =================
        if not name:
            flash("Category name waa required!", "danger")
            return redirect(url_for('main.add_category'))

        existing = mongo.db.categories.find_one({"name": name})

        if existing:
            flash("Category-kan hore ayuu u jiraa!", "danger")
            return redirect(url_for('main.add_category'))

        # ================= IMAGE UPLOAD (CLOUDINARY) =================
        image_url = ""

        file = request.files.get('image')

        if file and file.filename:

            upload_result = cloudinary.uploader.upload(
                file,
                folder="categories"
            )

            image_url = upload_result["secure_url"]  # 🔥 CLOUDINARY URL

        # ================= CREATE CATEGORY =================
        new_category = {
            "name": name,
            "image": image_url,
            "created_at": datetime.utcnow()
        }

        mongo.db.categories.insert_one(new_category)

        flash(f"Category '{name}' si guul leh ayaa loo daray!", "success")
        return redirect(url_for('main.add_category'))

    return render_template(
        "backend/pages/components/categories/add_category.html"
    )



@bp.route('/all/categories')
@login_required
def all_categories():
    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)


    categories = mongo.db.categories.find().sort("created_at", -1)

    category_list = [Category(cat) for cat in categories]

    return render_template(
        "backend/pages/components/categories/all_categories.html",
        categories=category_list
    )




@bp.route('/edit-category/<category_id>', methods=['GET', 'POST'])
@login_required
def edit_category(category_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    category = mongo.db.categories.find_one({
        "_id": ObjectId(category_id)
    })

    if not category:
        flash("Category lama helin!", "danger")
        return redirect(url_for('main.all_categories'))

    if request.method == 'POST':

        name = request.form.get('name')

        update_data = {
            "name": name,
            "updated_at": datetime.utcnow()
        }

        file = request.files.get('image')

        # ================= CLOUDINARY IMAGE UPDATE =================
        if file and file.filename:

            upload_result = cloudinary.uploader.upload(
                file,
                folder="categories"
            )

            new_image_url = upload_result["secure_url"]

            update_data["image"] = new_image_url

        # ================= UPDATE DB =================
        mongo.db.categories.update_one(
            {"_id": ObjectId(category_id)},
            {"$set": update_data}
        )

        flash("Category si guul leh ayaa loo cusboonaysiiyay!", "success")
        return redirect(url_for('main.all_categories'))

    return render_template(
        "backend/pages/components/categories/edit_category.html",
        category=Category(category)
    )




@bp.route('/delete-category/<category_id>', methods=['POST'])
@login_required
def delete_category(category_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    try:
        category = mongo.db.categories.find_one({
            "_id": ObjectId(category_id)
        })
    except Exception:
        flash("Invalid category ID!", "danger")
        return redirect(url_for('main.all_categories'))

    if not category:
        flash("Category lama helin!", "danger")
        return redirect(url_for('main.all_categories'))

    # ================= DELETE CLOUDINARY IMAGE =================
    public_id = category.get("public_id")

    if public_id:
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print("Cloudinary delete error:", e)

    # ================= DELETE FROM DB =================
    mongo.db.categories.delete_one({
        "_id": ObjectId(category_id)
    })

    flash("Category si guul leh ayaa loo tirtiray!", "success")
    return redirect(url_for('main.all_categories'))




@bp.route('/add-product', methods=['GET', 'POST'])
@login_required
def add_product():

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    categories = [
        Category(cat)
        for cat in mongo.db.categories.find().sort("name", 1)
    ]

    if request.method == 'POST':

        category_id = request.form.get('category_id')
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        brand = request.form.get('brand')
        sku = request.form.get('sku')

        status = True if request.form.get('status') == '1' else False

        # ================= VALIDATION =================
        if not category_id:
            flash("Category dooro!", "danger")
            return redirect(url_for('main.add_product'))

        if not name:
            flash("Product name waa required!", "danger")
            return redirect(url_for('main.add_product'))

        existing = mongo.db.products.find_one({"name": name})

        if existing:
            flash("Product-kan hore ayuu u jiraa!", "danger")
            return redirect(url_for('main.add_product'))

        # ================= CLOUDINARY IMAGE UPLOAD =================
        image_url = ""
        public_id = ""

        file = request.files.get('image')

        if file and file.filename:

            upload_result = cloudinary.uploader.upload(
                file,
                folder="products"
            )

            image_url = upload_result["secure_url"]
            public_id = upload_result["public_id"]

        # ================= SAVE PRODUCT =================
        product = {
            "category_id": ObjectId(category_id),

            "name": name,
            "description": description,

            "price": price,
            "stock": stock,

            "image": image_url,
            "public_id": public_id,

            "brand": brand,
            "sku": sku,

            "status": status,

            "created_at": datetime.utcnow(),
            "updated_at": None
        }

        mongo.db.products.insert_one(product)

        flash(f"{name} si guul leh ayaa loo daray!", "success")
        return redirect(url_for('main.all_products'))

    return render_template(
        "backend/pages/components/products/add_product.html",
        categories=categories
    )



@bp.route('/all/products')
@login_required
def all_products():

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    products = []

    for item in mongo.db.products.find().sort("created_at", -1):

        product = Product(item)

        category = mongo.db.categories.find_one({
            "_id": ObjectId(product.category_id)
        })

        product.category_name = (
            category.get("name")
            if category else "N/A"
        )

        products.append(product)

    return render_template(
        "backend/pages/components/products/all_products.html",
        products=products
    )




@bp.route('/edit-product/<product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    product = mongo.db.products.find_one({
        "_id": ObjectId(product_id)
    })

    if not product:
        flash("Product lama helin!", "danger")
        return redirect(url_for('main.all_products'))

    categories = [
        Category(cat)
        for cat in mongo.db.categories.find().sort("name", 1)
    ]

    if request.method == 'POST':

        category_id = request.form.get('category_id')
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        brand = request.form.get('brand')
        sku = request.form.get('sku')

        status = True if request.form.get('status') == '1' else False

        update_data = {
            "category_id": ObjectId(category_id),
            "name": name,
            "description": description,
            "price": price,
            "stock": stock,
            "brand": brand,
            "sku": sku,
            "status": status,
            "updated_at": datetime.utcnow()
        }

        # ================= CLOUDINARY IMAGE UPDATE =================
        file = request.files.get("image")

        if file and file.filename:

            upload_result = cloudinary.uploader.upload(
                file,
                folder="products"
            )

            new_image_url = upload_result["secure_url"]
            new_public_id = upload_result["public_id"]

            # optional: delete old image from cloudinary
            old_public_id = product.get("public_id")

            if old_public_id:
                try:
                    cloudinary.uploader.destroy(old_public_id)
                except Exception as e:
                    print("Cloudinary delete error:", e)

            update_data["image"] = new_image_url
            update_data["public_id"] = new_public_id

        mongo.db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )

        flash("Product si guul leh ayaa loo cusboonaysiiyay!", "success")
        return redirect(url_for('main.all_products'))

    return render_template(
        "backend/pages/components/products/edit_product.html",
        product=Product(product),
        categories=categories
    )





@bp.route('/delete-product/<product_id>', methods=['POST'])
@login_required
def delete_product(product_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    # =========================
    # FIND PRODUCT
    # =========================
    product = mongo.db.products.find_one({
        "_id": ObjectId(product_id)
    })

    if not product:
        flash("Product lama helin!", "danger")
        return redirect(url_for('main.all_products'))

    # =========================
    # CHECK IF USED IN ORDERS
    # =========================
    used_in_orders = mongo.db.orders.count_documents({
        "items.product_id": ObjectId(product_id)
    })

    if used_in_orders > 0:

        # SOFT DELETE (SAFE OPTION)
        mongo.db.products.update_one(
            {"_id": ObjectId(product_id)},
            {
                "$set": {
                    "deleted": True,
                    "status": False,
                    "deleted_at": datetime.utcnow()
                }
            }
        )

        flash(
            "Product-kan orders hore ayuu ku jiraa. Waa la qariyay (archive).",
            "warning"
        )
        return redirect(url_for('main.all_products'))

    # =========================
    # DELETE IMAGE FIRST
    # =========================
    public_id = product.get("public_id")

    if public_id:
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print("Cloudinary Error:", e)

    # =========================
    # HARD DELETE PRODUCT
    # =========================
    mongo.db.products.delete_one({
        "_id": ObjectId(product_id)
    })

    flash("Product si guul leh ayaa loo tirtiray!", "success")

    return redirect(url_for('main.all_products'))



@bp.route('/add-customer-ajax', methods=['POST'])
@login_required
def add_customer_ajax():
    data = request.json
    
    # Samee object-ka cusub ee la raacayo qaabka User class-kaaga
    new_customer = {
        "username": data.get('name'),
        "fullname": data.get('name'), # Waxaan u qaadanay magaca inuu yahay fullname
        "email": data.get('email'),
        "phone": data.get('phone'),
        "role": "customer",           # Si aad u kala saarto user-ka kale
        "status": True,
        "is_verified": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Ku kaydi database-ka (mongo.db.customers ama mongo.db.users)
    result = mongo.db.users.insert_one(new_customer)
    
    return jsonify({
        "success": True,
        "id": str(result.inserted_id),
        "name": data.get('name')
    })




@bp.route('/add-order', methods=['GET', 'POST'])
@login_required
def add_order():

    if request.method == 'POST':

        data = request.get_json()

        user_id = data.get('user_id')
        items_data = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Customer lama dooran"
            }), 400

        if not items_data:
            return jsonify({
                "success": False,
                "message": "Product lama dooran"
            }), 400

        total = 0
        items_list = []

        # Validation + Stock Check
        for item in items_data:

            product = mongo.db.products.find_one({
                "_id": ObjectId(item['product_id'])
            })

            qty = int(item['qty'])

            if not product:
                return jsonify({
                    "success": False,
                    "message": "Product ma jiro"
                }), 400

            if qty > int(product.get('stock', 0)):
                return jsonify({
                    "success": False,
                    "message": f"Stock kuma filna {product['name']}"
                }), 400

            line_total = float(product['price']) * qty
            total += line_total

            items_list.append({
                "product_id": ObjectId(item['product_id']),
                "name": product['name'],
                "price": float(product['price']),
                "qty": qty,
                "total": line_total
            })

        # Save Order
        new_order = {
            "user_id": ObjectId(user_id),
            "items": items_list,
            "total": total,
            "paid_amount": 0,
            "remaining_amount": total,
            "payment_status": "unpaid",
            "status": "pending",
            "payment_method": payment_method,
            "payment_history": [],
            "created_at": datetime.utcnow()
        }

        order_result = mongo.db.orders.insert_one(new_order)

        # Update Stock
        for item in items_data:
            mongo.db.products.update_one(
                {"_id": ObjectId(item['product_id'])},
                {"$inc": {"stock": -int(item['qty'])}}
            )

        return jsonify({
            "success": True,
            "message": "Order si guul leh ayaa loo sameeyay",
            "order_id": str(order_result.inserted_id)
        }), 201

    products = list(mongo.db.products.find({"status": True}))
    customers = list(mongo.db.users.find({"role": "customer"}))

    return render_template(
        "backend/pages/components/orders/add_order.html",
        products=products,
        customers=customers
    )


@bp.route('/all/orders')
@login_required
def all_orders():

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    orders = []

    cursor = mongo.db.orders.find({
        "deleted": {"$ne": True}
    }).sort("created_at", -1)

    for item in cursor:

        order = Order(item)

        # =========================
        # SAFE USER FETCH
        # =========================
        user = None

        try:
            if order.user_id:
                user = mongo.db.users.find_one({
                    "_id": ObjectId(order.user_id)
                })
        except Exception:
            user = None

        order.customer_name = user.get("username") if user and user.get("username") else "Unknown"

        # =========================
        # SAFE CREATED_AT
        # =========================
        if not order.created_at:
            order.created_at = None

        orders.append(order)

    return render_template(
        "backend/pages/components/orders/all_orders.html",
        orders=orders
    )



@bp.route('/edit-order/<order_id>', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    order_data = mongo.db.orders.find_one({"_id": ObjectId(order_id)})
    if not order_data:
        flash("Dalabka lama helin!", "danger")
        return redirect(url_for('main.all_orders'))

    order = Order(order_data)

    if request.method == 'POST':
        # 1. Update Status & Payment Info
        new_status = request.form.get('status')
        new_payment_status = request.form.get('payment_status')
        new_payment_amount = float(request.form.get('new_payment', 0))
        note = request.form.get('note', '')

        # Haddii lacag cusub la keenay
        if new_payment_amount > 0:
            order.add_payment(new_payment_amount, note)

        # 2. Update General Fields
        order.status = new_status
        
        # 3. Save to MongoDB
        mongo.db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "status": order.status,
                "payment_status": order.payment_status,
                "paid_amount": order.paid_amount,
                "payment_history": order.payment_history,
                "updated_at": datetime.utcnow()
            }}
        )

        flash("Dalabka si guul leh ayaa loo cusboonaysiiyay!", "success")
        return redirect(url_for('main.all_orders'))

    return render_template("backend/pages/components/orders/edit_order.html", order=order)


@bp.route('/delete-payment/<order_id>/<int:payment_index>', methods=['POST'])
@login_required
def delete_payment(order_id, payment_index):

    order = mongo.db.orders.find_one({
        "_id": ObjectId(order_id)
    })

    payment_history = order.get("payment_history", [])

    if payment_index >= len(payment_history):
        flash("Payment not found", "danger")
        return redirect(request.referrer)

    payment = payment_history[payment_index]

    amount = float(payment["amount"])

    payment_history.pop(payment_index)

    new_paid_amount = float(order["paid_amount"]) - amount

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {
            "$set": {
                "payment_history": payment_history,
                "paid_amount": new_paid_amount,
                "payment_status": "paid" if new_paid_amount >= order["total"] else "partial"
            }
        }
    )

    flash("Payment deleted successfully", "success")

    return redirect(request.referrer)



@bp.route('/delete-order/<order_id>', methods=['POST'])
@login_required
def delete_order(order_id):

    if current_user.role not in ['superadmin', 'admin']:
        return abort(403)

    order = mongo.db.orders.find_one({
        "_id": ObjectId(order_id)
    })

    if not order:
        flash("Order not found!", "danger")
        return redirect(url_for('main.all_orders'))

    paid_amount = float(order.get("paid_amount", 0))

    # ==============================
    # CASE 1: ORDER HAS PAYMENTS
    # ==============================
    if paid_amount > 0:

        # 1. Delete payment history first
        mongo.db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$set": {
                    "payment_history": [],
                    "paid_amount": 0,
                    "remaining_balance": order.get("total", 0),
                    "payment_status": "voided"
                }
            }
        )

        # 2. Then delete order (hard delete)
        mongo.db.orders.delete_one({
            "_id": ObjectId(order_id)
        })

        flash("Order + Payment history si guul leh ayaa loo tirtiray!", "success")
        return redirect(url_for('main.all_orders'))

    # ==============================
    # CASE 2: NO PAYMENTS (SAFE DELETE)
    # ==============================

    # RESTOCK products
    for item in order.get("items", []):
        mongo.db.products.update_one(
            {"_id": ObjectId(item["product_id"])},
            {"$inc": {"stock": int(item["qty"])}}
        )

    # DELETE ORDER
    mongo.db.orders.delete_one({
        "_id": ObjectId(order_id)
    })

    flash("Order si guul leh ayaa loo tirtiray (stock dib loo celiyay).", "success")
    return redirect(url_for('main.all_orders'))



#---------------------------------------------------
#---- Route: 70 | Dashboard - Backend Template -----
#---------------------------------------------------
@bp.route("/logout")
def logout():
    if current_user.is_authenticated:

        # Log the logout action
       

        # Only log out from Flask-Login
        logout_user()

        # ✅ Do NOT clear session or delete DB session yet
        # session.clear()  <-- remove this
        # db.session.delete(user_session)  <-- remove this

        # Flash message
        flash("You have been logged out! Your session record remains for inspection.", "success")

    # Clear remember_token cookie to prevent auto-login
    resp = make_response(redirect(url_for("main.index")))
    resp.set_cookie("remember_token", "", expires=0)
    return resp









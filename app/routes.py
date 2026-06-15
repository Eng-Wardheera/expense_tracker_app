from collections import defaultdict
import datetime
import math
import os
import random
import secrets
import traceback
import uuid

from bson import ObjectId
from flask import Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app import ALLOWED_EXTENSIONS
from app.extensions import mongo
from datetime import datetime, timedelta

from app.modal import Category, Product, User, UserRole


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

    return render_template(
        "frontend/pages/single_category.html",
        category=Category(category),
        products=products
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


@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    return render_template("backend/home/dashbaord.html", user=current_user)


@bp.route('/add-user', methods=['GET', 'POST'])
@login_required
def add_user():

    if current_user.role != 'superadmin':
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
        role = request.form.get('role')
        country = request.form.get('country')
        phone = request.form.get('phone')
        state = request.form.get('state')
        city = request.form.get('city')
        status = True if request.form.get('status') == '1' else False
        address = request.form.get('address')

        # ================= VALIDATION =================
        if password != confirm_password:
            flash("Passwords-ka isma laha!", "danger")
            return redirect(url_for('main.add_user'))

        if mongo.db.users.find_one({"email": email}):
            flash("Email-kan horey ayaa loo isticmaalay!", "danger")
            return redirect(url_for('main.add_user'))

        # ================= PHOTO UPLOAD =================
        photo_path = ""

        file = request.files.get('photo')

        if file and file.filename:

            # ✔ PROJECT ROOT (NOT APP INTERNAL)
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

            # DB stores PUBLIC path
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
            "status": status,
            "address": address,
            "photo": photo_path,
            "created_at": datetime.utcnow()
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
    if current_user.role != 'superadmin':
        return abort(403)

    raw_user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not raw_user:
        flash("User-ka lama helin!", "danger")
        return redirect(url_for('main.index'))

    user = User(raw_user)

    if request.method == 'POST':

        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        updated_data = {
            "fullname": request.form.get('fullname'),
            "username": request.form.get('username'),
            "email": request.form.get('email'),
            "role": request.form.get('role'),
            "country": request.form.get('country'),
            "phone": request.form.get('phone'),
            "address": request.form.get('address'),
            "bio": request.form.get('bio'),
            "status": True if request.form.get('status') == '1' else False,
            "updated_at": datetime.utcnow()
        }

        # ================= PASSWORD FIX =================
        if password:
            if password != confirm_password:
                flash("Passwords-ka isma laha!", "danger")
                return redirect(url_for('main.edit_user', user_id=user_id))

            updated_data["password"] = generate_password_hash(password)

        file = request.files.get('photo')

        if file and file.filename:

            # ================= DELETE OLD IMAGE =================
            old_photo = raw_user.get("photo")

            if old_photo:
                old_path = os.path.join(
                    os.path.abspath(os.getcwd()),
                    'static',
                    old_photo
                )

                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        print(f"Error deleting old image: {e}")

            # ================= SAVE NEW IMAGE =================
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

            # DB PATH
            updated_data["photo"] = f"backend/uploads/users/{filename}"

        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updated_data}
        )

        flash("Macluumaadka si guul leh ayaa loo cusbooneysiiyey!", "success")
        return redirect(url_for('main.edit_user', user_id=user_id))

    return render_template(
        "backend/pages/components/users/edit_user.html",
        user=user
    )



@bp.route('/delete-user/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'superadmin':
        return abort(403)

    # 1. Get user
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    # 2. Delete image file if exists
    if user and user.get('photo'):

        # correct project root
        project_root = os.path.abspath(os.getcwd())

        file_path = os.path.join(
            project_root,
            'static',
            user['photo']  # example: backend/uploads/users/xxx.jpg
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    # 3. Delete user from DB
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})

    flash("User-ka si guul leh ayaa loo tirtiray!", "success")
    return redirect(url_for('main.all_users'))


@bp.route('/all-users', methods=['GET'])
@login_required
def all_users():
    if current_user.role != 'superadmin':
        return abort(403) # ama redirect(url_for('login'))
        
    # 1. Ka soo saar dhammaan users-ka database-ka
    # .sort('-created_at') waxaa loola jeedaa inuu ku kala sooco taariikhda (ugu dambeeyay ugu horreeya)
    users_cursor = mongo.db.users.find().sort('created_at', -1)
    
    # 2. U beddel document kasta (dictionary) inuu noqdo User object
    # Tani waxay isticmaaleysaa fasalkaaga User ee aan horey uga soo hadalnay
    users = [User(user_data) for user_data in users_cursor]
    
    # 3. U dir template-ka
    return render_template('backend/pages/components/users/all_users.html', users=users)




@bp.route('/add-category', methods=['GET', 'POST'])
@login_required
def add_category():

    if current_user.role != 'superadmin':
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

        # ================= IMAGE UPLOAD =================
        image_path = ""

        file = request.files.get('image')

        if file and file.filename:

            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                'static',
                'backend',
                'uploads',
                'categories'
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file_path = os.path.join(upload_dir, filename)

            file.save(file_path)

            image_path = f"backend/uploads/categories/{filename}"

        # ================= CREATE CATEGORY =================
        new_category = {
            "name": name,
            "image": image_path,
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

    categories = mongo.db.categories.find().sort("created_at", -1)

    category_list = [Category(cat) for cat in categories]

    return render_template(
        "backend/pages/components/categories/all_categories.html",
        categories=category_list
    )




@bp.route('/edit-category/<category_id>', methods=['GET', 'POST'])
@login_required
def edit_category(category_id):

    if current_user.role != 'superadmin':
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

        if file and file.filename:

            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                'static',
                'backend',
                'uploads',
                'categories'
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"

            file_path = os.path.join(upload_dir, filename)

            file.save(file_path)

            image_path = f"backend/uploads/categories/{filename}"

            # delete old image
            old_image = category.get("image")

            if old_image:
                old_file = os.path.join(
                    project_root,
                    'static',
                    old_image
                )

                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass

            update_data["image"] = image_path

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

    if current_user.role != 'superadmin':
        return abort(403)

    category = mongo.db.categories.find_one({
        "_id": ObjectId(category_id)
    })

    if not category:
        flash("Category lama helin!", "danger")
        return redirect(url_for('main.all_categories'))

    # delete image
    image_path = category.get("image")

    if image_path:

        project_root = os.path.abspath(os.getcwd())

        full_path = os.path.join(
            project_root,
            'static',
            image_path
        )

        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except:
                pass

    mongo.db.categories.delete_one({
        "_id": ObjectId(category_id)
    })

    flash("Category si guul leh ayaa loo tirtiray!", "success")

    return redirect(url_for('main.all_categories'))





@bp.route('/add-product', methods=['GET', 'POST'])
@login_required
def add_product():

    if current_user.role != 'superadmin':
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

        status = (
            True
            if request.form.get('status') == '1'
            else False
        )

        # ================= VALIDATION =================

        if not category_id:
            flash("Category dooro!", "danger")
            return redirect(url_for('main.add_product'))

        if not name:
            flash("Product name waa required!", "danger")
            return redirect(url_for('main.add_product'))

        existing = mongo.db.products.find_one({
            "name": name
        })

        if existing:
            flash("Product-kan hore ayuu u jiraa!", "danger")
            return redirect(url_for('main.add_product'))

        # ================= IMAGE UPLOAD =================

        image_path = ""

        file = request.files.get('image')

        if file and file.filename:

            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                'static',
                'backend',
                'uploads',
                'products'
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = (
                f"{uuid.uuid4().hex}_"
                f"{secure_filename(file.filename)}"
            )

            file_path = os.path.join(
                upload_dir,
                filename
            )

            file.save(file_path)

            image_path = (
                f"backend/uploads/products/{filename}"
            )

        # ================= SAVE PRODUCT =================

        product = {

            "category_id": ObjectId(category_id),

            "name": name,
            "description": description,

            "price": price,
            "stock": stock,

            "image": image_path,

            "brand": brand,
            "sku": sku,

            "status": status,

            "created_at": datetime.utcnow(),
            "updated_at": None
        }

        mongo.db.products.insert_one(product)

        flash(
            f"{name} si guul leh ayaa loo daray!",
            "success"
        )

        return redirect(url_for('main.all_products'))

    return render_template(
        "backend/pages/components/products/add_product.html",
        categories=categories
    )



@bp.route('/all/products')
@login_required
def all_products():

    if current_user.role != 'superadmin':
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

    if current_user.role != 'superadmin':
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

        status = (
            True
            if request.form.get('status') == '1'
            else False
        )

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

        file = request.files.get("image")

        if file and file.filename:

            project_root = os.path.abspath(os.getcwd())

            upload_dir = os.path.join(
                project_root,
                "static",
                "backend",
                "uploads",
                "products"
            )

            os.makedirs(upload_dir, exist_ok=True)

            filename = (
                f"{uuid.uuid4().hex}_"
                f"{secure_filename(file.filename)}"
            )

            file_path = os.path.join(
                upload_dir,
                filename
            )

            file.save(file_path)

            image_path = (
                f"backend/uploads/products/{filename}"
            )

            old_image = product.get("image")

            if old_image:

                old_file = os.path.join(
                    project_root,
                    "static",
                    old_image
                )

                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass

            update_data["image"] = image_path

        mongo.db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )

        flash(
            "Product si guul leh ayaa loo cusboonaysiiyay!",
            "success"
        )

        return redirect(url_for('main.all_products'))

    return render_template(
        "backend/pages/components/products/edit_product.html",
        product=Product(product),
        categories=categories
    )


@bp.route('/delete-product/<product_id>', methods=['POST'])
@login_required
def delete_product(product_id):

    if current_user.role != 'superadmin':
        return abort(403)

    product = mongo.db.products.find_one({
        "_id": ObjectId(product_id)
    })

    if not product:
        flash("Product lama helin!", "danger")
        return redirect(url_for('main.all_products'))

    image = product.get("image")

    if image:

        project_root = os.path.abspath(os.getcwd())

        image_path = os.path.join(
            project_root,
            "static",
            image
        )

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass

    mongo.db.products.delete_one({
        "_id": ObjectId(product_id)
    })

    flash(
        "Product si guul leh ayaa loo tirtiray!",
        "success"
    )

    return redirect(url_for('main.all_products'))







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









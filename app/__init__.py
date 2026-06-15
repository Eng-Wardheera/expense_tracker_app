from datetime import datetime

import os
import traceback
from flask import Flask, flash, redirect, render_template, url_for
from flask_cors import CORS
from flask_login import LoginManager, current_user
from authlib.integrations.flask_client import OAuth
import pytz
from dotenv import load_dotenv
from app.tracker import init_tracker
from app.extensions import mongo, mail
from datetime import datetime
import cloudinary
import cloudinary.uploader






# Extensions - single instance only!

login_manager = LoginManager()

 # Enable CSRF globally

# Global Variables: 1
# Upload config & model
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Global Variables: 2
UPLOAD_FOLDER = "static/backend/uploads"


MAX_RETRIES = 5  # try 5 times to get a unique journey_code

 # ----- Timezone -----
  
# Google OAuth


oauth = OAuth()  # global instance
google = None    # placeholder
githup = None

EAT = pytz.timezone("Africa/Nairobi")

def now_eat():
    """Return current datetime in Nairobi timezone"""
    return datetime.now(EAT)

# Load environment variables from .env file
load_dotenv()


cloudinary.config(
    cloud_name="dzhairplt",
    api_key="597738172555213",
    api_secret="x4UXHFVqzH4Oq_MeBV4VGYoZHns"
)

#-------------------------------------------------------------
# Function: 29 create_app()
# Ujeeddo: Diyaarinta Flask App iyadoo la isku xiro configs, extensions, 
# filters, blueprints, errors, iyo security
#-------------------------------------------------------------
def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

   


    # Secure Secret Key
    app.secret_key = os.getenv('SECRET_KEY', 'XWt7819618552904Sm32Mxx2102dklF')
   

    # Configuration
   
    mongo_uri = os.getenv("MONGO_URI")

    if not mongo_uri:
        raise Exception("MONGO_URI not found")

    app.config["MONGO_URI"] = mongo_uri


    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    # create_app() dhexdiisa
    app.config['DEBUG'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = False

     # Configure Flask to use Gmail's SMTP server
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587  # TLS port
    app.config['MAIL_USERNAME'] = 'liilove668@gmail.com'  # Your Gmail address
    app.config['MAIL_PASSWORD'] = 'dvml ylyo ivek xrab'  # Your Gmail password or App password
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
   

  

  
    # Enable CORS for your frontend origin
     # Ka akhri port environment
    port = int(os.getenv("PORT", 7000))
    frontend_origin = os.getenv("FRONTEND_ORIGIN", f"http://127.0.0.1:{port}")

    # Dynamic CORS origin
    CORS(app, resources={r"/*": {"origins": frontend_origin}})

    # OAuth init
    # OAuth init
    oauth.init_app(app)
    global google
    google = oauth.register(
        name='google',
         client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    # OAuth setup
    oauth.init_app(app)
    global github
    github = oauth.register(
        name='github',
        client_id=os.getenv("GITHUB_CLIENT_ID"),
        client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )

  

  
    @app.template_filter('getattr')
    def getattr_filter(obj, name):
        return getattr(obj, name, None)

    # Import and register your routes (assuming routes.py)
    init_tracker(app, mongo)

 
    # Initialize extensions
    mongo.init_app(app)
    mail.init_app(app)  # Make sure you call init_app on the mail object
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # Register blueprints
   
    @app.context_processor
    def inject_year():
        return dict(current_year=datetime.now().year)

    # 27 Filter: Format datetime for input[type="datetime-local"]
    @app.template_filter('datetimeformat_input')
    def datetimeformat_input(value):
        if not value:
            return ''
        return value.strftime('%Y-%m-%dT%H:%M')


    # 28 Example: in filters.py (Jinja filter)
    @app.template_filter('datetimeformat_input_dateOnly')
    def datetimeformat_input_dateOnly(value):
        return value.strftime('%Y-%m-%d')  # only date


    # Import models and blueprints



  
    from .routes import bp 
    from app.modal import User

    
    app.register_blueprint(bp) # ,url_prefix='/main'
    
   


    # Oggolow dhammaan domains ama ku xadid domain gaar ah:
  

    @app.errorhandler(404)
    def not_found_error(error):
        site_settings = mongo.db.settings.find_one()
        return render_template(
            "backend/errors/auth-404-creative.html",
            settings=site_settings
        ), 404


    # ✅ Add template filter to app
    @app.template_filter('time_since')
    def time_since_filter(seconds):
        """Convert seconds to human-readable time like '5 minutes ago'."""
        seconds = int(seconds)
        intervals = (
            ('month', 2592000),  # 30*24*60*60
            ('week', 604800),    # 7*24*60*60
            ('day', 86400),
            ('hour', 3600),
            ('minute', 60),
            ('second', 1),
        )

        for name, count in intervals:
            value = seconds // count
            if value:
                return f"{value} {name}{'s' if value > 1 else ''} ago"
        return "just now"
    
    # 30 Custom 500 handler
    @app.errorhandler(500)
    def internal_error(error):
        from flask import request

        current_time = datetime.now(EAT).strftime("%Y-%m-%d %H:%M:%S")
        request_url = request.url
        user_info = current_user.username if current_user.is_authenticated else "Guest"

        error_message = str(error)
        error_trace = traceback.format_exc() if app.debug else None

        site_settings = mongo.db.settings.find_one()

        return render_template(
            "backend/errors/auth-500-creative.html",
            settings=site_settings,
            time=current_time,
            user=user_info,
            url=request_url,
            message=error_message,
            trace=error_trace,
            debug=app.debug
        ), 500

 

    @login_manager.unauthorized_handler
    def unauthorized():
        flash("Fadlan marka hore soo gal nidaamka.")
        return redirect(url_for('main.login')) # 'login' waa magaca function-ka login-kaaga

    @app.context_processor
    def inject_settings():
        return dict(settings=mongo.db.settings.find_one())

    # 31 Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        from bson.objectid import ObjectId
        # 1. Xogta ka soo hel database-ka
        user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        
        # 2. Haddi xogtu jirto, u beddel Object ka hor inta aadan return-garayn
        if user_data:
            return User(user_data) # <--- Halkan waa inuu ahaadaa User class object
        
        return None # Haddii kale return None


   
    
    return app

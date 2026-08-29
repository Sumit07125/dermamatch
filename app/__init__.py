import logging
from flask import Flask
from .utils import CustomJSONEncoder
from .errors import register_error_handlers
from .engine_loader import load_engine

def create_app():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    app = Flask(__name__)
    app.json_encoder = CustomJSONEncoder
    # Note: For Flask 2.2+, app.json_encoder is deprecated, use app.json.default.
    app.json.default = CustomJSONEncoder().default
    
    # Load configuration
    from . import config
    app.config.from_object(config)
    
    # Load recommendation engine (singleton)
    with app.app_context():
        load_engine()
        
    # Register error handlers
    register_error_handlers(app)
    
    # Register routes
    from .routes import api
    app.register_blueprint(api)
    
    return app

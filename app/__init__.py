from flask import Flask, jsonify
from config import Config
from .extensions import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from .routes.main import main_bp
    from .routes.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        # pass through HTTP errors
        if isinstance(e, int):
            return jsonify({'error': str(e)}), e
        
        # Check if it's an HTTP exception (like 404, 500 from abort)
        if hasattr(e, 'code'):
            return jsonify({'error': str(e)}), e.code
            
        # Generic 500
        print(f"Server Error: {e}")
        return jsonify({'error': f"Internal Server Error: {str(e)}"}), 500

    return app

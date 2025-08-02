from flask import Flask
from controllers.config import config_app
from models.models import db, User
from controllers.routes import init_routes
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# Configure the Flask application
config_app(app)

# Initialize the database
db.init_app(app)

# Create the database tables if they do not exist
with app.app_context():
    db.create_all()
    # Create admin user if it doesn't exist
    admin_user = User.query.filter_by(isadmin=True).first()
    if not admin_user:
        password = 'admin'
        passhash = generate_password_hash(password)
        admin_user = User(username='admin', passhash=passhash, name='Admin', city='Delhi', pincode=110043, isadmin=True)
        db.session.add(admin_user)
        db.session.commit()

# Import routes
init_routes(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
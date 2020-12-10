from flask_cors import CORS

from avctls import create_app
app = create_app()
CORS(app, resources={r"/*": {"origins": "*"}})

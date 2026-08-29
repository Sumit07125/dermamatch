import os
from dotenv import load_dotenv

# Load environment variables from .env if it exists
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    from app.config import API_HOST, API_PORT, DEBUG
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)

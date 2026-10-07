import os
from waitress import serve
from .app import create_app

if __name__ == '__main__':
    app = create_app()
    serve(app, host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '8000')), threads=4)

import os

from app import create_app

app = create_app(os.getenv("APP_ENV", "development"))

if __name__ == "__main__":
    host = os.getenv("LOCAL_HOST", "127.0.0.1")
    port = int(os.getenv("LOCAL_PORT", "5050"))
    app.run(host=host, port=port, debug=False, use_reloader=False)

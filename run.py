"""Development entry point:  python run.py
Production:                  waitress-serve --port=8000 run:app    (or gunicorn run:app)
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # 0.0.0.0 so a real iPhone on the same Wi-Fi can reach it; the simulator can use localhost.
    app.run(host="0.0.0.0", port=8000, debug=False)

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("DATABASE_URL not set in .env file.")
else:
    try:
        print(f"Attempting to connect to {db_url}...")
        with psycopg.connect(db_url) as conn:
            print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")

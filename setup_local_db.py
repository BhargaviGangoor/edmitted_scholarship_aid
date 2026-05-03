import os
import psycopg2
from dotenv import load_dotenv

def setup_database():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("Error: DATABASE_URL environment variable is not set.")
        return

    print(f"Connecting to database to create schema...")
    try:
        # We don't strictly require sslmode for local, but it's okay if provided in string
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                # We drop the table if it exists to allow a clean migration
                print("Creating pgvector extension...")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                print("Creating table 'financial_opportunities'...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS financial_opportunities (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        description TEXT,
                        min_gpa NUMERIC,
                        income_ceiling NUMERIC,
                        state_requirement TEXT,
                        embedding vector(3072)
                    );
                """)
            conn.commit()
            print("Schema created successfully! You can now run ingest.py.")
    except Exception as e:
        print(f"Failed to create schema: {e}")

if __name__ == "__main__":
    setup_database()

import pandas as pd
import psycopg2
from src.core.config import Config

CSV_PATH = "data/edmitted_top100_scholarships.csv"
DATABASE_URL = Config.DATABASE_URL

print("--- CSV Check ---")
df = pd.read_csv(CSV_PATH)
print(f"Total rows in CSV: {len(df)}")
duplicate_ids = df[df.duplicated('id', keep=False)]
if not duplicate_ids.empty:
    print(f"Rows with duplicate IDs in CSV: {len(duplicate_ids)}")
    print(duplicate_ids['id'].value_counts().head(10))
else:
    print("No duplicate IDs in CSV.")

print("\n--- Database Check ---")
try:
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM financial_opportunities;")
            count = cursor.fetchone()[0]
            print(f"Total rows in database: {count}")
            
            cursor.execute("SELECT id, count(*) FROM financial_opportunities GROUP BY id HAVING count(*) > 1;")
            db_dupes = cursor.fetchall()
            if db_dupes:
                print(f"Duplicate IDs in database: {len(db_dupes)}")
            else:
                print("No duplicate IDs in database (as expected due to PK).")
                
            cursor.execute("SELECT name, description, count(*) FROM financial_opportunities GROUP BY name, description HAVING count(*) > 1 LIMIT 10;")
            content_dupes = cursor.fetchall()
            if content_dupes:
                print(f"Rows with identical name AND description: {len(content_dupes)} (showing top 10)")
                for name, desc, c in content_dupes:
                    print(f" - {name}: {c} times")
            else:
                print("No rows with identical name AND description.")
except Exception as e:
    print(f"Error checking database: {e}")

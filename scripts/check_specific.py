import psycopg2
from src.core.config import Config

conn = psycopg2.connect(Config.DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT name, min_gpa, income_ceiling, state_requirement FROM financial_opportunities WHERE name = 'Gates Millennium Social Work Excellence Award';")
rows = cur.fetchall()
print("Requirements for 'Gates Millennium Social Work Excellence Award':")
for r in rows:
    print(r)
conn.close()

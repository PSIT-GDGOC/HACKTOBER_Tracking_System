import os
import sqlite3

db_path = "hacktoberfest.db"
print("Database path:", os.path.abspath(db_path))
print("File exists:", os.path.exists(db_path))
print(f"File size: {os.path.getsize(db_path):,} bytes\n")

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [row[0] for row in cur.fetchall()]

print(f"{'Table Name':<22} | {'Row Count':<10}")
print("-" * 36)
for table in sorted(tables):
    cur.execute(f"SELECT count(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"{table:<22} | {count:<10}")

conn.close()

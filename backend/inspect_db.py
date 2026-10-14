import sqlite3
import json
import os

conn = sqlite3.connect('backend/data/learnmate.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== TABLES ===")
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
for row in cursor.fetchall():
    print(f"\nTABLE: {row['name']}")
    print(row['sql'])

print("\n=== COURSES ===")
cursor.execute("SELECT * FROM courses")
for row in cursor.fetchall():
    print(dict(row))

print("\n=== DOCUMENTS ===")
cursor.execute("SELECT id, course_id, filename, file_type, ingestion_status, file_path FROM documents")
for row in cursor.fetchall():
    print(dict(row))

print("\n=== UPLOADED FILES IN DISK ===")
uploads_dir = "backend/data/uploads"
if os.path.exists(uploads_dir):
    for f in os.listdir(uploads_dir):
        fp = os.path.join(uploads_dir, f)
        print(f"  {f} ({os.path.getsize(fp)} bytes)")

print("\n=== LEARNER / TOPIC MASTERY RECORDS ===")
cursor.execute("SELECT count(*) as count FROM topic_mastery")
print(f"topic_mastery rows: {cursor.fetchone()['count']}")

cursor.execute("SELECT count(*) as count FROM assessments")
print(f"assessments rows: {cursor.fetchone()['count']}")

cursor.execute("SELECT DISTINCT user_id FROM assessments")
user_ids = [r['user_id'] for r in cursor.fetchall()]
print(f"assessment user_ids: {user_ids}")

conn.close()

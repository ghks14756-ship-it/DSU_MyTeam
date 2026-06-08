import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT discord_id, username, program FROM applications")
apps = cursor.fetchall()
for a in apps:
    if "김하늘" in a[1]:
        print("FOUND:", a)
conn.close()

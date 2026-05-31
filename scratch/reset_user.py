import sqlite3
import os

db_path = 'data/dsu_myteam.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE applications SET is_matched = 0, team_id = NULL WHERE discord_id = "1510544585636581467"')
    conn.commit()
    print("Reset successful.")
    conn.close()
else:
    print("DB not found.")

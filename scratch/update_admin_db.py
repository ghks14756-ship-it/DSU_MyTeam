import sqlite3

db_path = 'data/dsu_myteam.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('UPDATE applications SET discord_id = "396919592452358144" WHERE discord_id = "WEB_ADMIN-0000"')
conn.commit()
print("Updated application for ADMIN")
conn.close()

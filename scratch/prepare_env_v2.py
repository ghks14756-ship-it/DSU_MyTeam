import sqlite3

db_path = 'data/dsu_myteam.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 김성환(어드민) 및 하늘이 신청 내역 삭제
cursor.execute('DELETE FROM applications WHERE discord_id IN ("396919592452358144", "1510544585636581467")')
print(f"Deleted {cursor.rowcount} applications for Admin and Haneul.")

# 2. 관련 팀룸 데이터 삭제 (팀 ID 12)
cursor.execute('DELETE FROM team_rooms WHERE leader_id = "396919592452358144"')
print(f"Deleted {cursor.rowcount} team rooms for Admin.")

# 3. 매칭 결과 삭제
cursor.execute('DELETE FROM team_match_results WHERE leader_id = "396919592452358144"')
print(f"Deleted {cursor.rowcount} match results for Admin.")

conn.commit()
conn.close()
print("Environment preparation complete. DB is clean for the next test.")

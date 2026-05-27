"""
database/db_manager.py
SQLite 비동기 래퍼 (aiosqlite 사용)

테이블 목록:
  - applications   : 72시간 TTL 신청 데이터
  - activities     : MYDEX 활동 목록 (구글 시트 캐시)
  - team_rooms     : 조장이 생성한 팀 방
  - group_invites  : 그룹 신청 초대 코드
"""

import aiosqlite
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("DSUMyTeam.DB")


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    # ── 초기화 ────────────────────────────────────────────────────
    async def init(self) -> None:
        """DB 연결 및 테이블 생성."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ── 테이블 생성 ───────────────────────────────────────────────
    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            -- 신청 테이블 (핵심: 72시간 TTL)
            CREATE TABLE IF NOT EXISTS applications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id  TEXT NOT NULL,            -- 디스코드 유저 ID
                username    TEXT NOT NULL,            -- 닉네임
                student_id  TEXT NOT NULL,            -- 학번 (ex: 21011234)
                department  TEXT NOT NULL,            -- 학과
                skill       TEXT NOT NULL,            -- 특기/역할
                activity_id INTEGER,                  -- 신청한 활동 ID (FK)
                group_code  TEXT DEFAULT NULL,        -- 그룹 초대 코드 (그룹 신청 시)
                applied_at  TEXT NOT NULL,            -- 신청 시각 (ISO8601 UTC)
                expires_at  TEXT NOT NULL,            -- 만료 시각 (72h 후)
                is_matched  INTEGER DEFAULT 0,        -- 매칭 완료 여부
                team_id     INTEGER DEFAULT NULL,     -- 배정된 팀 ID
                FOREIGN KEY (activity_id) REFERENCES activities(id)
            );

            -- MYDEX 활동 목록 (구글 시트 캐시)
            CREATE TABLE IF NOT EXISTS activities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,     -- 활동명
                description TEXT DEFAULT '',
                deadline    TEXT DEFAULT NULL,         -- 마감일 (ISO8601)
                max_members INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                updated_at  TEXT NOT NULL
            );

            -- 팀 방 테이블
            CREATE TABLE IF NOT EXISTS team_rooms (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id     INTEGER,
                leader_id       TEXT NOT NULL,         -- 조장 디스코드 ID
                team_name       TEXT NOT NULL,
                required_skills TEXT DEFAULT '[]',     -- JSON 배열
                max_members     INTEGER DEFAULT 4,
                current_members INTEGER DEFAULT 1,
                text_channel_id TEXT DEFAULT NULL,     -- 생성된 채팅방 ID
                voice_channel_id TEXT DEFAULT NULL,    -- 생성된 음성방 ID
                created_at      TEXT NOT NULL,
                is_full         INTEGER DEFAULT 0,
                FOREIGN KEY (activity_id) REFERENCES activities(id)
            );

            -- 그룹 초대 코드 테이블
            CREATE TABLE IF NOT EXISTS group_invites (
                code        TEXT PRIMARY KEY,          -- 6자리 초대 코드
                creator_id  TEXT NOT NULL,             -- 코드 생성자 ID
                activity_id INTEGER,
                members     TEXT DEFAULT '[]',         -- JSON 배열 (discord_id 목록)
                created_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,             -- 코드 유효 기간 (72h)
                is_used     INTEGER DEFAULT 0
            );
        """)
        await self._conn.commit()
        log.info("DB 테이블 생성/확인 완료")

    # ══════════════════════════════════════════════════════════════
    #  신청 (Applications) CRUD
    # ══════════════════════════════════════════════════════════════

    async def create_application(
        self,
        discord_id: str,
        username: str,
        student_id: str,
        department: str,
        skill: str,
        activity_id: int | None = None,
        group_code: str | None = None,
    ) -> dict:
        """
        신청 데이터를 DB에 저장 (1인 1신청 중복 방지 로직 포함).
        """
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        from config import Config

        # 1인 1신청 검증 (is_matched = 0 이고 만료되지 않은 내역이 있는지 확인)
        if not Config.ALLOW_MULTIPLE_APPLICATIONS:
            async with self._conn.execute(
                "SELECT id FROM applications WHERE discord_id = ? AND is_matched = 0 AND expires_at > ?",
                (discord_id, now.isoformat())
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    raise ValueError("이미 대기 중인 신청 내역이 존재합니다.")

        expires = now + timedelta(hours=72)

        await self._conn.execute("""
            INSERT INTO applications
                (discord_id, username, student_id, department, skill,
                 activity_id, group_code, applied_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            discord_id, username, student_id, department, skill,
            activity_id, group_code,
            now.isoformat(), expires.isoformat()
        ))
        await self._conn.commit()

        return {
            "discord_id": discord_id,
            "username": username,
            "student_id": student_id,
            "department": department,
            "skill": skill,
            "applied_at": now,
            "expires_at": expires,
        }

    async def get_application(self, discord_id: str) -> dict | None:
        """단일 유저 신청 조회."""
        async with self._conn.execute(
            "SELECT * FROM applications WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_active_applications(self, activity_id: int | None = None) -> list[dict]:
        """만료되지 않고 매칭되지 않은 신청 목록."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
            SELECT * FROM applications
            WHERE expires_at > ? AND is_matched = 0
        """
        params: list = [now]
        if activity_id is not None:
            query += " AND activity_id = ?"
            params.append(activity_id)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_expired_applications(self) -> list[dict]:
        """만료된 신청 목록 (아직 삭제 안 된 것)."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            "SELECT * FROM applications WHERE expires_at <= ? AND is_matched = 0", (now,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_application(self, discord_id: str) -> None:
        """신청 삭제."""
        await self._conn.execute(
            "DELETE FROM applications WHERE discord_id = ?", (discord_id,)
        )
        await self._conn.commit()

    async def mark_matched(self, discord_id: str, team_id: int, username: str | None = None) -> None:
        """매칭 완료 처리. 동일 discord_id 다수 신청 처리용으로 username도 확인"""
        if username:
            await self._conn.execute(
                "UPDATE applications SET is_matched = 1, team_id = ? WHERE discord_id = ? AND username = ?",
                (team_id, discord_id, username)
            )
        else:
            await self._conn.execute(
                "UPDATE applications SET is_matched = 1, team_id = ? WHERE discord_id = ?",
                (team_id, discord_id)
            )
        await self._conn.commit()

    async def sync_applications_from_sheet(self, applications: list[dict]) -> int:
        """구글 시트의 '신청현황' 데이터를 DB와 동기화 (Upsert)"""
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        from datetime import timedelta
        
        for app in applications:
            if app.get("status") != "대기":
                continue
                
            activity_name = app.get("activity_name")
            activity_id = None
            if activity_name:
                async with self._conn.execute("SELECT id FROM activities WHERE name = ?", (activity_name,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        activity_id = row["id"]
                        
            # 디스코드 ID와 이름이 모두 같은 행을 찾음 (중복 방지용)
            async with self._conn.execute(
                "SELECT id FROM applications WHERE discord_id = ? AND username = ?", 
                (app["discord_id"], app["username"])
            ) as cursor:
                existing = await cursor.fetchone()
                
            applied_at = app.get("applied_at") or now
            expires_at = app.get("expires_at")
            if not expires_at:
                expires_at = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
                
            if existing:
                await self._conn.execute("""
                    UPDATE applications SET
                        student_id = ?, department = ?, skill = ?, activity_id = ?, 
                        applied_at = ?, expires_at = ?
                    WHERE id = ?
                """, (app["student_id"], app["department"], app["skill"], activity_id, applied_at, expires_at, existing["id"]))
            else:
                await self._conn.execute("""
                    INSERT INTO applications (discord_id, username, student_id, department, skill, activity_id, applied_at, expires_at, is_matched)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (app["discord_id"], app["username"], app["student_id"], app["department"], app["skill"], activity_id, applied_at, expires_at))
            count += 1
            
        await self._conn.commit()
        return count

    # ══════════════════════════════════════════════════════════════
    #  활동 목록 (Activities) CRUD
    # ══════════════════════════════════════════════════════════════

    async def upsert_activities(self, activities: list[dict]) -> int:
        """구글 시트 등에서 받아온 활동 목록을 일괄 Upsert."""
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        active_names = []
        for act in activities:
            active_names.append(act["name"])
            await self._conn.execute("""
                INSERT INTO activities (name, description, deadline, max_members, updated_at)
                VALUES (:name, :description, :deadline, :max_members, :updated_at)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    deadline    = excluded.deadline,
                    max_members = excluded.max_members,
                    is_active   = 1,
                    updated_at  = excluded.updated_at
            """, {**act, "updated_at": now})
            count += 1
            
        # 제공된 리스트에 없는 기존 활동들은 비활성화(is_active=0) 처리
        if active_names:
            placeholders = ",".join(["?"] * len(active_names))
            await self._conn.execute(f"""
                UPDATE activities SET is_active = 0 WHERE name NOT IN ({placeholders})
            """, active_names)
        else:
            await self._conn.execute("UPDATE activities SET is_active = 0")
            
        await self._conn.commit()
        return count

    async def get_active_activities(self) -> list[dict]:
        async with self._conn.execute(
            "SELECT * FROM activities WHERE is_active = 1 ORDER BY id"
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

    # ══════════════════════════════════════════════════════════════
    #  팀 방 (Team Rooms) CRUD
    # ══════════════════════════════════════════════════════════════

    async def create_team_room(
        self,
        activity_id: int,
        leader_id: str,
        team_name: str,
        required_skills: list[str],
        max_members: int = 4,
    ) -> int:
        """팀 방 생성 후 ID 반환."""
        import json
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._conn.execute("""
            INSERT INTO team_rooms
                (activity_id, leader_id, team_name, required_skills, max_members, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (activity_id, leader_id, team_name, json.dumps(required_skills, ensure_ascii=False), max_members, now))
        await self._conn.commit()
        return cursor.lastrowid

    async def update_team_channels(self, team_id: int, text_ch_id: str, voice_ch_id: str) -> None:
        await self._conn.execute("""
            UPDATE team_rooms SET text_channel_id = ?, voice_channel_id = ?
            WHERE id = ?
        """, (text_ch_id, voice_ch_id, team_id))
        await self._conn.commit()

    # ══════════════════════════════════════════════════════════════
    #  그룹 초대 코드 (Group Invites) CRUD
    # ══════════════════════════════════════════════════════════════

    async def create_group_invite(self, creator_id: str, activity_id: int) -> str:
        """6자리 초대 코드를 생성하고 DB에 저장 후 코드 반환."""
        import secrets
        import json
        from datetime import timedelta

        code = secrets.token_hex(3).upper()  # ex: 'A3F2B1'
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=72)

        await self._conn.execute("""
            INSERT INTO group_invites (code, creator_id, activity_id, members, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, creator_id, activity_id, json.dumps([creator_id]), now.isoformat(), expires.isoformat()))
        await self._conn.commit()
        return code

    async def join_group(self, code: str, discord_id: str) -> tuple[bool, str]:
        """초대 코드로 그룹 참가. (성공 여부, 메시지) 반환."""
        import json
        now = datetime.now(timezone.utc).isoformat()

        async with self._conn.execute(
            "SELECT * FROM group_invites WHERE code = ? AND expires_at > ? AND is_used = 0",
            (code, now)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "유효하지 않거나 만료된 초대 코드입니다."

            members = json.loads(row["members"])
            if discord_id in members:
                return False, "이미 이 그룹에 참가되어 있습니다."

            members.append(discord_id)
            await self._conn.execute(
                "UPDATE group_invites SET members = ? WHERE code = ?",
                (json.dumps(members), code)
            )
            await self._conn.commit()
            return True, f"그룹 참가 완료! 현재 멤버: {len(members)}명"

    async def get_group_invite(self, code: str) -> dict | None:
        async with self._conn.execute(
            "SELECT * FROM group_invites WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

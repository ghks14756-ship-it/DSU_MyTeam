import json
import uuid
import logging
from aiohttp import web
from datetime import datetime, timezone

log = logging.getLogger("DSUMyTeam.API")

routes = web.RouteTableDef()

def setup_api(app: web.Application, bot):
    """API 라우터 설정 및 봇 인스턴스 주입"""
    app['bot'] = bot
    app.add_routes(routes)

@routes.options('/api/apply')
@routes.options('/api/create_team')
@routes.options('/api/teams')
async def options_handler(request):
    """CORS 처리"""
    return web.Response(headers={
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    })

def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@routes.get('/api/activities')
async def api_activities(request: web.Request):
    bot = request.app['bot']
    try:
        programs = await bot.gsheet.get_programs()
        return add_cors_headers(web.json_response({"success": True, "data": programs}))
    except Exception as e:
        log.error(f"프로그램 목록 로드 실패: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

@routes.get('/api/teams')
async def api_teams(request: web.Request):
    bot = request.app['bot']
    try:
        teams = await bot.gsheet.get_teams()
        # Filter for active teams if needed, but for now return all
        return add_cors_headers(web.json_response({"success": True, "data": teams}))
    except Exception as e:
        log.error(f"팀 목록 로드 실패: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

@routes.post('/api/apply')
async def api_apply(request: web.Request):
    """
    구간 1: 매칭 신청 (웹 -> 봇/시트)
    """
    bot = request.app['bot']
    
    try:
        data = await request.json()
        log.info(f"웹 매칭 신청 수신: {data}")
        
        # 1. 고유 ID 발급 (실전 라이선스 키 형태: DUS-XXXX-XXXX-XXXX-XXXX)
        raw_uuid = str(uuid.uuid4()).replace("-", "").upper()
        unique_id = f"DUS-{raw_uuid[0:4]}-{raw_uuid[4:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}"
        
        # 2. 로컬 DB에 기록 (Discord ID는 아직 미인증 상태이므로 빈 값 대신 Unique_ID를 임시로 사용하거나 특정 Prefix 사용)
        # Auth_Status = '미인증' 상태로 applications 테이블에 넣으려면, db_manager 스키마 변경이 필요할 수 있으나
        # 현재는 디스코드 ID가 없으므로 discord_id 칼럼에 'WEB_' + unique_id 형태로 임시 저장하고, 나중에 인증 시 업데이트.
        temp_discord_id = f"WEB_{unique_id}"
        
        # DB 저장 (1인 1신청 검사는 아직 디스코드 ID가 없어서 웹 단계에서는 패스, 디코 연동 시점에 검사함)
        await bot.db._conn.execute("""
            INSERT INTO applications 
            (discord_id, username, student_id, department, skill, activity_id, is_matched, applied_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (
            temp_discord_id,
            data.get('name', '웹 유저'),
            data.get('student_id', '0000000'),
            data.get('department', '미정'),
            data.get('skill', '특기 없음'),
            1, # 임시 활동 ID
            datetime.now(timezone.utc).isoformat(),
            "2099-12-31T23:59:59" # 임시 무제한 만료 (인증 시 72h 부여)
        ))
        await bot.db._conn.commit()

        # 3. 구글 시트 저장
        sheet_data = {
            "unique_id": unique_id,
            "discord_id": "", # 미인증
            "auth_status": "미인증",
            "username": data.get('name', '웹 유저'),
            "student_id": data.get('student_id', '0000000'),
            "department": data.get('department', '미정'),
            "skill": data.get('skill', '특기 없음'),
            "condition_1": data.get('condition_1', ''),
            "condition_2": data.get('condition_2', ''),
            "condition_3": data.get('condition_3', ''),
            "match_status": "대기"
        }
        await bot.gsheet.record_application(sheet_data)
        
        return add_cors_headers(web.json_response({
            "success": True, 
            "unique_id": unique_id
        }))
        
    except Exception as e:
        log.error(f"매칭 신청 API 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

@routes.post('/api/create_team')
async def api_create_team(request: web.Request):
    """
    구간 2: 멤버 모집/구인 신청 (웹 -> 봇/시트)
    """
    bot = request.app['bot']
    
    try:
        data = await request.json()
        log.info(f"웹 팀 구인 수신: {data}")
        
        raw_uuid = str(uuid.uuid4()).replace("-", "").upper()
        team_id = f"TEAM-{raw_uuid[0:4]}-{raw_uuid[4:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}"
        
        # 조장이 디스코드에서 /인증 TEAM-XXXX 로 인증할 수 있도록 임시 신청 내역(applications) 생성
        temp_discord_id = f"WEB_{team_id}"
        leader_name = data.get('leader_name', '웹 조장 유저')
        leader_student_id = data.get('leader_student_id', '0000000')
        
        await bot.db._conn.execute("""
            INSERT INTO applications 
            (discord_id, username, student_id, department, skill, activity_id, is_matched, applied_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (
            temp_discord_id,
            leader_name,
            leader_student_id,
            data.get('department', '미정'),
            "팀장",
            1,
            datetime.now(timezone.utc).isoformat(),
            "2099-12-31T23:59:59"
        ))
        await bot.db._conn.commit()
        
        # 구글 시트 저장
        sheet_data = {
            "team_id": team_id,
            "leader_unique_id": team_id, # 이 ID로 디스코드에서 인증
            "leader_name": leader_name,
            "leader_student_id": leader_student_id,
            "department": data.get('department', ''),
            "program": data.get('program', ''),
            "summary": data.get('summary', ''),
            "description": data.get('description', ''),
            "target_members": data.get('target_members', 4),
            "team_status": "모집중"
        }
        await bot.gsheet.record_recruitment(sheet_data)
        
        return add_cors_headers(web.json_response({
            "success": True,
            "team_id": team_id
        }))
        
    except Exception as e:
        log.error(f"구인 신청 API 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

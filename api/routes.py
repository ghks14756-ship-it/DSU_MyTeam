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
@routes.options('/api/signup')
@routes.options('/api/login')
@routes.options('/api/my-status')
@routes.options('/api/generate-link-code')
async def options_handler(request):
    """CORS 처리"""
    return web.Response(headers={
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    })

def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@routes.get('/api/activities')
async def api_activities(request: web.Request):
    bot = request.app['bot']
    try:
        raw = await bot.gsheet.get_programs()
        # 프론트엔드 JS 기대값에 맞춤
        programs = []
        
        def _parse_int(val):
            try:
                # '3점', '포인트없음' 등 문자열이 들어올 수 있으므로 숫자 변환 시 예외 처리
                clean_val = str(val).replace('점', '').strip()
                return int(clean_val)
            except ValueError:
                return 0
                
        for p in raw:
            programs.append({
                "name": p.get("프로그램 내용", ""),
                "description": p.get("전달사항", ""),
                "deadline": p.get("신청일시", ""),
                "max_members": _parse_int(p.get("최대학습포인트", 0)),
                "category": p.get("카테고리별 분류", ""),
                "target": p.get("신청대상", ""),
                "type": p.get("신청형태", ""),
                "manager": p.get("프로그램 담당자", ""),
                "image": p.get("첨부파일", ""),
                # 원본 데이터 유지
                "프로그램 내용": p.get("프로그램 내용", ""),
                "전달사항": p.get("전달사항", ""),
                "신청일시": p.get("신청일시", ""),
                "카테고리별 분류": p.get("카테고리별 분류", ""),
                "카테고리": p.get("카테고리", ""),
                "첨부파일": p.get("첨부파일", ""),
                "신청대상": p.get("신청대상", ""),
                "최대학습포인트": p.get("최대학습포인트", ""),
                "프로그램 담당자": p.get("프로그램 담당자", "")
            })
        return add_cors_headers(web.json_response({"success": True, "data": programs}))
    except Exception as e:
        log.error(f"프로그램 목록 로드 실패: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

@routes.get('/api/teams')
async def api_teams(request: web.Request):
    bot = request.app['bot']
    try:
        teams = await bot.gsheet.get_teams()
        return add_cors_headers(web.json_response({"success": True, "data": teams}))
    except Exception as e:
        log.error(f"팀 목록 로드 실패: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

@routes.post('/api/apply')
async def api_apply(request: web.Request):
    bot = request.app['bot']
    
    try:
        data = await request.json()
        log.info(f"웹 매칭 신청 수신: {data}")
        
        raw_uuid = str(uuid.uuid4()).replace("-", "").upper()
        unique_id = f"DUS-{raw_uuid[0:4]}-{raw_uuid[4:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}"
        
        temp_discord_id = f"WEB_{unique_id}"
        
        # 1인 1신청 중복 예외가 나더라도 임시 discord_id라 충돌 안날 것임
        await bot.db.create_application(
            discord_id=temp_discord_id,
            username=data.get('name', '웹 유저'),
            student_id=data.get('student_id', '0000000'),
            department=data.get('department', '미정'),
            skill=data.get('skill', '특기 없음'),
            activity_id=1,
            group_code=None
        )

        sheet_data = {
            "unique_id": unique_id,
            "discord_id": "", 
            "auth_status": "미인증",
            "username": data.get('name', '웹 유저'),
            "student_id": data.get('student_id', '0000000'),
            "department": data.get('department', '미정'),
            "skill": data.get('skill', '특기 없음'),
            "condition_1": data.get('condition_1', ''),
            "condition_2": data.get('condition_2', ''),
            "condition_3": data.get('condition_3', ''),
            "match_status": "대기",
            "weekly_schedule": data.get('weekly_schedule', ''),
            "contact": data.get('contact', '')
        }
        await bot.gsheet.record_application(sheet_data)
        
        # 인증키 자동 생성 후 K열(인증키)에 저장
        auth_key = await bot.gsheet.generate_link_code(unique_id)
        
        return add_cors_headers(web.json_response({
            "success": True, 
            "unique_id": unique_id,
            "auth_key": auth_key  # 웹사이트에서 이 키를 유저에게 보여주면 됨
        }))
        
    except Exception as e:
        log.error(f"매칭 신청 API 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

@routes.post('/api/create_team')
async def api_create_team(request: web.Request):
    bot = request.app['bot']
    
    try:
        data = await request.json()
        log.info(f"웹 팀 구인 수신: {data}")
        
        raw_uuid = str(uuid.uuid4()).replace("-", "").upper()
        team_id = f"TEAM-{raw_uuid[0:4]}-{raw_uuid[4:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}"
        
        temp_discord_id = f"WEB_{team_id}"
        unique_id = (data.get('unique_id') or '').strip()
        if unique_id:
            temp_discord_id = f"WEB_{unique_id}"
            
        leader_name = data.get('leader_name', '웹 조장 유저')
        leader_student_id = data.get('leader_student_id', '0000000')
        
        await bot.db.create_application(
            discord_id=temp_discord_id,
            username=leader_name,
            student_id=leader_student_id,
            department=data.get('department', '미정'),
            skill="팀장",
            activity_id=1,
            group_code=None,
            is_leader=True
        )
        
        sheet_data = {
            "team_id": team_id,
            "leader_unique_id": team_id,
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

# [신규] 회원가입 API
@routes.post('/api/signup')
async def api_signup(request: web.Request):
    bot = request.app['bot']
    try:
        data = await request.json()
        web_id = data.get('web_id', '').strip()
        name = data.get('name', '').strip()
        nickname = data.get('nickname', '').strip() or name # 닉네임 없으면 이름으로 Fallback
        unique_id = data.get('unique_id', '').strip()
        
        if not web_id or not name or not unique_id:
            return add_cors_headers(web.json_response({"success": False, "error": "필수 필드가 누락되었습니다."}))
            
        # Unique_ID 존재 여부 검증
        user_record = await bot.gsheet.find_unique_id(unique_id)
        if not user_record:
            return add_cors_headers(web.json_response({"success": False, "error": "유효하지 않은 인증키입니다."}))
            
        # Web_ID 중복 여부 검증
        existing_member = await bot.gsheet.get_member_by_id(web_id)
        if existing_member:
            return add_cors_headers(web.json_response({"success": False, "error": "이미 사용 중인 아이디입니다."}))
            
        # 회원 정보 등록
        member_data = {
            "web_id": web_id,
            "nickname": nickname,
            "unique_id": unique_id
        }
        success = await bot.gsheet.register_member(member_data)
        
        if success:
            return add_cors_headers(web.json_response({"success": True}))
        else:
            return add_cors_headers(web.json_response({"success": False, "error": "구글 시트 저장 실패"}, status=500))
            
    except Exception as e:
        log.error(f"회원가입 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

# [신규] 로그인 API
@routes.post('/api/login')
async def api_login(request: web.Request):
    bot = request.app['bot']
    try:
        data = await request.json()
        web_id = data.get('web_id', '').strip()
        unique_id = data.get('unique_id', '').strip()
        
        member = None
        if web_id:
            member = await bot.gsheet.get_member_by_id(web_id)
        elif unique_id:
            member = await bot.gsheet.get_member_by_unique_id(unique_id)
            if not member:
                # 비회원(아이디 안만든 유저) 확인
                raw_user = await bot.gsheet.find_unique_id(unique_id)
                if raw_user:
                    # 비회원은 통합_사용자_관리의 가입시간을 업데이트할 수도 있지만 현재는 pass
                    return add_cors_headers(web.json_response({
                        "success": True,
                        "data": {
                            "web_id": None,
                            "nickname": raw_user.get("이름", "이름없음"),
                            "unique_id": unique_id,
                            "logged_in": True
                        }
                    }))
                    
        if member:
            # 로그인 성공 시 최근 접속일시 갱신
            update_id = web_id if web_id else unique_id
            await bot.gsheet.update_last_login(update_id, is_web_id=bool(web_id))
            
            return add_cors_headers(web.json_response({
                "success": True,
                "data": {
                    "web_id": member.get("Web_ID"),
                    "nickname": member.get("닉네임"),
                    "unique_id": member.get("Unique_ID"),
                    "logged_in": True
                }
            }))
        else:
            return add_cors_headers(web.json_response({"success": False, "error": "회원 정보를 찾을 수 없습니다."}))
            
    except Exception as e:
        log.error(f"로그인 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

# [신규] 현황 조회 API
@routes.get('/api/my-status')
async def api_my_status(request: web.Request):
    bot = request.app['bot']
    try:
        uid = request.query.get('uid', '').strip()
        if not uid:
            return add_cors_headers(web.json_response({"success": False, "error": "uid 파라미터가 필요합니다."}))
            
        status_data = await bot.gsheet.get_user_status(uid)
        return add_cors_headers(web.json_response({"success": True, "data": status_data}))
        
    except Exception as e:
        log.error(f"현황 조회 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

# [신규] 디스코드 연동 코드 생성 API
@routes.post('/api/generate-link-code')
async def api_generate_link_code(request: web.Request):
    bot = request.app['bot']
    try:
        data = await request.json()
        uid = data.get('unique_id', '').strip()
        
        if not uid:
            return add_cors_headers(web.json_response({"success": False, "error": "인증키가 필요합니다."}))
            
        code = await bot.gsheet.generate_link_code(uid)
        if code:
            return add_cors_headers(web.json_response({"success": True, "code": code}))
        else:
            return add_cors_headers(web.json_response({"success": False, "error": "코드 생성 실패"}))
            
    except Exception as e:
        log.error(f"연동 코드 생성 처리 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

# [신규] 내정보 조회 API
@routes.get('/api/my-profile')
async def api_get_my_profile(request: web.Request):
    bot = request.app['bot']
    try:
        uid = request.query.get('uid', '').strip()
        if not uid:
            return add_cors_headers(web.json_response({"success": False, "error": "uid 파라미터가 필요합니다."}))
            
        profile = await bot.gsheet.get_user_profile(uid)
        if not profile:
            return add_cors_headers(web.json_response({"success": False, "error": "사용자를 찾을 수 없습니다."}))
            
        return add_cors_headers(web.json_response({"success": True, "data": profile}))
        
    except Exception as e:
        log.error(f"내정보 조회 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

# [신규] 내정보 수정 API
@routes.post('/api/my-profile')
async def api_update_my_profile(request: web.Request):
    bot = request.app['bot']
    try:
        data = await request.json()
        uid = data.get('unique_id', '').strip()
        nickname = data.get('nickname', '').strip()
        email = data.get('email', '').strip()
        schedule = data.get('schedule', '').strip()
        
        if not uid:
            return add_cors_headers(web.json_response({"success": False, "error": "unique_id가 누락되었습니다."}))
            
        success = await bot.gsheet.update_user_profile(uid, nickname, email, schedule)
        if success:
            return add_cors_headers(web.json_response({"success": True}))
        else:
            return add_cors_headers(web.json_response({"success": False, "error": "구글 시트 저장 실패"}, status=500))
            
    except Exception as e:
        log.error(f"내정보 수정 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))

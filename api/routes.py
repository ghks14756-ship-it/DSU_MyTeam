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
@routes.options('/api/my-profile')
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
        
        # ── unique_id 결정: 로그인된 유저면 기존 ID 재사용, 비로그인이면 신규 생성 ──
        incoming_uid = data.get('unique_id', '').strip() if data.get('unique_id') else ''
        if incoming_uid and incoming_uid.startswith('DUS-'):
            unique_id = incoming_uid
            log.info(f"[apply] 기존 회원 신청: unique_id={unique_id}")
        else:
            raw_uuid = str(uuid.uuid4()).replace("-", "").upper()
            unique_id = f"DUS-{raw_uuid[0:4]}-{raw_uuid[4:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}"
            log.info(f"[apply] 신규 신청, unique_id 발급: {unique_id}")
        
        temp_discord_id = f"WEB_{unique_id}"
        
        # 1인 1신청 중복 예외가 나더라도 임시 discord_id라 충돌 안날 것임
        program_name = data.get('program', '').strip()  # 사용자가 선택한 프로그램
        await bot.db.create_application(
            discord_id=temp_discord_id,
            username=data.get('name', '웹 유저'),
            student_id=data.get('student_id', '0000000'),
            department=data.get('department', '미정'),
            skill=data.get('skill', '특기 없음'),
            activity_id=None,         # 프로그램명 텍스트로 저장하므로 None
            program=program_name,     # ★ 프로그램별 독립 매칭 필터 트리거
            group_code=None,
            contact=data.get('contact', ''),
            weekly_schedule=data.get('weekly_schedule', ''),
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
        
        program_name = data.get('program', '').strip()  # 팀장이 선택한 프로그램
        await bot.db.create_application(
            discord_id=temp_discord_id,
            username=leader_name,
            student_id=leader_student_id,
            department=data.get('department', '미정'),
            skill="팀장",
            activity_id=None,
            program=program_name,     # ★ 프로그램별 독립 매칭에 필수
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

# ──────────────────────────────────────────────────────────
# [신규] 팀장 대시보드 API 3종
# ──────────────────────────────────────────────────────────

@routes.get('/api/my-teams')
async def api_my_teams(request: web.Request):
    """팀장이 등록한 팀 목록 반환 (unique_id 기반)."""
    bot = request.app['bot']
    uid = request.rel_url.query.get('uid', '').strip()
    if not uid:
        return add_cors_headers(web.json_response({"success": False, "error": "uid 필요"}, status=400))
    try:
        teams = await bot.db.get_my_teams(f"WEB_{uid}")
        result = []
        for t in teams:
            leader_did = t['discord_id']
            async with bot.db._conn.execute(
                "SELECT COUNT(*) as cnt FROM applications WHERE pending_team_leader_id = ? AND is_matched = 1",
                (leader_did,)
            ) as cur:
                row = await cur.fetchone()
                matched_count = row['cnt'] if row else 0
            result.append({
                "discord_id": leader_did,
                "program": t.get("program", ""),
                "username": t.get("username", ""),
                "department": t.get("department", ""),
                "applied_at": t.get("applied_at", ""),
                "matched_members": matched_count,
                "max_members": 4,
            })
        return add_cors_headers(web.json_response({"success": True, "teams": result}))
    except Exception as e:
        log.error(f"my-teams API 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))


@routes.get('/api/team-applicants')
async def api_team_applicants(request: web.Request):
    """특정 팀(프로그램)의 신청자 목록 반환 (팀장 대시보드용)."""
    bot = request.app['bot']
    program = request.rel_url.query.get('program', '').strip()
    uid = request.rel_url.query.get('uid', '').strip()
    if not program or not uid:
        return add_cors_headers(web.json_response({"success": False, "error": "program, uid 필요"}, status=400))
    try:
        leader_did = f"WEB_{uid}"
        applicants = await bot.db.get_team_applicants(program, leader_did)
        result = []
        for a in applicants:
            result.append({
                "discord_id": a.get("discord_id", ""),
                "username": a.get("username", ""),
                "department": a.get("department", ""),
                "skill": a.get("skill", ""),
                "contact": a.get("contact", ""),
                "weekly_schedule": a.get("weekly_schedule", ""),
                "applied_at": a.get("applied_at", ""),
                "pending": bool(a.get("pending_approval", 0)),
                "pending_mine": a.get("pending_team_leader_id") == leader_did,
            })
        return add_cors_headers(web.json_response({"success": True, "applicants": result}))
    except Exception as e:
        log.error(f"team-applicants API 오류: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))


@routes.post('/api/approve-member')
async def api_approve_member(request: web.Request):
    """팀장이 신청자에게 팀 가입 초대 DM 발송."""
    bot = request.app['bot']
    try:
        data = await request.json()
        leader_uid = data.get('leader_uid', '').strip()
        applicant_discord_id = data.get('applicant_discord_id', '').strip()
        program = data.get('program', '').strip()

        if not leader_uid or not applicant_discord_id or not program:
            return add_cors_headers(web.json_response({"success": False, "error": "필수 파라미터 누락"}, status=400))

        leader_discord_id = f"WEB_{leader_uid}"
        app = await bot.db.get_application(applicant_discord_id)
        if not app:
            return add_cors_headers(web.json_response({"success": False, "error": "신청자를 찾을 수 없습니다"}, status=404))
        if app.get("pending_approval") and app.get("pending_team_leader_id") != leader_discord_id:
            return add_cors_headers(web.json_response({"success": False, "error": "이미 다른 팀장이 초대 중인 신청자입니다"}))
        if app.get("is_matched"):
            return add_cors_headers(web.json_response({"success": False, "error": "이미 매칭 완료된 신청자입니다"}))

        await bot.db.set_pending_approval(applicant_discord_id, leader_discord_id)

        leader_app = await bot.db.get_application(leader_discord_id)
        leader_name = leader_app.get('username', '팀장') if leader_app else '팀장'
        leader_dept = leader_app.get('department', '미정') if leader_app else '미정'

        dm_sent = False
        if not applicant_discord_id.startswith("WEB_"):
            try:
                applicant_user = await bot.fetch_user(int(applicant_discord_id))
                from cogs.random_match import PendingApprovalView
                view = PendingApprovalView(
                    bot=bot,
                    applicant_discord_id=applicant_discord_id,
                    leader_discord_id=leader_discord_id,
                    program=program,
                    leader_name=leader_name,
                )
                embed = discord.Embed(
                    title="📨 팀 가입 초대가 도착했습니다!",
                    description=(
                        f"**[{program}]** 프로그램의 팀장 **{leader_name}** ({leader_dept})님이\n"
                        f"팀에 초대했습니다.\n\n"
                        f"⚠️ **주의사항:** 24시간 내 미응답 시 자동으로 매칭 대기열로 복귀됩니다."
                    ),
                    color=0x5865F2,
                )
                embed.add_field(name="🏫 팀장 학과", value=leader_dept, inline=True)
                embed.add_field(name="📌 프로그램", value=program, inline=True)
                embed.set_footer(text="DSU My_team · 팀 가입 초대")
                await applicant_user.send(embed=embed, view=view)
                dm_sent = True
                log.info(f"[승인DM] 발송 완료: {applicant_discord_id} ← {leader_name}")
            except Exception as e:
                log.warning(f"[승인DM] DM 발송 실패 [{applicant_discord_id}]: {e}")

        return add_cors_headers(web.json_response({
            "success": True,
            "dm_sent": dm_sent,
            "message": "초대 DM이 발송되었습니다." if dm_sent else "pending 상태 처리 완료 (미인증 사용자는 DM 불가)."
        }))

    except Exception as e:
        log.error(f"approve-member API 오류: {e}")
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
        
        if not web_id or not name:
            return add_cors_headers(web.json_response({"success": False, "error": "필수 필드가 누락되었습니다."}))
            
        # Web_ID 중복 여부 검증
        existing_member = await bot.gsheet.get_member_by_id(web_id)
        if existing_member:
            return add_cors_headers(web.json_response({"success": False, "error": "이미 사용 중인 아이디입니다."}))
            
        # 자체 unique_id 및 인증키 발급
        import uuid, secrets, string
        raw_uuid = str(uuid.uuid4()).replace("-", "").upper()
        unique_id = f"DUS-{raw_uuid[0:4]}-{raw_uuid[4:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}"
        auth_key = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        
        # 1. 회원 정보 탭 등록
        member_data = {
            "web_id": web_id,
            "nickname": nickname,
            "unique_id": unique_id
        }
        success_member = await bot.gsheet.register_member(member_data)
        
        if not success_member:
            return add_cors_headers(web.json_response({"success": False, "error": "회원_정보 시트 저장 실패"}, status=500))

        # 2. 통합_사용자_관리 탭 등록 (회원가입 시 이름 및 고유 키 할당)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        user_row = [
            unique_id,
            "회원",        # 역할 (대기자 대신 회원으로 초기 등록)
            "",           # Discord_ID
            "미인증",     # Auth_Status
            name,         # username (실명)
            "",           # student_id
            "",           # department
            "",           # skill
            "미정",       # program
            now,
            auth_key      # K열(인증키) 발급
        ]
        
        loop = __import__('asyncio').get_running_loop()
        client = await loop.run_in_executor(None, bot.gsheet._get_client)
        def _append_user():
            doc = client.open_by_key(bot.gsheet.spreadsheet_id)
            ws_users = doc.worksheet(bot.gsheet.worksheet_users)
            ws_users.append_row(user_row)
            return True
            
        await loop.run_in_executor(None, _append_user)
        
        return add_cors_headers(web.json_response({"success": True}))
            
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

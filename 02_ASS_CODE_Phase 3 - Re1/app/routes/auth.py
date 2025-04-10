# app/routes/auth.py
# 사용자 인증 관련 라우트 (회원가입, 로그인, 로그아웃 등)

from flask import Blueprint, request, jsonify, session, current_app, g
from functools import wraps
# db_utils에서 필요한 함수들을 import
from app.utils.db_utils import find_user_by_email, add_user, check_user_password

# 'auth' 이름으로 Blueprint 객체 생성
# url_prefix='/auth'는 app/__init__.py에서 블루프린트 등록 시 설정
bp = Blueprint('auth', __name__)

# --- 로그인 확인 데코레이터 ---
def login_required(f):
    """
    요청을 처리하기 전에 사용자가 로그인되어 있는지 확인하는 데코레이터.
    로그인되어 있지 않으면 401 Unauthorized 에러를 반환합니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 세션에 'user_id'가 없으면 로그인되지 않은 상태
        if 'user_id' not in session:
            print("[Auth Decorator] 로그인 필요 - 접근 거부됨")
            return jsonify({"error": "로그인이 필요합니다."}), 401 # 401 Unauthorized
        # g 객체에 사용자 정보 저장 (선택적, 요청 처리 중 쉽게 접근하기 위함)
        # g.user_id = session['user_id']
        # g.user_email = session.get('user_email') # 이메일도 저장했다면 로드
        # 로그인이 되어 있으면 원래 함수 실행
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@bp.route('/register', methods=['POST'])
def register():
    """
    회원가입 처리 라우트.
    요청 본문에서 email, password를 받아 사용자를 등록합니다.
    """
    # 요청 본문이 JSON 형태라고 가정
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400

    email = data['email']
    password = data['password']

    # 간단한 유효성 검사 (추가 검증 필요 - 예: 이메일 형식, 비밀번호 복잡도)
    if len(password) < 8: # 예시: 최소 비밀번호 길이 검사
        return jsonify({"error": "비밀번호는 최소 8자 이상이어야 합니다."}), 400
    # TODO: 이메일 형식 검사 추가 (정규표현식 등 사용)

    print(f"[Auth Route - Register] 회원가입 시도: {email}")

    # 이메일 중복 확인 (DB 조회)
    existing_user = find_user_by_email(email)
    if existing_user:
        print(f"[Auth Route - Register] 이미 존재하는 이메일: {email}")
        return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409 # 409 Conflict

    # 사용자 추가 시도 (DB 저장)
    # add_user 함수는 성공 시 사용자 정보 dict, 이메일 중복 시 {"error": ...}, 실패 시 None 반환
    new_user_info = add_user(email, password) # 기본 역할 'USER'로 추가됨

    if new_user_info and "error" not in new_user_info:
        # 성공 시 사용자 정보 일부 반환 (비밀번호 해시는 제외)
        print(f"[Auth Route - Register] 회원가입 성공: {email} (ID: {new_user_info.get('id')})")
        return jsonify({
            "message": "회원가입 성공!",
            "user": {
                "id": new_user_info.get("id"),
                "email": new_user_info.get("email"),
                "role": new_user_info.get("role"),
                "created_at": new_user_info.get("created_at")
            }
        }), 201 # 201 Created
    elif new_user_info and new_user_info.get("error") == "Email already exists":
         # add_user 내에서 중복을 잡았을 경우
         # (위에서 find_user_by_email로 미리 체크해서 이 경우는 드물지만 방어 코드)
         return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409
    else:
        # 기타 DB 오류 등
        print(f"[Auth Route - Register] 회원가입 처리 중 서버 오류 발생: {email}")
        return jsonify({"error": "회원가입 처리 중 오류가 발생했습니다."}), 500

@bp.route('/login', methods=['POST'])
def login():
    """
    로그인 처리 라우트.
    요청 본문에서 email, password를 받아 인증 후 세션을 생성합니다.
    """
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400

    email = data['email']
    password = data['password']

    print(f"[Auth Route - Login] 로그인 시도: {email}")

    # 1. 이메일로 사용자 찾기 (DB 조회)
    user_data = find_user_by_email(email)

    # 2. 사용자 존재 및 비밀번호 확인
    if user_data and check_user_password(user_data['password_hash'], password):
        # 로그인 성공!
        # 세션에 사용자 ID와 이메일 저장 (이제 이 사용자는 로그인 상태)
        session.clear() # 기존 세션 정보가 있다면 초기화 (선택적)
        session['user_id'] = user_data['id']
        session['user_email'] = user_data['email'] # 이메일도 저장하여 /me 등에서 활용
        session['user_role'] = user_data['role'] # 역할 정보도 저장 (관리자 구분 등)
        # session.permanent = True # 세션 유지 기간 설정 (기본값은 브라우저 종료 시까지)
        print(f"[Auth Route - Login] 로그인 성공: {email} (User ID: {user_data['id']}, Role: {user_data['role']})")
        return jsonify({
            "message": "로그인 성공!",
            "user": { # 비밀번호 해시는 제외하고 반환
                "id": user_data['id'],
                "email": user_data['email'],
                "role": user_data['role']
            }
        })
    else:
        # 로그인 실패 (사용자 없거나 비밀번호 틀림)
        print(f"[Auth Route - Login] 로그인 실패: {email}")
        return jsonify({"error": "이메일 또는 비밀번호가 잘못되었습니다."}), 401 # 401 Unauthorized

@bp.route('/logout', methods=['POST'])
@login_required # 로그아웃은 로그인된 사용자만 가능하도록
def logout():
    """
    로그아웃 처리 라우트.
    현재 사용자의 세션 정보를 삭제합니다.
    """
    user_id = session.get('user_id') # 데코레이터에서 확인했지만, 로깅 위해 다시 가져옴
    user_email = session.get('user_email')

    # 세션에서 사용자 정보 제거
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_role', None)
    # 또는 session.clear() 로 모든 세션 정보 삭제 가능

    print(f"[Auth Route - Logout] 로그아웃 성공: {user_email} (User ID: {user_id})")
    return jsonify({"message": "로그아웃 되었습니다."})

@bp.route('/me', methods=['GET'])
@login_required # 로그인 필수
def get_current_user_info():
    """
    현재 로그인된 사용자의 정보를 반환하는 라우트.
    세션에 저장된 정보를 사용합니다.
    """
    # 데코레이터(@login_required)에서 이미 로그인 여부를 확인했으므로,
    # 세션에 user_id, user_email, user_role이 있다고 가정할 수 있음
    user_id = session['user_id']
    user_email = session['user_email']
    user_role = session['user_role']

    print(f"[Auth Route - Me] 현재 사용자 정보 요청: ID={user_id}, Email={user_email}")
    return jsonify({
        "message": "현재 로그인된 사용자 정보",
        "user": {
            "id": user_id,
            "email": user_email,
            "role": user_role
            # 필요한 다른 정보가 있다면 DB 조회 후 추가 가능
        }
    })

# TODO: 비밀번호 변경, 비밀번호 찾기/재설정 등의 기능 추가 고려

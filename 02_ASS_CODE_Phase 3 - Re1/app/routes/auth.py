# app/routes/auth.py
# 사용자 인증 관련 라우트 (회원가입, 로그인, 로그아웃 등)

from flask import Blueprint, request, jsonify, session, current_app, g, abort, render_template, redirect, url_for, flash # render_template, redirect, url_for, flash 추가
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
    로그인되어 있지 않으면 로그인 페이지로 리디렉션합니다. (API 요청 시에는 401 반환)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            print("[Auth Decorator] 로그인 필요 - 접근 거부됨")
            # API 요청(JSON 선호)일 경우 401 JSON 응답
            if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
                 return jsonify({"error": "로그인이 필요합니다."}), 401
            else:
                 # 일반 페이지 요청일 경우 로그인 페이지로 리디렉션
                 flash("로그인이 필요한 서비스입니다.", "warning")
                 return redirect(url_for('auth.login', next=request.url)) # 로그인 후 원래 가려던 페이지로 이동
        return f(*args, **kwargs)
    return decorated_function

# --- 관리자 확인 데코레이터 ---
def admin_required(f):
    """
    요청을 처리하기 전에 사용자가 관리자(admin) 권한을 가지고 있는지 확인하는 데코레이터.
    관리자가 아니면 403 Forbidden 에러를 반환합니다. (로그인 필수 선행 가정)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_role = session.get('user_role')
        if user_role != 'ADMIN':
            print(f"[Auth Decorator] 관리자 권한 필요 - 접근 거부됨 (User Role: {user_role})")
            flash("관리자 권한이 필요합니다.", "error")
            # 접근 권한 없을 시 이전 페이지 또는 메인 페이지로 리디렉션 고려
            # return redirect(request.referrer or url_for('synthesize.index'))
            abort(403) # 403 Forbidden 에러 발생
        return f(*args, **kwargs)
    return decorated_function


# --- Routes ---

# 수정: methods에 'GET' 추가
@bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    GET 요청 시 회원가입 페이지를 보여주고,
    POST 요청 시 회원가입을 처리합니다.
    """
    if request.method == 'POST':
        # --- POST 요청 처리 (기존 로직) ---
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400

        email = data['email']
        password = data['password']

        if len(password) < 8:
            return jsonify({"error": "비밀번호는 최소 8자 이상이어야 합니다."}), 400
        # TODO: 이메일 형식 서버측 검증 추가

        print(f"[Auth Route - Register POST] 회원가입 시도: {email}")
        existing_user = find_user_by_email(email)
        if existing_user:
            print(f"[Auth Route - Register POST] 이미 존재하는 이메일: {email}")
            return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409

        new_user_info = add_user(email, password)

        if new_user_info and "error" not in new_user_info:
            print(f"[Auth Route - Register POST] 회원가입 성공: {email} (ID: {new_user_info.get('id')})")
            # 회원가입 성공 시 바로 로그인 처리 또는 로그인 페이지로 안내
            # 여기서는 성공 메시지와 함께 201 반환 (JS에서 리디렉션)
            return jsonify({
                "message": "회원가입 성공! 로그인 페이지로 이동합니다.",
                "user": { # 민감 정보 제외
                    "id": new_user_info.get("id"),
                    "email": new_user_info.get("email"),
                    "role": new_user_info.get("role")
                }
            }), 201
        elif new_user_info and new_user_info.get("error") == "Email already exists":
             return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409
        else:
            print(f"[Auth Route - Register POST] 회원가입 처리 중 서버 오류 발생: {email}")
            return jsonify({"error": "회원가입 처리 중 오류가 발생했습니다."}), 500
    else:
        # --- GET 요청 처리 ---
        # 회원가입 페이지 템플릿 렌더링
        return render_template('auth/register.html')


# 수정: methods에 'GET' 추가
@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET 요청 시 로그인 페이지를 보여주고,
    POST 요청 시 로그인을 처리합니다.
    """
    if request.method == 'POST':
        # --- POST 요청 처리 (기존 로직) ---
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400

        email = data['email']
        password = data['password']

        print(f"[Auth Route - Login POST] 로그인 시도: {email}")
        user_data = find_user_by_email(email)

        if user_data and check_user_password(user_data['password_hash'], password):
            session.clear()
            session['user_id'] = user_data['id']
            session['user_email'] = user_data['email']
            session['user_role'] = user_data['role']
            print(f"[Auth Route - Login POST] 로그인 성공: {email} (User ID: {user_data['id']}, Role: {user_data['role']})")
            # 로그인 성공 시 메인 페이지 URL 반환 (JS에서 리디렉션)
            # 또는 여기서 바로 redirect 할 수도 있음
            return jsonify({
                "message": "로그인 성공!",
                "redirect_url": url_for('synthesize.index'), # 메인 페이지 URL 전달
                "user": {
                    "id": user_data['id'],
                    "email": user_data['email'],
                    "role": user_data['role']
                }
            })
        else:
            print(f"[Auth Route - Login POST] 로그인 실패: {email}")
            return jsonify({"error": "이메일 또는 비밀번호가 잘못되었습니다."}), 401
    else:
        # --- GET 요청 처리 ---
        # 로그인 페이지 템플릿 렌더링
        return render_template('auth/login.html')


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    로그아웃 처리 라우트.
    세션 정보를 삭제하고 로그인 페이지로 리디렉션합니다.
    """
    user_id = session.get('user_id')
    user_email = session.get('user_email')

    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_role', None)

    print(f"[Auth Route - Logout] 로그아웃 성공: {user_email} (User ID: {user_id})")
    flash("로그아웃 되었습니다.", "success")
    # 로그아웃 후 로그인 페이지로 리디렉션
    return redirect(url_for('auth.login'))


@bp.route('/me', methods=['GET'])
@login_required
def get_current_user_info():
    """
    현재 로그인된 사용자의 정보를 반환하는 라우트. (API)
    """
    user_id = session['user_id']
    user_email = session['user_email']
    user_role = session['user_role']

    print(f"[Auth Route - Me] 현재 사용자 정보 요청: ID={user_id}, Email={user_email}, Role={user_role}")
    return jsonify({
        "message": "현재 로그인된 사용자 정보",
        "user": {
            "id": user_id,
            "email": user_email,
            "role": user_role
        }
    })


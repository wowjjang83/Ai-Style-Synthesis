# app/routes/auth.py
# 사용자 인증 관련 라우트 (회원가입, 로그인, 로그아웃 등)

# 수정: werkzeug 대신 urllib.parse 사용
from flask import (
    Blueprint, request, jsonify, session, current_app, g, abort,
    render_template, redirect, url_for, flash
)
from urllib.parse import urlparse # Python 내장 URL 파싱 라이브러리 사용
from functools import wraps
# db_utils에서 필요한 함수들을 import
from app.utils.db_utils import find_user_by_email, add_user, check_user_password

# 'auth' 이름으로 Blueprint 객체 생성
bp = Blueprint('auth', __name__)

# --- 로그인 확인 데코레이터 ---
# (변경 없음)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            print("[Auth Decorator] 로그인 필요 - 접근 거부됨")
            if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
                 return jsonify({"error": "로그인이 필요합니다."}), 401
            else:
                 flash("로그인이 필요한 서비스입니다.", "warning")
                 login_url = url_for('auth.login', next=request.url)
                 print(f"[Auth Decorator] 로그인 페이지로 리디렉션: {login_url}")
                 return redirect(login_url)
        return f(*args, **kwargs)
    return decorated_function

# --- 관리자 확인 데코레이터 ---
# (변경 없음)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_role = session.get('user_role')
        if user_role != 'ADMIN':
            print(f"[Auth Decorator] 관리자 권한 필요 - 접근 거부됨 (User Role: {user_role})")
            flash("관리자 권한이 필요합니다.", "error")
            abort(403) # 403 Forbidden 에러 발생
        return f(*args, **kwargs)
    return decorated_function


# --- Routes ---

# /register (변경 없음)
@bp.route('/register', methods=['GET', 'POST'])
def register():
    # ... (기존 코드와 동일) ...
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400
        email = data['email']
        password = data['password']
        if len(password) < 8:
            return jsonify({"error": "비밀번호는 최소 8자 이상이어야 합니다."}), 400
        print(f"[Auth Route - Register POST] 회원가입 시도: {email}")
        existing_user = find_user_by_email(email)
        if existing_user:
            print(f"[Auth Route - Register POST] 이미 존재하는 이메일: {email}")
            return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409
        new_user_info = add_user(email, password)
        if new_user_info and "error" not in new_user_info:
            print(f"[Auth Route - Register POST] 회원가입 성공: {email} (ID: {new_user_info.get('id')})")
            return jsonify({
                "message": "회원가입 성공! 로그인 페이지로 이동합니다.",
                "user": { "id": new_user_info.get("id"), "email": new_user_info.get("email"), "role": new_user_info.get("role") }
            }), 201
        elif new_user_info and new_user_info.get("error") == "Email already exists":
             return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409
        else:
            print(f"[Auth Route - Register POST] 회원가입 처리 중 서버 오류 발생: {email}")
            return jsonify({"error": "회원가입 처리 중 오류가 발생했습니다."}), 500
    else:
        return render_template('auth/register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET 요청 시 로그인 페이지를 보여주고,
    POST 요청 시 로그인을 처리하고 적절한 페이지로 리디렉션합니다.
    """
    if request.method == 'POST':
        # --- POST 요청 처리 ---
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

            # --- 리디렉션 로직 (urllib.parse 사용) ---
            next_page = request.args.get('next')
            print(f"[Auth Route - Login POST] DEBUG: 'next' 파라미터 값: {next_page}") # 디버그 로그

            is_safe = False
            redirect_url = None # 초기화

            if next_page:
                parsed_next = urlparse(next_page)
                current_host = request.host
                print(f"[Auth Route - Login POST] DEBUG: Parsed next_page netloc: '{parsed_next.netloc}', Current request.host: '{current_host}'") # 디버그 로그

                # netloc이 없거나(상대경로) netloc이 현재 호스트와 같으면 안전
                if not parsed_next.netloc or parsed_next.netloc == current_host:
                    is_safe = True
                    print(f"[Auth Route - Login POST] 'next' URL 안전함 판정.")
                else:
                    is_safe = False
                    print(f"[Auth Route - Login POST] 경고: 'next' URL이 안전하지 않음 판정.")

            # 안전한 `next` URL이 있으면 거기로, 없으면 기본 페이지로 리디렉션 URL 결정
            if is_safe:
                redirect_url = next_page
                print(f"[Auth Route - Login POST] DEBUG: 최종 redirect_url 결정 (is_safe=True): {redirect_url}") # 디버그 로그
            else:
                print(f"[Auth Route - Login POST] DEBUG: is_safe=False 또는 next_page 없음. 기본 리디렉션 결정 시작.") # 디버그 로그
                if user_data['role'] == 'ADMIN':
                    redirect_url = url_for('admin.dashboard')
                    print(f"[Auth Route - Login POST] DEBUG: 최종 redirect_url 결정 (기본-관리자): {redirect_url}") # 디버그 로그
                else:
                    redirect_url = url_for('synthesize.index')
                    print(f"[Auth Route - Login POST] DEBUG: 최종 redirect_url 결정 (기본-사용자): {redirect_url}") # 디버그 로그

            # --- 최종 응답 반환 전 확인 ---
            print(f"[Auth Route - Login POST] DEBUG: 최종 반환될 redirect_url: {redirect_url}") # 디버그 로그

            # --- 응답 반환 ---
            return jsonify({
                "message": "로그인 성공!",
                "redirect_url": redirect_url, # 계산된 리디렉션 URL 전달
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
        return render_template('auth/login.html')


# /logout (변경 없음)
@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    # ... (기존 코드와 동일) ...
    user_id = session.get('user_id')
    user_email = session.get('user_email')
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_role', None)
    print(f"[Auth Route - Logout] 로그아웃 성공: {user_email} (User ID: {user_id})")
    flash("로그아웃 되었습니다.", "success")
    return redirect(url_for('auth.login'))


# /me (변경 없음)
@bp.route('/me', methods=['GET'])
@login_required
def get_current_user_info():
    # ... (기존 코드와 동일) ...
    user_id = session['user_id']
    user_email = session['user_email']
    user_role = session['user_role']
    print(f"[Auth Route - Me] 현재 사용자 정보 요청: ID={user_id}, Email={user_email}, Role={user_role}")
    return jsonify({
        "message": "현재 로그인된 사용자 정보",
        "user": { "id": user_id, "email": user_email, "role": user_role }
    })
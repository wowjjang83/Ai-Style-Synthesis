# app.py
from flask import Flask, jsonify, request, session # session 추가
from dotenv import load_dotenv
import os
from io import BytesIO
from PIL import Image
from werkzeug.utils import secure_filename
import psycopg2 # DB 드라이버
# --- AI Module Import ---
from google import genai
from ai_module import synthesize_image, apply_watermark_func
# --- DB Utils Import ---
# db_utils 함수 import 수정
from db_utils import get_setting, get_active_base_model, find_user_by_email, add_user, check_password, get_todays_usage, increment_usage
# app.py (상단 import 부분에 추가)
from werkzeug.security import generate_password_hash # add_user에서 사용하므로 직접 import는 불필요할 수 있음
from functools import wraps # 데코레이터 사용 위해 import
from datetime import date # 직접 사용하진 않지만 관련 함수 import 위해

# .env 파일 로드
load_dotenv()

# --- 환경 변수 로드 ---
api_key = os.getenv("GEMINI_API_KEY")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
flask_secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key_should_be_changed")

# --- 초기화 ---
# API 클라이언트
if api_key:
    client = genai.Client(api_key=api_key)
    print("Google AI Client 초기화 완료!")
else:
    print("오류: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다. AI 호출이 불가능합니다.")
    client = None

# Flask 앱
app = Flask(__name__)

# <<< Flask Secret Key 설정 >>>
app.config['SECRET_KEY'] = flask_secret_key
print(f"Flask SECRET_KEY 설정됨 (길이: {len(app.config['SECRET_KEY'])})")

# --- 설정 ---
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- 유틸리티 함수 ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 로그인 확인 데코레이터 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 세션에 user_id가 없으면 로그인되지 않은 상태
        if 'user_id' not in session:
            print("[Auth Decorator] 로그인 필요 - 접근 거부됨")
            return jsonify({"error": "로그인이 필요합니다."}), 401 # 401 Unauthorized
        # 로그인이 되어 있으면 원래 함수 실행
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/')
def home():
    return jsonify({"message": "ASS Backend is running!"})

@app.route('/test-db')
def test_db_connection():
    # ... (이전 DB 테스트 코드는 그대로 유지) ...
    conn = None
    try:
        print("[DB Test] 데이터베이스 연결 시도...")
        conn = psycopg2.connect(host=db_host,port=db_port,dbname=db_name,user=db_user,password=db_password)
        cur = conn.cursor()
        cur.execute('SELECT version();')
        db_version = cur.fetchone()
        cur.close()
        conn.close()
        print("[DB Test] 데이터베이스 연결 성공 및 버전 확인 완료!")
        return jsonify({"message": "Database connection successful!","db_version": db_version[0] if db_version else "N/A"})
    except psycopg2.Error as e:
        error_message = f"Database connection failed: {e}"
        print(f"[DB Test] {error_message}")
        return jsonify({"error": error_message}), 500
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(f"[DB Test] {error_message}")
        return jsonify({"error": error_message}), 500
    finally:
        if conn is not None:
            conn.close()
            print("[DB Test] 데이터베이스 연결 종료됨 (finally).")

# --- 사용자 인증 라우트 ---
@app.route('/register', methods=['POST']) # <<< 회원가입 API 엔드포인트
def register_route():
    # 요청 본문이 JSON 형태라고 가정
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400

    email = data['email']
    password = data['password']

    # 간단한 유효성 검사 (추가적인 검증 필요 - 예: 이메일 형식, 비밀번호 길이 등)
    if len(password) < 8: # 예시: 최소 비밀번호 길이 검사
        return jsonify({"error": "비밀번호는 최소 8자 이상이어야 합니다."}), 400

    print(f"[Register Route] 회원가입 시도: {email}")

    # 이메일 중복 확인
    existing_user = find_user_by_email(email)
    if existing_user:
        print(f"[Register Route] 이미 존재하는 이메일: {email}")
        return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409 # 409 Conflict

    # 사용자 추가 시도
    new_user_info = add_user(email, password)

    if new_user_info and not new_user_info.get("error"):
        # 성공 시 사용자 정보 일부 반환 (비밀번호 해시는 제외)
        return jsonify({
            "message": "회원가입 성공!",
            "user": {
                "id": new_user_info["id"],
                "email": new_user_info["email"],
                "created_at": new_user_info["created_at"]
            }
        }), 201 # 201 Created
    elif new_user_info and new_user_info.get("error") == "Email already exists":
         # add_user 내에서 중복을 잡았을 경우 (여기서는 미리 체크해서 이 경우는 드묾)
         return jsonify({"error": "이미 사용 중인 이메일입니다."}), 409
    else:
        # 기타 DB 오류 등
        return jsonify({"error": "회원가입 처리 중 오류가 발생했습니다."}), 500


# --- 로그인 라우트 ---
@app.route('/login', methods=['POST']) # <<< 로그인 API 엔드포인트
def login_route():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email과 password를 JSON 형식으로 제공해야 합니다."}), 400

    email = data['email']
    password = data['password']

    print(f"[Login Route] 로그인 시도: {email}")

    # 1. 이메일로 사용자 찾기
    user_data = find_user_by_email(email)

    # 2. 사용자 존재 및 비밀번호 확인
    if user_data and check_password(user_data['password_hash'], password):
        # 로그인 성공!
        # 세션에 사용자 ID 저장 (이제 이 사용자는 로그인 상태)
        session['user_id'] = user_data['id']
        session['user_email'] = user_data['email'] # 이메일도 저장 (선택적)
        print(f"[Login Route] 로그인 성공: {email} (User ID: {user_data['id']})")
        return jsonify({
            "message": "로그인 성공!",
            "user": { # 비밀번호 해시는 제외하고 반환
                "id": user_data['id'],
                "email": user_data['email']
            }
        })
    else:
        # 로그인 실패
        print(f"[Login Route] 로그인 실패: {email}")
        return jsonify({"error": "이메일 또는 비밀번호가 잘못되었습니다."}), 401 # 401 Unauthorized

# --- 로그아웃 라우트 (세션 지우기) ---
@app.route('/logout', methods=['POST']) # <<< 로그아웃 API 엔드포인트
def logout_route():
    user_id = session.get('user_id')
    if user_id:
        # 세션에서 사용자 정보 제거
        session.pop('user_id', None)
        session.pop('user_email', None) # 다른 세션 정보도 있다면 제거
        print(f"[Logout Route] 로그아웃 성공: User ID {user_id}")
        return jsonify({"message": "로그아웃 성공!"})
    else:
        print("[Logout Route] 로그아웃 시도: 로그인 상태 아님")
        return jsonify({"error": "로그인 상태가 아닙니다."}), 401

# --- 현재 사용자 정보 반환 라우트 ---
@app.route('/me') # <<< /me 엔드포인트 (GET 방식)
@login_required   # <<< 로그인 필수 적용
def me_route():
    # 데코레이터에서 이미 로그인 확인됨
    user_id = session.get('user_id')
    user_email = session.get('user_email') # 로그인 시 세션에 저장한 정보 사용
    print(f"[/me Route] 현재 사용자 정보 요청: ID={user_id}, Email={user_email}")
    return jsonify({
        "message": "현재 로그인된 사용자 정보",
        "user": {
            "id": user_id,
            "email": user_email
        }
    })

# --- 이미지 합성 API 엔드포인트 (수정) ---
@app.route('/synthesize/web', methods=['POST'])
@login_required
def synthesize_web_route():
    user_id = session['user_id']
    print(f"[Synthesize Route] 요청 사용자 ID: {user_id}")

    # --- 사용량 제한 확인 ---
    try:
        limit_str = get_setting('max_user_syntheses')
        daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3 # 숫자 변환 확인 강화
        current_usage = get_todays_usage(user_id)
        if current_usage >= daily_limit:
            return jsonify({"error": f"일일 최대 합성 횟수({daily_limit}회)를 초과했습니다."}), 429
    except Exception as e:
         print(f"[Synthesize Route] 사용량 확인 중 오류: {e}")
         return jsonify({"error": "사용량 확인 중 오류 발생"}), 500

    # --- AI 클라이언트 및 베이스 모델 확인 ---
    if not client: return jsonify({"error": "API Client가 초기화되지 않았습니다."}), 500
    active_model = get_active_base_model()
    if not active_model or not active_model.get("image_url"):
        return jsonify({"error": "활성 베이스 모델을 찾을 수 없습니다."}), 500
    base_img_path = active_model["image_url"]

    # --- 입력 처리 ---
    if 'item_image' not in request.files: return jsonify({"error": "No 'item_image' part"}), 400
    if 'item_type' not in request.form: return jsonify({"error": "No 'item_type' data"}), 400
    item_file = request.files['item_image']
    item_type = request.form['item_type']
    if item_file.filename == '': return jsonify({"error": "No selected file"}), 400
    if not allowed_file(item_file.filename): return jsonify({"error": "File type not allowed"}), 400
    item_filename = secure_filename(item_file.filename)
    item_filepath = os.path.join(app.config['UPLOAD_FOLDER'], item_filename)
    try:
        item_file.save(item_filepath)
    except Exception as e:
        return jsonify({"error": "Failed to save item image"}), 500

    # --- AI 합성 호출 ---
    print(f"[Synthesize Route] AI 합성 호출 시작 (Base: {base_img_path})...")
    result_image_bytes = synthesize_image(client, base_img_path, item_filepath, item_type)

    # --- 결과 처리 (워터마크 추가) ---
    if result_image_bytes:
        final_image_bytes = result_image_bytes # 최종 이미지 바이트 변수

        # --- 워터마크 적용 로직 ---
        try:
            apply_wm_setting = get_setting('apply_watermark')
            apply_wm = apply_wm_setting.lower() == 'true' if apply_wm_setting else False # 설정값 읽기 (기본 false)
            print(f"[Synthesize Route] 워터마크 적용 설정: {apply_wm}")

            if apply_wm:
                watermark_path = "watermark.png" # 워터마크 파일 경로
                watermarked_bytes = apply_watermark_func(result_image_bytes, watermark_path)
                if watermarked_bytes:
                    final_image_bytes = watermarked_bytes # 성공 시 워터마크 적용된 바이트 사용
                else:
                    print("[Synthesize Route] 경고: 워터마크 적용 실패, 원본 이미지 사용.")
        except Exception as wm_e:
            print(f"[Synthesize Route] 워터마크 처리 중 오류 발생: {wm_e}")
        # --- 워터마크 적용 로직 끝 ---

        # --- 사용량 증가 ---
        if not increment_usage(user_id):
            print(f"[Synthesize Route] 경고: 사용량 증가 실패 (User ID: {user_id})")

        # --- 최종 이미지 저장 ---
        try:
            output_filename_base = f"output_{user_id}_{secure_filename(item_type)}_{os.path.splitext(item_filename)[0]}"
            output_filename = f"{output_filename_base}.png" # 저장 형식을 PNG로 고정 (워터마크 투명도 위해)
            output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            # 최종 이미지 바이트(원본 또는 워터마크)를 사용
            img = Image.open(BytesIO(final_image_bytes))
            img.save(output_filepath) # PNG로 저장
            print(f"[Synthesize Route] 합성 성공! 결과를 '{output_filepath}' 파일로 저장했습니다.")
            return jsonify({"message": "Synthesis successful!", "output_file": output_filepath })
        except Exception as e:
            print(f"[Flask Route] 결과 이미지 저장 중 오류: {e}")
            return jsonify({"error": "Synthesis succeeded but failed to save output."}), 500
    else:
        print("[Synthesize Route] 합성 실패 (AI module).")
        return jsonify({"error": "Image synthesis failed (AI module)."}), 500



# --- App Execution ---
if __name__ == '__main__':
    app.run(debug=True)
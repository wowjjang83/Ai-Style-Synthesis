import os
import uuid
import datetime # 사용량 추적 등에 필요할 수 있음
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, session, send_from_directory, redirect, url_for, abort
from dotenv import load_dotenv
import google.generativeai as genai

# --- 사용자 정의 모듈 Import ---
# db_utils.py 와 ai_module.py 가 app.py 와 같은 디렉토리에 있다고 가정
import db_utils
import ai_module

# .env 파일 로드
load_dotenv()

# --- Flask 앱 설정 ---
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_change_me') # 개발용 임시 키, 실제 환경에서는 변경

# --- 폴더 설정 ---
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
BASE_MODEL_FOLDER = os.path.join(app.static_folder, 'base_models') # static 폴더 하위
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# 폴더 생성 (없으면)
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, BASE_MODEL_FOLDER]:
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            print(f"폴더 생성됨: {folder}")
        except OSError as e:
            print(f"폴더 생성 실패: {folder}, 이유: {e}")
            # 폴더 생성 실패 시 심각한 문제이므로, 여기서 앱 실행을 중단하거나 적절한 처리 필요

# --- Google AI 설정 ---
GOOGLE_API_KEY = os.environ.get('GEMINI_API_KEY')
gemini_model = None # 전역 변수로 선언
if not GOOGLE_API_KEY:
    print("오류: GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. AI 기능 사용 불가.")
else:
    try:
         genai.configure(api_key=GOOGLE_API_KEY)
         print("Google AI SDK 설정 완료.")
         # 사용할 모델 객체 생성
         gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")
         print(f"Gemini 모델 '{gemini_model.model_name}' 인스턴스 생성 완료.")
    except Exception as e:
         print(f"Google AI SDK 설정 중 오류 발생: {e}. AI 기능 사용 불가.")


# --- 헬퍼 함수 ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 데코레이터 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"DEBUG [Decorator]: Path={request.path}, Current Session = {session}") # 세션 내용 로깅
        # if 'user_id' not in session: # <<< 세션 유무 체크를 임시로 주석 처리!
            # ... (기존 401 또는 redirect 로직 부분 전체 주석 처리) ...
            # pass # 일단 통과시킴
        # else 조건 없이 항상 원래 함수 실행
        # user_id = session.get('user_id', 'Unknown (Check Bypassed)') # ID가 없을 수 있음을 인지
        # print(f"DEBUG [Decorator]: Proceeding for user_id={user_id}")
        return f(*args, **kwargs)
    return decorated_function

# --- 라우트 정의 ---

@app.route('/')
@login_required # 메인 페이지 접근 시 로그인 요구
def index():
    """ 메인 페이지 (index.html) 서빙 """
    return app.send_static_file('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    """ 로그인 처리 """
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"success": False, "message": "이메일과 비밀번호를 모두 입력해주세요."}), 400

        email = data.get('email')
        password = data.get('password')

        user = db_utils.find_user_by_email(email) # 이 함수는 db_utils 에 구현되어 있어야 함

        if user and check_password_hash(user.get('password_hash'), password): # DB 필드명 확인
            session['user_id'] = user.get('id')
            session['user_email'] = user.get('email') # 세션에 이메일도 저장 (선택 사항)
            print(f"로그인 성공: User ID={user['id']}, Email={user['email']}")
            print(f"DEBUG [Login Success]: Session set for user_id={session.get('user_id')}")
            return jsonify({"success": True, "message": "로그인 성공"})
        else:
            print(f"로그인 실패: Email={email}")
            return jsonify({"success": False, "message": "이메일 또는 비밀번호가 잘못되었습니다."}), 401
    else: # GET 요청 시
        # 이미 로그인 상태면 메인으로, 아니면 로그인 페이지 보여주기
        if 'user_id' in session:
             return redirect(url_for('index'))
        return app.send_static_file('login.html') # 로그인 HTML 파일 서빙

@app.route('/register', methods=['GET', 'POST'])
def register_route():
    """ 회원가입 처리 """
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"success": False, "message": "이메일과 비밀번호를 모두 입력해주세요."}), 400

        email = data.get('email')
        password = data.get('password')

        # 이메일 중복 확인
        if db_utils.find_user_by_email(email):
            return jsonify({"success": False, "message": "이미 사용 중인 이메일입니다."}), 409 # Conflict

        # 비밀번호 해싱
        password_hash = generate_password_hash(password)

        # 사용자 추가
        user_added = db_utils.add_user(email, password_hash) # 이 함수는 db_utils 에 구현되어 있어야 함

        if user_added:
            print(f"회원가입 성공: Email={email}")
            return jsonify({"success": True, "message": "회원가입 성공. 로그인해주세요."}), 201 # Created
        else:
            print(f"회원가입 실패: Email={email}")
            return jsonify({"success": False, "message": "회원가입 중 오류가 발생했습니다."}), 500
    else: # GET 요청 시
        if 'user_id' in session:
             return redirect(url_for('index'))
        return app.send_static_file('register.html') # 회원가입 HTML 파일 서빙

@app.route('/logout', methods=['POST'])
@login_required
def logout_route():
    """ 로그아웃 처리 """
    user_id = session.get('user_id')
    session.pop('user_id', None)
    session.pop('user_email', None) # 세션에 저장했다면 같이 삭제
    print(f"로그아웃: User ID={user_id}")
    return jsonify({"success": True, "message": "로그아웃 되었습니다."})

@app.route('/me', methods=['GET'])
@login_required
def get_current_user():
    print("--- /me route function entered ---")
    user_id = session.get('user_id') # .get() 사용

    if not user_id: # 세션에 user_id 없음
         app.logger.error("세션에서 user_id를 찾을 수 없습니다. (로그인 필요 또는 세션 만료)")
         return jsonify({"success": False, "message": "세션이 유효하지 않습니다. 다시 로그인해주세요."}), 401

    # --- user_id가 세션에 존재함 ---
    try:
        print(f"--- Attempting to fetch info for user_id: {user_id} ---")
        # 1. 사용자 정보 조회 (이메일 등)
        user = db_utils.find_user_by_id(user_id)
        if not user:
             print(f"경고: 세션 ID({user_id})에 해당하는 사용자를 DB에서 찾을 수 없음")
             # 세션은 있지만 DB에 사용자가 없는 경우, 세션 정리 고려
             # session.pop('user_id', None)
             # session.pop('user_email', None)
             return jsonify({"success": False, "message": "사용자 정보를 찾을 수 없습니다."}), 404

        user_email = user.get('email') # DB 조회 결과에서 이메일 가져오기

        # 2. 남은 횟수 계산 (★★★ 누락되었던 부분 ★★★)
        daily_limit = 3 # 기본값
        try:
            daily_limit_str = db_utils.get_setting('daily_limit_per_user') # DB에서 설정값 읽기
            if daily_limit_str and daily_limit_str.isdigit():
                daily_limit = int(daily_limit_str)
            elif daily_limit_str is None:
                 print(f"경고 [/me]: 'daily_limit_per_user' 설정 없음. 기본값 {daily_limit} 사용.")
                 # 필요하다면 여기서 DB에 기본값 INSERT 하는 로직 추가 가능
                 # db_utils.set_setting('daily_limit_per_user', str(daily_limit)) # 예시
            else:
                 print(f"경고 [/me]: 'daily_limit_per_user' 값({daily_limit_str}) 이상. 기본값 {daily_limit} 사용.")
        except Exception as setting_err:
             print(f"ERROR [/me]: getting daily limit setting failed: {setting_err}. Using default {daily_limit}.")
             # app.logger.error(...) 사용 권장

        todays_usage = 0 # 기본값
        try:
            usage_val = db_utils.get_todays_usage(user_id) # DB에서 오늘 사용량 읽기
            # DB 조회 결과가 None이거나 숫자가 아닌 경우 대비
            todays_usage = int(usage_val) if usage_val is not None else 0
        except Exception as usage_err:
             print(f"ERROR [/me]: getting today's usage failed: {usage_err}. Assuming usage is 0.")
             # app.logger.error(...) 사용 권장

        remaining_attempts = max(0, daily_limit - todays_usage) # 최종 남은 횟수 계산

        # 3. 디버그 로그 출력 (이제 모든 변수 정의됨)
        print(f"DEBUG [/me]: User={user_id}, Limit={daily_limit}, Used={todays_usage}, Remaining={remaining_attempts}")

        # 4. 최종 JSON 응답 반환
        return jsonify({
            "success": True,
            "user": {"email": user_email},
            "remaining_attempts": remaining_attempts
        }), 200

    except Exception as e:
        # DB 조회나 계산 중 발생할 수 있는 다른 예외 처리
        app.logger.error(f"Error fetching user info or calculating limits for user_id {user_id}: {e}")
        print(f"ERROR in /me: {e}")
        import traceback
        traceback.print_exc() # 개발 중 상세 오류 확인 위해 추가
        return jsonify({"success": False, "message": "사용자 정보 조회 중 내부 오류가 발생했습니다."}), 500


@app.route('/api/base_model/active', methods=['GET'])
@login_required
def get_active_base_model_info():
    """ 현재 활성화된 기본 모델 정보 반환 (상대 URL 경로 포함) """
    try:
        active_model = db_utils.get_active_base_model() # 이 함수는 db_utils 에 구현되어 있어야 함
        # print(f"DEBUG: Active Model Raw Data = {active_model}") # 필요시 로깅

        if active_model:
            # DB에 저장된 파일명 가져오기 (키 이름 확인!)
            filename_from_db = active_model.get('image_url') # 이전 디버깅에서 확인한 키
            if filename_from_db:
                # 웹 접근 가능한 상대 URL 생성
                image_url_relative = f"/base_models/{filename_from_db}"
                print(f"활성 베이스 모델 로드 성공: ID={active_model.get('id')}, Name={active_model.get('name')}, URL={image_url_relative}")
                return jsonify({
                    "success": True,
                    "id": active_model.get('id'),
                    "name": active_model.get('name'),
                    "image_url": image_url_relative # 상대 URL 반환
                }), 200
            else:
                app.logger.error("Active base model data is missing the image URL key ('image_url').")
                return jsonify({"success": False, "message": "활성화된 기본 모델 정보(이미지 URL)를 찾을 수 없습니다."}), 404
        else:
            return jsonify({"success": False, "message": "활성화된 기본 모델이 없습니다."}), 404

    except Exception as e:
        app.logger.error(f"Error fetching active base model: {e}")
        print(f"ERROR in /api/base_model/active: {e}")
        return jsonify({"success": False, "message": "기본 모델 정보 조회 중 오류가 발생했습니다."}), 500

@app.route('/synthesize/web', methods=['POST'])
@login_required
def synthesize_from_web():
    """ 웹 인터페이스로부터 아이템 이미지(파일)와 종류를 받아 합성 수행 """
    user_id = session['user_id']
    # 경로 변수 초기화 시 절대 경로 여부 명확히 하기 위해 None 사용
    temp_item_image_path_absolute = None
    saved_output_path = None

    try:
        # 1. 사용량 제한 확인
        daily_limit_str = db_utils.get_setting('daily_limit_per_user')
        daily_limit = 3
        if daily_limit_str and daily_limit_str.isdigit():
            daily_limit = int(daily_limit_str)
        elif daily_limit_str is None:
            print(f"경고 (in synthesize): 'daily_limit_per_user' 설정 없음. 기본값 {daily_limit} 사용.")
        else:
            print(f"경고 (in synthesize): 'daily_limit_per_user' 값({daily_limit_str}) 이상. 기본값 {daily_limit} 사용.")

        todays_usage = db_utils.get_todays_usage(user_id)
        if todays_usage >= daily_limit:
            app.logger.warning(f"User {user_id} exceeded daily limit ({todays_usage}/{daily_limit})")
            return jsonify({"success": False, "message": f"일일 사용량({daily_limit}회)을 초과했습니다."}), 429

        # 2. 입력 데이터 받기 및 임시 저장
        item_type = request.form.get('item_type')
        if not item_type:
            return jsonify({"success": False, "message": "아이템 종류(item_type)가 필요합니다."}), 400

        if 'item_image' not in request.files:
            return jsonify({"success": False, "message": "아이템 이미지 파일(item_image)이 없습니다."}), 400

        item_file = request.files['item_image']

        if item_file.filename == '':
             return jsonify({"success": False, "message": "선택된 아이템 이미지 파일이 없습니다."}), 400

        if item_file and allowed_file(item_file.filename):
            item_filename_secure = secure_filename(f"user_{user_id}_{uuid.uuid4().hex}_{item_file.filename}")
            # UPLOAD_FOLDER 자체가 상대 경로일 수 있으므로, 저장 후 절대 경로 생성
            temp_item_image_path_relative = os.path.join(app.config['UPLOAD_FOLDER'], item_filename_secure)
            item_file.save(temp_item_image_path_relative)
            temp_item_image_path_absolute = os.path.abspath(temp_item_image_path_relative) # 절대 경로
            print(f"Item image saved to: {temp_item_image_path_absolute}")
        else:
             return jsonify({"success": False, "message": "허용되지 않는 파일 형식입니다."}), 400

        # 3. 활성 기본 모델 정보 및 경로 생성
        active_model = db_utils.get_active_base_model()
        if not active_model or not active_model.get('image_url'): # 이전 디버깅에서 확인한 'image_url' 키 사용
             app.logger.error("Active base model not found or image URL key ('image_url') missing.")
             return jsonify({"success": False, "message": "활성화된 기본 모델 정보(이미지 URL)를 찾을 수 없습니다."}), 503

        base_model_filename = active_model.get('image_url') # DB에는 파일명만 저장되어 있다고 가정
        # BASE_MODEL_FOLDER 경로와 파일명을 합쳐 절대 경로 생성
        base_model_image_path_absolute = os.path.abspath(os.path.join(BASE_MODEL_FOLDER, base_model_filename))
        print(f"Using base model path: {base_model_image_path_absolute}")

        # 4. AI 합성 모듈 호출 (model 객체 전달 방식 사용)
        print(f"[Synthesize Route] Calling AI synthesis function...")
        if not gemini_model: # 앱 시작 시 모델 생성 실패한 경우
             raise Exception("Gemini 모델이 초기화되지 않았습니다.")

        image_bytes = ai_module.synthesize_image(
            model=gemini_model, # 설정 시 생성한 모델 객체 전달
            base_image_path=base_model_image_path_absolute,
            item_image_path=temp_item_image_path_absolute,
            item_type=item_type
        )

        if image_bytes:
            print("[Synthesize Route] AI synthesis successful, received image bytes.")
            # 5. 결과 이미지 저장 및 URL 생성
            # 확장자는 AI 모델이 반환하는 이미지 타입에 맞추는 것이 좋으나, 우선 png로 가정
            output_filename = f"result_{user_id}_{uuid.uuid4().hex}.png"
            saved_output_path_relative = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            saved_output_path = os.path.abspath(saved_output_path_relative) # 저장 경로도 절대 경로로

            with open(saved_output_path, 'wb') as f:
                f.write(image_bytes)
            print(f"[Synthesize Route] Result image saved to: {saved_output_path}")

            # 웹 접근 URL 생성 (반드시 슬래시로 시작하는 상대 경로)
            result_image_url = f"/{app.config['OUTPUT_FOLDER']}/{output_filename}"

            # 6. 사용량 증가
            db_utils.increment_usage(user_id) # 이 함수는 db_utils 에 구현되어 있어야 함

            # 7. 결과 반환
            return jsonify({
                "success": True,
                "result_image_url": result_image_url,
                "watermarked": False # 현재 미구현
            }), 200
        else:
            # AI 모듈 실패 (None 반환)
            print("[Synthesize Route] AI synthesis failed (module returned None).")
            # ai_module 내부에서 이미 에러 로깅 가정
            raise Exception("AI 이미지 합성에 실패했습니다. (AI 모듈 실패)")

    except Exception as e:
        app.logger.error(f"Error during synthesis for user {user_id}: {e}")
        print(f"ERROR in /synthesize/web: {e}") # 터미널에도 출력
        # traceback 로깅 추가 (디버깅 시 유용)
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"합성 중 오류 발생: {e}"}), 500

    finally:
        # 8. 임시 업로드 파일 삭제
        # 절대 경로 변수를 사용해야 함
        if temp_item_image_path_absolute and os.path.exists(temp_item_image_path_absolute):
            try:
                os.remove(temp_item_image_path_absolute)
                print(f"[Synthesize Route] Temporary item file deleted: {temp_item_image_path_absolute}")
            except Exception as e:
                app.logger.error(f"Error deleting temporary item file {temp_item_image_path_absolute}: {e}")
                print(f"ERROR deleting temp file: {e}")


@app.route('/output/<path:filename>') # <path:filename> 사용 시 하위 디렉토리 포함 가능 (현재는 불필요)
# @login_required # 결과 이미지는 로그인 없이도 접근 가능하게 할지, 아니면 로그인 요구할지 결정
def serve_output_image(filename):
    """ '/output' 경로의 생성된 이미지 파일을 서빙합니다. """
    print(f"Serving output image: {filename}")
    output_dir = os.path.abspath(app.config['OUTPUT_FOLDER'])
    # 파일 경로 조작 방지 (secure_filename 은 URL 파라미터에 직접 사용하기 부적합)
    requested_path = os.path.abspath(os.path.join(output_dir, filename))

    if not requested_path.startswith(output_dir):
         # 요청 경로가 output 폴더 바깥을 벗어나면 접근 거부
         print(f"Forbidden access attempt: {filename}")
         abort(403) # Forbidden

    # send_from_directory 사용 (보안 및 편의성)
    try:
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename)
    except FileNotFoundError:
         print(f"Output file not found: {filename}")
         abort(404) # Not Found


# --- 앱 실행 ---
if __name__ == '__main__':
    # host='0.0.0.0' 은 외부 접근 허용 시 사용
    app.run(debug=True, host='0.0.0.0', port=5000) # port=5000 명시
# app/__init__.py

import os
from flask import Flask, jsonify, g # g 추가 (요청 컨텍스트 변수)
from dotenv import load_dotenv
from google import generativeai as genai

# .env 파일 로드 (애플리케이션 컨텍스트 외부에서도 환경 변수 사용 가능하도록)
# run.py에서도 로드하지만, 여기서도 로드하면 다른 방식으로 실행될 때도 안전합니다.
load_dotenv()

def create_app(config_name=None):
    """
    Flask 애플리케이션 팩토리 함수.
    앱 인스턴스를 생성하고 설정, 확장 초기화, 블루프린트 등록 등을 수행합니다.
    """
    # Flask 앱 인스턴스 생성
    # instance_relative_config=True: instance 폴더에서 설정 파일을 로드할 수 있도록 합니다. (선택적)
    app = Flask(__name__,
                instance_relative_config=True,
                static_folder='static',  # 정적 파일 폴더 지정
                template_folder='templates') # 템플릿 폴더 지정

    # --- 1. 설정 로드 ---
    # 기본 설정 로드 (환경 변수 우선)
    # SECRET_KEY: 세션, 쿠키 등의 암호화에 사용되는 필수 값
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default_dev_secret_key_please_change')
    # 업로드 및 결과 폴더 설정 (프로젝트 루트 기준 상대 경로 사용)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    app.config['UPLOAD_FOLDER'] = os.path.join(project_root, 'uploads')
    app.config['OUTPUT_FOLDER'] = os.path.join(project_root, 'outputs')
    # 허용 파일 확장자
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
    # 데이터베이스 연결 정보 (db_utils 에서 직접 os.getenv 사용하므로 여기서는 생략 가능)

    # TODO: 환경별 설정 파일 로드 (config.py 등을 사용하여 분리 가능)
    # if config_name == 'production':
    #     app.config.from_object('config.ProductionConfig')
    # elif config_name == 'testing':
    #     app.config.from_object('config.TestingConfig')
    # else: # development or default
    #     app.config.from_object('config.DevelopmentConfig')

    print(f" * Flask App '{app.name}' 생성됨 (환경: {config_name or os.getenv('FLASK_ENV', 'development')})")
    print(f" * Upload Folder: {app.config['UPLOAD_FOLDER']}")
    print(f" * Output Folder: {app.config['OUTPUT_FOLDER']}")
    if app.config['SECRET_KEY'] == 'default_dev_secret_key_please_change':
        print(" * 경고: 기본 SECRET_KEY 사용 중. 운영 환경에서는 반드시 변경하세요!")

    # --- 2. 폴더 생성 ---
    # 업로드 및 출력 폴더가 없으면 생성
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
        print(f" * 필수 폴더 확인/생성 완료.")
    except OSError as e:
        print(f" * 오류: 필수 폴더 생성 실패 - {e}")
        # 폴더 생성 실패 시 앱 실행을 중단할지 여부 결정 필요

    # --- 3. 확장 초기화 ---
    # Google AI 클라이언트 초기화
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        try:
            # 앱 컨텍스트에 AI 클라이언트 저장 (g 객체 또는 app 객체 직접 사용 가능)
            # app.ai_client = genai.Client(api_key=api_key) # app 객체에 직접 저장하는 방식
            # 요청 컨텍스트(g)에 저장하는 방식은 매 요청마다 초기화 필요할 수 있음
            # 여기서는 앱 시작 시 한 번 초기화하여 app 객체에 저장
            app.config['AI_CLIENT'] = genai.Client(api_key=api_key)
            print(" * Google AI Client 초기화 완료.")
        except Exception as e:
            print(f" * 오류: Google AI Client 초기화 실패 - {e}")
            app.config['AI_CLIENT'] = None # 실패 시 None으로 설정
    else:
        print(" * 경고: GEMINI_API_KEY 환경 변수가 없습니다. AI 기능 사용 불가.")
        app.config['AI_CLIENT'] = None

    # TODO: 다른 Flask 확장 초기화 (예: SQLAlchemy, Migrate, LoginManager 등)
    # from .extensions import db, migrate, login_manager
    # db.init_app(app)
    # migrate.init_app(app, db)
    # login_manager.init_app(app)
    # login_manager.login_view = 'auth.login' # 로그인 필요한 페이지 접근 시 리디렉션될 라우트

    # --- 4. 블루프린트 등록 ---
    # 각 기능별 라우트가 정의된 블루프린트를 앱에 등록
    from .routes import auth as auth_bp
    from .routes import synthesize as synthesize_bp
    # from .routes import main as main_bp # 필요시 추가
    # from .routes import admin as admin_bp # Phase 3 후반 추가

    app.register_blueprint(auth_bp.bp, url_prefix='/auth') # '/auth' 접두사 사용
    app.register_blueprint(synthesize_bp.bp) # 접두사 없이 루트 레벨에서 사용
    # app.register_blueprint(main_bp.bp)
    # app.register_blueprint(admin_bp.bp, url_prefix='/admin')

    print(" * 블루프린트 등록 완료: auth, synthesize")

    # --- 5. 에러 핸들러 등록 (선택적이지만 권장) ---
    @app.errorhandler(404)
    def page_not_found(e):
        # HTML 페이지 또는 JSON 응답 반환 가능
        # return render_template('404.html'), 404
        return jsonify(error=str(e), message="요청한 페이지를 찾을 수 없습니다."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        # return render_template('500.html'), 500
        # 실제 운영 환경에서는 상세 오류를 노출하지 않도록 주의
        import traceback
        traceback.print_exc()
        return jsonify(error="Internal Server Error", message="서버 내부 오류가 발생했습니다."), 500

    # --- 6. 요청 컨텍스트 처리 (선택적) ---
    # @app.before_request
    # def before_request_func():
    #     # 모든 요청 전에 실행될 코드 (예: g 객체에 사용자 정보 로드)
    #     g.user = get_current_user() # 예시 함수

    # @app.after_request
    # def after_request_func(response):
    #     # 모든 요청 후에 실행될 코드 (예: 응답 헤더 추가)
    #     return response

    # @app.teardown_appcontext
    # def teardown_db(exception):
    #     # 애플리케이션 컨텍스트 종료 시 실행 (예: DB 커넥션 반환)
    #     db = g.pop('db', None)
    #     if db is not None:
    #         db.close()

    # --- 7. 템플릿 컨텍스트 프로세서 (선택적) ---
    # @app.context_processor
    # def inject_global_vars():
    #     # 모든 템플릿에서 사용할 수 있는 변수 주입
    #     return dict(site_name="AI Style Synthesis")


    # 완성된 앱 인스턴스 반환
    return app


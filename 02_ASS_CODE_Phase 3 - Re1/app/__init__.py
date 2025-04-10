# app/__init__.py

import os
from flask import Flask, jsonify, g
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime # datetime import 추가

# .env 파일 로드
load_dotenv()

def create_app(config_name=None):
    """
    Flask 애플리케이션 팩토리 함수.
    """
    app = Flask(__name__,
                instance_relative_config=True,
                static_folder='static',
                template_folder='templates')

    # --- 1. 설정 로드 ---
    # (이전 코드와 동일)
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default_dev_secret_key_please_change')
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    app.config['UPLOAD_FOLDER'] = os.path.join(project_root, 'uploads')
    app.config['OUTPUT_FOLDER'] = os.path.join(project_root, 'outputs')
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

    print(f" * Flask App '{app.name}' 생성됨 (환경: {config_name or os.getenv('FLASK_ENV', 'development')})")
    print(f" * Upload Folder: {app.config['UPLOAD_FOLDER']}")
    print(f" * Output Folder: {app.config['OUTPUT_FOLDER']}")
    if app.config['SECRET_KEY'] == 'default_dev_secret_key_please_change':
        print(" * 경고: 기본 SECRET_KEY 사용 중. 운영 환경에서는 반드시 변경하세요!")

    # --- 2. 폴더 생성 ---
    # (이전 코드와 동일)
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
        print(f" * 필수 폴더 확인/생성 완료.")
    except OSError as e:
        print(f" * 오류: 필수 폴더 생성 실패 - {e}")

    # --- 3. 확장 초기화 ---
    # (이전 코드와 동일)
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        try:
            genai.configure(api_key=api_key)
            print(" * Google AI SDK 설정 완료 (API Key 구성됨).")
            app.config['AI_SDK_CONFIGURED'] = True
        except Exception as e:
            print(f" * 오류: Google AI SDK 설정 실패 - {e}")
            app.config['AI_SDK_CONFIGURED'] = False
    else:
        print(" * 경고: GEMINI_API_KEY 환경 변수가 없습니다. AI 기능 사용 불가.")
        app.config['AI_SDK_CONFIGURED'] = False

    # --- 4. 블루프린트 등록 ---
    # (이전 코드와 동일)
    from .routes import auth as auth_bp
    from .routes import synthesize as synthesize_bp
    from .routes import admin as admin_bp

    app.register_blueprint(auth_bp.bp, url_prefix='/auth')
    app.register_blueprint(synthesize_bp.bp)
    app.register_blueprint(admin_bp.bp, url_prefix='/admin')

    print(" * 블루프린트 등록 완료: auth, synthesize, admin")

    # --- 5. 에러 핸들러 등록 ---
    # (이전 코드와 동일)
    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(error=str(e), message="이 페이지에 접근할 권한이 없습니다."), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return jsonify(error=str(e), message="요청한 페이지를 찾을 수 없습니다."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        import traceback
        traceback.print_exc()
        return jsonify(error="Internal Server Error", message="서버 내부 오류가 발생했습니다."), 500

    # --- 6. 요청 컨텍스트 처리 (선택적) ---
    # ...

    # --- 7. 템플릿 컨텍스트 프로세서 ---
    @app.context_processor
    def inject_global_vars():
        """모든 템플릿에서 사용할 수 있는 변수를 주입합니다."""
        return dict(
            current_year=datetime.utcnow().year # 현재 연도 주입
            # site_name="AI Style Synthesis" # 다른 전역 변수 추가 가능
        )
    print(" * 컨텍스트 프로세서 등록 완료: inject_global_vars")


    # 완성된 앱 인스턴스 반환
    return app

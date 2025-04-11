# run.py
# Flask 애플리케이션 실행 스크립트

# app 패키지로부터 애플리케이션 팩토리 함수 import
# (app/__init__.py 파일에 정의될 예정)
from app import create_app
import os
from dotenv import load_dotenv

# .env 파일 로드 (Flask 앱 생성 전에 환경 변수 로드)
load_dotenv()

# 애플리케이션 팩토리 호출하여 Flask 앱 인스턴스 생성
# create_app() 함수는 app/__init__.py 내부에 정의됩니다.
# 환경 설정 (예: 'development', 'production')을 인자로 전달할 수도 있습니다.
# os.getenv('FLASK_CONFIG') or 'default' 와 같은 방식으로 환경별 설정 로드 가능
app = create_app(os.getenv('FLASK_ENV') or 'development')

# 이 스크립트가 직접 실행될 때만 Flask 개발 서버 실행
if __name__ == '__main__':
    # app.run()을 사용하여 개발 서버 시작
    # debug=True: 개발 모드 활성화 (코드 변경 시 자동 재시작, 디버거 사용 가능)
    # host='0.0.0.0': 로컬 네트워크의 다른 기기에서 접근 가능하도록 설정 (기본값: '127.0.0.1')
    # port=5000: 사용할 포트 번호 (기본값: 5000)
    app.run(debug=True, host='0.0.0.0', port=5000)

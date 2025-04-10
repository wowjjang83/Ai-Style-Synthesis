# app/routes/synthesize.py
# 이미지 합성 관련 라우트 및 기능

import os
from flask import (
    Blueprint, request, jsonify, session, current_app,
    render_template, send_from_directory
)
from werkzeug.utils import secure_filename
from io import BytesIO
from PIL import Image

# 유틸리티 및 모듈 import
from app.utils.db_utils import (
    get_setting, get_active_base_model, get_todays_usage, increment_usage
)
from app.utils.ai_module import synthesize_image, apply_watermark_func
# 인증 데코레이터 import
from app.routes.auth import login_required

# 'synthesize' 이름으로 Blueprint 객체 생성
bp = Blueprint('synthesize', __name__)

# --- 유틸리티 함수 ---
def allowed_file(filename):
    """허용된 이미지 파일 확장자인지 확인합니다."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# --- Routes ---

@bp.route('/')
@login_required # 메인 페이지 접근 시 로그인 필요
def index():
    """
    메인 이미지 합성 페이지를 렌더링합니다.
    """
    # TODO: 페이지 로드 시 필요한 초기 데이터 전달 (예: 사용자 정보, 남은 횟수)
    user_email = session.get('user_email', 'Unknown')
    user_id = session.get('user_id')
    remaining_attempts = 0
    daily_limit = 3 # 기본값 또는 설정값

    if user_id:
        try:
            limit_str = get_setting('max_user_syntheses')
            daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3
            current_usage = get_todays_usage(user_id)
            remaining_attempts = max(0, daily_limit - current_usage)
        except Exception as e:
            print(f"[Route /] 사용량 조회 중 오류: {e}")
            # 오류 발생 시 기본값 사용 또는 에러 처리

    # 활성 베이스 모델 정보 가져오기 (이미지 URL 등)
    active_model = get_active_base_model()
    base_model_image_url = active_model.get('image_url', 'https://placehold.co/512x512/cccccc/666666?text=No+Active+Model') if active_model else 'https://placehold.co/512x512/cccccc/666666?text=No+Active+Model'

    # web.html 템플릿 렌더링 시 필요한 데이터 전달
    return render_template(
        'synthesize/web.html',
        user_email=user_email,
        remaining_attempts=remaining_attempts,
        base_model_image_url=base_model_image_url
    )

@bp.route('/synthesize/web', methods=['POST'])
@login_required # 이미지 합성은 로그인 필수
def synthesize_web_route():
    """
    웹 인터페이스로부터 아이템 이미지와 종류를 받아 AI 합성을 수행하는 라우트.
    파일 업로드 형태로 처리합니다.
    """
    user_id = session['user_id'] # 데코레이터 통과했으므로 user_id 존재 보장
    print(f"[Route /synthesize/web] 요청 사용자 ID: {user_id}")

    # --- 0. AI 클라이언트 확인 ---
    ai_client = current_app.config.get('AI_CLIENT')
    if not ai_client:
        print("[Route /synthesize/web] 오류: AI Client가 초기화되지 않았습니다.")
        return jsonify({"error": "AI 서비스를 사용할 수 없습니다. 관리자에게 문의하세요."}), 503 # Service Unavailable

    # --- 1. 사용량 제한 확인 ---
    try:
        limit_str = get_setting('max_user_syntheses')
        daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3
        current_usage = get_todays_usage(user_id)
        print(f"[Route /synthesize/web] 사용량 확인: User ID={user_id}, 현재={current_usage}, 제한={daily_limit}")
        if current_usage >= daily_limit:
            return jsonify({"error": f"일일 최대 합성 횟수({daily_limit}회)를 초과했습니다."}), 429 # Too Many Requests
    except Exception as e:
         print(f"[Route /synthesize/web] 사용량 확인 중 오류: {e}")
         # DB 오류 시에도 요청 처리 중단
         return jsonify({"error": "사용량 확인 중 오류가 발생했습니다."}), 500

    # --- 2. 활성 베이스 모델 확인 ---
    active_model = get_active_base_model()
    if not active_model or not active_model.get("image_url"):
        print("[Route /synthesize/web] 오류: 활성 베이스 모델을 찾을 수 없습니다.")
        return jsonify({"error": "현재 사용 가능한 베이스 모델이 없습니다."}), 500
    # 베이스 모델 이미지 경로 또는 URL
    # TODO: image_url이 로컬 경로인지 웹 URL인지 구분 처리 필요
    # 현재는 로컬 파일 시스템 경로라고 가정
    base_img_path = active_model["image_url"]
    # 만약 URL이라면 다운로드 받아서 사용해야 함
    # if base_img_path.startswith('http'):
    #    # URL에서 이미지 다운로드 로직 추가
    #    pass
    # elif not os.path.isabs(base_img_path):
    #     # 상대 경로인 경우 절대 경로로 변환 (예: 프로젝트 루트 기준)
    #     base_img_path = os.path.join(current_app.root_path, '..', base_img_path) # 예시 경로

    # 임시: 베이스 모델 경로가 실제 파일인지 확인 (로컬 경로 가정 시)
    if not os.path.exists(base_img_path):
         print(f"[Route /synthesize/web] 오류: 베이스 모델 이미지 파일 접근 불가 - {base_img_path}")
         return jsonify({"error": "베이스 모델 이미지 파일을 찾을 수 없습니다."}), 500

    # --- 3. 입력 데이터 (아이템 이미지, 종류) 처리 ---
    if 'item_image' not in request.files:
        return jsonify({"error": "요청에 'item_image' 파일이 포함되지 않았습니다."}), 400
    if 'item_type' not in request.form:
        return jsonify({"error": "요청에 'item_type' 데이터가 포함되지 않았습니다."}), 400

    item_file = request.files['item_image']
    item_type = request.form['item_type']

    if item_file.filename == '':
        return jsonify({"error": "아이템 이미지가 선택되지 않았습니다."}), 400
    if not allowed_file(item_file.filename):
        return jsonify({"error": "허용되지 않는 파일 형식입니다 (PNG, JPG, JPEG만 가능)."}), 400

    # 파일 이름 안전하게 처리 및 저장 경로 설정
    item_filename = secure_filename(f"user{user_id}_{item_type}_{item_file.filename}")
    item_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], item_filename)

    try:
        # 업로드된 아이템 이미지 임시 저장
        item_file.save(item_filepath)
        print(f"[Route /synthesize/web] 아이템 이미지 저장 완료: {item_filepath}")
    except Exception as e:
        print(f"[Route /synthesize/web] 아이템 이미지 저장 중 오류: {e}")
        return jsonify({"error": "아이템 이미지 저장에 실패했습니다."}), 500

    # --- 4. AI 합성 호출 ---
    print(f"[Route /synthesize/web] AI 합성 호출 시작 (Base: {os.path.basename(base_img_path)}, Item: {item_filename})...")
    result_image_bytes = synthesize_image(ai_client, base_img_path, item_filepath, item_type)

    # --- 5. 결과 처리 (워터마크 적용 및 저장) ---
    if result_image_bytes:
        print("[Route /synthesize/web] AI 합성 성공 (결과 바이트 수신).")
        final_image_bytes = result_image_bytes # 최종 이미지 바이트 변수

        # --- 워터마크 적용 로직 ---
        try:
            apply_wm_setting = get_setting('apply_watermark')
            # 설정값이 'true' (대소문자 무관)일 때만 적용
            apply_wm = apply_wm_setting.lower() == 'true' if isinstance(apply_wm_setting, str) else False
            print(f"[Route /synthesize/web] 워터마크 적용 설정: {apply_wm}")

            if apply_wm:
                # 워터마크 이미지 경로 설정 (app/static/images/ 폴더에 있다고 가정)
                watermark_path = os.path.join(current_app.static_folder, 'images', 'watermark.png')
                print(f"[Route /synthesize/web] 워터마크 적용 시도 (Path: {watermark_path})")
                watermarked_bytes = apply_watermark_func(result_image_bytes, watermark_path)
                if watermarked_bytes and watermarked_bytes != result_image_bytes: # 성공 및 변경 확인
                    final_image_bytes = watermarked_bytes # 성공 시 워터마크 적용된 바이트 사용
                    print("[Route /synthesize/web] 워터마크 적용 성공.")
                else:
                    print("[Route /synthesize/web] 경고: 워터마크 적용 실패 또는 변경 없음, 원본 이미지 사용.")
        except Exception as wm_e:
            print(f"[Route /synthesize/web] 워터마크 처리 중 오류 발생: {wm_e}")
            # 워터마크 오류 시에도 원본 결과는 저장되도록 진행
        # --- 워터마크 적용 로직 끝 ---

        # --- 사용량 증가 (DB 업데이트) ---
        if not increment_usage(user_id):
            # 사용량 증가 실패는 치명적 오류는 아니므로 경고만 로깅
            print(f"[Route /synthesize/web] 경고: 사용량 증가 실패 (User ID: {user_id})")

        # --- 최종 결과 이미지 저장 ---
        try:
            # 출력 파일 이름 생성 (고유성 및 정보 포함)
            output_filename_base = f"output_{user_id}_{item_type}_{os.path.splitext(secure_filename(item_file.filename))[0]}"
            output_filename = f"{output_filename_base}.png" # 저장 형식을 PNG로 고정 (워터마크 투명도 유지)
            output_filepath = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)

            # 최종 이미지 바이트(원본 또는 워터마크)를 파일로 저장
            img = Image.open(BytesIO(final_image_bytes))
            img.save(output_filepath, format='PNG') # PNG로 저장
            print(f"[Route /synthesize/web] 최종 결과 이미지 저장 완료: {output_filepath}")

            # 클라이언트에게 결과 이미지 접근 URL 반환
            # '/outputs/<filename>' 라우트를 통해 접근 가능하도록 URL 생성
            output_url = f"/outputs/{output_filename}" # url_for 사용 가능: url_for('synthesize.serve_output_file', filename=output_filename)

            # 임시 업로드 파일 삭제 (선택적)
            try:
                os.remove(item_filepath)
                print(f"[Route /synthesize/web] 임시 업로드 파일 삭제: {item_filepath}")
            except OSError as e:
                 print(f"[Route /synthesize/web] 경고: 임시 업로드 파일 삭제 실패 - {e}")


            return jsonify({
                "message": "이미지 합성에 성공했습니다!",
                "output_file_url": output_url, # 클라이언트가 이미지를 표시할 URL
                "watermarked": apply_wm # 워터마크 적용 여부 정보 전달
                })
        except Exception as e:
            print(f"[Route /synthesize/web] 결과 이미지 저장 중 오류: {e}")
            # 합성은 성공했지만 저장 실패
            return jsonify({"error": "합성 결과 저장 중 오류가 발생했습니다."}), 500
    else:
        # AI 합성 자체가 실패한 경우
        print("[Route /synthesize/web] AI 합성 실패 (ai_module 반환값 없음).")
        # 임시 업로드 파일 삭제 (선택적)
        try:
            os.remove(item_filepath)
            print(f"[Route /synthesize/web] AI 실패 후 임시 업로드 파일 삭제: {item_filepath}")
        except OSError as e:
            print(f"[Route /synthesize/web] 경고: AI 실패 후 임시 업로드 파일 삭제 실패 - {e}")

        return jsonify({"error": "AI 이미지 합성에 실패했습니다."}), 500


@bp.route('/outputs/<path:filename>')
def serve_output_file(filename):
    """
    '/outputs' 폴더에 저장된 생성 결과 이미지를 클라이언트에게 제공하는 라우트.
    """
    print(f"[Route /outputs] 요청 파일: {filename}")
    try:
        return send_from_directory(
            current_app.config['OUTPUT_FOLDER'],
            filename,
            as_attachment=False # 브라우저에서 바로 표시되도록 설정
        )
    except FileNotFoundError:
         print(f"[Route /outputs] 오류: 파일을 찾을 수 없음 - {filename}")
         # from flask import abort
         # abort(404)
         return jsonify({"error": "요청한 파일을 찾을 수 없습니다."}), 404

# TODO: 베이스 모델 변경, 설정값 조회 등의 API 엔드포인트 추가 가능

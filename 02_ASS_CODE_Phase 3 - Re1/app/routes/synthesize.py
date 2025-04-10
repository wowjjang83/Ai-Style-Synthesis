# app/routes/synthesize.py
# 이미지 합성 관련 라우트 및 기능

import os
from flask import (
    Blueprint, request, jsonify, session, current_app,
    render_template, send_from_directory, flash # flash 추가
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
    # current_app 컨텍스트 내에서 config 접근
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# --- Routes ---

@bp.route('/')
@login_required # 메인 페이지 접근 시 로그인 필요
def index():
    """
    메인 이미지 합성 페이지를 렌더링합니다.
    페이지 로드 시 필요한 사용자 정보, 남은 횟수, 기본 모델 정보를 전달합니다.
    """
    user_email = session.get('user_email', 'Unknown')
    user_id = session.get('user_id') # 데코레이터 통과로 user_id는 항상 존재
    remaining_attempts = 0
    daily_limit = 3 # 기본값
    base_model_image_url = 'https://placehold.co/512x512/cccccc/666666?text=No+Active+Model' # 기본값

    print(f"[Route /] 페이지 로드 요청: User ID={user_id}, Email={user_email}")

    # DB에서 남은 횟수 계산
    try:
        limit_str = get_setting('max_user_syntheses')
        daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3
        current_usage = get_todays_usage(user_id)
        remaining_attempts = max(0, daily_limit - current_usage)
        print(f"[Route /] 사용량 정보: Limit={daily_limit}, Current={current_usage}, Remaining={remaining_attempts}")
    except Exception as e:
        print(f"[Route /] 오류: 사용량 조회 중 오류 발생 - {e}")
        flash("사용자 정보를 불러오는 중 오류가 발생했습니다.", "error")
        # 오류 발생 시 기본값(remaining_attempts=0) 사용

    # DB에서 활성 베이스 모델 정보 가져오기
    try:
        active_model = get_active_base_model()
        if active_model and active_model.get("image_url"):
            base_model_image_url = active_model["image_url"]
             # TODO: URL인지 로컬 경로인지 확인 및 처리 필요
             # 만약 로컬 경로이고, static 폴더 외부에 있다면 직접 서빙 불가
             # -> '/models/images/<model_id>' 같은 라우트 추가 고려 필요
             # 임시: URL이라고 가정하거나, 접근 가능한 경로라고 가정
            print(f"[Route /] 활성 모델 로드: ID={active_model.get('id')}, URL={base_model_image_url}")
        else:
            print("[Route /] 경고: 활성 베이스 모델을 찾을 수 없습니다.")
            flash("현재 설정된 기본 모델이 없습니다. 관리자에게 문의하세요.", "warning")
    except Exception as e:
        print(f"[Route /] 오류: 활성 베이스 모델 조회 중 오류 발생 - {e}")
        flash("기본 모델 정보를 불러오는 중 오류가 발생했습니다.", "error")
        # 오류 발생 시 기본 이미지 URL 사용

    # web.html 템플릿 렌더링 시 필요한 데이터 전달
    return render_template(
        'synthesize/web.html',
        user_email=user_email,
        remaining_attempts=remaining_attempts,
        base_model_image_url=base_model_image_url
    )

# --- /synthesize/web 라우트 (이전 코드 유지) ---
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
    base_img_path = active_model["image_url"]
    # TODO: URL/로컬 경로 처리 및 접근성 확인 강화 필요
    if not base_img_path.startswith('http') and not os.path.exists(base_img_path):
         # 임시: 로컬 파일 경로인데 존재하지 않는 경우
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
    # allowed_file 함수 호출 시 current_app 컨텍스트 필요
    with current_app.app_context():
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
            apply_wm = apply_wm_setting.lower() == 'true' if isinstance(apply_wm_setting, str) else False
            print(f"[Route /synthesize/web] 워터마크 적용 설정: {apply_wm}")

            if apply_wm:
                watermark_path = os.path.join(current_app.static_folder, 'images', 'watermark.png')
                print(f"[Route /synthesize/web] 워터마크 적용 시도 (Path: {watermark_path})")
                watermarked_bytes = apply_watermark_func(result_image_bytes, watermark_path)
                if watermarked_bytes and watermarked_bytes != result_image_bytes:
                    final_image_bytes = watermarked_bytes
                    print("[Route /synthesize/web] 워터마크 적용 성공.")
                else:
                    print("[Route /synthesize/web] 경고: 워터마크 적용 실패 또는 변경 없음, 원본 이미지 사용.")
        except Exception as wm_e:
            print(f"[Route /synthesize/web] 워터마크 처리 중 오류 발생: {wm_e}")
        # --- 워터마크 적용 로직 끝 ---

        # --- 사용량 증가 (DB 업데이트) ---
        if not increment_usage(user_id):
            print(f"[Route /synthesize/web] 경고: 사용량 증가 실패 (User ID: {user_id})")

        # --- 최종 결과 이미지 저장 ---
        try:
            output_filename_base = f"output_{user_id}_{item_type}_{os.path.splitext(secure_filename(item_file.filename))[0]}"
            output_filename = f"{output_filename_base}.png"
            output_filepath = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)

            img = Image.open(BytesIO(final_image_bytes))
            img.save(output_filepath, format='PNG')
            print(f"[Route /synthesize/web] 최종 결과 이미지 저장 완료: {output_filepath}")

            output_url = f"/outputs/{output_filename}"

            # 임시 업로드 파일 삭제
            try:
                os.remove(item_filepath)
                print(f"[Route /synthesize/web] 임시 업로드 파일 삭제: {item_filepath}")
            except OSError as e:
                 print(f"[Route /synthesize/web] 경고: 임시 업로드 파일 삭제 실패 - {e}")

            # 남은 횟수 다시 계산하여 반환 (선택적)
            new_remaining = max(0, daily_limit - (current_usage + 1))

            return jsonify({
                "message": "이미지 합성에 성공했습니다!",
                "output_file_url": output_url,
                "watermarked": apply_wm,
                "remaining_attempts": new_remaining # 업데이트된 남은 횟수 전달
                })
        except Exception as e:
            print(f"[Route /synthesize/web] 결과 이미지 저장 중 오류: {e}")
            return jsonify({"error": "합성 결과 저장 중 오류가 발생했습니다."}), 500
    else:
        # AI 합성 자체가 실패한 경우
        print("[Route /synthesize/web] AI 합성 실패 (ai_module 반환값 없음).")
        # 임시 업로드 파일 삭제
        try:
            os.remove(item_filepath)
            print(f"[Route /synthesize/web] AI 실패 후 임시 업로드 파일 삭제: {item_filepath}")
        except OSError as e:
            print(f"[Route /synthesize/web] 경고: AI 실패 후 임시 업로드 파일 삭제 실패 - {e}")

        return jsonify({"error": "AI 이미지 합성에 실패했습니다."}), 500


# --- /outputs/<filename> 라우트 (이전 코드 유지) ---
@bp.route('/outputs/<path:filename>')
def serve_output_file(filename):
    """
    '/outputs' 폴더에 저장된 생성 결과 이미지를 클라이언트에게 제공하는 라우트.
    """
    print(f"[Route /outputs] 요청 파일: {filename}")
    output_dir = current_app.config['OUTPUT_FOLDER']
    # 보안: 파일 이름 및 경로 검증 추가 고려 (예: '..' 포함 여부 등)
    safe_path = os.path.abspath(os.path.join(output_dir, filename))
    if not safe_path.startswith(os.path.abspath(output_dir)):
        print(f"[Route /outputs] 오류: 잘못된 경로 접근 시도 - {filename}")
        return jsonify({"error": "잘못된 파일 경로입니다."}), 400

    try:
        return send_from_directory(
            output_dir,
            filename,
            as_attachment=False # 브라우저에서 바로 표시
        )
    except FileNotFoundError:
         print(f"[Route /outputs] 오류: 파일을 찾을 수 없음 - {filename}")
         return jsonify({"error": "요청한 파일을 찾을 수 없습니다."}), 404


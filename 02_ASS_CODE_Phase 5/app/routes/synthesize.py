# app/routes/synthesize.py
# 이미지 합성 관련 라우트 및 기능

import os
from flask import (
    Blueprint, request, jsonify, session, current_app,
    render_template, send_from_directory, flash, url_for # url_for 추가
)
from werkzeug.utils import secure_filename
from io import BytesIO
from PIL import Image
import traceback # 상세 오류 로깅용

# 유틸리티 및 모듈 import
from app.utils.db_utils import (
    get_setting, get_active_base_model, get_todays_usage, increment_usage
)
# 수정: synthesize_image 함수는 이제 client 인자를 받음
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

    # DB에서 활성 베이스 모델 정보 가져오기
    try:
        active_model = get_active_base_model()
        if active_model and active_model.get("image_url"):
            base_model_image_url = active_model["image_url"]
            if not base_model_image_url.startswith('/static/') and not base_model_image_url.startswith('http'):
                 print(f"[Route /] 경고: 베이스 모델 image_url ('{base_model_image_url}')이 예상된 형식이 아닙니다.")
            print(f"[Route /] 활성 모델 로드: ID={active_model.get('id')}, URL={base_model_image_url}")
        else:
            print("[Route /] 경고: 활성 베이스 모델을 찾을 수 없습니다.")
            flash("현재 설정된 기본 모델이 없습니다. 관리자에게 문의하세요.", "warning")
    except Exception as e:
        print(f"[Route /] 오류: 활성 베이스 모델 조회 중 오류 발생 - {e}")
        flash("기본 모델 정보를 불러오는 중 오류가 발생했습니다.", "error")

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
    """
    user_id = session['user_id']
    print(f"[Route /synthesize/web] 요청 사용자 ID: {user_id}")

    # --- 0. AI 클라이언트 확인 ---
    # 수정: app.config 에서 AI_CLIENT 가져오기
    ai_client = current_app.config.get('AI_CLIENT')
    # 수정: AI_CLIENT 객체 존재 여부 확인
    if not ai_client:
        print("[Route /synthesize/web] 오류: AI Client가 초기화되지 않았습니다 (app.config['AI_CLIENT'] 없음).")
        return jsonify({"error": "AI 서비스가 설정되지 않았거나 초기화에 실패했습니다. 관리자에게 문의하세요."}), 503

    # --- 1. 사용량 제한 확인 ---
    try:
        limit_str = get_setting('max_user_syntheses')
        daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3
        current_usage = get_todays_usage(user_id)
        print(f"[Route /synthesize/web] 사용량 확인: User ID={user_id}, 현재={current_usage}, 제한={daily_limit}")
        if current_usage >= daily_limit:
            return jsonify({"error": f"일일 최대 합성 횟수({daily_limit}회)를 초과했습니다."}), 429
    except Exception as e:
         print(f"[Route /synthesize/web] 사용량 확인 중 오류: {e}")
         return jsonify({"error": "사용량 확인 중 오류가 발생했습니다."}), 500

    # --- 2. 활성 베이스 모델 확인 및 경로 처리 ---
    # (이전 수정과 동일)
    active_model = get_active_base_model()
    if not active_model or not active_model.get("image_url"):
        print("[Route /synthesize/web] 오류: 활성 베이스 모델을 찾을 수 없습니다.")
        return jsonify({"error": "현재 사용 가능한 베이스 모델이 없습니다."}), 500

    base_img_url_path = active_model["image_url"]
    base_img_fs_path = None
    if base_img_url_path.startswith('/static/'):
        relative_path = os.path.normpath(base_img_url_path[len('/static/'):])
        base_img_fs_path = os.path.join(current_app.static_folder, relative_path)
        print(f"[Route /synthesize/web] 베이스 모델 URL 경로 '{base_img_url_path}' -> 파일 시스템 경로 '{base_img_fs_path}' 변환 시도")
    elif base_img_url_path.startswith('http'):
        print(f"[Route /synthesize/web] 오류: 웹 URL 베이스 모델은 아직 지원되지 않습니다 - {base_img_url_path}")
        return jsonify({"error": "웹 URL 형태의 베이스 모델은 현재 지원되지 않습니다."}), 501
    else:
        base_img_fs_path = base_img_url_path
        print(f"[Route /synthesize/web] 베이스 모델 경로가 URL 형태가 아님, 파일 시스템 경로로 간주: {base_img_fs_path}")

    if not base_img_fs_path or not os.path.exists(base_img_fs_path) or not os.path.isfile(base_img_fs_path):
         print(f"[Route /synthesize/web] 오류: 베이스 모델 이미지 파일 접근 불가 - 경로: {base_img_fs_path} (원본 URL: {base_img_url_path})")
         return jsonify({"error": "베이스 모델 이미지 파일을 찾거나 접근할 수 없습니다."}), 500
    else:
         print(f"[Route /synthesize/web] 베이스 모델 파일 시스템 경로 확인: {base_img_fs_path}")


    # --- 3. 입력 데이터 처리 ---
    # (이전 코드와 동일)
    if 'item_image' not in request.files:
        return jsonify({"error": "요청에 'item_image' 파일이 포함되지 않았습니다."}), 400
    if 'item_type' not in request.form:
        return jsonify({"error": "요청에 'item_type' 데이터가 포함되지 않았습니다."}), 400

    item_file = request.files['item_image']
    item_type = request.form['item_type']

    if item_file.filename == '':
        return jsonify({"error": "아이템 이미지가 선택되지 않았습니다."}), 400
    if not allowed_file(item_file.filename): # allowed_file 은 current_app 컨텍스트 불필요
        return jsonify({"error": "허용되지 않는 파일 형식입니다 (PNG, JPG, JPEG만 가능)."}), 400

    temp_filename = secure_filename(f"user{user_id}_{item_type}_{item_file.filename}")
    item_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_filename)

    try:
        item_file.save(item_filepath)
        print(f"[Route /synthesize/web] 아이템 이미지 저장 완료: {item_filepath}")
    except Exception as e:
        print(f"[Route /synthesize/web] 아이템 이미지 저장 중 오류: {e}")
        return jsonify({"error": "아이템 이미지 저장에 실패했습니다."}), 500

    # --- 4. AI 합성 및 결과 처리 ---
    result_image_bytes = None
    final_response = None
    try:
        # 수정: ai_client 객체를 synthesize_image 함수에 전달
        print(f"[Route /synthesize/web] AI 합성 호출 시작 (Base FS Path: {base_img_fs_path}, Item Path: {item_filepath})...")
        result_image_bytes = synthesize_image(ai_client, base_img_fs_path, item_filepath, item_type)

        # 결과 처리
        if result_image_bytes:
            print("[Route /synthesize/web] AI 합성 성공 (결과 바이트 수신).")
            final_image_bytes = result_image_bytes
            apply_wm = False

            # 워터마크 적용 로직 ...
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

            # 사용량 증가 ...
            usage_incremented = increment_usage(user_id)
            if not usage_incremented:
                print(f"[Route /synthesize/web] 경고: 사용량 증가 실패 (User ID: {user_id})")

            # 최종 결과 이미지 저장 ...
            try:
                output_filename_base = f"output_{user_id}_{item_type}_{os.path.splitext(secure_filename(item_file.filename))[0]}"
                output_filename = f"{output_filename_base}.png"
                output_filepath = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)
                img = Image.open(BytesIO(final_image_bytes))
                img.save(output_filepath, format='PNG')
                print(f"[Route /synthesize/web] 최종 결과 이미지 저장 완료: {output_filepath}")
                output_url = url_for('synthesize.serve_output_file', filename=output_filename, _external=False)

                # 남은 횟수 다시 계산 ...
                current_usage_after = get_todays_usage(user_id)
                new_remaining = max(0, daily_limit - current_usage_after)

                # 성공 응답 설정
                final_response = jsonify({
                    "message": "이미지 합성에 성공했습니다!",
                    "output_file_url": output_url,
                    "watermarked": apply_wm,
                    "remaining_attempts": new_remaining
                    })

            except Exception as e:
                print(f"[Route /synthesize/web] 결과 이미지 저장 중 오류: {e}")
                traceback.print_exc()
                final_response = jsonify({"error": "합성 결과 저장 중 오류가 발생했습니다."}), 500
        else:
            # AI 합성 자체가 실패한 경우
            print("[Route /synthesize/web] AI 합성 실패 (ai_module 반환값 없음).")
            final_response = jsonify({"error": "AI 이미지 합성에 실패했습니다."}), 500

    except Exception as e:
        # synthesize_image 호출 등에서 예외 발생 시
        print(f"[Route /synthesize/web] AI 합성 또는 후처리 중 예외 발생: {e}")
        traceback.print_exc()
        final_response = jsonify({"error": "이미지 합성 처리 중 오류가 발생했습니다."}), 500
    finally:
        # --- 임시 업로드 파일 삭제 ---
        if os.path.exists(item_filepath):
            try:
                os.remove(item_filepath)
                print(f"[Route /synthesize/web] 임시 업로드 파일 삭제 완료: {item_filepath}")
            except OSError as e:
                print(f"[Route /synthesize/web] 경고: 임시 업로드 파일 삭제 실패 - {e}")
        else:
             print(f"[Route /synthesize/web] 정보: 삭제할 임시 업로드 파일 없음 또는 이미 삭제됨 - {item_filepath}")

    # 최종 응답 반환
    return final_response if final_response else (jsonify({"error": "알 수 없는 서버 오류."}), 500)


# --- /outputs/<filename> 라우트 ---
@bp.route('/outputs/<path:filename>')
def serve_output_file(filename):
    """
    '/outputs' 폴더에 저장된 생성 결과 이미지를 클라이언트에게 제공하는 라우트.
    """
    print(f"[Route /outputs] 요청 파일: {filename}")
    output_dir = current_app.config['OUTPUT_FOLDER']
    safe_filename = secure_filename(filename)
    if safe_filename != filename:
         print(f"[Route /outputs] 경고: 파일 이름이 안전하게 변경됨 ('{filename}' -> '{safe_filename}')")

    safe_path = os.path.abspath(os.path.join(output_dir, safe_filename))
    if not safe_path.startswith(os.path.abspath(output_dir)):
        print(f"[Route /outputs] 오류: 잘못된 경로 접근 시도 - {safe_filename}")
        return jsonify({"error": "잘못된 파일 경로입니다."}), 400

    try:
        return send_from_directory(
            output_dir,
            safe_filename,
            as_attachment=False
        )
    except FileNotFoundError:
         print(f"[Route /outputs] 오류: 파일을 찾을 수 없음 - {safe_filename}")
         return jsonify({"error": "요청한 파일을 찾을 수 없습니다."}), 404


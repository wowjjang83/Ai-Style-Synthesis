# app/routes/synthesize.py
# 이미지 합성 관련 라우트 및 기능

import os
import requests # requests 라이브러리 import
import tempfile # 임시 파일 생성을 위해 import
from flask import (
    Blueprint, request, jsonify, session, current_app,
    render_template, send_from_directory, flash, url_for
)
from werkzeug.utils import secure_filename
from io import BytesIO
from PIL import Image
import traceback

# 유틸리티 및 모듈 import
from app.utils.db_utils import (
    get_setting, get_active_base_model, get_todays_usage, increment_usage
)

# 수정: synthesize_multi_items_single_call 함수 import 추가
from app.utils.ai_module import (
    synthesize_image, # 단일 합성 (현재 사용 안함)
    synthesize_multi_items_single_call, # 다중 합성 함수
    apply_watermark_func
)

from app.routes.auth import login_required

bp = Blueprint('synthesize', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@bp.route('/')
@login_required
def index():
    # ... (기존 index 함수 코드와 동일) ...
    user_email = session.get('user_email', 'Unknown')
    user_id = session.get('user_id')
    remaining_attempts = 0
    daily_limit = 3
    base_model_image_url = 'https://placehold.co/512x512/cccccc/666666?text=No+Active+Model'
    print(f"[Route /] 페이지 로드 요청: User ID={user_id}, Email={user_email}")
    try:
        limit_str = get_setting('max_user_syntheses')
        daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3
        current_usage = get_todays_usage(user_id)
        remaining_attempts = max(0, daily_limit - current_usage)
        print(f"[Route /] 사용량 정보: Limit={daily_limit}, Current={current_usage}, Remaining={remaining_attempts}")
    except Exception as e:
        print(f"[Route /] 오류: 사용량 조회 중 오류 발생 - {e}")
        flash("사용자 정보를 불러오는 중 오류가 발생했습니다.", "error")
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
    return render_template(
        'synthesize/web.html',
        user_email=user_email,
        remaining_attempts=remaining_attempts,
        base_model_image_url=base_model_image_url
    )

@bp.route('/synthesize/web', methods=['POST'])
@login_required
def synthesize_web_route():
    user_id = session['user_id']
    print(f"[Route /synthesize/web Multi-SingleCall] 요청 사용자 ID: {user_id}")

    ai_client = current_app.config.get('AI_CLIENT')
    if not ai_client:
        return jsonify({"error": "AI 서비스가 설정되지 않았거나 초기화에 실패했습니다."}), 503

    # --- 1. 사용량 제한 확인 (동일) ---
    try:
        limit_str = get_setting('max_user_syntheses'); daily_limit = int(limit_str) if limit_str and limit_str.isdigit() else 3
        current_usage = get_todays_usage(user_id)
        if current_usage >= daily_limit:
            return jsonify({"error": f"일일 최대 합성 횟수({daily_limit}회)를 초과했습니다."}), 429
    except Exception as e:
         return jsonify({"error": "사용량 확인 중 오류가 발생했습니다."}), 500

    # --- 임시 파일 관리 ---
    temp_files_to_delete = []
    base_img_fs_path = None
    result_image_bytes = None
    final_response = None

    try:
        # --- 2. 활성 베이스 모델 확인 및 경로 처리 (동일) ---
        active_model = get_active_base_model()
        if not active_model or not active_model.get("image_url"):
            return jsonify({"error": "현재 사용 가능한 베이스 모델이 없습니다."}), 500

        base_img_url_path = active_model["image_url"]

        if base_img_url_path.startswith('/static/'):
            relative_path = os.path.normpath(base_img_url_path[len('/static/'):])
            base_img_fs_path = os.path.join(current_app.static_folder, relative_path)
            if not os.path.exists(base_img_fs_path) or not os.path.isfile(base_img_fs_path):
                return jsonify({"error": "베이스 모델 이미지 파일을 찾거나 접근할 수 없습니다. (Local)"}), 500
        elif base_img_url_path.startswith('http'):
            try:
                response = requests.get(base_img_url_path, stream=True, timeout=15)
                response.raise_for_status()
                content_type = response.headers.get('content-type')
                if not content_type or not content_type.lower().startswith('image/'):
                    return jsonify({"error": f"베이스 모델 URL에서 유효한 이미지를 찾을 수 없습니다 (Type: {content_type})."}), 400
                suffix = '.' + content_type.split('/')[-1].split(';')[0] if content_type else '.tmp'
                temp_base_image_fd, base_img_fs_path = tempfile.mkstemp(suffix=suffix, prefix=f'base_user{user_id}_')
                os.close(temp_base_image_fd)
                with open(base_img_fs_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                temp_files_to_delete.append(base_img_fs_path) # 삭제 목록 추가
                print(f"[Route /synthesize/web Multi-SingleCall] 외부 URL 이미지 다운로드 및 임시 저장 완료: {base_img_fs_path}")
            except requests.exceptions.RequestException as req_e: return jsonify({"error": f"베이스 모델 이미지 다운로드 중 오류: {req_e}"}), 500
            except Exception as down_e: return jsonify({"error": f"베이스 모델 처리 중 오류: {down_e}"}), 500
        else:
            base_img_fs_path = base_img_url_path
            if not os.path.exists(base_img_fs_path) or not os.path.isfile(base_img_fs_path):
                 return jsonify({"error": "베이스 모델 이미지 파일을 찾거나 접근할 수 없습니다. (Path)"}), 500

        # --- 3. 입력 아이템 데이터 처리 (동일) ---
        item_count = request.form.get('item_count', type=int, default=0)
        print(f"[Route /synthesize/web Multi-SingleCall] 전달된 아이템 개수: {item_count}")
        if item_count == 0: return jsonify({"error": "합성할 아이템이 전달되지 않았습니다."}), 400

        items_to_synthesize = [] # [{'type': str, 'path': str}]
        for i in range(item_count):
            item_type_key = f'item_type_{i}'; item_image_key = f'item_image_{i}'
            if item_type_key not in request.form or item_image_key not in request.files: continue
            item_type = request.form[item_type_key]; item_file = request.files[item_image_key]
            if item_file.filename == '' or not item_type: continue
            if not allowed_file(item_file.filename): continue
            try:
                file_ext = os.path.splitext(item_file.filename)[1]
                temp_item_fd, item_filepath = tempfile.mkstemp(suffix=file_ext, prefix=f'item_user{user_id}_{i}_')
                os.close(temp_item_fd)
                item_file.save(item_filepath)
                temp_files_to_delete.append(item_filepath) # 삭제 목록 추가
                items_to_synthesize.append({'type': item_type, 'path': item_filepath})
                print(f"[Route /synthesize/web Multi-SingleCall] 아이템 {i} 임시 저장: {item_filepath} (Type: {item_type})")
            except Exception as e:
                print(f"[Route /synthesize/web Multi-SingleCall] 아이템 {i} 저장 중 오류: {e}")
                return jsonify({"error": f"아이템 {i+1} 이미지 저장 중 오류가 발생했습니다."}), 500

        if not items_to_synthesize: return jsonify({"error": "처리할 유효한 아이템이 없습니다."}), 400

        # --- 4. AI 동시 합성 호출 (수정됨) ---
        print(f"\n[Route /synthesize/web Multi-SingleCall] AI 동시 합성 호출 시작 ({len(items_to_synthesize)}개 아이템)...")
        try:
            # 새 함수 호출
            result_image_bytes = synthesize_multi_items_single_call(
                client=ai_client,
                base_image_path=base_img_fs_path,
                items_info=items_to_synthesize # 아이템 정보 리스트 전달
            )
        except Exception as ai_e:
             print(f"[Route /synthesize/web Multi-SingleCall] AI 호출 중 예외 발생: {ai_e}")
             traceback.print_exc()
             result_image_bytes = None # 오류 시 결과 없도록 처리

        # --- 5. 최종 결과 처리 (동일) ---
        if result_image_bytes:
            print("[Route /synthesize/web Multi-SingleCall] AI 합성 성공 (결과 바이트 수신).")
            final_image_bytes = result_image_bytes
            apply_wm = False
            # 워터마크 적용
            try:
                apply_wm_setting = get_setting('apply_watermark'); apply_wm = apply_wm_setting.lower() == 'true' if isinstance(apply_wm_setting, str) else False
                print(f"[Route /synthesize/web Multi-SingleCall] 워터마크 적용 설정: {apply_wm}")
                if apply_wm:
                    watermark_path = os.path.join(current_app.static_folder, 'images', 'watermark.png')
                    if not os.path.exists(watermark_path): print(f"  - 경고: 워터마크 파일 없음: {watermark_path}")
                    else:
                        print(f"  - 워터마크 적용 시도...")
                        watermarked_bytes = apply_watermark_func(result_image_bytes, watermark_path)
                        if watermarked_bytes and watermarked_bytes != result_image_bytes: final_image_bytes = watermarked_bytes; print("  - 워터마크 적용 성공.")
                        else: print("  - 워터마크 적용 실패 또는 변경 없음.")
            except Exception as wm_e: print(f"  - 워터마크 처리 중 오류: {wm_e}")

            # 사용량 증가
            usage_incremented = increment_usage(user_id)
            if not usage_incremented: print(f"[Route /synthesize/web Multi-SingleCall] 경고: 사용량 증가 실패 (User ID: {user_id})")

            # 최종 결과 이미지 저장
            try:
                first_item_type = items_to_synthesize[0]['type'] if items_to_synthesize else 'multi'
                first_item_name = os.path.splitext(os.path.basename(items_to_synthesize[0]['path']))[0] if items_to_synthesize else 'items'
                output_filename_base = f"output_{user_id}_{first_item_type}_{first_item_name}"
                output_filename = f"{output_filename_base}.png"
                output_filepath = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)
                img = Image.open(BytesIO(final_image_bytes)); img.save(output_filepath, format='PNG')
                print(f"[Route /synthesize/web Multi-SingleCall] 최종 결과 이미지 저장 완료: {output_filepath}")
                output_url = url_for('synthesize.serve_output_file', filename=output_filename, _external=False)

                # 남은 횟수 계산
                current_usage_after = get_todays_usage(user_id)
                new_remaining = max(0, daily_limit - current_usage_after)

                # final_response = jsonify({
                #     "message": f"총 {len(items_to_synthesize)}개 아이템 합성에 성공했습니다!" if not ai_e else "합성 중 일부 오류 발생", # 메시지 수정 고려
                #     "output_file_url": output_url,
                #     "watermarked": apply_wm,
                #     "remaining_attempts": new_remaining
                #     })
                final_response = jsonify({
                    "message": f"총 {len(items_to_synthesize)}개 아이템 합성에 성공했습니다!", # 성공 메시지만 사용
                    "output_file_url": output_url,
                    "watermarked": apply_wm,
                    "remaining_attempts": new_remaining
                    })
            except Exception as save_e:
                print(f"[Route /synthesize/web Multi-SingleCall] 결과 이미지 저장 중 오류: {save_e}"); traceback.print_exc()
                final_response = jsonify({"error": "합성 결과 저장 중 오류가 발생했습니다."}), 500
        else:
            # AI 합성 실패
            print("[Route /synthesize/web Multi-SingleCall] AI 합성 실패 (ai_module 반환값 없음).")
            final_response = jsonify({"error": "AI 이미지 합성에 실패했습니다."}), 500

        # 최종 응답 반환
        return final_response

    except Exception as e:
        print(f"[Route /synthesize/web Multi-SingleCall] 처리 중 예외 발생: {e}"); traceback.print_exc()
        return jsonify({"error": "이미지 합성 처리 중 오류가 발생했습니다."}), 500
    finally:
        # --- 모든 임시 파일 삭제 ---
        print(f"[Route /synthesize/web Multi-SingleCall] 임시 파일 삭제 시작 (총 {len(temp_files_to_delete)}개)...")
        for temp_file_path in temp_files_to_delete:
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path); print(f"  - 삭제 완료: {temp_file_path}")
                except OSError as e: print(f"  - 경고: 임시 파일 삭제 실패 - {e}")



# --- /outputs/<filename> 라우트 ---
@bp.route('/outputs/<path:filename>')
def serve_output_file(filename):
    # ... (기존 serve_output_file 함수 코드와 동일) ...
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
        return send_from_directory( output_dir, safe_filename, as_attachment=False )
    except FileNotFoundError:
         print(f"[Route /outputs] 오류: 파일을 찾을 수 없음 - {safe_filename}")
         return jsonify({"error": "요청한 파일을 찾을 수 없습니다."}), 404
# app/routes/admin.py
# 관리자 기능 관련 API 라우트

from flask import Blueprint, request, jsonify, current_app, abort
from app.routes.auth import login_required, admin_required
from app.utils.db_utils import (
    get_all_base_models, add_base_model, get_base_model_by_id,
    update_base_model, delete_base_model, get_setting, update_setting
)

# 'admin' 이름으로 Blueprint 객체 생성
# url_prefix='/admin'은 app/__init__.py에서 블루프린트 등록 시 설정
bp = Blueprint('admin', __name__)

# --- Base Model Management Routes ---

@bp.route('/models', methods=['GET'])
@login_required
@admin_required
def list_base_models():
    """모든 베이스 모델 목록을 조회합니다."""
    try:
        models = get_all_base_models()
        return jsonify(models)
    except Exception as e:
        print(f"[Admin Route - GET /models] 오류: {e}")
        return jsonify({"error": "베이스 모델 목록 조회 중 오류가 발생했습니다."}), 500

@bp.route('/models', methods=['POST'])
@login_required
@admin_required
def create_base_model():
    """새로운 베이스 모델을 생성합니다."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('image_url'):
        return jsonify({"error": "'name'과 'image_url'은 필수 항목입니다."}), 400

    name = data['name']
    image_url = data['image_url']
    prompt = data.get('prompt') # Optional
    is_active = data.get('is_active', False) # Optional, default False

    try:
        # TODO: image_url 유효성 검사 (URL 형식 또는 실제 파일 경로 존재 여부)
        new_model = add_base_model(name=name, image_url=image_url, prompt=prompt, is_active=is_active)
        if new_model:
            return jsonify(new_model), 201 # 201 Created
        else:
            # add_base_model 내부에서 오류 로깅됨
            return jsonify({"error": "베이스 모델 생성 중 오류가 발생했습니다."}), 500
    except Exception as e:
        print(f"[Admin Route - POST /models] 오류: {e}")
        return jsonify({"error": "베이스 모델 생성 중 서버 오류가 발생했습니다."}), 500

@bp.route('/models/<int:model_id>', methods=['PUT'])
@login_required
@admin_required
def modify_base_model(model_id):
    """기존 베이스 모델 정보를 수정합니다."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "수정할 데이터가 없습니다."}), 400

    # 업데이트할 필드만 추출
    name = data.get('name')
    image_url = data.get('image_url')
    prompt = data.get('prompt')
    is_active = data.get('is_active') # None일 수도 있음

    # is_active는 boolean 타입이어야 함
    if is_active is not None and not isinstance(is_active, bool):
        return jsonify({"error": "'is_active' 값은 true 또는 false 여야 합니다."}), 400

    try:
        # TODO: image_url 유효성 검사
        updated_model = update_base_model(
            model_id=model_id,
            name=name,
            image_url=image_url,
            prompt=prompt,
            is_active=is_active
        )
        if updated_model:
            return jsonify(updated_model)
        else:
            # ID가 없거나 DB 오류 발생 시
            # update_base_model 함수 내에서 로깅됨
            # ID가 없는 경우 404 반환 고려
            existing_model = get_base_model_by_id(model_id)
            if not existing_model:
                 return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없습니다."}), 404
            else:
                 return jsonify({"error": "베이스 모델 수정 중 오류가 발생했습니다."}), 500
    except Exception as e:
        print(f"[Admin Route - PUT /models/{model_id}] 오류: {e}")
        return jsonify({"error": "베이스 모델 수정 중 서버 오류가 발생했습니다."}), 500

@bp.route('/models/<int:model_id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_base_model(model_id):
    """특정 베이스 모델을 활성화합니다. (다른 모델은 비활성화됨)"""
    try:
        # is_active=True 로 업데이트 시도
        updated_model = update_base_model(model_id=model_id, is_active=True)
        if updated_model:
            return jsonify(updated_model)
        else:
            # ID가 없거나 DB 오류 발생 시
            existing_model = get_base_model_by_id(model_id)
            if not existing_model:
                 return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없습니다."}), 404
            else:
                 return jsonify({"error": "베이스 모델 활성화 중 오류가 발생했습니다."}), 500
    except Exception as e:
        print(f"[Admin Route - POST /models/{model_id}/activate] 오류: {e}")
        return jsonify({"error": "베이스 모델 활성화 중 서버 오류가 발생했습니다."}), 500


@bp.route('/models/<int:model_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_base_model(model_id):
    """베이스 모델을 삭제합니다."""
    try:
        success = delete_base_model(model_id)
        if success:
            # 204 No Content는 본문 없이 성공을 의미
            return '', 204
            # 또는 메시지와 함께 200 OK 반환 가능
            # return jsonify({"message": f"베이스 모델 (ID: {model_id}) 삭제 성공"})
        else:
            # ID가 없는 경우
            return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없거나 삭제에 실패했습니다."}), 404
    except Exception as e:
        print(f"[Admin Route - DELETE /models/{model_id}] 오류: {e}")
        return jsonify({"error": "베이스 모델 삭제 중 서버 오류가 발생했습니다."}), 500


# --- System Settings Management Routes ---

# 관리할 설정 키 목록 정의
MANAGEABLE_SETTINGS = ['max_user_syntheses', 'apply_watermark']

@bp.route('/settings', methods=['GET'])
@login_required
@admin_required
def get_system_settings():
    """관리 가능한 시스템 설정 목록을 조회합니다."""
    settings = {}
    try:
        for key in MANAGEABLE_SETTINGS:
            settings[key] = get_setting(key)
            # 값이 None일 경우 처리 (DB에 키가 없을 수 있음)
            if settings[key] is None:
                print(f"[Admin Route - GET /settings] 경고: 설정 키 '{key}'를 찾을 수 없습니다.")
                # 기본값을 반환하거나 None 그대로 둘 수 있음
                # settings[key] = 'default_value' # 예시

        # 타입 변환 (필요시)
        if settings.get('max_user_syntheses') is not None:
            try:
                settings['max_user_syntheses'] = int(settings['max_user_syntheses'])
            except ValueError:
                 print(f"[Admin Route - GET /settings] 경고: 'max_user_syntheses' 값이 숫자가 아님 ('{settings['max_user_syntheses']}')")
                 # 오류 처리 또는 문자열 그대로 반환
        if settings.get('apply_watermark') is not None:
            settings['apply_watermark'] = settings['apply_watermark'].lower() == 'true'

        return jsonify(settings)
    except Exception as e:
        print(f"[Admin Route - GET /settings] 오류: {e}")
        return jsonify({"error": "시스템 설정 조회 중 오류가 발생했습니다."}), 500

@bp.route('/settings', methods=['PUT'])
@login_required
@admin_required
def modify_system_settings():
    """시스템 설정을 업데이트합니다."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "수정할 설정 데이터가 없습니다."}), 400

    updated_settings = {}
    errors = {}

    for key, value in data.items():
        if key not in MANAGEABLE_SETTINGS:
            errors[key] = "관리할 수 없는 설정 항목입니다."
            continue

        # 값 유효성 검사 및 타입 변환
        setting_value_str = str(value) # DB 저장을 위해 문자열로 변환
        if key == 'max_user_syntheses':
            try:
                int_value = int(value)
                if int_value < 0:
                    errors[key] = "사용량 제한은 0 이상이어야 합니다."
                    continue
                setting_value_str = str(int_value)
            except (ValueError, TypeError):
                errors[key] = "사용량 제한은 숫자여야 합니다."
                continue
        elif key == 'apply_watermark':
            if not isinstance(value, bool):
                errors[key] = "워터마크 설정은 true 또는 false 여야 합니다."
                continue
            setting_value_str = 'true' if value else 'false'

        # DB 업데이트 시도
        try:
            success = update_setting(key, setting_value_str)
            if success:
                updated_settings[key] = value # 성공 시 원래 값(타입 변환된) 저장
            else:
                # 키가 존재하지 않거나 DB 오류
                errors[key] = "설정 업데이트에 실패했습니다."
        except Exception as e:
            print(f"[Admin Route - PUT /settings] 키 '{key}' 업데이트 중 오류: {e}")
            errors[key] = "설정 업데이트 중 서버 오류 발생."

    if errors:
        # 일부 또는 전체 업데이트 실패
        return jsonify({
            "message": "일부 설정 업데이트 실패.",
            "updated": updated_settings,
            "errors": errors
        }), 400 # 또는 500 (서버 오류 포함 시)
    else:
        # 모든 요청된 설정 업데이트 성공
        return jsonify({
            "message": "시스템 설정 업데이트 성공.",
            "updated": updated_settings
        })

# TODO: 관리자 대시보드 페이지 라우트 추가 (render_template 사용)
# @bp.route('/')
# @login_required
# @admin_required
# def dashboard():
#    return render_template('admin/dashboard.html')

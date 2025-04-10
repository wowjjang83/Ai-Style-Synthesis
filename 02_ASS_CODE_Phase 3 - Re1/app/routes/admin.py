# app/routes/admin.py
# 관리자 기능 관련 API 라우트 및 페이지

from flask import Blueprint, request, jsonify, current_app, abort, render_template, flash
from app.routes.auth import login_required, admin_required
from app.utils.db_utils import (
    get_all_base_models, add_base_model, get_base_model_by_id, # get_base_model_by_id 추가 확인
    update_base_model, delete_base_model, get_setting, update_setting,
    get_active_base_model, # 활성 모델 정보 조회 위해 추가
    get_total_usage_for_date # 총 사용량 조회 함수 import
)
from datetime import date
import traceback # 상세 오류 로깅용

# 'admin' 이름으로 Blueprint 객체 생성
# url_prefix='/admin'은 app/__init__.py에서 블루프린트 등록 시 설정
bp = Blueprint('admin', __name__)

# --- 관리자 페이지 렌더링 라우트 ---

@bp.route('/') # /admin/ 경로
@bp.route('/dashboard') # /admin/dashboard 경로
@login_required # 로그인 필수
@admin_required # 관리자 권한 필수
def dashboard():
    """관리자 대시보드 페이지를 렌더링합니다."""
    print("[Admin Route] GET /admin/dashboard 요청")
    try:
        # 대시보드에 필요한 데이터 조회
        models = get_all_base_models()
        model_count = len(models)

        active_model = get_active_base_model()
        active_model_id = active_model.get('id') if active_model else None

        watermark_setting = get_setting('apply_watermark')
        watermark_enabled = watermark_setting.lower() == 'true' if isinstance(watermark_setting, str) else False

        # 수정: 오늘 총 사용량 조회 기능 사용
        today_date = date.today()
        total_today_usage = get_total_usage_for_date(today_date) # 함수 호출

        return render_template(
            'admin/dashboard.html',
            model_count=model_count,
            total_today_usage=total_today_usage, # 계산된 값 전달
            active_model_id=active_model_id,
            watermark_enabled=watermark_enabled
        )
    except Exception as e:
        print(f"[Admin Route - GET /dashboard] 오류: {e}")
        traceback.print_exc() # 개발 중 상세 오류 확인
        flash("대시보드 로딩 중 오류가 발생했습니다.", "error")
        # 오류 발생 시에도 기본 템플릿은 렌더링 시도 (오류 메시지 포함)
        return render_template('admin/dashboard.html', error="데이터 로딩 실패")

@bp.route('/models/manage') # /admin/models/manage 경로
@login_required
@admin_required
def manage_models():
    """베이스 모델 관리 페이지를 렌더링합니다."""
    print("[Admin Route] GET /admin/models/manage 요청")
    try:
        models = get_all_base_models()
        # 날짜 형식 등 필요한 데이터 가공은 여기서 하거나 템플릿 필터 사용
        return render_template('admin/manage_models.html', models=models)
    except Exception as e:
        print(f"[Admin Route - GET /models/manage] 오류: {e}")
        traceback.print_exc()
        flash("베이스 모델 목록 로딩 중 오류가 발생했습니다.", "error")
        return render_template('admin/manage_models.html', models=[], error="데이터 로딩 실패")


# 관리할 설정 키 목록 정의 (API 와 공유)
MANAGEABLE_SETTINGS = ['max_user_syntheses', 'apply_watermark']

@bp.route('/settings/manage') # /admin/settings/manage 경로
@login_required
@admin_required
def manage_settings():
    """시스템 설정 관리 페이지를 렌더링합니다."""
    print("[Admin Route] GET /admin/settings/manage 요청")
    settings_data = {}
    try:
        # GET /admin/settings API 와 유사하게 설정값 조회
        for key in MANAGEABLE_SETTINGS:
            settings_data[key] = get_setting(key)
            # DB에 값이 없는 경우 기본값 설정
            if settings_data[key] is None:
                 if key == 'max_user_syntheses': settings_data[key] = 3 # 기본값 3
                 elif key == 'apply_watermark': settings_data[key] = 'false' # 기본값 false (문자열)

        # 타입 변환 (템플릿에서 사용하기 편하도록)
        if settings_data.get('max_user_syntheses') is not None:
            try:
                settings_data['max_user_syntheses'] = int(settings_data['max_user_syntheses'])
            except (ValueError, TypeError):
                 print(f"[Admin Route - GET /settings/manage] 경고: max_user_syntheses 값이 숫자가 아님 ('{settings_data['max_user_syntheses']}')")
                 settings_data['max_user_syntheses'] = 3 # 오류 시 기본값
        if settings_data.get('apply_watermark') is not None:
            settings_data['apply_watermark'] = settings_data['apply_watermark'].lower() == 'true' # boolean으로 변환

        return render_template('admin/manage_settings.html', settings=settings_data)
    except Exception as e:
        print(f"[Admin Route - GET /settings/manage] 오류: {e}")
        traceback.print_exc()
        flash("시스템 설정 로딩 중 오류가 발생했습니다.", "error")
        return render_template('admin/manage_settings.html', settings={}, error="데이터 로딩 실패")


# --- Base Model Management Routes (API) ---

@bp.route('/models', methods=['GET'])
@login_required
@admin_required
def list_base_models():
    """모든 베이스 모델 목록을 조회합니다. (API)"""
    print("[Admin API] GET /admin/models 요청")
    try:
        models = get_all_base_models()
        # TODO: 페이지네이션 구현 고려
        return jsonify(models)
    except Exception as e:
        print(f"[Admin API - GET /models] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "베이스 모델 목록 조회 중 오류가 발생했습니다."}), 500

# 단일 베이스 모델 조회 API (수정 시 사용)
@bp.route('/models/<int:model_id>', methods=['GET'])
@login_required
@admin_required
def get_single_base_model(model_id):
    """ID로 특정 베이스 모델 정보를 조회합니다. (API)"""
    print(f"[Admin API] GET /admin/models/{model_id} 요청")
    try:
        model = get_base_model_by_id(model_id)
        if model:
            return jsonify(model)
        else:
            print(f"[Admin API - GET /models/{model_id}] 오류: 모델 ID {model_id} 없음")
            return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없습니다."}), 404
    except Exception as e:
        print(f"[Admin API - GET /models/{model_id}] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "베이스 모델 정보 조회 중 오류가 발생했습니다."}), 500

@bp.route('/models', methods=['POST'])
@login_required
@admin_required
def create_base_model():
    """새로운 베이스 모델을 생성합니다. (API)"""
    print("[Admin API] POST /admin/models 요청")
    data = request.get_json()
    if not data or not data.get('name') or not data.get('image_url'):
        return jsonify({"error": "'name'과 'image_url'은 필수 항목입니다."}), 400

    name = data['name']
    image_url = data['image_url']
    prompt = data.get('prompt')
    is_active = data.get('is_active', False) # '새 모델 추가' 시 활성화 옵션은 UI에서 제공하지 않음 (기본 False)

    try:
        # TODO: image_url 유효성 검사 (URL 형식, 정적 파일 경로 유효성 등)
        new_model = add_base_model(name=name, image_url=image_url, prompt=prompt, is_active=is_active)
        if new_model:
            print(f"[Admin API - POST /models] 성공: 새 모델 ID={new_model.get('id')}")
            return jsonify(new_model), 201 # 201 Created
        else:
            # add_base_model 내부에서 오류 로깅됨
            return jsonify({"error": "베이스 모델 생성 중 DB 오류가 발생했습니다."}), 500
    except Exception as e:
        print(f"[Admin API - POST /models] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "베이스 모델 생성 중 서버 오류가 발생했습니다."}), 500

@bp.route('/models/<int:model_id>', methods=['PUT'])
@login_required
@admin_required
def modify_base_model(model_id):
    """기존 베이스 모델 정보를 수정합니다. (API)"""
    print(f"[Admin API] PUT /admin/models/{model_id} 요청")
    data = request.get_json()
    if not data:
        return jsonify({"error": "수정할 데이터가 없습니다."}), 400

    # 업데이트할 필드만 추출 (None 이면 업데이트 안 함)
    name = data.get('name')
    image_url = data.get('image_url')
    prompt = data.get('prompt')
    # is_active는 별도 API(/activate)로 처리하므로 여기서 제외하거나,
    # 필요시 명시적으로 None인지 확인하여 처리
    is_active = data.get('is_active')
    if is_active is not None:
         print(f"[Admin API - PUT /models/{model_id}] 경고: is_active 필드는 /activate 엔드포인트를 사용하세요.")
         # is_active 필드는 무시하거나 오류 처리 가능
         is_active = None # 여기서는 무시

    # TODO: image_url 유효성 검사

    try:
        updated_model = update_base_model(
            model_id=model_id, name=name, image_url=image_url, prompt=prompt, is_active=is_active
        )
        if updated_model:
            print(f"[Admin API - PUT /models/{model_id}] 성공")
            return jsonify(updated_model)
        else:
            # ID가 없거나 DB 오류 발생 시
            existing_model = get_base_model_by_id(model_id)
            if not existing_model:
                 print(f"[Admin API - PUT /models/{model_id}] 오류: 모델 ID {model_id} 없음")
                 return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없습니다."}), 404
            else:
                 print(f"[Admin API - PUT /models/{model_id}] 오류: DB 업데이트 실패")
                 return jsonify({"error": "베이스 모델 수정 중 오류가 발생했습니다."}), 500
    except Exception as e:
        print(f"[Admin API - PUT /models/{model_id}] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "베이스 모델 수정 중 서버 오류가 발생했습니다."}), 500

@bp.route('/models/<int:model_id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_base_model(model_id):
    """특정 베이스 모델을 활성화합니다. (다른 모델은 비활성화됨) (API)"""
    print(f"[Admin API] POST /admin/models/{model_id}/activate 요청")
    try:
        # is_active=True 로 업데이트 시도 (update_base_model 함수 내에서 다른 모델 비활성화 처리)
        updated_model = update_base_model(model_id=model_id, is_active=True)
        if updated_model:
            print(f"[Admin API - POST /models/{model_id}/activate] 성공")
            return jsonify(updated_model)
        else:
            existing_model = get_base_model_by_id(model_id)
            if not existing_model:
                 print(f"[Admin API - POST /models/{model_id}/activate] 오류: 모델 ID {model_id} 없음")
                 return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없습니다."}), 404
            else:
                 print(f"[Admin API - POST /models/{model_id}/activate] 오류: DB 업데이트 실패")
                 return jsonify({"error": "베이스 모델 활성화 중 오류가 발생했습니다."}), 500
    except Exception as e:
        print(f"[Admin API - POST /models/{model_id}/activate] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "베이스 모델 활성화 중 서버 오류가 발생했습니다."}), 500


@bp.route('/models/<int:model_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_base_model(model_id):
    """베이스 모델을 삭제합니다. (API)"""
    print(f"[Admin API] DELETE /admin/models/{model_id} 요청")
    try:
        success = delete_base_model(model_id)
        if success:
            print(f"[Admin API - DELETE /models/{model_id}] 성공")
            return '', 204 # No Content
        else:
            print(f"[Admin API - DELETE /models/{model_id}] 오류: 모델 ID {model_id} 없거나 삭제 실패")
            return jsonify({"error": f"ID {model_id}의 베이스 모델을 찾을 수 없거나 삭제에 실패했습니다."}), 404
    except Exception as e:
        print(f"[Admin API - DELETE /models/{model_id}] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "베이스 모델 삭제 중 서버 오류가 발생했습니다."}), 500

# --- System Settings Management Routes (API) ---

@bp.route('/settings', methods=['GET'])
@login_required
@admin_required
def get_system_settings():
    """관리 가능한 시스템 설정 목록을 조회합니다. (API)"""
    print("[Admin API] GET /admin/settings 요청")
    settings = {}
    try:
        for key in MANAGEABLE_SETTINGS:
            settings[key] = get_setting(key)
            if settings[key] is None:
                 if key == 'max_user_syntheses': settings[key] = 3
                 elif key == 'apply_watermark': settings[key] = 'false'

        # 타입 변환 (API 응답 시 실제 타입으로)
        if settings.get('max_user_syntheses') is not None:
            try: settings['max_user_syntheses'] = int(settings['max_user_syntheses'])
            except (ValueError, TypeError): settings['max_user_syntheses'] = 3
        if settings.get('apply_watermark') is not None:
            settings['apply_watermark'] = settings['apply_watermark'].lower() == 'true'

        return jsonify(settings)
    except Exception as e:
        print(f"[Admin API - GET /settings] 오류: {e}")
        traceback.print_exc()
        return jsonify({"error": "시스템 설정 조회 중 오류가 발생했습니다."}), 500

@bp.route('/settings', methods=['PUT'])
@login_required
@admin_required
def modify_system_settings():
    """시스템 설정을 업데이트합니다. (API)"""
    print("[Admin API] PUT /admin/settings 요청")
    data = request.get_json()
    if not data:
        return jsonify({"error": "수정할 설정 데이터가 없습니다."}), 400

    updated_settings = {}
    errors = {}

    for key, value in data.items():
        if key not in MANAGEABLE_SETTINGS:
            print(f"[Admin API - PUT /settings] 경고: 관리할 수 없는 키 '{key}'는 무시됨.")
            continue

        # 값 유효성 검사 및 타입 변환 (DB 저장을 위해 문자열로)
        setting_value_str = ''
        original_value = value # 성공 시 반환할 원래 값 저장

        if key == 'max_user_syntheses':
            try:
                int_value = int(value)
                if int_value < 0: errors[key] = "사용량 제한은 0 이상이어야 합니다."; continue
                setting_value_str = str(int_value)
            except (ValueError, TypeError): errors[key] = "사용량 제한은 숫자여야 합니다."; continue
        elif key == 'apply_watermark':
            if not isinstance(value, bool): errors[key] = "워터마크 설정은 true 또는 false 여야 합니다."; continue
            setting_value_str = 'true' if value else 'false'
        else: setting_value_str = str(value) # 다른 타입의 설정 추가 대비

        # DB 업데이트 시도
        try:
            success = update_setting(key, setting_value_str)
            if success:
                updated_settings[key] = original_value # 성공 시 원래 값(타입 변환된) 저장
            else:
                # update_setting 함수에서 rowcount가 0인 경우 (키가 없거나 값이 같음)
                errors[key] = "설정 업데이트 실패 (키가 없거나 값이 동일). DB 로그 확인 필요."
        except Exception as e:
            print(f"[Admin API - PUT /settings] 키 '{key}' 업데이트 중 오류: {e}")
            traceback.print_exc()
            errors[key] = "설정 업데이트 중 서버 오류 발생."

    if errors:
        # 일부 또는 전체 업데이트 실패
        print(f"[Admin API - PUT /settings] 실패: {errors}")
        return jsonify({
            "message": "일부 설정 업데이트 실패.",
            "updated": updated_settings, # 성공한 부분만이라도 반환
            "errors": errors
        }), 400 # Bad Request 또는 500 Internal Server Error 고려
    else:
        # 모든 요청된 설정 업데이트 성공
        print(f"[Admin API - PUT /settings] 성공: {updated_settings}")
        return jsonify({
            "message": "시스템 설정 업데이트 성공.",
            "updated": updated_settings
        })


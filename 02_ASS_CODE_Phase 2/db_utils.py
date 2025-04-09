# db_utils.py
import psycopg2
import os
from dotenv import load_dotenv
from datetime import date # 오늘 날짜 사용 위해 import
import psycopg2.extras # 딕셔너리 커서 사용 위해 import

load_dotenv()

db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

# --- 데이터베이스 연결 함수 (개선 필요) ---
# 참고: 매번 연결을 열고 닫는 것은 비효율적입니다.
# 실제 애플리케이션에서는 커넥션 풀링 또는 Flask의 Context를 사용하는 것이 좋습니다.
# 우선은 간단하게 각 함수 내에서 연결/종료하는 방식으로 구현합니다.
def get_db_connection():
    """데이터베이스 연결 객체를 반환합니다."""
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        return conn
    except psycopg2.Error as e:
        print(f"데이터베이스 연결 실패: {e}")
        return None

# --- 시스템 설정 관련 함수 ---
def get_setting(setting_key: str) -> str | None:
    """system_settings 테이블에서 특정 키의 값을 가져옵니다."""
    conn = get_db_connection()
    if not conn:
        return None

    value = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = %s", (setting_key,))
            result = cur.fetchone()
            if result:
                value = result[0]
                print(f"설정값 읽기 성공: {setting_key} = {value}")
            else:
                print(f"설정값 읽기 실패: 키 '{setting_key}'를 찾을 수 없음")
    except psycopg2.Error as e:
        print(f"설정값 읽기 중 오류 발생 (key={setting_key}): {e}")
    finally:
        if conn:
            conn.close()
    return value

# --- 베이스 모델 관련 함수 ---
def get_active_base_model() -> dict | None:
    """활성화된(is_active=True) 베이스 모델 정보를 딕셔너리로 반환합니다."""
    conn = get_db_connection()
    if not conn:
        return None

    model_data = None
    try:
        with conn.cursor() as cur:
            # is_active가 true인 모델 중 하나를 가져옴 (ORDER BY id DESC 등으로 최신 모델 우선 가능)
            cur.execute("SELECT id, name, image_url, prompt FROM base_models WHERE is_active = TRUE LIMIT 1")
            result = cur.fetchone()
            if result:
                # 결과를 딕셔너리로 변환 (컬럼 이름 매칭 필요)
                # 여기서는 순서 기반: id, name, image_url, prompt
                model_data = {
                    "id": result[0],
                    "name": result[1],
                    "image_url": result[2],
                    "prompt": result[3]
                }
                print(f"활성 베이스 모델 로드 성공: ID={model_data['id']}, Name={model_data['name']}")
            else:
                print("활성 베이스 모델을 찾을 수 없습니다 (is_active=True인 모델 없음).")
    except psycopg2.Error as e:
        print(f"활성 베이스 모델 로드 중 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
    return model_data


# db_utils.py (하단에 추가)
from werkzeug.security import generate_password_hash, check_password_hash # 비밀번호 해싱용

# --- 사용자 관련 함수 ---
def find_user_by_email(email: str) -> dict | None:
    """이메일 주소로 사용자를 찾아 사용자 정보를 딕셔너리로 반환합니다."""
    conn = get_db_connection()
    if not conn: return None
    user_data = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
            result = cur.fetchone()
            if result:
                user_data = {"id": result[0], "email": result[1], "password_hash": result[2]}
                print(f"사용자 찾기 성공: {email}")
            else:
                 print(f"사용자 찾기 실패: {email} 없음")
    except psycopg2.Error as e:
        print(f"이메일로 사용자 찾기 중 오류 발생 (email={email}): {e}")
    finally:
        if conn: conn.close()
    return user_data

def add_user(email: str, password: str) -> dict | None:
    """새로운 사용자를 users 테이블에 추가합니다. 비밀번호는 해싱하여 저장합니다."""
    conn = get_db_connection()
    if not conn: return None

    # 비밀번호 해싱
    password_hash = generate_password_hash(password)
    print(f"비밀번호 해싱 완료 (원본: {password[:2]}..., 해시: {password_hash[:10]}...)")

    new_user_data = None
    try:
        with conn.cursor() as cur:
            # 이메일 중복 방지를 위해 INSERT 시 예외 처리 활용 가능 (또는 미리 find_user_by_email 호출)
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email, created_at",
                (email, password_hash)
            )
            conn.commit() # 데이터베이스 변경사항 저장!
            result = cur.fetchone()
            if result:
                new_user_data = {"id": result[0], "email": result[1], "created_at": result[2]}
                print(f"새 사용자 추가 성공: {email}")
            else: # 보통 RETURNING 사용 시 이 경우는 드묾
                 print(f"새 사용자 추가 실패 (INSERT 후 결과 없음): {email}")

    except psycopg2.IntegrityError as e: # 주로 UNIQUE 제약조건 위반 시 발생
        conn.rollback() # 오류 발생 시 트랜잭션 롤백
        print(f"사용자 추가 실패 (이미 존재하는 이메일 가능성): {email}, 오류: {e}")
        # 이미 존재하는 사용자 정보 반환 시도 (선택적)
        # existing_user = find_user_by_email(email)
        # return {"error": "Email already exists", "user": existing_user} # 이런 식으로 처리 가능
        return {"error": "Email already exists"} # 간단히 오류 메시지만 반환
    except psycopg2.Error as e:
        conn.rollback()
        print(f"사용자 추가 중 DB 오류 발생: {email}, 오류: {e}")
        return None # 일반 DB 오류
    finally:
        if conn: conn.close()

    return new_user_data

# --- 비밀번호 확인 함수 ---
def check_password(hashed_password: str, provided_password: str) -> bool:
    """저장된 해시 비밀번호와 사용자가 입력한 비밀번호를 비교합니다."""
    return check_password_hash(hashed_password, provided_password)

# --- 사용량 추적 관련 함수 ---
def get_todays_usage(user_id: int) -> int:
    """usage_tracking 테이블에서 특정 사용자의 오늘 사용 횟수를 가져옵니다."""
    conn = get_db_connection()
    if not conn: return 0 # 연결 실패 시 0 반환 (또는 오류 처리)

    count = 0
    today = date.today()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count FROM usage_tracking WHERE user_id = %s AND usage_date = %s",
                (user_id, today)
            )
            result = cur.fetchone()
            if result:
                count = result[0]
                print(f"사용량 조회 성공: User ID={user_id}, Date={today}, Count={count}")
            else:
                print(f"사용량 조회: 오늘 사용 기록 없음 (User ID={user_id}, Date={today})")
    except psycopg2.Error as e:
        print(f"사용량 조회 중 오류 발생 (User ID={user_id}, Date={today}): {e}")
    finally:
        if conn: conn.close()
    return count

def increment_usage(user_id: int) -> bool:
    """usage_tracking 테이블에서 특정 사용자의 오늘 사용 횟수를 1 증가시킵니다. (INSERT 또는 UPDATE)"""
    conn = get_db_connection()
    if not conn: return False

    success = False
    today = date.today()
    try:
        with conn.cursor() as cur:
            # 오늘 날짜 레코드가 있으면 count + 1, 없으면 새로 삽입 (count=1)
            # ON CONFLICT ... DO UPDATE 구문 활용 (PostgreSQL 9.5 이상)
            cur.execute(
                """
                INSERT INTO usage_tracking (user_id, usage_date, count)
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, usage_date)
                DO UPDATE SET count = usage_tracking.count + 1;
                """,
                (user_id, today)
            )
            conn.commit() # 변경사항 저장
            success = True
            print(f"사용량 증가 성공: User ID={user_id}, Date={today}")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"사용량 증가 중 오류 발생 (User ID={user_id}, Date={today}): {e}")
    finally:
        if conn: conn.close()
    return success

# --- 데이터베이스 연결 함수 (수정: 딕셔너리 커서 사용) ---
# get_db_connection 함수를 수정하여 딕셔너리 형태로 결과를 받도록 합니다.
def get_db_connection(use_dict_cursor=False): # 파라미터 추가
    """데이터베이스 연결 객체를 반환합니다."""
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        # 딕셔너리 커서 사용 여부 결정
        if use_dict_cursor:
            conn.cursor_factory = psycopg2.extras.DictCursor
        return conn
    except psycopg2.Error as e:
        print(f"데이터베이스 연결 실패: {e}")
        return None

# --- 베이스 모델 관련 함수 (CRUD 추가) ---

# get_active_base_model 함수 수정 (딕셔너리 커서 사용)
def get_active_base_model() -> dict | None:
    """활성화된(is_active=True) 베이스 모델 정보를 딕셔너리로 반환합니다."""
    # 딕셔너리 커서를 사용하도록 get_db_connection 호출 수정
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None
    model_data = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM base_models WHERE is_active = TRUE LIMIT 1")
            result = cur.fetchone() # DictRow 객체 또는 None 반환
            if result:
                model_data = dict(result) # DictRow를 일반 딕셔너리로 변환
                print(f"활성 베이스 모델 로드 성공: ID={model_data.get('id')}, Name={model_data.get('name')}")
            else:
                print("활성 베이스 모델을 찾을 수 없습니다.")
    except psycopg2.Error as e:
        print(f"활성 베이스 모델 로드 중 오류 발생: {e}")
    finally:
        if conn: conn.close()
    return model_data

def add_base_model(name: str, image_url: str, prompt: str = None) -> dict | None:
    """새 베이스 모델을 추가합니다. is_active는 기본 False."""
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None
    new_model_data = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO base_models (name, image_url, prompt, is_active)
                VALUES (%s, %s, %s, FALSE)
                RETURNING *;
                """,
                (name, image_url, prompt)
            )
            conn.commit()
            result = cur.fetchone()
            if result:
                new_model_data = dict(result)
                print(f"베이스 모델 추가 성공: ID={new_model_data.get('id')}")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"베이스 모델 추가 중 오류 발생: {e}")
    finally:
        if conn: conn.close()
    return new_model_data

def get_base_model_by_id(model_id: int) -> dict | None:
    """ID로 특정 베이스 모델 정보를 가져옵니다."""
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None
    model_data = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM base_models WHERE id = %s", (model_id,))
            result = cur.fetchone()
            if result:
                model_data = dict(result)
                print(f"베이스 모델 조회 성공 (ID={model_id})")
            else:
                print(f"베이스 모델 조회 실패: ID={model_id} 없음")
    except psycopg2.Error as e:
        print(f"베이스 모델 조회(ID={model_id}) 중 오류 발생: {e}")
    finally:
        if conn: conn.close()
    return model_data

def get_all_base_models() -> list[dict]:
    """모든 베이스 모델 목록을 가져옵니다."""
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return []
    models = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM base_models ORDER BY id ASC")
            results = cur.fetchall()
            models = [dict(row) for row in results]
            print(f"모든 베이스 모델 조회 성공: {len(models)}개")
    except psycopg2.Error as e:
        print(f"모든 베이스 모델 조회 중 오류 발생: {e}")
    finally:
        if conn: conn.close()
    return models

def update_base_model(model_id: int, name: str = None, image_url: str = None, prompt: str = None, is_active: bool = None) -> dict | None:
    """베이스 모델 정보를 업데이트합니다."""
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None

    updated_model_data = None
    fields_to_update = []
    values = []

    # 업데이트할 필드와 값 동적 구성
    if name is not None: fields_to_update.append("name = %s"); values.append(name)
    if image_url is not None: fields_to_update.append("image_url = %s"); values.append(image_url)
    if prompt is not None: fields_to_update.append("prompt = %s"); values.append(prompt)
    if is_active is not None: fields_to_update.append("is_active = %s"); values.append(is_active)

    if not fields_to_update:
        print("업데이트할 필드가 없습니다.")
        # ID로 현재 정보 조회 후 반환하거나 None 반환
        return get_base_model_by_id(model_id)

    values.append(model_id) # WHERE 절을 위한 ID 추가

    try:
        with conn.cursor() as cur:
            # 만약 is_active를 True로 설정하는 경우, 다른 모든 모델을 False로 변경 (선택적 로직)
            if is_active is True:
                print(f"ID={model_id}를 활성화하기 전에 다른 모델 비활성화 시도...")
                cur.execute("UPDATE base_models SET is_active = FALSE WHERE id != %s", (model_id,))
                print("다른 모델 비활성화 완료.")

            # 실제 업데이트 쿼리 실행
            query = f"UPDATE base_models SET {', '.join(fields_to_update)} WHERE id = %s RETURNING *"
            cur.execute(query, tuple(values))
            conn.commit()

            result = cur.fetchone()
            if result:
                updated_model_data = dict(result)
                print(f"베이스 모델 업데이트 성공: ID={model_id}")
            else:
                print(f"베이스 모델 업데이트 실패: ID={model_id} 없음 (또는 변경사항 없음?)")

    except psycopg2.Error as e:
        conn.rollback()
        print(f"베이스 모델 업데이트(ID={model_id}) 중 오류 발생: {e}")
    finally:
        if conn: conn.close()
    return updated_model_data

def delete_base_model(model_id: int) -> bool:
    """ID로 베이스 모델을 삭제합니다."""
    conn = get_db_connection()
    if not conn: return False
    success = False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM base_models WHERE id = %s", (model_id,))
            conn.commit()
            # 실제로 삭제되었는지 확인 (영향받은 행 수 확인)
            if cur.rowcount > 0:
                success = True
                print(f"베이스 모델 삭제 성공: ID={model_id}")
            else:
                print(f"베이스 모델 삭제 실패: ID={model_id} 없음")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"베이스 모델 삭제(ID={model_id}) 중 오류 발생: {e}")
    finally:
        if conn: conn.close()
    return success

def update_setting(setting_key: str, setting_value: str) -> bool:
    """system_settings 테이블에서 특정 키의 값을 업데이트합니다."""
    conn = get_db_connection()
    if not conn: return False

    success = False
    try:
        with conn.cursor() as cur:
            # 현재 시간을 가져와 updated_at도 갱신
            cur.execute(
                """
                UPDATE system_settings
                SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
                WHERE setting_key = %s
                """,
                (setting_value, setting_key)
            )
            conn.commit() # 변경사항 저장
            # 업데이트가 성공했는지 확인 (영향받은 행 수 확인)
            if cur.rowcount > 0:
                success = True
                print(f"설정값 업데이트 성공: {setting_key} = {setting_value}")
            else:
                # 해당 키가 존재하지 않으면 rowcount가 0일 수 있음
                print(f"설정값 업데이트: 키 '{setting_key}'를 찾을 수 없거나 값이 동일하여 변경사항 없음.")
                # 키가 없는 경우 INSERT 하는 로직 추가 고려 가능 (UPSERT)
                # 여기서는 키가 이미 존재한다고 가정하고 UPDATE만 시도
                # 키가 없는 것도 성공으로 간주할지 여부 결정 필요 (여기서는 False 유지)

    except psycopg2.Error as e:
        conn.rollback()
        print(f"설정값 업데이트 중 오류 발생 (key={setting_key}): {e}")
    finally:
        if conn: conn.close()
    return success

# TODO: Add other CRUD functions for base_models (add, update, delete, get_by_id, get_all...)
# TODO: Add functions for users table (register, find_by_email...)
# TODO: Add functions for usage_tracking table (check_limit, increment_count...)
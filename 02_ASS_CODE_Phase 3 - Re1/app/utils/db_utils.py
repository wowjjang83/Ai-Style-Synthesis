# app/utils/db_utils.py
# 데이터베이스 상호작용 관련 유틸리티 함수 모음

import psycopg2
import os
from dotenv import load_dotenv
from datetime import date
import psycopg2.extras # 딕셔너리 커서 사용
from werkzeug.security import generate_password_hash, check_password_hash # 비밀번호 해싱

# .env 파일 로드 (DB 접속 정보 등 환경 변수 사용)
# 이 파일이 다른 모듈에서 import될 때도 환경 변수를 사용할 수 있도록 로드합니다.
load_dotenv()

# 데이터베이스 연결 정보 가져오기
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

# --- 데이터베이스 연결 함수 ---
def get_db_connection(use_dict_cursor=False):
    """
    데이터베이스 연결 객체를 반환합니다.

    Args:
        use_dict_cursor (bool): True로 설정하면 결과를 딕셔너리 형태로 반환하는 커서를 사용합니다.

    Returns:
        psycopg2.connection or None: 성공 시 연결 객체, 실패 시 None
    """
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
            print("[DB Connection] DictCursor 사용")
        else:
            print("[DB Connection] Standard Cursor 사용")
        print(f"[DB Connection] 데이터베이스 '{db_name}' 연결 성공 ({db_host}:{db_port})")
        return conn
    except psycopg2.Error as e:
        print(f"[DB Connection] 데이터베이스 연결 실패: {e}")
        return None
    except Exception as e:
        print(f"[DB Connection] 예상치 못한 오류 발생: {e}")
        return None

# --- 시스템 설정 (system_settings) 관련 함수 ---
def get_setting(setting_key: str) -> str | None:
    """
    system_settings 테이블에서 특정 키(setting_key)에 해당하는 값을 조회합니다.

    Args:
        setting_key (str): 조회할 설정 키

    Returns:
        str or None: 설정 값 (문자열), 키가 없거나 오류 발생 시 None
    """
    conn = get_db_connection()
    if not conn:
        return None

    value = None
    try:
        # 기본 커서 사용 (값 하나만 필요)
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = %s", (setting_key,))
            result = cur.fetchone()
            if result:
                value = result[0]
                print(f"[DB Get Setting] 성공: {setting_key} = '{value}'")
            else:
                print(f"[DB Get Setting] 실패: 키 '{setting_key}' 없음")
    except psycopg2.Error as e:
        print(f"[DB Get Setting] 오류 발생 (key={setting_key}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (get_setting)")
    return value

def update_setting(setting_key: str, setting_value: str) -> bool:
    """
    system_settings 테이블에서 특정 키(setting_key)의 값을 업데이트합니다.
    키가 존재하지 않으면 업데이트되지 않습니다. (UPSERT는 구현되지 않음)

    Args:
        setting_key (str): 업데이트할 설정 키
        setting_value (str): 새로운 설정 값

    Returns:
        bool: 업데이트 성공 시 True, 실패 시 False
    """
    conn = get_db_connection()
    if not conn: return False

    success = False
    try:
        with conn.cursor() as cur:
            # updated_at 컬럼도 현재 시간으로 갱신
            cur.execute(
                """
                UPDATE system_settings
                SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
                WHERE setting_key = %s
                """,
                (setting_value, setting_key)
            )
            conn.commit() # 변경사항 저장!

            # 업데이트된 행의 수 확인
            if cur.rowcount > 0:
                success = True
                print(f"[DB Update Setting] 성공: {setting_key} = '{setting_value}'")
            else:
                # 키가 없거나 값이 동일하여 변경되지 않은 경우
                print(f"[DB Update Setting] 실패 또는 변경 없음: 키 '{setting_key}'")
    except psycopg2.Error as e:
        conn.rollback() # 오류 발생 시 롤백
        print(f"[DB Update Setting] 오류 발생 (key={setting_key}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (update_setting)")
    return success

# --- 베이스 모델 (base_models) 관련 함수 ---
def get_active_base_model() -> dict | None:
    """
    활성화된(is_active=True) 베이스 모델 정보를 딕셔너리로 반환합니다.
    활성화된 모델이 여러 개일 경우 ID가 가장 큰 (최신) 모델을 반환합니다.

    Returns:
        dict or None: 활성 베이스 모델 정보 (딕셔너리), 없거나 오류 시 None
    """
    # 결과를 딕셔너리로 받기 위해 DictCursor 사용
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None

    model_data = None
    try:
        with conn.cursor() as cur:
            # is_active=True 조건 추가 및 ORDER BY id DESC 로 최신 모델 우선 조회
            cur.execute("SELECT * FROM base_models WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
            result = cur.fetchone() # DictRow 객체 또는 None 반환
            if result:
                model_data = dict(result) # DictRow를 일반 딕셔너리로 변환
                print(f"[DB Get Active Model] 성공: ID={model_data.get('id')}, Name={model_data.get('name')}")
            else:
                print("[DB Get Active Model] 활성 베이스 모델 없음")
    except psycopg2.Error as e:
        print(f"[DB Get Active Model] 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (get_active_base_model)")
    return model_data

def add_base_model(name: str, image_url: str, prompt: str = None, is_active: bool = False) -> dict | None:
    """
    새로운 베이스 모델을 base_models 테이블에 추가합니다.

    Args:
        name (str): 모델 이름
        image_url (str): 모델 이미지 URL 또는 파일 경로
        prompt (str, optional): 모델 생성에 사용된 프롬프트. Defaults to None.
        is_active (bool, optional): 활성화 여부. Defaults to False.

    Returns:
        dict or None: 추가된 모델 정보 (딕셔너리), 실패 시 None
    """
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None

    new_model_data = None
    try:
        with conn.cursor() as cur:
            # 만약 is_active=True로 추가하는 경우, 기존 활성 모델 비활성화 (선택적)
            if is_active:
                print("[DB Add Model] 신규 모델 활성화 시, 기존 모델 비활성화 시도...")
                cur.execute("UPDATE base_models SET is_active = FALSE WHERE is_active = TRUE")
                print("[DB Add Model] 기존 모델 비활성화 완료.")

            cur.execute(
                """
                INSERT INTO base_models (name, image_url, prompt, is_active)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
                """,
                (name, image_url, prompt, is_active)
            )
            conn.commit()
            result = cur.fetchone()
            if result:
                new_model_data = dict(result)
                print(f"[DB Add Model] 성공: ID={new_model_data.get('id')}, Name={new_model_data.get('name')}")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Add Model] 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (add_base_model)")
    return new_model_data

def get_base_model_by_id(model_id: int) -> dict | None:
    """
    ID로 특정 베이스 모델 정보를 조회합니다.

    Args:
        model_id (int): 조회할 모델의 ID

    Returns:
        dict or None: 모델 정보 (딕셔너리), 없거나 오류 시 None
    """
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None

    model_data = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM base_models WHERE id = %s", (model_id,))
            result = cur.fetchone()
            if result:
                model_data = dict(result)
                print(f"[DB Get Model By ID] 성공 (ID={model_id})")
            else:
                print(f"[DB Get Model By ID] 실패: ID={model_id} 없음")
    except psycopg2.Error as e:
        print(f"[DB Get Model By ID] 오류 발생 (ID={model_id}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (get_base_model_by_id)")
    return model_data

def get_all_base_models() -> list[dict]:
    """
    모든 베이스 모델 목록을 리스트 형태로 반환합니다. (ID 오름차순 정렬)

    Returns:
        list[dict]: 모델 정보 딕셔너리의 리스트, 오류 시 빈 리스트
    """
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return []

    models = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM base_models ORDER BY id ASC")
            results = cur.fetchall()
            models = [dict(row) for row in results]
            print(f"[DB Get All Models] 성공: {len(models)}개 조회")
    except psycopg2.Error as e:
        print(f"[DB Get All Models] 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (get_all_base_models)")
    return models

def update_base_model(model_id: int, name: str = None, image_url: str = None, prompt: str = None, is_active: bool = None) -> dict | None:
    """
    지정된 ID의 베이스 모델 정보를 업데이트합니다.
    업데이트할 필드만 인자로 전달합니다.

    Args:
        model_id (int): 업데이트할 모델의 ID
        name (str, optional): 새 이름. Defaults to None.
        image_url (str, optional): 새 이미지 URL. Defaults to None.
        prompt (str, optional): 새 프롬프트. Defaults to None.
        is_active (bool, optional): 새 활성화 상태. Defaults to None.

    Returns:
        dict or None: 업데이트된 모델 정보 (딕셔너리), 실패 시 None
    """
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
        print(f"[DB Update Model] 경고: 업데이트할 필드가 없습니다 (ID={model_id}).")
        # 변경할 필드가 없으면 현재 정보 조회 후 반환 (선택적)
        return get_base_model_by_id(model_id)

    values.append(model_id) # WHERE 절을 위한 ID 추가

    try:
        with conn.cursor() as cur:
            # 만약 is_active를 True로 설정하는 경우, 다른 모든 모델을 False로 변경
            if is_active is True:
                print(f"[DB Update Model] ID={model_id} 활성화 시, 다른 모델 비활성화 시도...")
                # model_id와 다른 모델들의 is_active를 False로 설정
                cur.execute("UPDATE base_models SET is_active = FALSE WHERE id != %s AND is_active = TRUE", (model_id,))
                print("[DB Update Model] 다른 모델 비활성화 완료.")

            # 실제 업데이트 쿼리 실행
            query = f"UPDATE base_models SET {', '.join(fields_to_update)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING *"
            cur.execute(query, tuple(values))
            conn.commit()

            result = cur.fetchone()
            if result:
                updated_model_data = dict(result)
                print(f"[DB Update Model] 성공: ID={model_id}")
            else:
                # ID가 존재하지 않는 경우 등
                print(f"[DB Update Model] 실패: ID={model_id} 없음 (또는 변경사항 없음)")

    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Update Model] 오류 발생 (ID={model_id}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (update_base_model)")
    return updated_model_data

def delete_base_model(model_id: int) -> bool:
    """
    ID로 베이스 모델을 삭제합니다.

    Args:
        model_id (int): 삭제할 모델의 ID

    Returns:
        bool: 삭제 성공 시 True, 실패 시 False
    """
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
                print(f"[DB Delete Model] 성공: ID={model_id}")
            else:
                print(f"[DB Delete Model] 실패: ID={model_id} 없음")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Delete Model] 오류 발생 (ID={model_id}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (delete_base_model)")
    return success

# --- 사용자 (users) 관련 함수 ---
def find_user_by_email(email: str) -> dict | None:
    """
    이메일 주소로 사용자를 찾아 사용자 정보를 딕셔너리로 반환합니다.
    (비밀번호 해시 포함)

    Args:
        email (str): 찾을 사용자의 이메일

    Returns:
        dict or None: 사용자 정보 (딕셔너리), 없거나 오류 시 None
    """
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None

    user_data = None
    try:
        with conn.cursor() as cur:
            # 비밀번호 해시도 함께 조회
            cur.execute("SELECT id, email, password_hash, role, created_at FROM users WHERE email = %s", (email,))
            result = cur.fetchone()
            if result:
                user_data = dict(result)
                print(f"[DB Find User] 성공: Email={email}")
            else:
                 print(f"[DB Find User] 실패: Email={email} 없음")
    except psycopg2.Error as e:
        print(f"[DB Find User] 오류 발생 (Email={email}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (find_user_by_email)")
    return user_data

def add_user(email: str, password: str, role: str = 'USER') -> dict | None:
    """
    새로운 사용자를 users 테이블에 추가합니다. 비밀번호는 해싱하여 저장합니다.

    Args:
        email (str): 새 사용자의 이메일 (로그인 ID)
        password (str): 새 사용자의 비밀번호 (평문)
        role (str, optional): 사용자 역할. Defaults to 'USER'.

    Returns:
        dict or None: 성공 시 추가된 사용자 정보 (id, email, role, created_at),
                      이메일 중복 시 {"error": "Email already exists"},
                      기타 오류 시 None
    """
    conn = get_db_connection(use_dict_cursor=True)
    if not conn: return None

    # 비밀번호 해싱
    try:
        password_hash = generate_password_hash(password)
        print(f"[DB Add User] 비밀번호 해싱 완료 (Email: {email})")
    except Exception as e:
        print(f"[DB Add User] 비밀번호 해싱 중 오류 발생: {e}")
        if conn: conn.close()
        return None # 해싱 실패 시 사용자 추가 불가

    new_user_data = None
    try:
        with conn.cursor() as cur:
            # INSERT 시 RETURNING 절을 사용하여 추가된 정보 바로 받기
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, %s)
                RETURNING id, email, role, created_at;
                """,
                (email, password_hash, role)
            )
            conn.commit() # 데이터베이스 변경사항 저장!
            result = cur.fetchone()
            if result:
                new_user_data = dict(result)
                print(f"[DB Add User] 성공: Email={email}, Role={role}")
            else: # RETURNING 사용 시 이 경우는 거의 발생하지 않음
                 print(f"[DB Add User] 실패 (INSERT 후 결과 없음): Email={email}")

    except psycopg2.IntegrityError as e: # 주로 UNIQUE 제약조건 위반 (이메일 중복) 시 발생
        conn.rollback() # 오류 발생 시 트랜잭션 롤백
        print(f"[DB Add User] 실패 (이메일 중복 가능성): Email={email}, 오류: {e}")
        # 이메일 중복 시 특정 에러 메시지 반환
        return {"error": "Email already exists"}
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Add User] DB 오류 발생: Email={email}, 오류: {e}")
        return None # 일반 DB 오류
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (add_user)")

    return new_user_data

# --- 비밀번호 확인 함수 ---
def check_user_password(hashed_password: str, provided_password: str) -> bool:
    """
    저장된 해시 비밀번호와 사용자가 입력한 비밀번호(평문)를 비교합니다.

    Args:
        hashed_password (str): DB에 저장된 비밀번호 해시
        provided_password (str): 사용자가 입력한 비밀번호 (평문)

    Returns:
        bool: 비밀번호 일치 시 True, 불일치 시 False
    """
    try:
        return check_password_hash(hashed_password, provided_password)
    except Exception as e:
        print(f"[Check Password] 비밀번호 확인 중 오류 발생: {e}")
        return False

# --- 사용량 추적 (usage_tracking) 관련 함수 ---
def get_todays_usage(user_id: int) -> int:
    """
    usage_tracking 테이블에서 특정 사용자의 오늘 날짜(usage_date) 사용 횟수(count)를 조회합니다.

    Args:
        user_id (int): 조회할 사용자의 ID

    Returns:
        int: 오늘 사용 횟수. 기록이 없거나 오류 시 0 반환.
    """
    conn = get_db_connection()
    if not conn: return 0 # 연결 실패 시 0 반환

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
                print(f"[DB Get Usage] 성공: User ID={user_id}, Date={today}, Count={count}")
            else:
                # 오늘 사용 기록이 없는 경우 count는 0 유지
                print(f"[DB Get Usage] 오늘 사용 기록 없음 (User ID={user_id}, Date={today})")
    except psycopg2.Error as e:
        print(f"[DB Get Usage] 오류 발생 (User ID={user_id}, Date={today}): {e}")
        # 오류 발생 시에도 0 반환 (또는 예외 처리 방식 변경 가능)
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (get_todays_usage)")
    return count

def increment_usage(user_id: int) -> bool:
    """
    usage_tracking 테이블에서 특정 사용자의 오늘 날짜(usage_date) 사용 횟수(count)를 1 증가시킵니다.
    오늘 날짜의 기록이 없으면 새로 생성하고 count를 1로 설정합니다. (UPSERT 기능)

    Args:
        user_id (int): 사용량을 증가시킬 사용자의 ID

    Returns:
        bool: 작업 성공 시 True, 실패 시 False
    """
    conn = get_db_connection()
    if not conn: return False

    success = False
    today = date.today()
    try:
        with conn.cursor() as cur:
            # ON CONFLICT ... DO UPDATE 구문을 사용하여 UPSERT 구현 (PostgreSQL 9.5 이상)
            # user_id와 usage_date가 충돌하면 (이미 존재하면) count를 1 증가시키고 last_attempt_at 갱신
            # 존재하지 않으면 새로 INSERT (count=1)
            cur.execute(
                """
                INSERT INTO usage_tracking (user_id, usage_date, count, last_attempt_at)
                VALUES (%s, %s, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, usage_date)
                DO UPDATE SET
                    count = usage_tracking.count + 1,
                    last_attempt_at = CURRENT_TIMESTAMP;
                """,
                (user_id, today)
            )
            conn.commit() # 변경사항 저장
            success = True
            print(f"[DB Increment Usage] 성공: User ID={user_id}, Date={today}")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Increment Usage] 오류 발생 (User ID={user_id}, Date={today}): {e}")
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (increment_usage)")
    return success

# --- 추가: 특정 날짜의 총 사용량 조회 함수 ---
def get_total_usage_for_date(usage_date: date) -> int:
    """
    usage_tracking 테이블에서 특정 날짜(usage_date)의 모든 사용자 사용 횟수 총합을 조회합니다.

    Args:
        usage_date (date): 조회할 날짜

    Returns:
        int: 해당 날짜의 총 사용 횟수. 기록이 없거나 오류 시 0 반환.
    """
    conn = get_db_connection()
    if not conn: return 0 # 연결 실패 시 0 반환

    total_count = 0
    try:
        with conn.cursor() as cur:
            # SUM() 집계 함수 사용, 결과가 NULL일 경우 COALESCE로 0 반환
            cur.execute(
                "SELECT COALESCE(SUM(count), 0) FROM usage_tracking WHERE usage_date = %s",
                (usage_date,)
            )
            result = cur.fetchone()
            if result:
                total_count = result[0]
                print(f"[DB Get Total Usage] 성공: Date={usage_date}, Total Count={total_count}")
            # 결과가 없어도 COALESCE 덕분에 0이 반환됨
    except psycopg2.Error as e:
        print(f"[DB Get Total Usage] 오류 발생 (Date={usage_date}): {e}")
        # 오류 발생 시에도 0 반환 (또는 예외 처리 방식 변경 가능)
    finally:
        if conn:
            conn.close()
            # print("[DB Connection] 연결 종료 (get_total_usage_for_date)")
    return total_count

# --- 추가적인 유틸리티 함수 (필요시) ---
# 예: 특정 역할(role)을 가진 사용자 목록 조회 등



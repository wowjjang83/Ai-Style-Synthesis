-- 사용자 테이블
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 기본 모델 테이블
CREATE TABLE base_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    image_url VARCHAR(1024) NOT NULL, -- 이미지 저장 방식에 따라 달라질 수 있음
    prompt TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 시스템 설정 테이블 (Key-Value 방식)
CREATE TABLE system_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value VARCHAR(1024),
    description TEXT, -- 설정 설명 (선택적)
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 기본 설정값 예시 (필요시 추가/수정)
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('apply_watermark', 'false', '결과 이미지에 워터마크 적용 여부 (true/false)'),
('max_system_syntheses', '1000', '시스템 전체 일일 최대 합성 횟수'),
('max_user_syntheses', '3', '사용자별 일일 최대 합성 횟수'),
('active_background_mood', 'STUDIO', '합성 시 기본 배경/분위기 옵션');


-- 사용량 추적 테이블 (사용자별 일일 카운트)
CREATE TABLE usage_tracking (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, usage_date) -- 사용자 ID와 날짜 조합을 기본 키로 사용
);

-- 테이블 생성 확인용 (선택적)
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
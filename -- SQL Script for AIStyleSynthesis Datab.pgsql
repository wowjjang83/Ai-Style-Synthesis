-- SQL Script for AIStyleSynthesis Database Setup (PostgreSQL)

-- Optional: Drop the existing database if you want a clean start.
-- WARNING: This will permanently delete all data in the ass_db database!
-- Uncomment the following lines only if you are sure.
-- DROP DATABASE IF EXISTS ass_db;

-- Optional: Create the database if it doesn't exist.
-- It's often better to create the database manually via your tool or command line first.
-- CREATE DATABASE ass_db;

-- Connect to the ass_db database before running the rest of the script.
-- Example in psql: \c ass_db

-- 테이블삭제 -- 초기화
--drop table base_models;
--drop table system_settings;
--drop table usage_tracking;
--drop table users;

-- Create the 'users' table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,                      -- 사용자 고유 ID (자동 증가)
    email VARCHAR(255) NOT NULL UNIQUE,         -- 사용자 이메일 (로그인 ID, 중복 불가)
    password_hash VARCHAR(255) NOT NULL,        -- 해싱된 사용자 비밀번호
    role VARCHAR(50) NOT NULL DEFAULT 'USER',   -- 사용자 역할 ('USER', 'ADMIN' 등)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- 생성 시각
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  -- 마지막 수정 시각
);

-- Add index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- Comment on table and columns for clarity
COMMENT ON TABLE users IS '사용자 정보를 저장하는 테이블';
COMMENT ON COLUMN users.email IS '사용자 이메일 (로그인 ID, 중복 불가)';
COMMENT ON COLUMN users.password_hash IS '해싱된 사용자 비밀번호';
COMMENT ON COLUMN users.role IS '사용자 역할 (USER, ADMIN 등)';

-- Create the 'base_models' table
CREATE TABLE IF NOT EXISTS base_models (
    id SERIAL PRIMARY KEY,                      -- 베이스 모델 고유 ID (자동 증가)
    name VARCHAR(255) NOT NULL,                 -- 모델 이름
    image_url TEXT NOT NULL,                    -- 모델 이미지 URL 또는 서버 경로
    prompt TEXT,                                -- 모델 생성에 사용된 프롬프트 (선택 사항)
    is_active BOOLEAN NOT NULL DEFAULT FALSE,   -- 현재 활성화된 모델인지 여부
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- 생성 시각
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  -- 마지막 수정 시각
);

-- Comment on table and columns
COMMENT ON TABLE base_models IS 'AI 합성에 사용될 베이스 모델 정보';
COMMENT ON COLUMN base_models.image_url IS '모델 이미지 URL 또는 서버 내 파일 경로';
COMMENT ON COLUMN base_models.is_active IS '현재 사용자들이 합성 시 사용할 모델인지 여부';

-- Create the 'system_settings' table
-- Using setting_key as PRIMARY KEY for simplicity, assuming few settings.
CREATE TABLE IF NOT EXISTS system_settings (
    setting_key VARCHAR(100) PRIMARY KEY,       -- 설정 키 (예: 'max_user_syntheses')
    setting_value TEXT NOT NULL,                -- 설정 값 (문자열로 저장)
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- 마지막 수정 시각
);

-- Comment on table and columns
COMMENT ON TABLE system_settings IS '시스템 전반의 설정을 저장하는 테이블';
COMMENT ON COLUMN system_settings.setting_key IS '설정 항목의 고유 키';
COMMENT ON COLUMN system_settings.setting_value IS '설정 값 (데이터 타입에 맞게 애플리케이션에서 변환 필요)';

-- Insert default system settings
-- Use INSERT ... ON CONFLICT ... DO UPDATE to avoid errors if keys already exist
INSERT INTO system_settings (setting_key, setting_value) VALUES
    ('max_user_syntheses', '3'), -- 사용자별 일일 최대 합성 횟수 기본값
    ('apply_watermark', 'false') -- 워터마크 적용 여부 기본값 (문자열 'false')
ON CONFLICT (setting_key) DO UPDATE SET
    setting_value = EXCLUDED.setting_value,
    updated_at = CURRENT_TIMESTAMP;

-- Create the 'usage_tracking' table
CREATE TABLE IF NOT EXISTS usage_tracking (
    id SERIAL PRIMARY KEY,                      -- 추적 기록 고유 ID (자동 증가)
    user_id INTEGER NOT NULL,                   -- 사용자 ID (users 테이블 참조)
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE, -- 사용 날짜
    count INTEGER NOT NULL DEFAULT 1,           -- 해당 날짜의 사용 횟수
    last_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- 마지막 시도 시각

    -- Foreign Key constraint referencing the users table
    CONSTRAINT fk_user
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE, -- 사용자가 삭제되면 관련 사용량 기록도 삭제 (정책에 따라 변경 가능: RESTRICT, SET NULL 등)

    -- Ensure a user has only one record per day
    CONSTRAINT unique_user_date UNIQUE (user_id, usage_date)
);

-- Add indexes for faster queries on usage_tracking
CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_id ON usage_tracking (user_id);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_usage_date ON usage_tracking (usage_date);

-- Comment on table and columns
COMMENT ON TABLE usage_tracking IS '사용자별 일일 API 사용량을 추적하는 테이블';
COMMENT ON COLUMN usage_tracking.user_id IS '사용자 ID (users 테이블 참조)';
COMMENT ON COLUMN usage_tracking.usage_date IS '사용 날짜';
COMMENT ON COLUMN usage_tracking.count IS '해당 사용자의 해당 날짜 사용(시도) 횟수';
COMMENT ON COLUMN usage_tracking.last_attempt_at IS '해당 날짜의 마지막 시도 시각';


-- Function to automatically update 'updated_at' timestamp on users table
-- (Optional but good practice)
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for 'users' table
DROP TRIGGER IF EXISTS set_timestamp_users ON users; -- Drop existing trigger first if needed
CREATE TRIGGER set_timestamp_users
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- Trigger for 'base_models' table
DROP TRIGGER IF EXISTS set_timestamp_base_models ON base_models;
CREATE TRIGGER set_timestamp_base_models
BEFORE UPDATE ON base_models
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- Trigger for 'system_settings' table (already handled in query)
-- Note: The trigger for system_settings is not strictly necessary
-- if updated_at is always set manually in the UPDATE query like in db_utils.py.
-- However, adding it provides consistency.
-- DROP TRIGGER IF EXISTS set_timestamp_system_settings ON system_settings;
-- CREATE TRIGGER set_timestamp_system_settings
-- BEFORE UPDATE ON system_settings
-- FOR EACH ROW
-- EXECUTE FUNCTION trigger_set_timestamp();


-- Grant privileges if necessary (replace 'your_app_user' with the actual user)
-- GRANT ALL PRIVILEGES ON DATABASE ass_db TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

-- End of script

-- 테이블 항목 전체삭제
-- delete from base_models;

-- 테이블 항목삭제
-- delete from base_models where id=1;

-- 예시: 베이스 모델 추가 및 활성화
INSERT INTO base_models (name, image_url, is_active, prompt) VALUES
('기본 여성 모델', '/app/static/images/base_image.jpg', TRUE, 'A photo of a young korean woman');
-- '/path/to/your/base_image.jpg' 부분은 실제 이미지 파일의 **유효한 경로 또는 URL**로 반드시 변경해야 합니다!
-- 로컬 파일 경로를 사용하는 경우, Flask 애플리케이션이 해당 파일에 접근할 수 있어야 합니다.

-- 항목 업데이트(수정)
UPDATE base_models SET image_url = '/static/images/base_model.jpg' WHERE id = 2;
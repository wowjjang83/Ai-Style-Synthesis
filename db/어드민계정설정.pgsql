-- 예시: 'admin@example.com' 사용자에게 관리자 권한 부여
UPDATE users
SET role = 'ADMIN'
WHERE email = 'test@test.com';

# 워터마크 비활성화
# UPDATE system_settings SET setting_value = 'false' WHERE setting_key = 'apply_watermark';

# 워터마크 활성화
# UPDATE system_settings SET setting_value = 'true' WHERE setting_key = 'apply_watermark';

# 최대 합성횟수
UPDATE system_settings SET setting_value = 1000 WHERE setting_key = 'max_user_syntheses';

# 워터마크 비활성화
# UPDATE system_settings SET setting_value = 'false' WHERE setting_key = 'apply_watermark';

# 워터마크 활성화
# UPDATE system_settings SET setting_value = 'true' WHERE setting_key = 'apply_watermark';

# 카운트 초기화
UPDATE usage_tracking SET count = 0 WHERE user_id = 2;

# delete users set id='1'
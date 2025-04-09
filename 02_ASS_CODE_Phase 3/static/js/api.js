// static/js/api.js

const API_BASE_URL = ''; // 백엔드 API 기본 URL (Flask 서버 주소, 로컬이면 보통 비워둠)

/**
 * 백엔드 API 호출을 위한 기본 fetch 함수
 * @param {string} endpoint - 호출할 API 엔드포인트 (예: '/login')
 * @param {string} method - HTTP 메소드 ('GET', 'POST', 'PUT', 'DELETE' 등)
 * @param {object} [body=null] - 요청 본문 (POST, PUT 등)
 * @param {boolean} [requiresAuth=false] - 인증이 필요한 요청인지 여부 (향후 사용)
 * @returns {Promise<object>} - API 응답 Promise
 */
async function callApi(endpoint, method = 'GET', body = null, requiresAuth = false) {
    const url = `${API_BASE_URL}${endpoint}`;
    const options = {
        method: method,
        headers: {
            // 'Content-Type': 'application/json' // body가 있을 때만 설정하는 것이 더 안전할 수 있음
        },
        // credentials: 'include' // 다른 도메인으로 요청 시 쿠키 전송 필요시 사용 (현재는 같은 origin이라 불필요)
    };

    if (body) {
        // body가 객체면 JSON으로, FormData면 그대로 전송 (파일 업로드 등 대비)
        if (body instanceof FormData) {
            // FormData의 경우 Content-Type 헤더를 설정하지 않아야 브라우저가 자동으로 설정함
            options.body = body;
        } else {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }
    }

    console.log(`Calling API: ${method} ${url}`, options.body instanceof FormData ? '[FormData]' : options.body); // 디버깅 로그 (FormData는 내용 로깅 생략)

    try {
        const response = await fetch(url, options);
        // 응답 본문이 없을 수 있는 경우 (예: 204 No Content) 또는 JSON이 아닌 경우 처리
        const contentType = response.headers.get("content-type");
        let data;
        if (contentType && contentType.indexOf("application/json") !== -1) {
            data = await response.json(); // 응답을 JSON으로 파싱
        } else {
            // JSON이 아닌 경우 텍스트로 읽거나, 상태 코드로만 판단
            data = { success: response.ok, status: response.status, message: await response.text() }; // 임시 구조
            // 204 No Content 같이 성공이지만 본문 없는 경우도 data는 이 구조를 따름
            if (response.ok && !data.message) {
                data.message = `Operation successful with status ${response.status}`;
            }
        }


        if (!response.ok) {
            // API 에러 처리 (예: 4xx, 5xx 상태 코드)
            // 서버에서 { "message": "에러 내용" } 형태로 응답한다고 가정
            const errorMessage = data?.message || `HTTP error! status: ${response.status}`;
            console.error(`API Error (${response.status}):`, errorMessage);
            throw new Error(errorMessage);
        }

        console.log(`API Response (${method} ${url}):`, data); // 디버깅 로그
        // 성공 응답에 'success' 필드가 없다면, response.ok 기준으로 추가해주는 것이 일관성에 좋음
        if (data.success === undefined) {
             data.success = true;
        }
        return data; // 성공 시 파싱된 데이터 반환 (또는 생성된 데이터 구조)

    } catch (error) {
        console.error(`Network or processing error calling ${method} ${url}:`, error);
        // 네트워크 오류나 JSON 파싱 오류 등 처리
        // error.message 를 그대로 사용하거나, 좀 더 사용자 친화적인 메시지로 변환
        throw new Error(error.message || 'An unexpected error occurred.');
    }
}

// --- 인증 관련 API 함수 ---

/**
 * 사용자 로그인
 * @param {string} email
 * @param {string} password
 * @returns {Promise<object>} 로그인 결과 (성공 시 사용자 정보 또는 성공 메시지 포함)
 */
async function loginUser(email, password) {
    // 실제 백엔드 /login API 호출 (POST) [source: 105, 36]
    return callApi('/login', 'POST', { email, password });
}

/**
 * 사용자 회원가입
 * @param {string} email
 * @param {string} password
 * @returns {Promise<object>} 회원가입 결과
 */
async function registerUser(email, password) {
    // 실제 백엔드 /register API 호출 (POST) [source: 104, 36]
    return callApi('/register', 'POST', { email, password });
}

/**
 * 사용자 로그아웃
 * @returns {Promise<object>} 로그아웃 결과
 */
async function logoutUser() {
    // 실제 백엔드 /logout API 호출 (POST) [source: 106, 36]
    // 로그아웃은 보통 요청 본문(body) 없이 세션 쿠키만으로 처리됨
    return callApi('/logout', 'POST');
}


/**
 * 현재 로그인된 사용자 정보 가져오기
 * @returns {Promise<object>} 사용자 정보 (email, remaining_attempts)
 */
async function getUserInfo() {
    // 실제 백엔드 /me API 호출 (GET)
    return callApi('/me', 'GET', null, true); // requiresAuth = true (세션 쿠키 필요)
}

/**
 * 현재 활성화된 기본 모델 정보 가져오기
 * @returns {Promise<object>} 활성 모델 정보 (id, name, image_url)
 */
async function getActiveBaseModel() {
    // 실제 백엔드 /api/base_model/active API 호출 (GET)
    return callApi('/api/base_model/active', 'GET', null, true); // requiresAuth = true
}

/**
 * 이미지 합성 요청 (파일 업로드 포함)
 * @param {string} itemType - 아이템 종류 (예: 'top', 'hair')
 * @param {File} itemFile - 사용자가 업로드한 아이템 이미지 파일 객체
 * @returns {Promise<object>} 합성 결과 (result_image_url, watermarked)
 */
async function synthesizeImage(itemType, itemFile) {
    // FormData 객체 생성
    const formData = new FormData();
    formData.append('item_type', itemType);
    formData.append('item_image', itemFile); // 파일 객체 직접 추가

    // 실제 백엔드 /synthesize/web API 호출 (POST, FormData 사용)
    // callApi 함수는 FormData를 처리하도록 이미 수정됨
    return callApi('/synthesize/web', 'POST', formData, true); // requiresAuth = true
}


console.log("api.js loaded (with user/model/synthesize API calls)"); // 스크립트 로딩 확인용
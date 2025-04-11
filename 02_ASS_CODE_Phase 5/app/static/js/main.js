// app/static/js/main.js

// 프론트엔드 JavaScript 로직을 작성합니다.
// 예: DOM 조작, 이벤트 처리, API 호출 등

// 페이지 로드 시 실행할 초기화 코드
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM fully loaded and parsed');

    // TODO: 합성 페이지 관련 초기화 (web.html의 인라인 스크립트 이전)
    // initSynthesisPage();

    // TODO: 로그인/회원가입 페이지 관련 초기화
    // initAuthPage();
});

// --- 함수 정의 ---

// 예시: 합성 페이지 초기화 함수
function initSynthesisPage() {
    // web.html에 있던 요소들에 대한 이벤트 리스너 설정 등
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('item-image-upload');
    // ... 기타 요소들 ...

    if (uploadArea && fileInput /* && other elements */) {
        console.log('Initializing synthesis page elements...');
        // uploadArea.addEventListener('click', () => fileInput.click());
        // fileInput.addEventListener('change', handleFileSelect);
        // ... 기타 이벤트 리스너 ...
    }
}

// 예시: 인증 페이지 초기화 함수
function initAuthPage() {
    // 로그인 또는 회원가입 폼 관련 로직
    const loginForm = document.getElementById('login-form'); // 예시 ID
    if (loginForm) {
        console.log('Initializing login page elements...');
        // loginForm.addEventListener('submit', handleLoginSubmit);
    }
    // ...
}

// --- API 호출 함수 (예시) ---
async function synthesizeImageAPI(formData) {
    try {
        const response = await fetch('/synthesize/web', {
            method: 'POST',
            body: formData,
            // headers: { 'X-CSRFToken': '...' } // CSRF 토큰 필요 시 추가
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: '서버 응답 오류' }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }

        return await response.json(); // 성공 시 JSON 결과 반환
    } catch (error) {
        console.error('API Call Error:', error);
        throw error; // 오류를 다시 던져 호출한 쪽에서 처리하도록 함
    }
}

// --- 기타 헬퍼 함수 ---

// 예: 오류 메시지 표시 함수
function displayErrorMessage(message) {
    const errorArea = document.getElementById('error-message-area');
    const errorContent = document.getElementById('error-message-content');
    if (errorArea && errorContent) {
        errorContent.textContent = message;
        errorArea.classList.remove('hidden');
    }
}

// 예: 오류 메시지 숨김 함수
function hideErrorMessage() {
     const errorArea = document.getElementById('error-message-area');
     if (errorArea) {
         errorArea.classList.add('hidden');
     }
}

// --- 이벤트 핸들러 함수 (web.html에서 이전 필요) ---
// function handleFileSelect(event) { ... }
// function handleDragOver(event) { ... }
// function handleDragLeave(event) { ... }
// function handleDrop(event) { ... }
// function displayPreview(file) { ... }
// function removeImage() { ... }
// async function handleSynthesize() { ... }


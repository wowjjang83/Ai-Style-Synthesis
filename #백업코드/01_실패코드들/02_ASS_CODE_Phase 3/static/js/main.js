// static/js/main.js

console.log("main.js loaded");

// --- DOM 요소 참조 ---
const userInfoSpan = document.getElementById('user-info');
const baseModelImage = document.getElementById('base-model-image');
const itemTypeSelect = document.getElementById('item-type');
const itemUploadInput = document.getElementById('item-upload');
const itemUrlInput = document.getElementById('item-url'); // URL 입력 (추후 사용)
const itemPreviewDiv = document.getElementById('item-preview');
const synthesizeButton = document.getElementById('synthesize-button');
const loadingIndicator = document.getElementById('loading-indicator');
const resultImage = document.getElementById('result-image');
const downloadButton = document.getElementById('download-button');
const generalErrorMessageDiv = document.createElement('div'); // 공통 에러 메시지 표시용
generalErrorMessageDiv.style.color = 'red';
generalErrorMessageDiv.style.marginTop = '10px';
// 에러 메시지를 표시할 적절한 위치에 추가 (예: synthesizeButton 다음)
synthesizeButton.parentNode.insertBefore(generalErrorMessageDiv, synthesizeButton.nextSibling);


// --- 상태 변수 ---
let selectedItemFile = null; // 사용자가 업로드한 파일 객체 저장

// --- 초기화 함수 ---
async function initializePage() {
    console.log("Initializing page...");
    try {
        // 1. 로그인 상태 확인 및 사용자 정보 로드
        const userInfo = await getUserInfo(); // api.js 함수 호출
        console.log("User info:", userInfo);
        if (userInfo && userInfo.success) {
            displayUserInfo(userInfo); // 사용자 정보 표시
        } else {
            // 로그인 안됨 -> 로그인 페이지로 리디렉션
            console.log("User not logged in or failed to get info. Redirecting to login.");
            window.location.href = 'login.html';
            return; // 리디렉션 후 함수 종료
        }

        // 2. 활성 기본 모델 로드
        await loadActiveBaseModel(); // api.js 함수 호출

        // 3. 이벤트 리스너 설정
        setupEventListeners();
        console.log("Page initialized successfully.");

    } catch (error) {
        console.error("Initialization failed:", error);
        // 페이지 초기화 실패 시 사용자에게 알림 (예: alert 또는 특정 영역에 메시지 표시)
        generalErrorMessageDiv.textContent = `페이지 초기화 실패: ${error.message}. 로그인이 필요할 수 있습니다.`;
        // 로그인 페이지로 보낼 수도 있음
        // window.location.href = 'login.html';
    }
}

// --- 헬퍼 함수 ---

// 사용자 정보 표시
function displayUserInfo(userInfo) {
    if (userInfoSpan) {
        // API 응답 구조에 맞춰 이메일과 남은 횟수를 안전하게 가져옵니다.
        const userEmail = userInfo.user?.email || '이메일 없음'; // userInfo 안의 user 객체 안의 email 접근 시도
        const remainingAttempts = userInfo.remaining_attempts !== undefined ? userInfo.remaining_attempts : '?'; // userInfo 에 remaining_attempts 가 있는지 확인

        userInfoSpan.textContent = `환영합니다, ${userEmail}! | 남은 횟수: ${remainingAttempts}`;

        // 로그아웃 버튼 추가 로직 (기존과 동일)
        if (!userInfoSpan.querySelector('button')) { // 버튼 중복 추가 방지
             const logoutButton = document.createElement('button');
             logoutButton.textContent = '로그아웃';
             logoutButton.style.marginLeft = '10px';
             logoutButton.onclick = handleLogoutClick;
             userInfoSpan.appendChild(logoutButton);
        }
    }
}

// 로그아웃 처리
async function handleLogoutClick() {
    try {
        await logoutUser(); // api.js 함수 호출
        alert('로그아웃 되었습니다.');
        window.location.href = 'login.html'; // 로그아웃 후 로그인 페이지로
    } catch (error) {
        console.error("Logout failed:", error);
        alert(`로그아웃 실패: ${error.message}`);
    }
}


// 활성 기본 모델 이미지 로드
async function loadActiveBaseModel() {
    try {
        const modelInfo = await getActiveBaseModel(); // api.js 함수 호출
        if (modelInfo && modelInfo.success && modelInfo.image_url) {
            baseModelImage.src = modelInfo.image_url;
            baseModelImage.alt = modelInfo.name || 'Active Base Model';
            console.log("Active base model loaded:", modelInfo.name);
        } else {
            console.error("Failed to load active base model:", modelInfo?.message);
            baseModelImage.alt = "기본 모델 로드 실패";
            // 기본 placeholder 이미지 유지 또는 에러 메시지 표시
            generalErrorMessageDiv.textContent = '활성 기본 모델 로드에 실패했습니다.';
        }
    } catch (error) {
        console.error("Error loading active base model:", error);
        baseModelImage.alt = "기본 모델 로드 중 오류 발생";
        generalErrorMessageDiv.textContent = `기본 모델 로드 중 오류: ${error.message}`;
    }
}

// 아이템 이미지 파일 업로드 처리 및 미리보기
function handleItemUpload(event) {
    const files = event.target.files;
    if (files.length > 0) {
        selectedItemFile = files[0]; // 파일 객체 저장
        console.log("Item file selected:", selectedItemFile.name, selectedItemFile.type);

        // 파일 타입 검증 (선택 사항 - 브라우저에서 제한 + 서버에서도 검증 필요)
        const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
        if (!allowedTypes.includes(selectedItemFile.type)) {
            alert('허용되지 않는 파일 형식입니다. (png, jpg, jpeg, webp)');
            selectedItemFile = null;
            itemUploadInput.value = ''; // 입력 필드 초기화
            itemPreviewDiv.innerHTML = ''; // 미리보기 제거
            return;
        }

        // 미리보기 생성
        const reader = new FileReader();
        reader.onload = function(e) {
            itemPreviewDiv.innerHTML = `<img src="${e.target.result}" alt="Item Preview" style="max-width: 100%; max-height: 150px; object-fit: contain;">`;
        }
        reader.readAsDataURL(selectedItemFile); // 파일을 Data URL로 읽음
        generalErrorMessageDiv.textContent = ''; // 이전 오류 메시지 제거

    } else {
        selectedItemFile = null;
        itemPreviewDiv.innerHTML = ''; // 파일 선택 취소 시 미리보기 제거
    }
}

// 합성 시작 처리
async function handleSynthesizeClick() {
    console.log("Synthesize button clicked.");
    generalErrorMessageDiv.textContent = ''; // 이전 오류 메시지 초기화

    // 1. 입력 값 확인
    const itemType = itemTypeSelect.value;
    if (!itemType) {
        alert("아이템 종류를 선택해주세요.");
        return;
    }
    if (!selectedItemFile) {
        alert("아이템 이미지 파일을 업로드해주세요.");
        return;
    }

    // 2. 로딩 상태 시작
    loadingIndicator.style.display = 'block';
    resultImage.style.display = 'none'; // 이전 결과 숨기기
    downloadButton.style.display = 'none';
    synthesizeButton.disabled = true; // 버튼 비활성화

    try {
        // 3. API 호출
        console.log(`Calling synthesizeImage with type: ${itemType}, file: ${selectedItemFile.name}`);
        const result = await synthesizeImage(itemType, selectedItemFile); // api.js 함수 호출
        console.log("Synthesis API result:", result);

        if (result && result.success && result.result_image_url) {
            // 4. 성공 처리
            resultImage.src = result.result_image_url;
            resultImage.style.display = 'block';
            downloadButton.style.display = 'inline-block'; // 다운로드 버튼 표시

            // 남은 횟수 업데이트
            const userInfo = await getUserInfo();
            if (userInfo && userInfo.success) {
                 displayUserInfo(userInfo); // 헤더 정보 업데이트
            }
        } else {
            // 5. 실패 처리
            throw new Error(result?.message || '합성 실패. 응답 형식이 올바르지 않습니다.');
        }

    } catch (error) {
        console.error("Synthesis failed:", error);
        generalErrorMessageDiv.textContent = `합성 실패: ${error.message}`;
        // 실패 시 결과 이미지 영역에 메시지 표시할 수도 있음
        // resultImage.style.display = 'none';
    } finally {
        // 6. 로딩 상태 종료
        loadingIndicator.style.display = 'none';
        synthesizeButton.disabled = false; // 버튼 다시 활성화
    }
}

// 결과 이미지 다운로드 처리
function handleDownloadClick() {
    const imageUrl = resultImage.src;
    if (!imageUrl || imageUrl.endsWith('placeholder_result.png')) { // placeholder 이미지 다운로드 방지
        alert("다운로드할 결과 이미지가 없습니다.");
        return;
    }

    const filename = `synthesized_${Date.now()}.png`; // 다운로드 파일명 (확장자는 실제 이미지 따라 변경 가능)

    // 임시 링크 생성 및 클릭하여 다운로드 트리거
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = filename;
    document.body.appendChild(link); // 링크를 DOM에 추가해야 Firefox 등에서 동작
    link.click();
    document.body.removeChild(link); // 사용 후 제거
    console.log(`Downloading image: ${filename}`);
}


// --- 이벤트 리스너 설정 ---
function setupEventListeners() {
    if (itemUploadInput) {
        itemUploadInput.addEventListener('change', handleItemUpload);
        console.log("File upload listener attached.");
    }
    // URL 입력 리스너 (추후 구현 시)
    // if (itemUrlInput) { ... }

    if (synthesizeButton) {
        synthesizeButton.addEventListener('click', handleSynthesizeClick);
        console.log("Synthesize button listener attached.");
    }
    if (downloadButton) {
        downloadButton.addEventListener('click', handleDownloadClick);
        console.log("Download button listener attached.");
    }
}

// --- 페이지 로드 시 초기화 함수 실행 ---
document.addEventListener('DOMContentLoaded', initializePage);
// static/js/auth.js

console.log("auth.js loaded"); // 스크립트 로딩 확인

// 로그인 폼 처리
const loginForm = document.getElementById('login-form');
if (loginForm) {
    console.log("Login form found.");
    const errorMessageElement = loginForm.querySelector('#error-message');

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // 폼 기본 제출 동작 방지
        console.log("Login form submitted.");
        errorMessageElement.textContent = ''; // 이전 오류 메시지 초기화

        const email = loginForm.querySelector('#email').value;
        const password = loginForm.querySelector('#password').value;

        if (!email || !password) {
            errorMessageElement.textContent = '이메일과 비밀번호를 모두 입력해주세요.';
            return;
        }

        try {
            console.log("Calling api.loginUser...");
            const result = await loginUser(email, password); // api.js의 함수 호출
            console.log("Login API result:", result);

            if (result.success) { // 임시 응답 기준
                alert('로그인 성공!'); // 성공 알림 (임시)
                window.location.href = 'index.html'; // 메인 페이지로 리디렉션
            } else {
                errorMessageElement.textContent = result.message || '로그인 실패. 다시 시도해주세요.';
            }
        } catch (error) {
            console.error("Login error:", error);
            errorMessageElement.textContent = error.message || '로그인 중 오류가 발생했습니다.';
        }
    });
}

// 회원가입 폼 처리
const registerForm = document.getElementById('register-form');
if (registerForm) {
    console.log("Register form found.");
    const errorMessageElement = registerForm.querySelector('#error-message');

    registerForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // 폼 기본 제출 동작 방지
        console.log("Register form submitted.");
        errorMessageElement.textContent = ''; // 이전 오류 메시지 초기화

        const email = registerForm.querySelector('#email').value;
        const password = registerForm.querySelector('#password').value;
        const confirmPassword = registerForm.querySelector('#confirm-password').value;

        if (!email || !password || !confirmPassword) {
            errorMessageElement.textContent = '모든 필드를 입력해주세요.';
            return;
        }

        if (password !== confirmPassword) {
            errorMessageElement.textContent = '비밀번호가 일치하지 않습니다.';
            return;
        }

        // 비밀번호 복잡성 검사 등 추가 가능

        try {
            console.log("Calling api.registerUser...");
            const result = await registerUser(email, password); // api.js의 함수 호출
            console.log("Register API result:", result);

             if (result.success) { // 임시 응답 기준
                alert('회원가입 성공! 로그인 페이지로 이동합니다.'); // 성공 알림 (임시)
                window.location.href = 'login.html'; // 로그인 페이지로 리디렉션
            } else {
                errorMessageElement.textContent = result.message || '회원가입 실패. 다시 시도해주세요.';
            }
        } catch (error) {
            console.error("Registration error:", error);
            errorMessageElement.textContent = error.message || '회원가입 중 오류가 발생했습니다.';
        }
    });
}
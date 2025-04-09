import google.generativeai as genai
import os
from dotenv import load_dotenv
import PIL.Image

# .env 파일 및 API 키 로드 (이전과 동일)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("오류: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다.")
    exit()

try:
    genai.configure(api_key=api_key)
    print("Google AI SDK 설정 완료!")

    # --- 1. 이미지 로드 (이전과 동일) ---
    image_path = "base_model.jpg"
    if not os.path.exists(image_path):
        print(f"오류: 이미지 파일을 찾을 수 없습니다 - {image_path}")
        exit()
    print(f"이미지 로딩 중: {image_path}")
    img = PIL.Image.open(image_path)
    print("이미지 로딩 완료.")

    # --- 2. 모델 준비 및 프롬프트 정의 (수정) ---
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print(f"'{model.model_name}' 모델 로드 완료!")

    # 프롬프트 정의 (이미지 + 직접적인 편집 요청 텍스트 - Source 3.2 아이디어 기반)
    prompt_parts = [
        img,
        "\nEdit this image to add a red t-shirt to the person.", # <<< 직접적인 편집/추가 요청
    ]

    # --- 3. API 호출 및 응답 확인 (수정) ---
    print("Gemini API 호출 중 (편집/생성 시도)...")
    # stream=True 를 사용하면 응답 구조 확인에 더 유용할 수 있음 (선택적)
    response = model.generate_content(prompt_parts) #, stream=True)
    # if stream=True: response.resolve() # 스트리밍 사용 시 응답 완료 대기

    print("\n--- API 응답 ---")
    # 응답 객체 전체 구조 확인
    print(f"Response object type: {type(response)}")
    # print(dir(response)) # 모든 속성/메서드 확인 필요 시 주석 해제

    # 이미지 데이터가 포함되어 있는지 확인 (예상되는 구조 기반)
    image_found = False
    if hasattr(response, 'parts'):
        print(f"Response parts 발견: {len(response.parts)} 개")
        for part in response.parts:
            if hasattr(part, 'mime_type') and 'image' in part.mime_type:
                print(f"### 이미지 파트 발견! Mime type: {part.mime_type} ###")
                # 이미지 데이터 접근 시도 (실제 속성 이름은 다를 수 있음)
                # 예: image_data = part.inline_data.data (Base64 인코딩 데이터 등)
                image_found = True
            elif hasattr(part, 'text'):
                print(f"텍스트 파트 발견: {part.text}")
            else:
                print(f"알 수 없는 파트 유형: {part}")
    # parts 속성이 없거나 이미지 파트가 없을 경우 텍스트라도 출력 시도
    if not image_found:
        if hasattr(response, 'text'):
             print(f"텍스트만 발견됨: {response.text}")
        else:
            print("응답에서 텍스트나 이미지 파트를 명확히 찾을 수 없음. 전체 응답 출력:")
            print(response)

    print("----------------")

except Exception as e:
    print(f"오류 발생: {e}")
# 수정된 import 경로 적용
from google import genai
from google.genai import types
# --- 나머지 라이브러리 import ---
from PIL import Image
from io import BytesIO
import os
from dotenv import load_dotenv

# .env 파일 로드 (API 키는 여기서 로드됨)
load_dotenv()

# --- 함수 정의 ---
def synthesize_image(client: genai.Client, base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다.
    (client 객체를 인자로 받도록 수정)

    Args:
        client (genai.Client): 초기화된 genai 클라이언트 객체
        base_image_path (str): 베이스 모델 이미지 파일 경로
        item_image_path (str): 아이템 이미지 파일 경로
        item_type (str): 아이템 종류 (예: 'top', 'bottom', 'shoes', 'bag')

    Returns:
        bytes | None: 성공 시 합성된 이미지 데이터(bytes), 실패 시 None
    """
    print(f"이미지 합성 시작: base='{base_image_path}', item='{item_image_path}', type='{item_type}'")
    try:
        # --- 1. 이미지 로드 ---
        if not os.path.exists(base_image_path) or not os.path.exists(item_image_path):
            print("오류: 입력 이미지 파일을 찾을 수 없습니다.")
            return None
        base_img = Image.open(base_image_path)
        item_img = Image.open(item_image_path)
        print("이미지 로딩 완료.")

        # --- 2. 프롬프트 구성 (개선 필요) ---
        prompt_text = f"\nApply the {item_type} item from the second image onto the person in the first image. Keep the person's face, pose, and body shape unchanged."
        prompt_parts = [base_img, item_img, prompt_text]
        print("프롬프트 구성 완료.")

        # --- 3. API 호출 ---
        target_model = "gemini-2.0-flash-exp-image-generation"
        generation_config = types.GenerateContentConfig(
            response_modalities=['Text', 'Image'] # Text도 다시 포함
        )
        
        print(f"'{target_model}' API 호출...")
        # client를 인자로 받아서 사용
        response = client.models.generate_content(
            model=target_model,
            contents=prompt_parts,
            config=generation_config
        )
        print("API 호출 완료.")

        # --- 4. 응답 처리 (candidate 조건문 수정) ---
        image_bytes = None # 이미지 바이트 저장 변수 초기화
        if response.candidates:
            candidate = response.candidates[0] # candidate를 먼저 할당
            # candidate 할당 후 content 와 parts 확인
            if candidate.content and candidate.content.parts:
                print(f"응답 파트 {len(candidate.content.parts)}개 발견:")
                for part in candidate.content.parts:
                    if part.inline_data is not None:
                        print("이미지 데이터 파트 발견!")
                        # 이미지 바이트 저장 (여러 이미지 파트가 올 경우 마지막 것만 저장됨 - 추후 필요시 수정)
                        image_bytes = part.inline_data.data
                        print("이미지 데이터 추출 성공.")
                        # 텍스트 파트는 무시 (response_modalities=['Image'] 설정 시 없을 수 있음)
                    elif part.text is not None:
                         print(f"텍스트 파트 발견 (무시됨): {part.text}")

            # 최종적으로 이미지 바이트가 있는지 확인 후 반환
            if image_bytes:
                 print("합성 성공: 이미지 데이터 반환.")
                 return image_bytes
            else:
                 print("응답 파트에 유효한 이미지 데이터가 없습니다.")
                 return None
        else:
            print("API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}")
            return None

    except Exception as e:
        print(f"이미지 합성 중 오류 발생: {e}")
        return None

# --- 함수 테스트 예시 (수정) ---
if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        # client를 여기서 초기화하고 함수에 전달
        client = genai.Client(api_key=api_key)
        print("테스트: Google AI Client 초기화 완료!")

        # 함수 호출
        result_bytes = synthesize_image(client, "base_model.jpg", "item_tshirt.jpg", "t-shirt")

        # 결과 처리
        if result_bytes:
            try:
                img = Image.open(BytesIO(result_bytes))
                img.save("final_synthesis_output.png")
                img.show()
                print("테스트: 최종 합성 이미지를 저장하고 표시했습니다.")
            except Exception as e:
                print(f"테스트: 결과 이미지 처리/저장 오류: {e}")
        else:
            print("테스트: 이미지 합성에 실패했습니다.")
    else:
        print("테스트: API 키를 로드할 수 없습니다.")
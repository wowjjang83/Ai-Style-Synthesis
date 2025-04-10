from google import genai
import os
from dotenv import load_dotenv
import PIL.Image
import base64
from io import BytesIO

# .env 파일 및 API 키 로드 (이전과 동일)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("오류: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다.")
    exit()

try:
    # --- genai.Client 방식으로 API 클라이언트 초기화 ---
    client = genai.Client(api_key=api_key)
    
    print("Google AI Client 초기화 완료!")

    # --- 1. 이미지 로드 (이전과 동일) ---
    image_path = "base_model.jpg"
    if not os.path.exists(image_path):
        print(f"오류: 이미지 파일을 찾을 수 없습니다 - {image_path}")
        exit()
    print(f"이미지 로딩 중: {image_path}")
    img = PIL.Image.open(image_path)
    print("이미지 로딩 완료.")

    # --- 2. 프롬프트 정의 (이전과 동일) ---
    # 직접적인 편집 요청 프롬프트 사용
    prompt_parts = [
        img,
        "\nEdit this image to add a red t-shirt to the person.",
    ]

    # --- 3. API 호출 (client.models.generate_content 사용) 및 응답 심층 분석 ---
    target_model = "gemini-2.0-flash" # 사용자 요청 모델 이름 사용
    print(f"'{target_model}' 모델로 Gemini API 호출 중 (편집/생성 시도)...")

    # client.models.generate_content 호출 (contents 파라미터 사용)
    response = client.models.generate_content(
        model=target_model,
        contents=prompt_parts # 이미지와 텍스트 리스트 전달
    )

    print("\n--- API 응답 상세 분석 ---")
    print(f"Response object type: {type(response)}")
    print(f"Available attributes/methods: {dir(response)}") # 모든 속성 확인

    image_data_found = False

    # 가능성 1: Imagen 스타일의 'generated_images' 속성 확인
    if hasattr(response, 'generated_images') and response.generated_images:
        print("\n[검사 1] 'generated_images' 속성 발견!")
        for i, gen_image in enumerate(response.generated_images):
            print(f"  - generated_images[{i}] 상세: {dir(gen_image)}")
            if hasattr(gen_image, 'image') and hasattr(gen_image.image, 'image_bytes') and gen_image.image.image_bytes:
                print(f"  - !!! 이미지 바이트 데이터 발견 (generated_images[{i}])!")
                image_data_found = True
            else:
                print(f"  - generated_images[{i}] 에서 image_bytes 데이터 없음.")
    else:
        print("\n[검사 1] 'generated_images' 속성 없음 또는 비어있음.")

    # 가능성 2: 'parts' 내부에 이미지 데이터
    if hasattr(response, 'parts') and response.parts:
        print(f"\n[검사 2] 'parts' 속성 발견 ({len(response.parts)} 개). 상세 검사:")
        for i, part in enumerate(response.parts):
            print(f"  - Part {i}: Type={type(part)}, Attributes={dir(part)}")
            if hasattr(part, 'mime_type') and 'image' in part.mime_type:
                print(f"    - !!! 이미지 Mime Type 발견: {part.mime_type}")
                if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data') and part.inline_data.data:
                    print("    - !!! 인라인 데이터(inline_data.data) 발견!")
                    image_data_found = True
                else:
                    print("    - 이미지 Mime Type은 있으나 'inline_data.data' 없음.")
            elif hasattr(part, 'text'):
                print(f"    - 텍스트 파트 발견: {part.text[:150]}...")
            else:
                print(f"    - 이미지/텍스트 아닌 다른 유형의 파트.")
    else:
        print("\n[검사 2] 'parts' 속성 없음 또는 비어있음.")

    # 최종 결과
    print("\n--- 최종 결론 ---")
    if image_data_found:
        print("!!! 이미지 데이터가 응답 객체 내 어딘가에 포함된 것으로 확인되었습니다! (위 로그 상세 확인 필요)")
    else:
        print("응답 객체 내에서 이미지 데이터를 찾지 못했습니다.")
        try:
            final_text = response.text
            print("반환된 텍스트:", final_text)
        except Exception:
            print("텍스트 응답 추출 실패 또는 없음. 전체 응답 객체:", response)
    print("-----------------")

except Exception as e:
    print(f"오류 발생: {e}")
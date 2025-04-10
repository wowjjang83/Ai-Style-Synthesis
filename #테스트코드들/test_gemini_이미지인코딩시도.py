import google.generativeai as genai
import os
from dotenv import load_dotenv
import PIL.Image
import base64 # Base64 확인용
from io import BytesIO # 바이트 데이터 처리용

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

    # --- 2. 모델 준비 및 프롬프트 정의 (이전과 동일) ---
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print(f"'{model.model_name}' 모델 로드 완료!")

    prompt_parts = [
        img,
        "\nEdit this image to add a red t-shirt to the person.",
    ]

    # --- 3. API 호출 및 응답 심층 분석 ---
    print("Gemini API 호출 중 (편집/생성 시도)...")
    response = model.generate_content(prompt_parts)

    print("\n--- API 응답 상세 분석 ---")
    print(f"Response object type: {type(response)}")
    print(f"Available attributes/methods: {dir(response)}") # 모든 속성 확인

    image_data_found = False

    # 가능성 1: Imagen 스타일의 'generated_images' 속성 확인 (Source 3.1 참고)
    if hasattr(response, 'generated_images') and response.generated_images:
        print("\n[검사 1] 'generated_images' 속성 발견!")
        for i, gen_image in enumerate(response.generated_images):
            print(f"  - generated_images[{i}] 상세: {dir(gen_image)}") # 속성 확인
            if hasattr(gen_image, 'image') and hasattr(gen_image.image, 'image_bytes') and gen_image.image.image_bytes:
                print(f"  - !!! 이미지 바이트 데이터 발견 (generated_images[{i}])!")
                image_data_found = True
                # 이미지 저장 시도 (예시)
                # try:
                #     img_data = BytesIO(gen_image.image.image_bytes)
                #     generated_img = PIL.Image.open(img_data)
                #     generated_img.save(f"generated_image_{i}.png")
                #     print(f"    - generated_image_{i}.png 로 저장 완료.")
                # except Exception as img_e:
                #     print(f"    - 이미지 처리/저장 중 오류: {img_e}")
            else:
                print(f"  - generated_images[{i}] 에서 image_bytes 데이터 없음.")
    else:
        print("\n[검사 1] 'generated_images' 속성 없음 또는 비어있음.")

    # 가능성 2: 'parts' 내부에 이미지 데이터 (이전 검사 확장)
    if hasattr(response, 'parts') and response.parts:
        print(f"\n[검사 2] 'parts' 속성 발견 ({len(response.parts)} 개). 상세 검사:")
        for i, part in enumerate(response.parts):
            print(f"  - Part {i}: Type={type(part)}, Attributes={dir(part)}")
            if hasattr(part, 'mime_type') and 'image' in part.mime_type:
                print(f"    - !!! 이미지 Mime Type 발견: {part.mime_type}")
                # 이미지 데이터가 있는지 확인 (예: part.inline_data.data)
                if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data') and part.inline_data.data:
                    print("    - !!! 인라인 데이터(inline_data.data) 발견!")
                    image_data_found = True
                    # Base64 디코딩 및 저장 시도 (예시)
                    # try:
                    #     img_bytes = base64.b64decode(part.inline_data.data)
                    #     img_data = BytesIO(img_bytes)
                    #     generated_img = PIL.Image.open(img_data)
                    #     generated_img.save(f"generated_image_part_{i}.png")
                    #     print(f"      - generated_image_part_{i}.png 로 저장 완료.")
                    # except Exception as img_e:
                    #     print(f"      - Base64 디코딩/이미지 처리 오류: {img_e}")
                else:
                    print("    - 이미지 Mime Type은 있으나 'inline_data.data' 없음.")
            elif hasattr(part, 'text'):
                print(f"    - 텍스트 파트 발견: {part.text[:150]}...") # 너무 길면 일부만 출력
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
        # 텍스트 응답이라도 다시 확인
        try:
            final_text = response.text
            print("반환된 텍스트:", final_text)
        except Exception: # Handle cases where .text might error if response is blocked etc.
            print("텍스트 응답 추출 실패 또는 없음. 전체 응답 객체:", response)
    print("-----------------")

except Exception as e:
    print(f"오류 발생: {e}")
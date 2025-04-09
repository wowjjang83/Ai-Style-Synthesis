#import google.generativeai as genai
#from google.generativeai import types # GenerateContentConfig 사용 위해 필요
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import os
from dotenv import load_dotenv
# import base64 # 이번 예제에서는 직접 사용 안 함

# .env 파일에서 API 키 로드
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("오류: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다. .env 파일을 확인하세요.")
    # 절대 코드에 직접 키를 넣거나 공유하지 마세요!
    exit()

try:
    # --- genai.Client 방식으로 API 클라이언트 초기화 ---
    client = genai.Client(api_key=api_key)
    print("Google AI Client 초기화 완료!")

    # --- 1. 베이스 모델 이미지 로드 ---
    image_path = "base_model.jpg"
    if not os.path.exists(image_path):
        print(f"오류: 베이스 모델 이미지 파일을 찾을 수 없습니다 - {image_path}")
        exit()
    print(f"베이스 모델 이미지 로딩 중: {image_path}")
    img = Image.open(image_path)
    print("베이스 모델 이미지 로딩 완료.")

    # --- 2. 프롬프트 정의 (이미지 + 편집 요청 텍스트) ---
    prompt_parts = [
        img, # 입력 이미지
        "\nEdit this image to add a red t-shirt to the person.", # 편집 요청
        # 또는 "\nGenerate an image of this person wearing a red t-shirt." 등 시도 가능
    ]

    # --- 3. API 호출 (실험용 모델 + 이미지 응답 설정) ---
    target_model = "gemini-2.0-flash-exp-image-generation" # 사용자 발견 모델
    #target_model = "gemini-2.0-flash" # 사용자 발견 모델
    print(f"'{target_model}' 모델로 Gemini API 호출 중 (이미지 편집/생성 시도)...")

    # 응답에 이미지가 포함될 수 있도록 설정
    generation_config = types.GenerateContentConfig(
        response_modalities=['Text', 'Image'] # 이미지와 텍스트 응답 모두 기대
    )

    # API 호출
    response = client.models.generate_content(
        model=target_model,
        contents=prompt_parts,
        config=generation_config
    )

    # --- 4. 응답 처리 (사용자 예제 기반) ---
    print("\n--- API 응답 처리 ---")
    output_image_saved = False
    output_text = ""

    # 응답 구조 확인 및 데이터 추출
    if response.candidates:
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            print(f"응답 파트 {len(candidate.content.parts)}개 발견:")
            for i, part in enumerate(candidate.content.parts):
                if part.text is not None:
                    print(f"  - 텍스트 파트 {i}: {part.text}")
                    output_text += part.text + "\n"
                elif part.inline_data is not None:
                    print(f"  - 이미지 데이터 파트 {i} 발견!")
                    if hasattr(part.inline_data, 'mime_type'):
                         print(f"    Mime Type: {part.inline_data.mime_type}")

                    # 이미지 데이터 저장 시도
                    try:
                        image_bytes = part.inline_data.data
                        generated_image = Image.open(BytesIO(image_bytes))
                        output_filename = f'generated_output_{i}.png' # 파일 이름 지정
                        generated_image.save(output_filename)
                        # generated_image.show() # 필요시 이미지 보기
                        print(f"  - !!! 이미지를 '{output_filename}'으로 저장했습니다!")
                        output_image_saved = True
                    except Exception as e:
                        print(f"  - 이미지 데이터 처리 또는 저장 중 오류 발생: {e}")
                else:
                    print(f"  - 파트 {i}: 텍스트나 인라인 데이터가 아닌 유형입니다.")
        else:
            print("응답에 content 또는 parts가 없습니다.")
    else:
        print("API 응답에 candidates가 없습니다.")
        if hasattr(response, 'prompt_feedback'):
            print(f"Prompt Feedback: {response.prompt_feedback}")

    print("\n--- 최종 결론 ---")
    if output_image_saved:
        print("이미지 생성이 성공하여 파일로 저장되었습니다.")
        generated_image.show()
    else:
        print("이미지 데이터가 응답에서 발견되지 않았거나 저장에 실패했습니다.")
        if output_text:
            print("대신 반환된 텍스트:", output_text.strip())
        else:
            # .text 속성이 없을 수 있으므로 try-except 유지
            try:
                final_text = response.text
                print("반환된 텍스트(대체):", final_text)
            except Exception:
                 print("텍스트 응답 추출 실패 또는 없음.")
    print("-----------------")

except Exception as e:
    print(f"오류 발생: {e}")
# 수정된 import 경로 적용
from google import genai
from google.genai import types
# --- 나머지 라이브러리 import ---
from PIL import Image
from io import BytesIO
import os
from dotenv import load_dotenv

# .env 파일 및 API 키 로드
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("오류: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다. .env 파일을 확인하세요.")
    exit()

try:
    # --- genai.Client 방식으로 API 클라이언트 초기화 ---
    # 'genai'는 이제 'from google import genai'를 통해 사용
    client = genai.Client(api_key=api_key)
    print("Google AI Client 초기화 완료!")

    # --- 1. 이미지 로드 (베이스 모델 + 사용자 아이템) ---
    base_image_path = "base_model.jpg"
    item_image_path = "item_tshirt.jpg" # 실제 아이템 이미지 파일 이름 사용

    if not os.path.exists(base_image_path):
        print(f"오류: 베이스 모델 이미지 파일을 찾을 수 없습니다 - {base_image_path}")
        exit()
    if not os.path.exists(item_image_path):
        print(f"오류: 아이템 이미지 파일을 찾을 수 없습니다 - {item_image_path}")
        exit()

    print(f"베이스 모델 이미지 로딩 중: {base_image_path}")
    base_img = Image.open(base_image_path)
    print("베이스 모델 이미지 로딩 완료.")

    print(f"아이템 이미지 로딩 중: {item_image_path}")
    item_img = Image.open(item_image_path)
    print("아이템 이미지 로딩 완료.")

    # --- 2. 프롬프트 정의 (이미지 2개 + 텍스트) ---
    prompt_parts = [
        base_img,
        item_img,
        "\nApply the clothing item from the second image onto the person in the first image. Keep the person's face, pose, and body shape.",
    ]

    # --- 3. API 호출 (실험용 모델 + 이미지 응답 설정) ---
    target_model = "gemini-2.0-flash-exp-image-generation"
    print(f"'{target_model}' 모델로 Gemini API 호출 중 (이미지 합성 시도)...")

    # 'types'는 이제 'from google.genai import types'를 통해 사용
    generation_config = types.GenerateContentConfig(
        response_modalities=['Text', 'Image']
    )

    response = client.models.generate_content(
        model=target_model,
        contents=prompt_parts,
        config=generation_config
    )

    # --- 4. 응답 처리 (이전과 동일) ---
    print("\n--- API 응답 처리 ---")
    output_image_saved = False
    output_text = ""

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
                    try:
                        image_bytes = part.inline_data.data
                        generated_image = Image.open(BytesIO(image_bytes))
                        output_filename = f'synthesis_output_{i}.png'
                        generated_image.save(output_filename)
                        print(f"  - !!! 합성 이미지를 '{output_filename}'으로 저장했습니다!")
                        output_image_saved = True
                        generated_image.show() # 생성된 이미지 바로 보기
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
        print("이미지 합성이 성공하여 파일로 저장되었습니다.")
    else:
        print("이미지 데이터가 응답에서 발견되지 않았거나 저장에 실패했습니다.")
        if output_text:
            print("대신 반환된 텍스트:", output_text.strip())
        else:
            try:
                final_text = response.text
                print("반환된 텍스트(대체):", final_text)
            except Exception:
                 print("텍스트 응답 추출 실패 또는 없음.")
    print("-----------------")

except Exception as e:
    print(f"오류 발생: {e}")
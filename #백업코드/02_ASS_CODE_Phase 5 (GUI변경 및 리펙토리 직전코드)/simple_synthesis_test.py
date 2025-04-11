# simple_synthesis_test.py
# 웹 서버 없이 Google AI Gemini API를 사용한 이미지 합성을 테스트하는 스크립트

#import google.generativeai as genai    <-- 절대 안쓰도록 주의
#from google.generativeai import types  <-- 절대 안쓰도록 주의
#------- 중요 import
from google import genai            # <-- 이게 맞는거임
from google.genai import types      # <-- 이게 맞는거임
#------------------------------------------------------
import os
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
import traceback

#def run_synthesis_test(base_image_path: str, item_image_path: str, item_type: str, output_filename: str = "test_output.png"):
def synthesize_image(client: genai.Client, base_image_path: str, item_image_path: str, item_type: str, output_filename: str = "test_output.png") -> bytes | None:
    """
    지정된 이미지와 타입으로 Gemini 이미지 합성을 테스트하고 결과를 파일로 저장합니다.
    """
    print("--- 이미지 합성 테스트 시작 ---")
    print(f"베이스 이미지: {base_image_path}")
    print(f"아이템 이미지: {item_image_path}")
    print(f"아이템 타입: {item_type}")
    print(f"출력 파일명: {output_filename}")

    # 2. 이미지 로드
    base_img = None
    item_img = None
    try:
        # with 구문으로 파일 핸들 자동 관리 및 메모리 복사
        with Image.open(base_image_path) as base_img_fp, \
             Image.open(item_image_path) as item_img_fp:
            base_img = base_img_fp.copy()
            item_img = item_img_fp.copy()
            print("이미지 로딩 및 메모리 복사 완료.")
    except FileNotFoundError as fnf_err:
         print(f"오류: 이미지 파일을 찾을 수 없습니다 - {fnf_err}")
         return False
    except Exception as img_err:
        print(f"오류: 이미지 파일 로딩/처리 실패 - {img_err}")
        traceback.print_exc()
        return False

    if not base_img or not item_img:
         print("오류: 이미지 객체 생성 실패.")
         return False

    # 3. 프롬프트 구성
    prompt_text = (
        f"Apply the {item_type} item from the second image onto the person in the first image. "
        f"Keep the person's original face, pose, and body shape strictly unchanged. "
        f"Ensure the item fits naturally and realistically. "
        f"Maintain a photorealistic style and high quality."
    )
    prompt_parts = [base_img, item_img, prompt_text]
    print("프롬프트 구성 완료.")

    # 4. API 호출
    try:
        # model = genai.GenerativeModel(model_name=target_model_name)    <--------- X

        
        # generation_config = types.GenerationConfig(      X
        #     response_modalities=['Text', 'Image']
        # )
        generation_config = types.GenerateContentConfig(
            response_modalities=['Text', 'Image'] # Text도 다시 포함
        )
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        target_model_name = "gemini-2.0-flash-exp-image-generation"
        print(f"'{target_model_name}' 모델 API 호출...")
        response = client.models.generate_content(
            model=target_model_name,
            contents=prompt_parts,
            #settings=safety_settings,
            config=generation_config
        )
        
        # response = model.generate_content(
        #     contents=prompt_parts,
        #     config=generation_config,
        #     safety_settings=safety_settings,
        # )
        print("API 호출 완료.")

        # 5. 응답 처리 (수정된 로직 적용)
        image_bytes = None
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                 # inline_data가 있고 mime_type이 image로 시작하는 part 찾기
                 image_part = None
                 for part in candidate.content.parts:
                     if hasattr(part, 'inline_data') and part.inline_data and hasattr(part.inline_data, 'mime_type') and part.inline_data.mime_type.startswith("image/"):
                         image_part = part
                         break

                 if image_part:
                     image_bytes = image_part.inline_data.data
                     print(f"응답에서 이미지 데이터 추출 성공 (MIME: {image_part.inline_data.mime_type}).")
                 else:
                     text_part = next((part for part in candidate.content.parts if hasattr(part, 'text') and part.text), None)
                     if text_part:
                         print(f"경고: 응답에 이미지가 없지만 텍스트는 있음 - {text_part.text[:100]}...")
                     else:
                         print("오류: 응답 파트에 이미지 또는 텍스트 데이터가 없습니다.")
                         try:
                             print(f"전체 응답 후보 내용: {candidate.content}")
                         except Exception:
                             print("전체 응답 후보 내용 로깅 실패")
            else:
                 print("오류: 응답에 유효한 content 또는 parts가 없습니다.")
                 # 추가적인 응답 정보 로깅
                 if hasattr(candidate, 'finish_reason'): print(f"Finish Reason: {candidate.finish_reason}")
                 if hasattr(candidate, 'safety_ratings'): print(f"Safety Ratings: {candidate.safety_ratings}")

        else:
            print("오류: API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}")

        # 6. 결과 저장
        if image_bytes:
            try:
                result_img = Image.open(BytesIO(image_bytes))
                result_img.save(output_filename)
                print(f"성공: 합성된 이미지를 '{output_filename}'으로 저장했습니다.")
                return True
            except Exception as save_err:
                print(f"오류: 결과 이미지 저장 실패 - {save_err}")
                traceback.print_exc()
                return False
        else:
            print("최종 실패: 유효한 이미지 데이터를 얻지 못했습니다.")
            return False

    except Exception as e:
        print(f"테스트 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return False
    finally:
        print("--- 이미지 합성 테스트 종료 ---")


# --- 테스트 실행 ---
if __name__ == "__main__":
    # --- 설정값 (사용자 환경에 맞게 수정) ---
    # 실제 존재하는 베이스 모델 이미지 경로 또는 URL
    # base_image_file = "app/static/images/base_model.jpg" # 예시 로컬 경로
    base_image_file = "C:/ASS/02_ASS_CODE_Phase 3 - Re1/app/static/images/base_model.jpg" # 예시 절대 경로 (Windows)

    # 실제 존재하는 아이템 이미지 경로 또는 URL
    # item_image_file = "item_tshirt.jpg" # 예시 로컬 경로
    item_image_file = "C:/ASS/02_ASS_CODE_Phase 3 - Re1/app/static/images/item_tshirt.jpg" # 예시 절대 경로 (Windows)

    # 아이템 종류 (프롬프트에 사용됨)
    item_category = "top" # 예: 'top', 'shoes', 'hair' 등

    # 저장될 결과 이미지 파일 이름
    output_file = "C:/ASS/02_ASS_CODE_Phase 3 - Re1/outputs/simple_test_output.png"
    # --- 설정값 끝 ---

    # 경로가 절대 경로가 아니면 현재 스크립트 위치 기준으로 변환 (선택적)
    # if not os.path.isabs(base_image_file):
    #     base_image_file = os.path.join(os.path.dirname(__file__), base_image_file)
    # if not os.path.isabs(item_image_file):
    #     item_image_file = os.path.join(os.path.dirname(__file__), item_image_file)

    # 테스트 함수 실행
    if os.path.exists(base_image_file) and os.path.exists(item_image_file):
        # 1. API 키 로드 및 설정
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")

        try:
            #genai.configure(api_key=api_key)  <---  중요!: 이렇게 하면 안됨
            # client를 여기서 초기화하고 함수에 전달 <--- 이렇게 해야함
            client = genai.Client(api_key=api_key)
            print("Google AI SDK 설정 완료.")
            
            synthesize_image(client,base_image_file, item_image_file, item_category, output_file)
        except Exception as e:
            print(f"오류: Google AI SDK 설정 실패 - {e}")
            
    else:
        print("오류: 설정된 베이스 또는 아이템 이미지 경로가 잘못되었습니다. 스크립트 내 경로를 수정하세요.")
        if not os.path.exists(base_image_file): print(f" - 찾을 수 없음: {base_image_file}")
        if not os.path.exists(item_image_file): print(f" - 찾을 수 없음: {item_image_file}")


import os
from PIL import Image # Pillow 라이브러리 사용 (pip install Pillow)
import google.generativeai as genai
from google.generativeai import types

# 함수 시그니처: client 대신 model 객체 사용
def synthesize_image(model: genai.GenerativeModel, base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다. (Gemini Model 객체 사용)

    Args:
        model (genai.GenerativeModel): 초기화된 Gemini 모델 객체
        base_image_path (str): 베이스 모델 이미지 파일 절대 경로
        item_image_path (str): 아이템 이미지 파일 절대 경로
        item_type (str): 아이템 종류 (예: 'top', 'bottom')

    Returns:
        bytes | None: 성공 시 합성된 이미지 데이터(bytes), 실패 시 None
    """
    print(f"[AI Module] 이미지 합성 시작: base='{os.path.basename(base_image_path)}', item='{os.path.basename(item_image_path)}', type='{item_type}'")
    print(f"[AI Module DEBUG] Base Path: {base_image_path}")
    print(f"[AI Module DEBUG] Item Path: {item_image_path}")
    
    base_img = None # finally 에서 사용하기 위해 미리 선언
    item_img = None # finally 에서 사용하기 위해 미리 선언

    try:
        # --- 이미지 파일 존재 확인 ---
        # app.py 에서 절대 경로를 전달하므로, 여기서 다시 확인
        if not os.path.exists(base_image_path):
            print(f"[AI Module] 오류: 베이스 이미지 파일을 찾을 수 없습니다. 경로: {base_image_path}")
            return None
        if not os.path.exists(item_image_path):
             print(f"[AI Module] 오류: 아이템 이미지 파일을 찾을 수 없습니다. 경로: {item_image_path}")
             return None

        # --- 이미지 로드 (Pillow 사용) ---
        try:
            base_img = Image.open(base_image_path)
            item_img = Image.open(item_image_path)
            # 데이터를 메모리로 로드 (파일 핸들 조기 해제에 도움될 수 있음)
            base_img.load()
            item_img.load()
            print(f"[AI Module] 이미지 로딩 및 데이터 로드 완료. Base: {base_img.format} {base_img.size}, Item: {item_img.format} {item_img.size}")
        except Exception as img_err:
            print(f"[AI Module] 오류: 이미지 파일 로딩 중 문제 발생 ({img_err})")
            return None # 로딩 실패 시 None 반환


        # --- 프롬프트 구성 ---
        #prompt_text = f"\nApply the style and shape of the {item_type} from the second image {item_img} onto the corresponding area of the person in the first image {base_img}. Keep the person's original face, pose, body shape, and background unchanged. Ensure the result is photorealistic."
        #prompt_parts = [ base_img, item_img, prompt_text ]
        prompt_text = f"\n"
        prompt_parts = [ f"Please create an image of a woman",prompt_text ]
        print("[AI Module] 프롬프트 구성 완료.")

        # 프롬프트는 모델과 아이템 종류에 맞게 개선 필요
        prompt_parts = [
             base_img, # 첫 번째 이미지: 베이스 모델
             item_img, # 두 번째 이미지: 아이템
             prompt_text # 텍스트 지시사항
        ]
        print("[AI Module] 프롬프트 구성 완료.")

        # --- API 호출 설정 ---
        # 기존 코드:
        # generation_config = types.GenerateContentConfig(
        #     response_modalities=['Text', 'Image'] # 또는 ['Image']
        # )
        # 수정 코드: 'Content' 제거
        generation_config = types.GenerationConfig(
            #response_modalities=['Image'] # 이미지 결과만 필요 시
            #response_mime_type="image/png" # 필요 시 추가
        )
        # 안전 설정 (필요시 조정)
        safety_settings={
            'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
            'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
            'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
            'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
        }

        # --- API 호출 (수정: model 객체 직접 사용) ---
        print(f"[AI Module] '{model.model_name}' API 호출...")
        try:
            response = model.generate_content(
                contents=prompt_parts,
                generation_config=generation_config,
                safety_settings=safety_settings # 안전 설정 적용
            )
            print("[AI Module] API 호출 완료.")
            # print(f"[AI Module DEBUG] Raw Response: {response}") # 매우 상세한 응답 확인 시
        except Exception as api_err:
             print(f"[AI Module] API 호출 중 오류 발생: {api_err}")
             # API 관련 상세 오류가 있다면 여기서 확인 가능 (예: response.prompt_feedback)
             # if hasattr(api_err, 'response') and hasattr(api_err.response, 'prompt_feedback'):
             #      print(f"[AI Module] Prompt Feedback on Error: {api_err.response.prompt_feedback}")
             return None


        # --- 응답 처리 ---
        image_bytes = None
        output_text = ""
        try:
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                print(f"[AI Module] 응답 파트 {len(response.candidates[0].content.parts)}개 발견:")
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        print(f"[AI Module] 이미지 데이터 파트 발견! (MimeType: {part.inline_data.mime_type})")
                        image_bytes = part.inline_data.data
                        break # 첫 번째 이미지 데이터만 사용
                    # 텍스트 응답은 무시 (response_modalities=['Image'] 설정 시)
                    # elif part.text:
                    #     print(f"[AI Module] 텍스트 파트 발견 (무시됨): {part.text[:50]}...")

                if image_bytes:
                    print("[AI Module] 합성 성공: 이미지 데이터(bytes) 반환.")
                    return image_bytes
                else:
                    print("[AI Module] 응답 파트에 유효한 이미지 데이터가 없습니다.")
                    # 텍스트 응답이 있었다면 여기서 로깅
                    return None
            else:
                print("[AI Module] 응답 파트에 유효한 이미지 데이터가 없습니다.")
                if output_text: # output_text 변수에 part.text가 누적되었다면
                    print(f"[AI Module] 대신 받은 텍스트:\n---\n{output_text}---")
                if hasattr(response, 'prompt_feedback'):
                    print(f"[AI Module] Prompt Feedback: {response.prompt_feedback}")
                # <<< 후보 content 직접 로깅 추가 >>>
                if response.candidates and response.candidates[0].content:
                    print(f"[AI Module DEBUG] Raw Response Content: {response.candidates[0].content}")
                return None

        except Exception as resp_err:
            print(f"[AI Module] API 응답 처리 중 오류 발생: {resp_err}")
            print(f"[AI Module] 이미지 합성 함수 내 알 수 없는 오류 발생: {e}")
            traceback.print_exc()
            return None
        
    except Exception as e:
        print(f"[AI Module] 이미지 합성 함수 내 알 수 없는 오류 발생: {e}")
        import traceback
        traceback.print_exc() # 상세 traceback 출력
        return None
    
    finally:
        # --- 파일 핸들 명시적 닫기 (파일 삭제 오류 방지) ---
        if base_img:
            try:
                base_img.close()
                print("[AI Module DEBUG] Closed base_img file handle.")
            except Exception as close_err:
                print(f"[AI Module DEBUG] Error closing base_img: {close_err}")
        if item_img:
            try:
                item_img.close()
                print("[AI Module DEBUG] Closed item_img file handle.")
            except Exception as close_err:
                print(f"[AI Module DEBUG] Error closing item_img: {close_err}")

# --- 필요하다면 다른 AI 관련 헬퍼 함수들 ---
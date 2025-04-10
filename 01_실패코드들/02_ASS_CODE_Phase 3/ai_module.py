# ai_module.py (최종 수정본)

import os
from PIL import Image
# 사용자님의 Phase 2 성공 코드 방식 적용
from google import generativeai as genai
from google.generativeai import types
import traceback

# 함수 시그니처: client: genai.Client 사용 (사용자 방식 존중)
def synthesize_image(client: genai.Client, base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다. (genai.Client 객체 사용)

    Args:
        client (genai.Client): 초기화된 genai 클라이언트 객체
        base_image_path (str): 베이스 모델 이미지 파일 절대 경로
        item_image_path (str): 아이템 이미지 파일 절대 경로
        item_type (str): 아이템 종류 (예: 'top', 'bottom')

    Returns:
        bytes | None: 성공 시 합성된 이미지 데이터(bytes), 실패 시 None
    """
    print(f"[AI Module] 이미지 합성 시작: base='{os.path.basename(base_image_path)}', item='{os.path.basename(item_image_path)}', type='{item_type}'")
    print(f"[AI Module DEBUG] Base Path: {base_image_path}")
    print(f"[AI Module DEBUG] Item Path: {item_image_path}")

    base_img = None
    item_img = None
    try:
        # --- 이미지 파일 존재 확인 ---
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
            base_img.load()
            item_img.load()
            print(f"[AI Module] 이미지 로딩 및 데이터 로드 완료. Base: {base_img.format} {base_img.size}, Item: {item_img.format} {item_img.size}")
        except Exception as img_err:
            print(f"[AI Module] 오류: 이미지 파일 로딩 중 문제 발생 ({img_err})")
            return None

        # --- 프롬프트 구성 (수정된 상세 프롬프트 사용) ---
        prompt_text = f"Apply the style and shape of the {item_type} item from the second image (item image) onto the corresponding area of the person in the first image (base image). Keep the person's original face, pose, body shape, and background unchanged. Ensure the result is photorealistic."
        prompt_parts = [
             base_img, # 첫 번째 이미지: 베이스 모델
             item_img, # 두 번째 이미지: 아이템
             prompt_text # 텍스트 지시사항
        ]
        print("[AI Module] 프롬프트 구성 완료.")

        # --- API 호출 설정 (수정: response_modalities 제거) ---
        generation_config = types.GenerationConfig(
            # response_modalities 인수는 없음
            # response_mime_type 도 이미지 생성에는 사용 불가
        )
        safety_settings={
            'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
            'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
            'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
            'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
        }

        # --- API 호출 (수정: client.models 사용 - 사용자 방식 존중) ---
        target_model = "gemini-2.0-flash-exp-image-generation" # 모델 이름 명시
        print(f"[AI Module] '{target_model}' API 호출 (client.models 사용)...")
        try:
            response = client.models.generate_content( # client.models 사용
                model=target_model, # 호출 시 모델 이름 전달
                contents=prompt_parts,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            print("[AI Module] API 호출 완료.")
        except Exception as api_err:
             print(f"[AI Module] API 호출 중 오류 발생: {api_err}")
             # 필요시 피드백 로깅 추가
             # if hasattr(api_err, 'response') and hasattr(api_err.response, 'prompt_feedback'):
             #      print(f"[AI Module] Prompt Feedback on Error: {api_err.response.prompt_feedback}")
             return None

        # --- 응답 처리 (텍스트 로깅 활성화) ---
        image_bytes = None
        output_text = ""
        try:
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                print(f"[AI Module] 응답 파트 {len(response.candidates[0].content.parts)}개 발견:")
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        print(f"[AI Module] 이미지 데이터 파트 발견! (MimeType: {part.inline_data.mime_type})")
                        image_bytes = part.inline_data.data
                        break
                    elif part.text: # <<< 텍스트 로그 활성화 >>>
                        print(f"[AI Module] 텍스트 파트 발견: {part.text[:100]}...")
                        output_text += part.text + "\n"

                if image_bytes:
                    print("[AI Module] 합성 성공: 이미지 데이터(bytes) 반환.")
                    return image_bytes
                else:
                    # 이미지 없고, 텍스트/피드백 로깅
                    print("[AI Module] 응답 파트에 유효한 이미지 데이터가 없습니다.")
                    if output_text:
                         print(f"[AI Module] 대신 받은 텍스트:\n---\n{output_text}---")
                    if hasattr(response, 'prompt_feedback'):
                         print(f"[AI Module] Prompt Feedback: {response.prompt_feedback}")
                    # 필요시 전체 content 로깅
                    # if response.candidates and response.candidates[0].content:
                    #      print(f"[AI Module DEBUG] Raw Response Content: {response.candidates[0].content}")
                    return None
            else:
                 # 후보나 파트 없음
                 print("[AI Module] API 응답에서 유효한 content parts를 찾을 수 없습니다.")
                 if hasattr(response, 'prompt_feedback'):
                      print(f"[AI Module] Prompt Feedback: {response.prompt_feedback}")
                 return None

        except Exception as resp_err:
             print(f"[AI Module] API 응답 처리 중 오류 발생: {resp_err}")
             # 필요시 피드백 로깅 추가
             # if hasattr(response, 'prompt_feedback'):
             #      print(f"[AI Module] Prompt Feedback on Error: {response.prompt_feedback}")
             return None

    except Exception as e:
        print(f"[AI Module] 이미지 합성 함수 내 알 수 없는 오류 발생: {e}")
        traceback.print_exc()
        return None

    finally:
        # 파일 핸들 닫기
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


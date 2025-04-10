# app/utils/ai_module.py
# AI 이미지 합성 및 관련 처리 함수 모음

import os
from io import BytesIO
from PIL import Image, ImageEnhance
import google.generativeai as genai
from google.generativeai import types
import traceback # 상세 오류 로깅용

# --- 이미지 합성 함수 ---
def synthesize_image(base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다. (Google AI Gemini 사용)
    genai.configure()가 미리 호출되어 API 키가 설정되어 있어야 합니다.

    Args:
        base_image_path (str): 베이스 모델 이미지 파일 경로.
        item_image_path (str): 아이템 이미지 파일 경로.
        item_type (str): 아이템 종류 (예: 'top', 'bottom', 'hair'). 프롬프트 생성에 사용됩니다.

    Returns:
        bytes or None: 성공 시 합성된 이미지 데이터(bytes), 실패 시 None.
    """
    print(f"[AI Module - Synthesize] 이미지 합성 시작: Base='{os.path.basename(base_image_path)}', Item='{os.path.basename(item_image_path)}', Type='{item_type}'")

    try:
        # --- 1. 이미지 로드 (with 구문 사용 및 복사) ---
        base_img = None
        item_img = None
        try:
            with Image.open(base_image_path) as base_img_fp, \
                 Image.open(item_image_path) as item_img_fp:
                base_img = base_img_fp.copy()
                item_img = item_img_fp.copy()
                print("[AI Module - Synthesize] 이미지 로딩 및 메모리 복사 완료.")
        except FileNotFoundError as fnf_err:
             print(f"[AI Module - Synthesize] 오류: 이미지 파일을 찾을 수 없습니다 - {fnf_err}")
             return None
        except Exception as img_err:
            print(f"[AI Module - Synthesize] 오류: 이미지 파일 로딩/처리 실패 - {img_err}")
            traceback.print_exc()
            return None

        if not base_img or not item_img:
             print("[AI Module - Synthesize] 오류: 이미지 객체 생성 실패.")
             return None

        # --- 2. 프롬프트 구성 ---
        prompt_text = (
            f"Apply the {item_type} item from the second image onto the person in the first image. "
            f"Keep the person's original face, pose, and body shape strictly unchanged. "
            f"Ensure the item fits naturally and realistically. "
            f"Maintain a photorealistic style and high quality."
        )
        prompt_parts = [base_img, item_img, prompt_text]
        print("[AI Module - Synthesize] 프롬프트 구성 완료.")

        # --- 3. API 호출 설정 ---
        target_model_name = "gemini-1.5-flash-latest"
        model = genai.GenerativeModel(model_name=target_model_name)

        # response_mime_type 제거됨
        generation_config = types.GenerationConfig(
            temperature=0.8
        )
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        print(f"[AI Module - Synthesize] '{target_model_name}' 모델 API 호출...")
        response = model.generate_content(
            contents=prompt_parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        print("[AI Module - Synthesize] API 호출 완료.")

        # --- 4. 응답 처리 (수정: 이미지 파트 찾는 로직 변경) ---
        image_bytes = None
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                 # 수정: inline_data가 있고 mime_type이 image로 시작하는 part 찾기
                 image_part = None
                 for part in candidate.content.parts:
                     # part 객체에 inline_data 속성이 있는지, 값이 있는지, mime_type 속성이 있는지 먼저 확인
                     if hasattr(part, 'inline_data') and part.inline_data and hasattr(part.inline_data, 'mime_type') and part.inline_data.mime_type.startswith("image/"):
                         image_part = part
                         break # 첫 번째 이미지 파트를 찾으면 중단

                 if image_part:
                     image_bytes = image_part.inline_data.data
                     print(f"[AI Module - Synthesize] 응답에서 이미지 데이터 추출 성공 (MIME: {image_part.inline_data.mime_type}).")
                 else:
                     # 이미지가 없는 경우, 텍스트 응답이라도 있는지 확인
                     text_part = next((part for part in candidate.content.parts if hasattr(part, 'text') and part.text), None)
                     if text_part:
                         print(f"[AI Module - Synthesize] 경고: 응답에 이미지가 없지만 텍스트는 있음 - {text_part.text[:100]}...")
                     else:
                         print("[AI Module - Synthesize] 오류: 응답 파트에 이미지 또는 텍스트 데이터가 없습니다.")
                         # 상세 응답 내용 로깅 (디버깅용)
                         try:
                             print(f"[AI Module - Synthesize] 전체 응답 후보 내용: {candidate.content}")
                         except Exception:
                             print("[AI Module - Synthesize] 전체 응답 후보 내용 로깅 실패")

            else:
                 print("[AI Module - Synthesize] 오류: 응답에 유효한 content 또는 parts가 없습니다.")
                 if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 'STOP':
                     print(f"[AI Module - Synthesize] 생성 중단 사유: {candidate.finish_reason}")
                 if hasattr(candidate, 'safety_ratings'):
                     print(f"[AI Module - Synthesize] 안전 등급: {candidate.safety_ratings}")

            if image_bytes:
                print("[AI Module - Synthesize] 합성 성공: 이미지 데이터 반환.")
                return image_bytes
            else:
                print("[AI Module - Synthesize] 최종 실패: 응답에서 유효한 이미지 데이터를 찾을 수 없습니다.")
                return None
        else:
            print("[AI Module - Synthesize] 최종 실패: API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 print(f"[AI Module - Synthesize] 프롬프트 피드백: {response.prompt_feedback}")
            return None

    # ... (기존 except 블록들 유지) ...
    except AttributeError as ae:
         # 이전에 발생했던 mime_type 관련 오류도 여기서 잡힐 수 있음
         print(f"[AI Module - Synthesize] 속성 오류 또는 라이브러리 문제 가능성: {ae}")
         print("[AI Module - Synthesize] API 응답 구조 또는 라이브러리 버전 확인 필요.")
         traceback.print_exc()
         return None
    except Exception as e:
        print(f"[AI Module - Synthesize] 이미지 합성 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return None


# --- 워터마크 적용 함수 ---
# (이전 코드와 동일 - 변경 없음)
def apply_watermark_func(image_bytes: bytes, watermark_path: str, opacity: float = 0.15) -> bytes | None:
    """
    주어진 이미지 바이트 데이터에 워터마크 이미지를 타일링하여 반투명하게 적용합니다.
    """
    print(f"[AI Module - Watermark] 워터마크 적용 시작 (Opacity: {opacity})")
    if not image_bytes:
        print("[AI Module - Watermark] 오류: 입력 이미지 데이터가 없습니다.")
        return None
    try:
        with Image.open(BytesIO(image_bytes)).convert("RGBA") as base_image:
            base_width, base_height = base_image.size
            print(f"[AI Module - Watermark] 원본 이미지 로드 완료 (Size: {base_width}x{base_height})")

            if not os.path.exists(watermark_path):
                print(f"[AI Module - Watermark] 경고: 워터마크 파일을 찾을 수 없음 - {watermark_path}. 원본 이미지 반환.")
                return image_bytes

            with Image.open(watermark_path).convert("RGBA") as watermark_base:
                watermark = watermark_base.copy()
                wm_width, wm_height = watermark.size
                print(f"[AI Module - Watermark] 워터마크 이미지 로드 완료 (Size: {wm_width}x{wm_height})")

                if 0.0 <= opacity < 1.0:
                    try:
                        alpha = watermark.split()[3]
                        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                        watermark.putalpha(alpha)
                        print(f"[AI Module - Watermark] 알파 채널 투명도 조절 완료 (Opacity: {opacity})")
                    except IndexError:
                        print("[AI Module - Watermark] 경고: 워터마크에 알파 채널 없음. 전체 이미지 투명도 적용 시도.")
                        watermark = Image.blend(Image.new('RGBA', watermark.size, (0,0,0,0)), watermark, alpha=opacity)

                tiled_layer = Image.new('RGBA', base_image.size, (255, 255, 255, 0))
                print(f"[AI Module - Watermark] 타일링 레이어 생성 및 워터마크 붙여넣기 시작...")
                for y in range(0, base_height, wm_height):
                    for x in range(0, base_width, wm_width):
                        tiled_layer.paste(watermark, (x, y), watermark)
                print("[AI Module - Watermark] 타일링 레이어 생성 완료")

                final_image = Image.alpha_composite(base_image, tiled_layer)
                print("[AI Module - Watermark] 원본 이미지에 타일링 레이어 합성 완료")

                output_buffer = BytesIO()
                final_image.save(output_buffer, format='PNG')
                output_bytes = output_buffer.getvalue()

                print("[AI Module - Watermark] 워터마크 적용 완료 (PNG 형식)")
                return output_bytes

    except FileNotFoundError:
        print(f"[AI Module - Watermark] 오류: 워터마크 파일 접근 불가 - {watermark_path}. 원본 이미지 반환.")
        return image_bytes
    except Exception as e:
        print(f"[AI Module - Watermark] 워터마크 적용 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return image_bytes

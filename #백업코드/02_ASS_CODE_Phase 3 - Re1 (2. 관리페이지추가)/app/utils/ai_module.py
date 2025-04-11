# app/utils/ai_module.py
# AI 이미지 합성 및 관련 처리 함수 모음 (사용자 성공 테스트 기반 수정)

import os
from io import BytesIO
from PIL import Image, ImageEnhance
# 수정: 사용자 성공 코드의 import 방식 적용
from google import genai
from google.genai import types
import traceback # 상세 오류 로깅용

# --- 이미지 합성 함수 ---
# 수정: client 인자 다시 추가 (genai.Client 타입)
def synthesize_image(client: genai.Client, base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다. (Google AI Gemini 사용)
    초기화된 genai.Client 객체가 필요합니다.

    Args:
        client (genai.Client): 초기화된 Google AI 클라이언트 객체.
        base_image_path (str): 베이스 모델 이미지 파일 경로.
        item_image_path (str): 아이템 이미지 파일 경로.
        item_type (str): 아이템 종류 (예: 'top', 'bottom', 'hair'). 프롬프트 생성에 사용됩니다.

    Returns:
        bytes or None: 성공 시 합성된 이미지 데이터(bytes), 실패 시 None.
    """
    print(f"[AI Module - Synthesize] 이미지 합성 시작: Base='{os.path.basename(base_image_path)}', Item='{os.path.basename(item_image_path)}', Type='{item_type}'")

    # 클라이언트 객체 유효성 확인 (선택적)
    if not client:
        print("[AI Module - Synthesize] 오류: 유효한 AI 클라이언트 객체가 전달되지 않았습니다.")
        return None

    try:
        # --- 1. 이미지 로드 (with 구문 사용 및 복사) ---
        base_img = None
        item_img = None
        try:
            # with 구문을 사용하여 파일 핸들이 자동으로 닫히도록 함
            with Image.open(base_image_path) as base_img_fp, \
                 Image.open(item_image_path) as item_img_fp:
                # Pillow 이미지를 메모리에 복사하여 파일 핸들 의존성 제거
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

        # 이미지 객체가 제대로 로드되었는지 확인
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
        # 메모리에 복사된 이미지 객체 사용
        prompt_parts = [base_img, item_img, prompt_text]
        print("[AI Module - Synthesize] 프롬프트 구성 완료.")

        # --- 3. API 호출 설정 ---
        # 사용자 성공 코드 기준 모델 이름 사용
        target_model_name = "gemini-2.0-flash-exp-image-generation"
        # 사용자 성공 코드 기준 GenerateContentConfig 사용
        generation_config = types.GenerateContentConfig(
            response_modalities=['Text', 'Image'] # Text, Image 모두 받도록 설정
        )
        # Safety settings (사용자 코드에서는 API 호출 시 사용 안 함, 필요시 주석 해제)
        # safety_settings = [ ... ]

        print(f"[AI Module - Synthesize] '{target_model_name}' 모델 API 호출...")
        # 사용자 성공 코드 기준 client.models.generate_content 사용
        response = client.models.generate_content(
            model=target_model_name,
            contents=prompt_parts,
            # settings=safety_settings, # 필요시 safety settings 파라미터 확인 후 적용
            config=generation_config # config 파라미터 사용
        )
        print("[AI Module - Synthesize] API 호출 완료.")

        # --- 4. 응답 처리 (사용자 성공 코드 기준 로직) ---
        image_bytes = None
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                 # inline_data가 있고 mime_type이 image로 시작하는 part 찾기
                 image_part = None
                 for part in candidate.content.parts:
                     # 사용자 테스트에서 성공한 로직 적용
                     if hasattr(part, 'inline_data') and part.inline_data and hasattr(part.inline_data, 'mime_type') and part.inline_data.mime_type.startswith("image/"):
                         image_part = part
                         break

                 if image_part:
                     image_bytes = image_part.inline_data.data
                     print(f"[AI Module - Synthesize] 응답에서 이미지 데이터 추출 성공 (MIME: {image_part.inline_data.mime_type}).")
                 else:
                     text_part = next((part for part in candidate.content.parts if hasattr(part, 'text') and part.text), None)
                     if text_part:
                         print(f"[AI Module - Synthesize] 경고: 응답에 이미지가 없지만 텍스트는 있음 - {text_part.text[:100]}...")
                     else:
                         print("[AI Module - Synthesize] 오류: 응답 파트에 이미지 또는 텍스트 데이터가 없습니다.")
                         try:
                             print(f"[AI Module - Synthesize] 전체 응답 후보 내용: {candidate.content}")
                         except Exception:
                             print("[AI Module - Synthesize] 전체 응답 후보 내용 로깅 실패")
            else:
                 print("[AI Module - Synthesize] 오류: 응답에 유효한 content 또는 parts가 없습니다.")
                 if hasattr(candidate, 'finish_reason'): print(f"Finish Reason: {candidate.finish_reason}")
                 if hasattr(candidate, 'safety_ratings'): print(f"Safety Ratings: {candidate.safety_ratings}")

        else:
            print("[AI Module - Synthesize] 실패: API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}")

        # --- 5. 반환값 처리 ---
        if image_bytes:
            print("[AI Module - Synthesize] 합성 성공: 이미지 데이터 반환.")
            return image_bytes # 이미지 바이트 반환
        else:
            print("[AI Module - Synthesize] 최종 실패: 유효한 이미지 데이터를 얻지 못했습니다.")
            return None # 실패 시 None 반환

    except Exception as e:
        # 모든 예외 처리
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
        # with 구문 사용하여 파일 핸들 자동 관리
        with Image.open(BytesIO(image_bytes)).convert("RGBA") as base_image:
            base_width, base_height = base_image.size
            print(f"[AI Module - Watermark] 원본 이미지 로드 완료 (Size: {base_width}x{base_height})")

            if not os.path.exists(watermark_path):
                print(f"[AI Module - Watermark] 경고: 워터마크 파일을 찾을 수 없음 - {watermark_path}. 원본 이미지 반환.")
                return image_bytes

            with Image.open(watermark_path).convert("RGBA") as watermark_base:
                # 원본 워터마크 복사하여 사용 (원본 객체 변경 방지)
                watermark = watermark_base.copy()
                wm_width, wm_height = watermark.size
                print(f"[AI Module - Watermark] 워터마크 이미지 로드 완료 (Size: {wm_width}x{wm_height})")

                # 워터마크 투명도 조절
                if 0.0 <= opacity < 1.0:
                    try:
                        alpha = watermark.split()[3]
                        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                        watermark.putalpha(alpha)
                        print(f"[AI Module - Watermark] 알파 채널 투명도 조절 완료 (Opacity: {opacity})")
                    except IndexError:
                        print("[AI Module - Watermark] 경고: 워터마크에 알파 채널 없음. 전체 이미지 투명도 적용 시도.")
                        watermark = Image.blend(Image.new('RGBA', watermark.size, (0,0,0,0)), watermark, alpha=opacity)

                # 타일링 레이어 생성 및 워터마크 적용
                tiled_layer = Image.new('RGBA', base_image.size, (255, 255, 255, 0))
                print(f"[AI Module - Watermark] 타일링 레이어 생성 및 워터마크 붙여넣기 시작...")
                for y in range(0, base_height, wm_height):
                    for x in range(0, base_width, wm_width):
                        tiled_layer.paste(watermark, (x, y), watermark)
                print("[AI Module - Watermark] 타일링 레이어 생성 완료")

                # 원본 이미지 위에 타일링 레이어 합성
                final_image = Image.alpha_composite(base_image, tiled_layer)
                print("[AI Module - Watermark] 원본 이미지에 타일링 레이어 합성 완료")

                # 결과 이미지 바이트로 변환 (PNG 형식)
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
        # 오류 발생 시 원본 이미지 바이트 반환하는 것이 더 안전할 수 있음
        return image_bytes # 또는 None 반환

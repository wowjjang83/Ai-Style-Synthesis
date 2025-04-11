# app/utils/ai_module.py
# AI 이미지 합성 및 관련 처리 함수 모음 (사용자 성공 테스트 기반 수정)

import os
from io import BytesIO
from PIL import Image, ImageEnhance # Pillow 라이브러리
# google import 방식 확인
from google import genai
from google.genai import types
import traceback # 상세 오류 로깅용

# --- 이미지 합성 함수 ---
# (synthesize_image 함수는 변경 없음 - 이전 코드 유지)
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
    if not client:
        print("[AI Module - Synthesize] 오류: 유효한 AI 클라이언트 객체가 전달되지 않았습니다.")
        return None
    try:
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

        prompt_text = (
            f"Apply the {item_type} item from the second image onto the person in the first image. "
            f"Keep the person's original face, pose, and body shape strictly unchanged. "
            f"Ensure the item fits naturally and realistically. "
            f"Maintain a photorealistic style and high quality."
        )
        prompt_parts = [base_img, item_img, prompt_text]
        print("[AI Module - Synthesize] 프롬프트 구성 완료.")

        target_model_name = "gemini-2.0-flash-exp-image-generation"
        generation_config = types.GenerateContentConfig(
            response_modalities=['Text', 'Image']
        )

        print(f"[AI Module - Synthesize] '{target_model_name}' 모델 API 호출...")
        response = client.models.generate_content(
            model=target_model_name,
            contents=prompt_parts,
            config=generation_config
        )
        print("[AI Module - Synthesize] API 호출 완료.")

        image_bytes = None
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                 image_part = None
                 for part in candidate.content.parts:
                     if hasattr(part, 'inline_data') and part.inline_data and hasattr(part.inline_data, 'mime_type') and part.inline_data.mime_type.startswith("image/"):
                         image_part = part
                         break
                 if image_part:
                     image_bytes = image_part.inline_data.data
                     print(f"[AI Module - Synthesize] 응답에서 이미지 데이터 추출 성공 (MIME: {image_part.inline_data.mime_type}).")
                 else:
                     text_part = next((part for part in candidate.content.parts if hasattr(part, 'text') and part.text), None)
                     if text_part: print(f"[AI Module - Synthesize] 경고: 응답에 이미지가 없지만 텍스트는 있음 - {text_part.text[:100]}...")
                     else: print("[AI Module - Synthesize] 오류: 응답 파트에 이미지 또는 텍스트 데이터가 없습니다.")
                     try: print(f"[AI Module - Synthesize] 전체 응답 후보 내용: {candidate.content}")
                     except Exception: print("[AI Module - Synthesize] 전체 응답 후보 내용 로깅 실패")
            else:
                 print("[AI Module - Synthesize] 오류: 응답에 유효한 content 또는 parts가 없습니다.")
                 if hasattr(candidate, 'finish_reason'): print(f"Finish Reason: {candidate.finish_reason}")
                 if hasattr(candidate, 'safety_ratings'): print(f"Safety Ratings: {candidate.safety_ratings}")
        else:
            print("[AI Module - Synthesize] 실패: API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}")

        if image_bytes:
            print("[AI Module - Synthesize] 합성 성공: 이미지 데이터 반환.")
            return image_bytes
        else:
            print("[AI Module - Synthesize] 최종 실패: 유효한 이미지 데이터를 얻지 못했습니다.")
            return None
    except Exception as e:
        print(f"[AI Module - Synthesize] 이미지 합성 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return None

# --- 워터마크 적용 함수 (수정됨: 리사이즈 및 중앙 배치 로직) ---
def apply_watermark_func(image_bytes: bytes, watermark_path: str, opacity: float = 0.5) -> bytes | None:
    """
    주어진 이미지 바이트 데이터에 워터마크 이미지를 리사이즈하여 중앙에 반투명하게 적용합니다.
    워터마크 가로=이미지 가로, 세로는 비율 유지.
    """
    print(f"[AI Module - Watermark] 워터마크 적용 시작 (리사이즈+중앙배치, Opacity: {opacity})")
    if not image_bytes:
        print("[AI Module - Watermark] 오류: 입력 이미지 데이터가 없습니다.")
        return None

    try:
        # 1. 원본 합성 이미지 로드 (RGBA로 변환)
        with Image.open(BytesIO(image_bytes)).convert("RGBA") as base_image:
            base_width, base_height = base_image.size
            print(f"[AI Module - Watermark] 원본 이미지 로드 완료 (Size: {base_width}x{base_height})")

            # 2. 워터마크 파일 존재 확인
            if not os.path.exists(watermark_path):
                print(f"[AI Module - Watermark] 경고: 워터마크 파일을 찾을 수 없음 - {watermark_path}. 원본 이미지 반환.")
                return image_bytes

            # 3. 워터마크 이미지 로드 (RGBA로 변환)
            with Image.open(watermark_path).convert("RGBA") as watermark_orig:
                wm_orig_width, wm_orig_height = watermark_orig.size
                print(f"[AI Module - Watermark] 워터마크 이미지 로드 완료 (Original Size: {wm_orig_width}x{wm_orig_height})")

                # 4. 워터마크 리사이즈 (가로 폭 맞추고 세로 비율 유지)
                target_wm_width = base_width
                # 비율 계산: target_h / target_w = orig_h / orig_w  => target_h = orig_h * target_w / orig_w
                target_wm_height = int(wm_orig_height * target_wm_width / wm_orig_width)
                print(f"[AI Module - Watermark] 워터마크 리사이즈 시도 (Target Size: {target_wm_width}x{target_wm_height})")
                # 고품질 리샘플링 사용 (Pillow 9.1.0 이상 권장, 이전 버전은 Image.ANTIALIAS)
                resampling_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                watermark_resized = watermark_orig.resize((target_wm_width, target_wm_height), resample=resampling_filter)
                print(f"[AI Module - Watermark] 워터마크 리사이즈 완료.")

                # 5. 워터마크 투명도(Opacity) 조절
                # Pillow 9.3.0 부터 Image.blend의 alpha 인자가 deprecated되고 Image.alpha_composite 권장됨
                # 여기서는 기존 로직 유지 또는 alpha_composite 사용 가능
                alpha = watermark_resized.split()[3] # 알파 채널 분리
                alpha = ImageEnhance.Brightness(alpha).enhance(opacity) # 알파 채널 밝기(투명도) 조절
                watermark_resized.putalpha(alpha) # 조절된 알파 채널 적용
                print(f"[AI Module - Watermark] 알파 채널 투명도 조절 완료 (Opacity: {opacity})")

                # 6. 워터마크 붙여넣을 위치 계산 (정 가운데)
                paste_x = (base_width - target_wm_width) // 2 # 가로 중앙 (항상 0이 됨)
                paste_y = (base_height - target_wm_height) // 2 # 세로 중앙
                print(f"[AI Module - Watermark] 워터마크 배치 위치 계산 (x={paste_x}, y={paste_y})")

                # 7. 최종 이미지 생성 (알파 블렌딩)
                # base_image 위에 watermark_resized를 paste_x, paste_y 위치에 붙여넣기
                # 세 번째 인자로 watermark_resized를 다시 전달하여 알파 채널을 마스크로 사용
                final_image = Image.new("RGBA", base_image.size) # 최종 이미지를 위한 새 캔버스
                final_image.paste(base_image, (0, 0)) # 원본 이미지를 먼저 붙여넣고
                # paste 메서드는 RGBA 이미지를 마스크로 사용하여 알파 블렌딩을 수행함
                final_image.paste(watermark_resized, (paste_x, paste_y), watermark_resized)
                # 또는 alpha_composite 사용:
                # watermark_layer = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
                # watermark_layer.paste(watermark_resized, (paste_x, paste_y), watermark_resized)
                # final_image = Image.alpha_composite(base_image, watermark_layer)

                print("[AI Module - Watermark] 원본 이미지에 리사이즈된 워터마크 합성 완료")

                # 8. 결과 이미지 바이트로 변환 (PNG 형식)
                output_buffer = BytesIO()
                final_image.save(output_buffer, format='PNG')
                output_bytes = output_buffer.getvalue()

                print("[AI Module - Watermark] 워터마크 적용 완료 (PNG 형식)")
                return output_bytes

    except FileNotFoundError:
        print(f"[AI Module - Watermark] 오류: 워터마크 파일 접근 불가 - {watermark_path}. 원본 이미지 반환.")
        return image_bytes # 원본 반환
    except Exception as e:
        print(f"[AI Module - Watermark] 워터마크 적용 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return image_bytes # 오류 시 원본 이미지 바이트 반환
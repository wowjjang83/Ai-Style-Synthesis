# app/utils/ai_module.py
# AI 이미지 합성 및 관련 처리 함수 모음

import os
from io import BytesIO
from PIL import Image, ImageEnhance
import google.generativeai as genai # 수정: google.generativeai import
from google.generativeai import types

# --- 이미지 합성 함수 ---
# 수정: client 인자 제거
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

    # API 키 설정 여부 확인 (선택적이지만 안전)
    # if not genai.is_configured(): # is_configured 같은 함수는 없을 수 있음
    #     print("[AI Module - Synthesize] 오류: Google AI SDK가 설정되지 않았습니다.")
    #     return None

    try:
        # --- 1. 이미지 로드 ---
        if not os.path.exists(base_image_path):
            print(f"[AI Module - Synthesize] 오류: 베이스 이미지 파일을 찾을 수 없습니다 - {base_image_path}")
            return None
        if not os.path.exists(item_image_path):
            print(f"[AI Module - Synthesize] 오류: 아이템 이미지 파일을 찾을 수 없습니다 - {item_image_path}")
            return None

        base_img = Image.open(base_image_path)
        item_img = Image.open(item_image_path)
        print("[AI Module - Synthesize] 이미지 로딩 완료.")

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
        target_model_name = "gemini-1.5-flash-latest" # 사용할 모델 이름

        # 수정: genai.GenerativeModel() 사용
        model = genai.GenerativeModel(model_name=target_model_name)

        generation_config = types.GenerationConfig(
            response_mime_type="image/png",
        )
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        print(f"[AI Module - Synthesize] '{target_model_name}' 모델 API 호출...")
        # 수정: model.generate_content() 사용
        response = model.generate_content(
            contents=prompt_parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        print("[AI Module - Synthesize] API 호출 완료.")

        # --- 4. 응답 처리 ---
        # (이전 코드와 동일)
        image_bytes = None
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                 part = candidate.content.parts[0]
                 if part.inline_data and part.inline_data.mime_type == 'image/png':
                     image_bytes = part.inline_data.data
                     print("[AI Module - Synthesize] 응답에서 PNG 이미지 데이터 추출 성공.")
                 else:
                     print(f"[AI Module - Synthesize] 오류: 응답 파트가 PNG 이미지가 아님 (MIME: {part.inline_data.mime_type if part.inline_data else 'N/A'})")
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
                print("[AI Module - Synthesize] 실패: 응답에서 유효한 이미지 데이터를 찾을 수 없습니다.")
                return None
        else:
            print("[AI Module - Synthesize] 실패: API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 print(f"[AI Module - Synthesize] 프롬프트 피드백: {response.prompt_feedback}")
            return None

    except genai.types.generation_types.BlockedPromptException as bpe:
         print(f"[AI Module - Synthesize] 오류: 프롬프트가 안전 설정에 의해 차단되었습니다 - {bpe}")
         return None
    except genai.types.generation_types.StopCandidateException as sce:
         print(f"[AI Module - Synthesize] 오류: 후보 생성이 중단되었습니다 - {sce}")
         return None
    except AttributeError as ae:
         # genai.configure 가 호출되지 않았을 때 발생 가능성 있음
         print(f"[AI Module - Synthesize] 설정 오류 또는 라이브러리 문제 가능성: {ae}")
         print("[AI Module - Synthesize] Google AI SDK 설정(genai.configure)이 올바르게 되었는지 확인하세요.")
         return None
    except Exception as e:
        import traceback
        print(f"[AI Module - Synthesize] 이미지 합성 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return None

# --- 워터마크 적용 함수 ---
# (이전 코드와 동일)
def apply_watermark_func(image_bytes: bytes, watermark_path: str, opacity: float = 0.15) -> bytes | None:
    """
    주어진 이미지 바이트 데이터에 워터마크 이미지를 타일링하여 반투명하게 적용합니다.
    (별도의 타일링 레이어 생성 후 합성 방식)

    Args:
        image_bytes (bytes): 원본 이미지 데이터 (AI 모듈에서 생성된).
        watermark_path (str): 워터마크 이미지 파일 경로.
        opacity (float): 워터마크 투명도 (0.0 ~ 1.0, 낮을수록 투명). Defaults to 0.15.

    Returns:
        bytes or None: 워터마크 적용된 이미지 바이트 (PNG 형식), 실패 시 원본 이미지 바이트 반환.
    """
    print(f"[AI Module - Watermark] 워터마크 적용 시작 (Opacity: {opacity})")
    if not image_bytes:
        print("[AI Module - Watermark] 오류: 입력 이미지 데이터가 없습니다.")
        return None

    try:
        # --- 1. 원본 이미지 로드 (RGBA 형식으로 변환) ---
        base_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
        base_width, base_height = base_image.size
        print(f"[AI Module - Watermark] 원본 이미지 로드 완료 (Size: {base_width}x{base_height})")

        # --- 2. 워터마크 이미지 로드 ---
        if not os.path.exists(watermark_path):
            print(f"[AI Module - Watermark] 경고: 워터마크 파일을 찾을 수 없음 - {watermark_path}. 원본 이미지 반환.")
            return image_bytes

        watermark = Image.open(watermark_path).convert("RGBA")
        wm_width, wm_height = watermark.size
        print(f"[AI Module - Watermark] 워터마크 이미지 로드 완료 (Size: {wm_width}x{wm_height})")

        # --- 3. 워터마크 투명도 조절 ---
        if 0.0 <= opacity < 1.0:
            try:
                alpha = watermark.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                watermark.putalpha(alpha)
                print(f"[AI Module - Watermark] 알파 채널 투명도 조절 완료 (Opacity: {opacity})")
            except IndexError:
                print("[AI Module - Watermark] 경고: 워터마크에 알파 채널 없음. 전체 이미지 투명도 적용 시도.")
                watermark = Image.blend(Image.new('RGBA', watermark.size, (0,0,0,0)), watermark, alpha=opacity)

        # --- 4. 타일링 레이어 생성 및 워터마크 적용 ---
        tiled_layer = Image.new('RGBA', base_image.size, (255, 255, 255, 0))
        print(f"[AI Module - Watermark] 타일링 레이어 생성 및 워터마크 붙여넣기 시작...")
        for y in range(0, base_height, wm_height):
            for x in range(0, base_width, wm_width):
                tiled_layer.paste(watermark, (x, y), watermark)
        print("[AI Module - Watermark] 타일링 레이어 생성 완료")

        # --- 5. 원본 이미지 위에 타일링 레이어 합성 ---
        final_image = Image.alpha_composite(base_image, tiled_layer)
        print("[AI Module - Watermark] 원본 이미지에 타일링 레이어 합성 완료")

        # --- 6. 결과 이미지 바이트로 변환 (PNG 형식) ---
        output_buffer = BytesIO()
        final_image.save(output_buffer, format='PNG')
        output_bytes = output_buffer.getvalue()

        print("[AI Module - Watermark] 워터마크 적용 완료 (PNG 형식)")
        return output_bytes

    except FileNotFoundError:
        print(f"[AI Module - Watermark] 오류: 워터마크 파일 접근 불가 - {watermark_path}. 원본 이미지 반환.")
        return image_bytes
    except Exception as e:
        import traceback
        print(f"[AI Module - Watermark] 워터마크 적용 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        return image_bytes


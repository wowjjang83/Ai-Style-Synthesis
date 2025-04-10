# app/utils/ai_module.py
# AI 이미지 합성 및 관련 처리 함수 모음

import os
from io import BytesIO
from PIL import Image, ImageEnhance
from google import generativeai as genai
from google.generativeai import types

# --- 이미지 합성 함수 ---
def synthesize_image(client: genai.Client, base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다. (Google AI Gemini 사용)

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
        print("[AI Module - Synthesize] 오류: Google AI 클라이언트가 초기화되지 않았습니다.")
        return None

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
        # TODO: Phase 1 기획서의 프롬프트 전략을 기반으로 개선 필요
        # (예: 배경 설정, 얼굴/포즈 유지 강화, 네거티브 프롬프트 등)
        prompt_text = (
            f"Apply the {item_type} item from the second image onto the person in the first image. "
            f"Keep the person's original face, pose, and body shape strictly unchanged. "
            f"Ensure the item fits naturally and realistically. "
            f"Maintain a photorealistic style and high quality."
            # f"Negative prompt: blurry, distorted, deformed, multiple limbs, extra fingers" # 필요시 네거티브 프롬프트 추가
        )
        prompt_parts = [base_img, item_img, prompt_text]
        print("[AI Module - Synthesize] 프롬프트 구성 완료.")

        # --- 3. API 호출 설정 ---
        # 사용 모델 확인 (Phase 2에서 결정된 실험용 모델)
        target_model_name = "gemini-1.5-flash-latest" # 또는 다른 사용 가능한 모델
        # target_model = client.get_generative_model(model_name=target_model_name) # 모델 객체 가져오기 (SDK 버전에 따라 다를 수 있음)
        # 현재 SDK(google-generativeai) 방식에 맞게 client.models.generate_content 사용
        target_model_ref = f"models/{target_model_name}" # 모델 참조 경로 형식

        generation_config = types.GenerationConfig(
            # candidate_count=1, # 생성할 후보 수 (기본값 1)
            # max_output_tokens=2048, # 텍스트 출력 최대 토큰 (이미지 생성에는 직접 영향 적음)
            # temperature=0.9, # 생성 다양성 (높을수록 무작위)
            # top_p=1.0, # 샘플링 확률 임계값
            # top_k=None, # 상위 K개 토큰만 고려
            response_mime_type="image/png", # 응답 타입을 PNG 이미지로 명시 (지원 여부 확인 필요)
            # response_modalities=['IMAGE'] # 응답 모달리티 (SDK 버전에 따라 사용법 다를 수 있음, response_mime_type 우선)
        )
        safety_settings = [ # 안전 설정 (필요에 따라 조정)
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        print(f"[AI Module - Synthesize] '{target_model_ref}' API 호출...")
        # API 호출
        response = client.generate_content(
            model=target_model_ref,
            contents=prompt_parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
            # stream=False # 스트리밍 여부 (기본 False)
        )
        print("[AI Module - Synthesize] API 호출 완료.")

        # --- 4. 응답 처리 ---
        image_bytes = None
        if response.candidates:
            candidate = response.candidates[0]
            # 응답 구조 확인 (response_mime_type 사용 시)
            if candidate.content and candidate.content.parts:
                 part = candidate.content.parts[0]
                 if part.inline_data and part.inline_data.mime_type == 'image/png':
                     image_bytes = part.inline_data.data
                     print("[AI Module - Synthesize] 응답에서 PNG 이미지 데이터 추출 성공.")
                 else:
                     print(f"[AI Module - Synthesize] 오류: 응답 파트가 PNG 이미지가 아님 (MIME: {part.inline_data.mime_type if part.inline_data else 'N/A'})")
            else:
                 print("[AI Module - Synthesize] 오류: 응답에 유효한 content 또는 parts가 없습니다.")
                 # 안전 설정 등으로 블록된 경우 피드백 확인
                 if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 'STOP':
                     print(f"[AI Module - Synthesize] 생성 중단 사유: {candidate.finish_reason}")
                 if hasattr(candidate, 'safety_ratings'):
                     print(f"[AI Module - Synthesize] 안전 등급: {candidate.safety_ratings}")

            if image_bytes:
                print("[AI Module - Synthesize] 합성 성공: 이미지 데이터 반환.")
                return image_bytes
            else:
                # 이미지 바이트가 없는 경우 (오류 또는 텍스트 응답 등)
                print("[AI Module - Synthesize] 실패: 응답에서 유효한 이미지 데이터를 찾을 수 없습니다.")
                # 텍스트 응답이 있는지 확인 (response_modalities 사용 시)
                # text_output = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                # if text_output:
                #    print(f"[AI Module - Synthesize] 대신 받은 텍스트: {text_output[:100]}...")
                return None
        else:
            # Candidates 자체가 없는 경우 (API 호출 실패 등)
            print("[AI Module - Synthesize] 실패: API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            # 프롬프트 피드백 확인 (블록된 경우 등)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 print(f"[AI Module - Synthesize] 프롬프트 피드백: {response.prompt_feedback}")
            return None

    except genai.types.generation_types.BlockedPromptException as bpe:
         print(f"[AI Module - Synthesize] 오류: 프롬프트가 안전 설정에 의해 차단되었습니다 - {bpe}")
         return None
    except genai.types.generation_types.StopCandidateException as sce:
         print(f"[AI Module - Synthesize] 오류: 후보 생성이 중단되었습니다 - {sce}")
         return None
    except Exception as e:
        # traceback 모듈 사용하여 상세 오류 로깅 가능
        import traceback
        print(f"[AI Module - Synthesize] 이미지 합성 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc() # 개발 중 상세 오류 확인용
        return None

# --- 워터마크 적용 함수 ---
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
            return image_bytes # 워터마크 파일 없으면 원본 그대로 반환

        watermark = Image.open(watermark_path).convert("RGBA")
        wm_width, wm_height = watermark.size
        print(f"[AI Module - Watermark] 워터마크 이미지 로드 완료 (Size: {wm_width}x{wm_height})")

        # --- 3. 워터마크 투명도 조절 ---
        if 0.0 <= opacity < 1.0:
            try:
                # 알파 채널 분리 및 투명도 조절
                alpha = watermark.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                watermark.putalpha(alpha)
                print(f"[AI Module - Watermark] 알파 채널 투명도 조절 완료 (Opacity: {opacity})")
            except IndexError:
                # 알파 채널이 없는 경우, 전체 이미지에 투명도 적용 시도 (덜 일반적)
                print("[AI Module - Watermark] 경고: 워터마크에 알파 채널 없음. 전체 이미지 투명도 적용 시도.")
                # Pillow 9.1.0 이상 필요할 수 있음
                watermark = Image.blend(Image.new('RGBA', watermark.size, (0,0,0,0)), watermark, alpha=opacity)
                # 또는 직접 픽셀 조작 (더 복잡)
        # opacity >= 1.0 인 경우는 원본 워터마크 그대로 사용 (이미 RGBA)

        # --- 4. 타일링 레이어 생성 및 워터마크 적용 ---
        # 원본과 동일한 크기의 완전 투명 레이어 생성
        tiled_layer = Image.new('RGBA', base_image.size, (255, 255, 255, 0))

        print(f"[AI Module - Watermark] 타일링 레이어 생성 및 워터마크 붙여넣기 시작...")
        for y in range(0, base_height, wm_height):
            for x in range(0, base_width, wm_width):
                # 투명 레이어에 (투명도 조절된) 워터마크 붙여넣기 (알파 채널 마스크 사용)
                tiled_layer.paste(watermark, (x, y), watermark)
        print("[AI Module - Watermark] 타일링 레이어 생성 완료")

        # --- 5. 원본 이미지 위에 타일링 레이어 합성 ---
        # Image.alpha_composite는 두 RGBA 이미지를 합성
        final_image = Image.alpha_composite(base_image, tiled_layer)
        print("[AI Module - Watermark] 원본 이미지에 타일링 레이어 합성 완료")

        # --- 6. 결과 이미지 바이트로 변환 (PNG 형식) ---
        output_buffer = BytesIO()
        # 최종 이미지는 알파 채널 보존을 위해 PNG로 저장
        final_image.save(output_buffer, format='PNG')
        output_bytes = output_buffer.getvalue()

        print("[AI Module - Watermark] 워터마크 적용 완료 (PNG 형식)")
        return output_bytes

    except FileNotFoundError:
        # watermark_path 오류는 위에서 처리했지만, 혹시 모를 경우 대비
        print(f"[AI Module - Watermark] 오류: 워터마크 파일 접근 불가 - {watermark_path}. 원본 이미지 반환.")
        return image_bytes
    except Exception as e:
        import traceback
        print(f"[AI Module - Watermark] 워터마크 적용 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()
        # 오류 발생 시 원본 이미지 바이트 반환
        return image_bytes

# --- 기타 AI 관련 함수 (필요시 추가) ---
# 예: 이미지 분석, 특정 객체 감지 등

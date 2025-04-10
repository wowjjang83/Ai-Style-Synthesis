# ai_module.py
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import os
from PIL import Image, ImageEnhance # ImageEnhance 추가 (투명도 조절용)
from io import BytesIO # BytesIO 추가 확인

def synthesize_image(client: genai.Client, base_image_path: str, item_image_path: str, item_type: str) -> bytes | None:
    """
    베이스 모델 이미지에 아이템 이미지를 합성합니다.

    Args:
        client (genai.Client): 초기화된 genai 클라이언트 객체
        base_image_path (str): 베이스 모델 이미지 파일 경로
        item_image_path (str): 아이템 이미지 파일 경로
        item_type (str): 아이템 종류 (예: 'top', 'bottom')

    Returns:
        bytes | None: 성공 시 합성된 이미지 데이터(bytes), 실패 시 None
    """
    print(f"[AI Module] 이미지 합성 시작: base='{base_image_path}', item='{item_image_path}', type='{item_type}'")
    try:
        # --- 이미지 로드 ---
        if not os.path.exists(base_image_path) or not os.path.exists(item_image_path):
            print("[AI Module] 오류: 입력 이미지 파일을 찾을 수 없습니다.")
            return None
        base_img = Image.open(base_image_path)
        item_img = Image.open(item_image_path)
        print("[AI Module] 이미지 로딩 완료.")

        # --- 프롬프트 구성 ---
        prompt_text = f"\nApply the {item_type} item from the second image onto the person in the first image. Keep the person's face, pose, and body shape unchanged."
        prompt_parts = [base_img, item_img, prompt_text]
        print("[AI Module] 프롬프트 구성 완료.")

        # --- API 호출 ---
        target_model = "gemini-2.0-flash-exp-image-generation"
        generation_config = types.GenerateContentConfig(
            response_modalities=['Text', 'Image'] # Text, Image 모두 포함
        )
        print(f"[AI Module] '{target_model}' API 호출...")
        response = client.models.generate_content(
            model=target_model,
            contents=prompt_parts,
            config=generation_config
        )
        print("[AI Module] API 호출 완료.")

        # --- 응답 처리 ---
        image_bytes = None
        output_text = ""
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                print(f"[AI Module] 응답 파트 {len(candidate.content.parts)}개 발견:")
                for part in candidate.content.parts:
                    if part.inline_data is not None:
                        print("[AI Module] 이미지 데이터 파트 발견!")
                        image_bytes = part.inline_data.data
                        # 여러 이미지 파트가 올 경우 일단 마지막 것만 사용
                    elif part.text is not None:
                        print(f"[AI Module] 텍스트 파트 발견: {part.text[:50]}...")
                        output_text += part.text # 텍스트도 기록
            else:
                 print("[AI Module] 응답에 content 또는 parts가 없습니다.")

            if image_bytes:
                print("[AI Module] 합성 성공: 이미지 데이터 반환.")
                return image_bytes
            else:
                print("[AI Module] 응답 파트에 유효한 이미지 데이터가 없습니다.")
                print(f"[AI Module] 대신 받은 텍스트: {output_text}")
                return None
        else:
            print("[AI Module] API 응답에서 유효한 candidates를 찾을 수 없습니다.")
            if hasattr(response, 'prompt_feedback'):
                 print(f"[AI Module] Prompt Feedback: {response.prompt_feedback}")
            return None

    except Exception as e:
        print(f"[AI Module] 이미지 합성 중 오류 발생: {e}")
        return None
    
    
# --- 워터마크 적용 함수 (수정: 별도 레이어 타일링 방식) ---
def apply_watermark_func(image_bytes: bytes, watermark_path: str, opacity: float = 0.15) -> bytes | None:
    """
    주어진 이미지 바이트에 워터마크 이미지를 타일링하여 반투명하게 전체적으로 덮습니다.
    (별도의 타일링 레이어 생성 후 합성)

    Args:
        image_bytes (bytes): 원본 이미지 데이터
        watermark_path (str): 워터마크 이미지 파일 경로
        opacity (float): 워터마크 투명도 (0.0 ~ 1.0, 낮을수록 투명)

    Returns:
        bytes | None: 워터마크 적용된 이미지 바이트, 실패 시 None
    """
    try:
        # 원본 이미지 로드 (RGBA)
        base_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
        base_width, base_height = base_image.size

        # 워터마크 이미지 로드 (RGBA)
        if not os.path.exists(watermark_path):
            print(f"[Watermark] 오류: 워터마크 파일을 찾을 수 없음 - {watermark_path}")
            return image_bytes # 오류 시 원본 반환

        watermark = Image.open(watermark_path).convert("RGBA")
        wm_width, wm_height = watermark.size

        # 워터마크 투명도 조절
        if 0.0 <= opacity < 1.0:
            try:
                alpha = watermark.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                watermark.putalpha(alpha)
            except IndexError:
                print("[Watermark] 경고: 워터마크 알파 채널 없음, 전체 투명도 적용 시도.")
                solid_alpha = Image.new('L', watermark.size, int(255 * opacity))
                watermark.putalpha(solid_alpha)
        # opacity >= 1.0 인 경우는 그대로 사용 (이미 RGBA)

        # --- 타일링 로직 수정: 별도 레이어 생성 ---
        # 1. 원본과 동일한 크기의 완전 투명 레이어 생성
        tiled_layer = Image.new('RGBA', base_image.size, (255, 255, 255, 0))

        # 2. 투명 레이어에 워터마크 타일링
        print(f"[Watermark] 타일링 레이어 생성 시작 (Watermark Size: {wm_width}x{wm_height}, Opacity: {opacity})")
        for y in range(0, base_height, wm_height):
            for x in range(0, base_width, wm_width):
                # 투명 레이어에 워터마크 붙여넣기 (알파 채널 마스크 사용)
                tiled_layer.paste(watermark, (x, y), watermark)
        print("[Watermark] 타일링 레이어 생성 완료")

        # 3. 원본 이미지 위에 타일링된 레이어 합성 (알파 블렌딩)
        final_image = Image.alpha_composite(base_image, tiled_layer)
        print("[Watermark] 원본 이미지에 타일링 레이어 합성 완료")
        # --- 타일링 로직 수정 끝 ---

        # 결과를 BytesIO에 저장하여 bytes로 반환
        output_buffer = BytesIO()
        # 최종 이미지는 PNG로 저장해야 알파 채널 보존 가능
        final_image.save(output_buffer, format='PNG')
        output_bytes = output_buffer.getvalue()

        print("[Watermark] 워터마크 적용 완료 (타일링)")
        return output_bytes

    except Exception as e:
        print(f"[Watermark] 워터마크 적용 중 오류 (타일링): {e}")
        return image_bytes # 오류 시 원본 이미지 바이트 반환
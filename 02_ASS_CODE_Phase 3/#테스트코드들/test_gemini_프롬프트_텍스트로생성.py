import google.generativeai as genai
import os
from dotenv import load_dotenv
import PIL.Image # Pillow 라이브러리 임포트


# .env 파일에서 환경 변수 로드
load_dotenv()

# API 키 설정
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("오류: GEMINI_API_KEY 환경 변수를 찾을 수 없습니다.")
    exit()

try:
    genai.configure(api_key=api_key)
    print("Google AI SDK 설정 완료!")

    # --- 1. 이미지 로드 ---
    image_path = "base_model.jpg" # 샘플 이미지 파일 경로 (같은 폴더에 있다고 가정)
    if not os.path.exists(image_path):
        print(f"오류: 이미지 파일을 찾을 수 없습니다 - {image_path}")
        print("테스트를 위해 'base_model.jpg' 파일을 코드와 같은 폴더('02_ASS_CODE')에 넣어주세요.")
        exit()

    print(f"이미지 로딩 중: {image_path}")
    img = PIL.Image.open(image_path)
    print("이미지 로딩 완료.")

    # --- 2. 모델 준비 및 프롬프트 정의 ---
    # 이미지 입력을 지원하는 모델 선택 (Gemini 1.5 Flash)
    model = genai.GenerativeModel('gemini-2.0-flash-latest')
    print(f"'{model.model_name}' 모델 로드 완료!")

    # 프롬프트 정의 (이미지 + 텍스트)
    prompt_parts = [
        "웹 개발자가 Gwmini API로 Imagen3 생성하는게 가능합니까? 가능하다면 생성된 이미지를 어떻게 화면에 보여주는지 알려주세요.",
        #img,  # 로드한 이미지 객체
        #"Please use Imagen 3 to create an image of a person wearing a red t-shirt with the appearance of this image. Create Image.",
        #"\n이 이미지의 외모로 빨간티셔츠를 입고있는 모습으로 Imagen 3 를 사용하여 이미지를 생성해주세요.",
        # "\nImagine this person is now wearing a bright red t-shirt. Describe their appearance.", # 제안 1: 상상하도록 유도
        # "\nGenerate a description of this person as if they were wearing a red t-shirt.", # 제안 2: ~인 것처럼 묘사하도록 유도
        # 참고: "빨간색 티셔츠를 입혀주세요" 같은 직접적인 편집 명령보다는,
        #       "빨간색 티셔츠를 입고 있는 모습을 묘사해줘" 또는 영어 프롬프트가
        #       초기 테스트에 더 안정적인 응답을 줄 수 있습니다.
    ]

    # --- 3. API 호출 및 응답 확인 ---
    print("Gemini API 호출 중...")
    # 참고: 이 API 호출이 직접 이미지를 '편집'해서 반환하기보다는,
    #       요청 내용을 바탕으로 텍스트 응답(묘사)을 생성할 가능성이 높습니다.
    #       어떤 응답이 오는지 확인하는 것이 목적입니다.
    response = model.generate_content(prompt_parts)

    print("\n--- API 응답 ---")
    # response 객체 구조 확인 (text 속성 외 다른 정보가 있을 수 있음)
    # print(dir(response)) # 어떤 속성들이 있는지 확인하려면 이 주석 해제
    try:
      print(response.text)
    except Exception as e:
      print(f"응답에서 텍스트를 추출하는 중 오류 발생: {e}")
      print("전체 응답 객체:", response) # 오류 시 전체 응답 구조 확인
    print("----------------")

except Exception as e:
    print(f"오류 발생: {e}")
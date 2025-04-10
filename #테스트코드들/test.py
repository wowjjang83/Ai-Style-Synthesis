from google import genai
import os
import PIL.Image # Pillow 라이브러리 임포트

client = genai.Client(api_key="AIzaSyD4YrI8IlBgUlISwYZlZyPY96GJd_Bw_Yk")

# --- 1. 이미지 로드 ---
image_path = "base_model.jpg" # 샘플 이미지 파일 경로 (같은 폴더에 있다고 가정)
if not os.path.exists(image_path):
    print(f"오류: 이미지 파일을 찾을 수 없습니다 - {image_path}")
    print("테스트를 위해 'base_model.jpg' 파일을 코드와 같은 폴더('02_ASS_CODE')에 넣어주세요.")
    exit()

print(f"이미지 로딩 중: {image_path}")
img = PIL.Image.open(image_path)
print("이미지 로딩 완료.")

#"Please use Imagen 3 to create an image of a person wearing a red t-shirt with the appearance of this image. Create Image."

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents= [
        img,
        "Please use Imagen 3 to create an image of a person wearing a red t-shirt with the appearance of this image. Create Image."
    ]
)
print(response.text)
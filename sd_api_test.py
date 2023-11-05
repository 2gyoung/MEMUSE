import json
import requests
import io
import base64
import sqlite3
from PIL import Image, PngImagePlugin
from datetime import datetime

# Stable Diffusion의 로컬 주소
url = "http://127.0.0.1:7860"

# 옵션 설정
# model list 중 선택한 model로 변수 적용
models = [
    "chosenMix_bakedVae.safetensors [52b8ebbd5b]",
    "cuteCartoon_v10.safetensors [d3a0fbfe0a]",
    "helloflatcute2d_V10.safetensors [5a7204177d]",
    "nightSkyYOZORAStyle_yozoraV1Origin.safetensors [e7bf829cff]",
    "pasteldiffusedmix_v22.safetensors [7d21f7acff]",
    "pastelMixStylizedAnime_pastelMixPrunedFP16.safetensors [d01a68ae76]",
    "v1-5-pruned-emaonly.safetensors [6ce0161689]"
    ]

# 사용자로부터 모델 선택 입력 - 추후 홈페이지에서 스타일 선택하면 그걸로 변경
print("모델 선택")
for i, model in enumerate(models):
    print(f"{i}: {model}")

selected_index = int(input("사용하고 싶은 모델 넘버 입력: "))

# 선택된 모델로 변경
selected_model = models[selected_index]
option_payload = {
    "sd_model_checkpoint" : selected_model
}

# 모델 변경 시 시간이 꽤 걸리므로 최대한 딜레이 줄이는 법 연구 필요
response = requests.post(url = f'{url}/sdapi/v1/options', json = option_payload)

# LORA 추가하는 법 연구중 - model 변경과 비슷하게 style 선택지를 선택했을 때 prompt list에 추가
# LORA 선택지
LORA_CHOICES = {
    "선화": "<lora:line illustration_20230901192549:0.85>",
    "수채화": "<lora:Colored lead:0.85>",
    "애니메이션": "<lora:cozy animation scenes_20230824111332-000018:0.85>",
    "선택하지 않음" : None
}

print("\nLORA 선택")
for key in LORA_CHOICES.keys():
    print(key)

selected_lora = input("원하는 스타일을 입력하세요: ")

# 데이터베이스의 텍스트 프롬프트로 연결
def get_latest_translated_text():
    # 데이터베이스 연결
    conn = sqlite3.connect('translations.db')
    c = conn.cursor()

    # 가장 최근의 번역된 텍스트를 검색
    c.execute('SELECT translated_text FROM translations ORDER BY id DESC LIMIT 1')

    # 데이터 가져오기
    result = c.fetchone()
    conn.close()

    # 결과가 있다면 번역된 텍스트를 반환, 없으면 빈 문자열 반환
    return result[0] if result else ""

# 이미지 데이터베이스 파일명
db_file = 'image_storage.db'

# 데이터베이스에 이미지 테이블 생성
def create_image_table():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute(''' CREATE TABLE IF NOT EXISTS images(
        id INTEGER PRIMARY KEY,
        image BLOB NOT NULL,
        created_at DATETIME NOT NULL);
        ''')
    conn.commit()
    conn.close()

create_image_table()

# DB에 이미지 저장
def insert_image_to_db(image_data, created_at):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("INSERT INTO images (image, created_at) VALUES (?, ?)", (image_data, created_at))
    conn.commit()
    conn.close()

translated_text = get_latest_translated_text()

# 중간 로그 출력
print(translated_text)

# payload에 필요한 키와 값 추가 : prompt, steps, neagtive_prompt, width, height, LORA 등
payload = {
    "prompt" : translated_text,
    "negative_prompt" : "easynegative, negative_hand_neg, (worst quality, low quality, normal quality:1.4), lowres, skin spots, acnes, skin blemishes, age spot, glans, extra fingers",
    "steps" : 25
}

# LORA 추가
if selected_lora in LORA_CHOICES:
    lora_style = LORA_CHOICES[selected_lora]
    if lora_style:
        payload["prompt"] += lora_style
else:
    print("잘못된 선택입니다.")

print(payload)

# API 요청, 반환값은 images, parameter, info
response = requests.post(url=f'{url}/sdapi/v1/txt2img', json = payload)

r = response.json()

# 이미지 저장, 데이터베이스에 이미지 데이터 삽입
for idx, base64_str in enumerate(r['images']):
    # 이미지 저장, 텍스트 데이터를 이진 데이터로 디코딩
    image_data = base64.b64decode(base64_str.split(",",1)[1])
    image = Image.open(io.BytesIO(base64.b64decode(idx.split(",",1)[1])))

    # API 요청을 보내 이미지 정보 검색
    png_payload = {
        "image": "data:image/png;base64," + idx
    }
    response2 = requests.post(url=f'{url}/sdapi/v1/png-info', json = png_payload)

    # PIL 이미지에 메타 데이터 삽입
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("parameters", response2.json().get("info"))

    # 현재 날짜와 시간을 문자열로 가져와 파일 이름으로 설정
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f'object/output_t2i{current_time}.png'

    # 이미지 저장
    image.save(file_name, pnginfo = pnginfo)
    
    # 데이터베이스에 이미지 데이터 삽입
    insert_image_to_db(image_data, current_time)
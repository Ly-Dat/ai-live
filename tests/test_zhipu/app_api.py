import time
import jwt  # Make sure this is the PyJWT library
import requests
from urllib.parse import urljoin

def generate_token(apikey: str, exp_seconds: int):
    try:
        id, secret = apikey.split(".")
    except Exception as e:
        raise Exception("invalid apikey", e)

    payload = {
        "api_key": id,
        "exp": int(round(time.time())) + exp_seconds,  # PyJWTThe exp field in expects a timestamp in seconds
        "timestamp": int(round(time.time() * 1000)),  # If you need a millisecond timestamp, you can keep this line
    }

    # Encode with PyJWTpayload
    token = jwt.encode(
        payload,
        secret,
        headers={"alg": "HS256", "sign_type": "SIGN"}
    )

    return token


token = generate_token("", 30 * 24 * 3600)

print(token)

base_url = "https://open.bigmodel.cn"

headers = {
    "Authorization": f"Bearer {token}",
}

url = urljoin(base_url, "/api/llm-application/open/application")

data = {
    "page": 1,
    "size": 20
}

# getRequest
response = requests.get(url=url, data=data, headers=headers)

print(response.json())

resp_json = response.json()

tmp_content = "智谱应用列表："

app_id = None

try:
    for data in resp_json["data"]["list"]:
        tmp_content += f"\n应用名：{data['name']}，应用ID：{data['id']}，知识库：{data['knowledge_ids']}"
        app_id = data['id']

    print(tmp_content)
except Exception as e:
    print(e)

def get_resp(prompt):
    url = urljoin(base_url, f"/api/llm-application/open/model-api/{app_id}/invoke")
    data = {
        "prompt": [{"role": "user", "content": prompt}],
        "returnType": "json_string",
        # "knowledge_ids": [],
        # "document_ids": []
    }

    response = requests.post(url=url, json=data, headers=headers)

    try:
        print(response.json())

        resp_json = response.json()
        resp_content = resp_json["data"]["content"]

        print(resp_content)
    except Exception as e:
        print(e)

get_resp("伊卡洛斯和妮姆芙的关系")

import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a9382a9d40789bef")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "semJ6dXY3Q0XDr8FCdSKqdlQK1XmA2iQ")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY")
MINIMAX_GROUP_ID = os.environ.get("MINIMAX_GROUP_ID", "2034271434573877321")

processed_events = set()


def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return resp.json().get("tenant_access_token")


def reply_message(message_id, content):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "msg_type": "text",
        "content": json.dumps({"text": content})
    }
    requests.post(url, headers=headers, json=payload)


def call_minimax(message):
    url = f"https://api.minimax.chat/v1/text/chatcompletion_v2?GroupId={MINIMAX_GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "MiniMax-Text-01",
        "messages": [
            {"role": "system", "content": "你是C5小助手，负责回答C5团队成员的问题，风格友好简洁。"},
            {"role": "user", "content": message}
        ]
    }
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    if "choices" not in data:
        raise Exception(f"API返回异常: {data}")
    return data["choices"][0]["message"]["content"]


@app.route("/feishu", methods=["POST"])
def feishu_event():
    data = request.json

    # URL 验证
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")})

    header = data.get("header", {})
    event_id = header.get("event_id")

    # 去重
    if event_id in processed_events:
        return jsonify({"code": 0})
    processed_events.add(event_id)

    event = data.get("event", {})
    msg = event.get("message", {})

    if msg.get("message_type") != "text":
        return jsonify({"code": 0})

    content = json.loads(msg.get("content", "{}"))
    text = content.get("text", "").strip()

    # 清除 @ 标签
    import re
    text = re.sub(r'@[^\s]+\s*', '', text).strip()

    if not text:
        return jsonify({"code": 0})

    try:
        reply = call_minimax(text)
        reply_message(msg.get("message_id"), reply)
    except Exception as e:
        reply_message(msg.get("message_id"), f"小助手出错了：{str(e)}")

    return jsonify({"code": 0})


@app.route("/", methods=["GET"])
def health():
    return "C5小助手运行中"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

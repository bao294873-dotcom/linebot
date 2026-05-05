from flask import Flask, request
import requests
import urllib.parse

app = Flask(__name__)

LINE_TOKEN = "填你的LINE_TOKEN"
AFFILIATE_ID = "填你的蝦皮ID"

def convert(url):
    encoded = urllib.parse.quote(url, safe='')
    return f"https://s.shopee.tw/an_redir?origin_link={encoded}&affiliate_id={AFFILIATE_ID}&sub_id=linebot"

def reply(token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": token,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=data)

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    for event in data["events"]:
        msg = event["message"]["text"]

        if "shopee" in msg:
            link = convert(msg)
            reply(event["replyToken"], f"已幫你轉好✨\n{link}")

        else:
            reply(event["replyToken"], "請貼蝦皮連結")

    return "OK"

app.run()
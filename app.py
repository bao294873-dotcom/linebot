from flask import Flask, request
import requests
import urllib.parse
import os

app = Flask(__name__)

# 🔑 這兩個一定要改
LINE_TOKEN = "ywb3PURnF6Iraz6L90mfGPl8XjF43EwSu8c+AFpLiSPzmD1TKU/3f/OczG2Ljy4N3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pmkDalO7RjD2SboVGef4m1rZqbbApeFhZWknnJmOTuTCwdB04t89/1O/w1cDnyilFU="
AFFILIATE_ID = "16358460019"


# ===== 蝦皮轉分潤 =====
def convert_shopee(url):
    encoded = urllib.parse.quote(url, safe='')
    return f"https://s.shopee.tw/an_redir?origin_link={encoded}&affiliate_id={AFFILIATE_ID}&sub_id=linebot"


# ===== LINE 回覆 =====
def reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    requests.post(url, headers=headers, json=data)


# ===== 接收 LINE 訊息 =====
@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    for event in data.get("events", []):
        if event.get("type") == "message":
            msg = event["message"]["text"]

            # 👉 判斷蝦皮連結（含短網址）
            if "tw.shp.ee" in msg or "s.shopee.tw" in msg:
                new_link = convert_shopee(msg)

                reply(
                    event["replyToken"],
                    f"已幫你轉好優惠連結✨\n{new_link}"
                )

            else:
                reply(
                    event["replyToken"],
                    "請貼蝦皮商品連結給我🙏"
                )

    return "OK"


# ===== Render 必備（超重要）=====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
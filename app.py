from flask import Flask, request
import requests
import urllib.parse
import os

app = Flask(__name__)

# =========================
# 🔑 只改這兩個地方
# =========================
LINE_TOKEN = "ywb3PURnF6Iraz6L90mfGPl8XjF43EwSu8c+AFpLiSPzmD1TKU/3f/OczG2Ljy4N3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pmkDalO7RjD2SboVGef4m1rZqbbApeFhZWknnJmOTuTCwdB04t89/1O/w1cDnyilFU="
AFFILIATE_ID = "16358460019"

# =========================


# ===== 蝦皮轉分潤（完整安全版）=====
def convert_shopee(url):
    try:
        # 強制去除空白
        url = url.strip()

        # encode
        encoded = urllib.parse.quote(url, safe='')

        new_link = (
            "https://s.shopee.tw/an_redir?"
            f"origin_link={encoded}"
            f"&affiliate_id={AFFILIATE_ID}"
            "&sub_id=linebot"
        )

        return new_link

    except:
        return None


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


# ===== 主邏輯 =====
@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    for event in data.get("events", []):
        if event.get("type") == "message":
            msg = event["message"]["text"]

            # ===== 判斷蝦皮連結 =====
            if "tw.shp.ee" in msg:

                link = convert_shopee(msg)

                if link:
                    reply(
                        event["replyToken"],
                        f"已幫你轉好優惠連結✨\n{link}"
                    )
                else:
                    reply(
                        event["replyToken"],
                        "轉換失敗，請再試一次🙏"
                    )

            else:
                reply(
                    event["replyToken"],
                    "請貼蝦皮商品連結給我🙏"
                )

    return "OK"


# ===== Render 必備（不能改）=====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
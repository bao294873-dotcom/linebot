from flask import Flask, request
import requests
import urllib.parse
import os

app = Flask(__name__)

# ===== 改成你自己的 =====
LINE_TOKEN = "MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU="
AFFILIATE_ID = "16358460019"
BITLY_TOKEN = "920dd5e5ae21d0c75cd3cfc3d50dc53b47576713"


# ===== 展開短網址 =====
def expand_url(url):
    try:
        r = requests.get(url, allow_redirects=True, timeout=5)
        return r.url
    except:
        return url


# ===== 蝦皮轉分潤 =====
def convert_shopee(url):
    try:
        url = url.strip()

        # 展開短網址
        if "shp.ee" in url or "s.shopee.tw" in url:
            url = expand_url(url)

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


# ===== Bitly 短網址 =====
def shorten_url(long_url):
    try:
        url = "https://api-ssl.bitly.com/v4/shorten"

        headers = {
            "Authorization": f"Bearer {BITLY_TOKEN}",
            "Content-Type": "application/json"
        }

        data = {
            "long_url": long_url
        }

        r = requests.post(url, headers=headers, json=data)

        print("BITLY STATUS =", r.status_code)
        print("BITLY RESPONSE =", r.text)

        return r.json().get("link", long_url)

    except Exception as e:
        print("BITLY ERROR =", e)
        return long_url


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

    r = requests.post(url, headers=headers, json=data)

    print("LINE REPLY STATUS =", r.status_code)
    print("LINE REPLY RESPONSE =", r.text)


# ===== 主邏輯 =====
@app.route("/callback", methods=["POST"])
def callback():

    # ===== 測試環境變數 =====
    print("LINE_TOKEN =", LINE_TOKEN)
    print("AFFILIATE_ID =", AFFILIATE_ID)
    print("BITLY_TOKEN =", BITLY_TOKEN)

    data = request.json

    for event in data.get("events", []):

if event.get("type") == "message":

    msg = event["message"]["text"]

    print("收到訊息 =", msg)

    if "http" in msg:

        # 轉分潤
        link = convert_shopee(msg)

        print("分潤連結 =", link)

        if link:

            short_link = shorten_url(link)

            print("短網址 =", short_link)

            reply(
                event["replyToken"],
                f"🔥 已幫你轉好優惠連結\n\n👉 {short_link}"
            )

        else:

            reply(
                event["replyToken"],
                "轉換失敗🙏"
            )

    else:

        reply(
            event["replyToken"],
            "請貼網址給我🙏"
        )

    return "OK"


# ===== Render 啟動 =====
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
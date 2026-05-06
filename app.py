from flask import Flask, request
import requests
import urllib.parse
import os

app = Flask(__name__)

LINE_TOKEN = os.environ.get("ywb3PURnF6Iraz6L90mfGPl8XjF43EwSu8c+AFpLiSPzmD1TKU/3f/OczG2Ljy4N3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pmkDalO7RjD2SboVGef4m1rZqbbApeFhZWknnJmOTuTCwdB04t89/1O/w1cDnyilFU="
)
AFFILIATE_ID = os.environ.get("16358460019")
BITLY_TOKEN = os.environ.get("920dd5e5ae21d0c75cd3cfc3d50dc53b47576713")



def expand_url(url):
    try:
        r = requests.get(url, allow_redirects=True, timeout=5)
        return r.url
    except:
        return url


def convert_shopee(url):
    try:
        url = url.strip()

        if "shp.ee" in url or "s.shopee.tw" in url:
            url = expand_url(url)

        encoded = urllib.parse.quote(url, safe='')

        return (
            "https://s.shopee.tw/an_redir?"
            f"origin_link={encoded}"
            f"&affiliate_id={AFFILIATE_ID}"
            "&sub_id=linebot"
        )
    except:
        return None


# ⭐ 加這段（你原本沒有）
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
        return r.json().get("link", long_url)

    except:
        return long_url


def reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }

    requests.post(url, headers=headers, json=data)


@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    for event in data.get("events", []):
        if event.get("type") == "message":
            msg = event["message"]["text"]

            if "shopee" in msg or "shp.ee" in msg:

                link = convert_shopee(msg)

                if link:
                    # ⭐ 這裡才會變短網址
                    short_link = shorten_url(link)

                    reply(
                        event["replyToken"],
                        f"🔥 已幫你轉好優惠連結\n\n👉 {short_link}"
                    )
                else:
                    reply(event["replyToken"], "轉換失敗🙏")

            else:
                reply(event["replyToken"], "請貼蝦皮商品連結🙏")

    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
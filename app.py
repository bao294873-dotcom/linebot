from flask import Flask, request
import requests
import urllib.parse
import os
import hmac
import hashlib
import time

app = Flask(__name__)

# ===== 你的資料 =====
LINE_TOKEN = "MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU="

AFFILIATE_ID = "16358460019"

PICSEE_TOKEN = "34b673ff3e4a16272b2e6ce89e0c3be44b81a55e"

# ===== 新增：酷澎金鑰 =====
COUPANG_ACCESS_KEY = "d8c159f4-5cb4-4496-bf2b-22011c715c09"
COUPANG_SECRET_KEY = "0fc019b181ee0508506e9889272fcc93a43942e7"


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

# ===== PicSee 縮網址 =====
def shorten_url(long_url):
    try:
        api_url = "https://api.picsee.io/v1/links"
        headers = {
            "X-API-TOKEN": PICSEE_TOKEN,
            "Content-Type": "application/json"
        }
        data = {"target": long_url}
        r = requests.post(api_url, headers=headers, json=data)
        result = r.json()
        return result["data"]["picseeUrl"]
    except Exception as e:
        print("PicSee錯誤 =", e)
        return long_url

# ===== 新增：取得酷澎每日特價 =====
def get_coupang_goldbox():
    try:
        method = "GET"
        path = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/goldbox"
        
        # 處理 UTC 時間
        os.environ['TZ'] = 'GMT+0'
        if hasattr(time, 'tzset'):
            time.tzset()
        datetime_str = time.strftime('%y%m%d') + 'T' + time.strftime('%H%M%S') + 'Z'
        
        # 產生 HMAC 簽章
        message = datetime_str + method + path
        signature = hmac.new(
            bytes(COUPANG_SECRET_KEY, "utf-8"),
            bytes(message, "utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        authorization = f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, signed-date={datetime_str}, signature={signature}"
        
        url = "https://api-gateway.coupang.com" + path
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json"
        }
        
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", [])
        else:
            print("酷澎 API 錯誤 =", r.text)
            return []
    except Exception as e:
        print("抓取酷澎發生例外錯誤 =", e)
        return []

# ===== 修改：LINE 回覆 (支援卡片格式) =====
def reply(reply_token, messages_list):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": reply_token,
        "messages": messages_list # 改為接收陣列
    }
    r = requests.post(url, headers=headers, json=data)
    print("LINE REPLY STATUS =", r.status_code)


# ===== 主程式 =====
@app.route("/callback", methods=["POST"])
def callback():
    data = request.json
    for event in data.get("events", []):
        if event.get("type") == "message":
            msg = event["message"]["text"]
            reply_token = event["replyToken"]

            # === 情境 1：使用者輸入「特價」===
            if msg == "特價":
                deals = get_coupang_goldbox()
                
                if not deals:
                    reply(reply_token, [{"type": "text", "text": "目前無法取得酷澎特價商品，請稍後再試🙏"}])
                    continue

                # 準備組裝 LINE 輪播卡片 (最多 10 張)
                columns = []
                for item in deals[:10]:
                    columns.append({
                        "thumbnailImageUrl": item.get("productImage", ""), # 商品圖片
                        "title": str(item.get("productName", ""))[:40],    # 標題最多 40 字
                        "text": f"特價: NT$ {item.get('productPrice', '')}", # 價格
                        "actions": [
                            {
                                "type": "uri",
                                "label": "立即搶購",
                                "uri": item.get("productUrl", "") # 酷澎的分潤網址
                            }
                        ]
                    })
                
                # 建立卡片模板
                carousel_message = {
                    "type": "template",
                    "altText": "今日酷澎特價商品出爐囉！", # 通知列顯示的文字
                    "template": {
                        "type": "carousel",
                        "columns": columns
                    }
                }
                
                # 傳送卡片
                reply(reply_token, [carousel_message])

            # === 情境 2：收到蝦皮網址 ===
            elif "http" in msg:
                link = convert_shopee(msg)
                if link:
                    short_link = shorten_url(link)
                    reply(reply_token, [{"type": "text", "text": f"🔥 已幫你轉好優惠連結\n\n👉 {short_link}"}])
                else:
                    reply(reply_token, [{"type": "text", "text": "轉換失敗🙏"}])

            # === 情境 3：其他訊息 ===
            else:
                reply(reply_token, [{"type": "text", "text": "請貼蝦皮網址給我，或輸入「特價」查看酷澎優惠🙏"}])

    return "OK"

# ===== 啟動 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
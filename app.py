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
        return long_url

# ===== 改用：搜尋酷澎商品 API =====
def search_coupang_deals():
    try:
        # 用 URL 編碼把中文字轉成 API 看得懂的格式
        keyword = urllib.parse.quote("特價") 
        method = "GET"
        # 改成呼叫 search 搜尋端點，並限制抓取 10 筆
        path = f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/search?keyword={keyword}&limit=10"
        
        os.environ['TZ'] = 'GMT+0'
        if hasattr(time, 'tzset'):
            time.tzset()
        datetime_str = time.strftime('%y%m%d') + 'T' + time.strftime('%H%M%S') + 'Z'
        
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
            "Content-Type": "application/json",
            "X-MARKET": "TW" # 🔥 一樣要貼上台灣專屬標籤
        }
        
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 200:
            # 搜尋 API 的回傳結構稍微不一樣，商品資料包在 productData 裡面
            products = r.json().get("data", {}).get("productData", [])
            return products, "OK"
        else:
            return [], f"狀態碼: {r.status_code}\n內容: {r.text}"
            
    except Exception as e:
        return [], f"系統例外錯誤: {str(e)}"
            
    except Exception as e:
        return [], f"系統例外錯誤: {str(e)}"

# ===== LINE 回覆 =====
def reply(reply_token, messages_list):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": reply_token,
        "messages": messages_list
    }
    requests.post(url, headers=headers, json=data)


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
                # 🔴 記得把這裡改成呼叫 search_coupang_deals
                deals, error_msg = search_coupang_deals() 
                
                if not deals:
                    reply(reply_token, [{"type": "text", "text": f"酷澎抓取失敗 😭\n\n🔍 偵錯原因：\n{error_msg}"}])
                    continue

                columns = []
                for item in deals[:10]:
                    columns.append({
                        "thumbnailImageUrl": item.get("productImage", ""),
                        "title": str(item.get("productName", ""))[:40],
                        "text": f"價格: NT$ {item.get('productPrice', '')}",
                        "actions": [
                            {
                                "type": "uri",
                                "label": "立即搶購",
                                "uri": item.get("productUrl", "")
                            }
                        ]
                    })

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
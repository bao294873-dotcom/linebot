import requests
import urllib.parse
import os
import csv
from io import StringIO

app = Flask(__name__)

# ===== 你的資料 =====
LINE_TOKEN = "MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU="
AFFILIATE_ID = "16358460019"

# ===== 新增：你的試算表 ID (從網址複製出來的那段) =====
SHEET_ID = "1mArqvVEM6AISWVefz2_UjCe23LeJ6DAZQTlJIAlrCXk"

# ===== 免金鑰：直接讀取試算表 =====
def get_deals_from_sheet(keyword):
    try:
        # 直接去下載 Google 表單的 CSV 格式資料
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        r = requests.get(url, timeout=10)
        r.encoding = 'utf-8' # 確保中文不會變亂碼
        
        # 將下載下來的文字轉換成字典格式
        csv_reader = csv.DictReader(StringIO(r.text))
        records = list(csv_reader)
        
        # 篩選出符合「關鍵字」的商品
        matched_deals = []
        for row in records:
            if str(row.get("觸發關鍵字", "")).strip() == keyword:
                matched_deals.append(row)
        return matched_deals
    except Exception as e:
        print("讀取表單失敗 =", e)
        return None

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

# ===== TinyURL 縮網址 =====
def shorten_url(long_url):
    try:
        api_url = f"https://tinyurl.com/api-create.php?url={long_url}"
        r = requests.get(api_url, timeout=10)
        
        if r.status_code == 200:
            return r.text, "OK"
        else:
            return long_url, f"TinyURL 錯誤 (HTTP {r.status_code})"
    except Exception as e:
        return long_url, f"縮網址異常: {str(e)}"

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
            msg = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # === 引擎 1：讀取 Google 試算表 ===
            deals = get_deals_from_sheet(msg)
            
            if deals:
                columns = []
                for item in deals[:10]:
                    columns.append({
                        "thumbnailImageUrl": str(item.get("圖片網址", "")).strip(),
                        "title": str(item.get("商品名稱", ""))[:40],
                        "text": str(item.get("價格", ""))[:60],
                        "actions": [
                            {
                                "type": "uri",
                                "label": "立即搶購",
                                "uri": str(item.get("你的分潤短網址", "")).strip()
                            }
                        ]
                    })
                
                carousel_message = {
                    "type": "template",
                    "altText": f"{msg} 專屬優惠來囉！",
                    "template": {
                        "type": "carousel",
                        "columns": columns
                    }
                }
                reply(reply_token, [carousel_message])
                continue 

            # === 引擎 2：蝦皮網址自動轉分潤 ===
            if "http" in msg:
                link = convert_shopee(msg)
                if link:
                    short_link, status = shorten_url(link)
                    if status == "OK":
                        reply(reply_token, [{"type": "text", "text": f"🔥 已幫你轉好優惠連結\n\n👉 {short_link}"}])
                    else:
                        reply(reply_token, [{"type": "text", "text": f"轉換成功，但縮網址失敗\n\n👉 原連結：{short_link}"}])
                else:
                    reply(reply_token, [{"type": "text", "text": "轉換失敗🙏"}])
            
            # === 情境 3：其他訊息 ===
            else:
                reply(reply_token, [{"type": "text", "text": "請貼蝦皮網址給我，或輸入關鍵字查看優惠喔🙏"}])

    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
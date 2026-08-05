from flask import Flask, request
import requests
import urllib.parse
import csv
from io import StringIO
import re             # 升級版轉址與網址比對
import datetime       # 升級版轉址產生時間戳
from curl_cffi import requests as cffi_requests  # 關鍵：用於繞過蝦皮 403 阻擋

app = Flask(__name__)

# ==========================================
# 🔐 1. 請在此填入你自己的金鑰與設定
# ==========================================
LINE_TOKEN = 'MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU='
SHEET_ID = '1mArqvVEM6AISWVefz2_UjCe23LeJ6DAZQTlJIAlrCXk'         # 你的試算表 ID
SHOPEE_AFF_ID = "16358460019"    # 你的蝦皮分潤 ID


# ==========================================
# ✨ 2. 防睡眠網頁首頁 (讓 cron-job 用 GET 戳進來)
# ==========================================
@app.route("/", methods=['GET'])
def index():
    return "機器人運作中，請勿打擾 🤖", 200

# ==========================================
# 📦 3. 讀取 Google 試算表的函數
# ==========================================
def get_deals_from_sheet(sheet_id):
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    response = requests.get(csv_url)
    response.encoding = 'utf-8'
    
    deals = []
    if response.status_code == 200:
        csv_data = StringIO(response.text)
        reader = csv.DictReader(csv_data)
        for row in reader:
            deals.append(row)
    return deals

# ==========================================
# 🎨 4. 將資料轉成 LINE 滑動卡片的函數
# ==========================================
def create_carousel_message(deals):
    columns = []
    for deal in deals[:10]: # LINE 滑動卡片最多只能放 10 頁
        encoded_url = urllib.parse.quote(deal.get('你的分潤短網址', ''), safe=':/?&=')
        encoded_image_url = urllib.parse.quote(deal.get('圖片網址', ''), safe=':/?&=')
        
        column = {
            "thumbnailImageUrl": encoded_image_url,
            "imageBackgroundColor": "#FFFFFF",
            "title": deal.get('商品名稱', '')[:40],
            "text": f"🔥 特價: {deal.get('價格', '')}\n平台: {deal.get('平台', '')}",
            "defaultAction": {
                "type": "uri",
                "label": "查看詳情",
                "uri": encoded_url
            },
            "actions": [
                {
                    "type": "uri",
                    "label": "👉 前往搶購",
                    "uri": encoded_url
                }
            ]
        }
        columns.append(column)
        
    return {
        "type": "template",
        "altText": "最新優惠來囉！請在手機上查看",
        "template": {
            "type": "carousel",
            "columns": columns,
            "imageAspectRatio": "square",
            "imageSize": "cover"
        }
    }

# ==========================================
# 🛠️ 升級版蝦皮轉址核心 (已加入 curl_cffi 破解 403)
# ==========================================
def build_sub_id():
    # 直接用內建 datetime 處理台灣時間 (UTC+8)
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)
    return f"linebot-{now.strftime('%Y%m%d%H%M%S')}"

def convert_shopee_link(original_url, aff_id):
    url = original_url
    
    # 1. 處理 an_redir 包過的連結
    if 'an_redir' in url:
        match = re.search(r'origin_link=([^&]+)', url)
        if match:
            url = urllib.parse.unquote(match.group(1))

    # 2. 展開短網址 (使用 curl_cffi 繞過 ALB 403 防火牆)
    is_short_url = re.search(r'shp\.ee|shope\.ee|s\.shopee\.tw|tw\.shp\.ee', url, re.IGNORECASE)
    if is_short_url and 'an_redir' not in url:
        try:
            # impersonate="chrome120" 模擬真實 Chrome 瀏覽器 TLS 指紋
            resp = cffi_requests.get(
                url, 
                impersonate="chrome120", 
                allow_redirects=True, 
                timeout=8
            )
            if resp.status_code == 200 and resp.url:
                url = resp.url
        except Exception as e:
            print(f"[短網址展開失敗] {e}")
            pass

    # 3. 清理舊的追蹤參數
    url = re.sub(r'[?&](mmp_pid|affiliate_id|aff_id|sub_id|utm_source|utm_medium|utm_campaign|uls_trackid)=[^&]*', '', url)
    if url.endswith('?'):
        url = url[:-1]

    # 4. 組裝官方分潤連結
    sub_id = build_sub_id()
    encoded = urllib.parse.quote(url)
    return f"https://s.shopee.tw/an_redir?origin_link={encoded}&affiliate_id={aff_id}&sub_id={sub_id}"

# ==========================================
# 🤖 5. 處理 LINE 傳來訊息的主程式 (Webhook)
# ==========================================
@app.route("/", methods=['POST'])
def webhook():
    try:
        body = request.get_json()
    except Exception as e:
        print(f"[收到非法 JSON] {e}")
        return 'Invalid JSON', 400
    
    if 'events' in body:
        for event in body['events']:
            # 處理文字訊息
            if event['type'] == 'message' and event['message']['type'] == 'text':
                reply_token = event['replyToken']
                user_message = event['message']['text'].strip()
                
                # 預設回覆訊息
                reply_message = {
                    "type": "text",
                    "text": "請傳送蝦皮商品連結傳給我，我幫你轉成優惠連結 🛍️\n\n或輸入蝦皮/酷澎查看隱藏優惠！"
                }
                
                # --------------------------------------------------
                # 情境 A：使用者傳送「網址」(觸發單一按鈕結帳卡片)
                # --------------------------------------------------
                url_match = re.search(r'(https?://[^\s]+)', user_message)
                
                if url_match:
                    extracted_url = url_match.group(1)
                    
                    # 把抽出來的純網址丟進去轉址
                    target_url = convert_shopee_link(extracted_url, SHOPEE_AFF_ID)                    
                
                    reply_message = {
                        "type": "template",
                        "altText": "🎁 專屬優惠連結已產生！請查看",
                        "template": {
                            "type": "buttons",
                            "title": "🎁 專屬優惠連結已產生 🎁",
                            "text": "⚠️ 優惠劵數量有限\n⏰ 請儘速完成訂單\n🔥 點擊下方立即結帳享折扣",
                            "actions": [
                                {
                                    "type": "uri",
                                    "label": "🛒 出發～買買買 🛒",
                                    "uri": target_url
                                }
                            ]
                        }
                    }
                    
                # --------------------------------------------------
                # 情境 B：呼叫「分類大廳」選單
                # --------------------------------------------------
                elif user_message in ["分類", "目錄", "特價商品"]:
                    reply_message = {
                        "type": "template",
                        "altText": "請選擇您想看的特價分類",
                        "template": {
                            "type": "buttons",
                            "title": "🛍️ 嚴選特價分類大廳",
                            "text": "請點擊下方按鈕，逛逛今日專屬優惠！",
                            "actions": [
                                {
                                    "type": "message",
                                    "label": "💄 美妝保養",
                                    "text": "找美妝"
                                },
                                {
                                    "type": "message",
                                    "label": "💻 3C家電",
                                    "text": "找3C"
                                },
                                {
                                    "type": "message",
                                    "label": "🍼 母嬰用品",
                                    "text": "找母嬰"
                                },
                                {
                                    "type": "message",
                                    "label": "🏠 居家生活",
                                    "text": "找居家"
                                }
                            ]
                        }
                    }
                    
                # --------------------------------------------------
                # 情境 C：讓 Python 閉嘴的「靜音關鍵字」
                # --------------------------------------------------
                elif user_message in ["推廣優惠券"]:
                    continue
                    
                # --------------------------------------------------
                # 情境 D：處理關鍵字與分類暗號
                # --------------------------------------------------
                else:
                    all_deals = get_deals_from_sheet(SHEET_ID)
                    
                    matched_deals = [d for d in all_deals if user_message in d.get('觸發關鍵字', '')]
                    
                    if matched_deals:
                        reply_message = create_carousel_message(matched_deals)
                    else:
                        reply_message = {
                            "type": "text",
                            "text": "目前沒有找到相關的優惠喔！\n你可以輸入【分類】來查看特價目錄，或直接貼上你想買的商品網址給我幫你找優惠！"
                        }
                        
                # --------------------------------------------------
                # 將結果回傳給使用者
                # --------------------------------------------------
                headers = {
                    'Authorization': f'Bearer {LINE_TOKEN}',
                    'Content-Type': 'application/json'
                }
                data = {
                    "replyToken": reply_token,
                    "messages": [reply_message]
                }
                requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)
                
    return 'OK'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
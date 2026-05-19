from flask import Flask, request
import requests
import urllib.parse
import csv
from io import StringIO

app = Flask(__name__)

# ===== 1. 請填入你自己的設定值 =====
LINE_TOKEN = 'MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU='  # 你的 LINE Token
SHEET_ID = '1mArqvVEM6AISWVefz2_UjCe23LeJ6DAZQTlJIAlrCXk'          # 你的試算表 ID
SHOPEE_AFF_ID = "16358460019"              # 你的蝦皮分潤 ID


# ===== ✨ 新增這個：讓排程工具「戳」進來的網頁首頁 (防睡眠) =====
@app.route("/", methods=['GET'])
def index():
    return "機器人運作中，請勿打擾 🤖", 200


# ===== 2. 讀取 Google 試算表的函數 =====
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

# ===== 3. 將資料轉成 LINE 滑動卡片的函數 =====
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

# ===== 4. 處理 LINE 傳來訊息的主程式 =====
@app.route("/", methods=['POST'])
def webhook():
    body = request.get_json()
    
    if 'events' in body:
        for event in body['events']:
            if event['type'] == 'message' and event['message']['type'] == 'text':
                reply_token = event['replyToken']
                user_message = event['message']['text'].strip()
                
                # --------------------------------------------------
                # 情境 A：使用者傳送「網址」(觸發單一按鈕結帳卡片)
                # --------------------------------------------------
                if user_message.startswith("http"):
                    
                    target_url = user_message
                    
                    # 確認傳來的是蝦皮網址，才幫它加上分潤尾巴
                    if "shopee.tw" in target_url or "shope.ee" in target_url:
                        if "?" in target_url:
                            target_url = f"{target_url}&aff_id={SHOPEE_AFF_ID}"
                        else:
                            target_url = f"{target_url}?aff_id={SHOPEE_AFF_ID}"

                    # 建立華麗的「按鈕模板訊息」
                    reply_message = {
                        "type": "template",
                        "altText": "🎁 優惠券已套用完成",
                        "template": {
                            "type": "buttons",
                            "title": "🎁 優惠券已套用完成",
                            "text": "⚠️ 折扣券採限量使用，用完提前截止\n⏰ 點擊後請盡速結帳保留優惠\n🔥 點擊下方立即結帳享折扣",
                            "actions": [
                                {
                                    "type": "uri",
                                    "label": "🛒出發買買買🛒",
                                    "uri": target_url
                                }
                            ]
                        }
                    }
                    
                # --------------------------------------------------
                # 情境 B：使用者傳送「關鍵字」(觸發試算表滑動卡片)
                # --------------------------------------------------
                else:
                    all_deals = get_deals_from_sheet(SHEET_ID)
                    
                    # 篩選出「觸發關鍵字」欄位符合使用者輸入的資料
                    matched_deals = [d for d in all_deals if user_message in d.get('觸發關鍵字', '')]
                    
                    if matched_deals:
                        reply_message = create_carousel_message(matched_deals)
                    else:
                        reply_message = {
                            "type": "text",
                            "text": "目前沒有找到相關的優惠喔！試試看輸入【優惠】或直接貼上你想買的蝦皮商品網址給我！"
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
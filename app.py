from flask import Flask, request
import requests
import urllib.parse
import csv
from io import StringIO

app = Flask(__name__)
# ==========================================
# 🔐 1. 請在此填入你自己的金鑰與設定
# ==========================================
LINE_TOKEN = 'MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU='  # 你的 LINE Token
SHEET_ID = '1mArqvVEM6AISWVefz2_UjCe23LeJ6DAZQTlJIAlrCXk'          # 你的試算表 ID
SHOPEE_AFF_ID = "16358460019"              # 你的蝦皮分潤 ID
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
# 🤖 5. 處理 LINE 傳來訊息的主程式 (Webhook)
# ==========================================
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
                    
                    try:
                        # 💥【反攔截核心】：遇到蝦皮短網址先解開
                        if "s.shopee.tw" in target_url or "shope.ee" in target_url:
                            response = requests.head(target_url, allow_redirects=True, timeout=5)
                            target_url = response.url
                        
                        # 清洗網址並換上自己的分潤 ID
                        if "shopee.tw" in target_url:
                            if "?" in target_url:
                                target_url = target_url.split("?")[0]
                            target_url = f"{target_url}?aff_id={SHOPEE_AFF_ID}"
                            
                    except Exception as e:
                        print(f"還原短網址發生錯誤: {e}")
                        if "?" in target_url:
                            target_url = f"{target_url}&aff_id={SHOPEE_AFF_ID}"
                        else:
                            target_url = f"{target_url}?aff_id={SHOPEE_AFF_ID}"

                    # 建立華麗的「按鈕模板訊息」 
                    reply_message = {
                        "type": "template",
                        "altText": "🎁 優惠券已成功套用！請查看並結帳",
                        "template": {
                            "type": "buttons",
                            "title": "✨優惠券已套用成功✨",
                            "text": "🔥 點擊下方立即結帳享折扣\n⚠️ 折扣券採限量使用\n⏰ 請儘速完成訂單",
                            "actions": [
                                {
                                    "type": "uri",
                                    "label": "🛒 出發～結帳去 🛒",
                                    "uri": target_url
                                }
                            ]
                        }
                    }
                    
                # --------------------------------------------------
                # 🤫 情境 B：讓 Python 閉嘴的「靜音關鍵字」
                # --------------------------------------------------
                elif user_message in ["推廣優惠券"]:
                    # 遇到圖文選單專用的字，Python 直接跳過，交給 LINE 後台回覆！
                    continue
                    
                # --------------------------------------------------
                # 情境 C：處理關鍵字與分類暗號 (壓軸的 else)
                # --------------------------------------------------
                else:
                    all_deals = get_deals_from_sheet(SHEET_ID)
                    
                    matched_deals = [d for d in all_deals if user_message in d.get('觸發關鍵字', '')]
                    
                    if matched_deals:
                        reply_message = create_carousel_message(matched_deals)
                    else:
                        reply_message = {
                            "type": "text",
                            "text": "目前沒有找到相關的優惠喔！請直接貼上你想買的蝦皮商品網址給我幫你找優惠！"
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
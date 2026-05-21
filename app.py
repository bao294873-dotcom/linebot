from flask import Flask, request
import requests
import urllib.parse
import csv
import os # 用來讀取 Render 的 PORT
from io import StringIO
import pytz # 用來轉時區
import datetime

app = Flask(__name__)

# ==========================================
# 🔐 1. 請在此填入你自己的金鑰與設定
# ==========================================
# (原本代碼的設定區)
LINE_TOKEN = 'MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU=' # 貼上你的 LINE Channel Access Token
SHEET_ID = '1mArqvVEM6AISWVefz2_UjCe23LeJ6DAZQTlJIAlrCXk' # 已幫你對過是正確的ID
SHOPEE_AFF_ID = '16358460019' # 貼上你的純數字蝦皮分潤 ID


# ==========================================
# ✨ 2. 防睡眠網頁首頁
# ==========================================
@app.route("/", methods=['GET'])
def index():
    return "機器人重生中，酷澎卡片這次絕對彈出來！🤖", 200

# ==========================================
# 📦 3. 讀取 Google 試算表的函數 (升級：精準讀取「優惠」工作表 )
# ==========================================
def get_deals_from_sheet(sheet_id):
    # 💥【修正細節】：強制指定讀取名為「優惠」 的工作表標籤 (修正 image_12.png 的潛在問題)
    sheet_name = urllib.parse.quote('優惠') # 將中文名稱編碼
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    
    try:
        response = requests.get(csv_url, timeout=10) # 加上逾時設定，防止 Render 卡住
        response.encoding = 'utf-8'
        
        deals = []
        if response.status_code == 200:
            csv_data = StringIO(response.text)
            # 使用 DictReader 精準抓取標題欄位
            reader = csv.DictReader(csv_data)
            for row in reader:
                deals.append(row)
        return deals
    except Exception as e:
        print(f"[試算表讀取錯誤] {e}")
        return []

# ==========================================
# 🎨 4. 將資料轉成 LINE 滑動卡片的函數
# ==========================================
def create_carousel_message(deals):
    columns = []
    
    # 預設圖片 (萬一試算表沒填時使用)
    default_img = "https://shopee.tw/favicon.ico" # 蝦皮圖示
    
    for deal in deals[:10]: # LINE 滑動卡片最多只能放 10 頁
        # 抓取資料並去除空白
        product_name = deal.get('商品名稱', '').strip()
        price = deal.get('價格', '').strip()
        platform = deal.get('平台', '').strip()
        img_url = deal.get('圖片網址', '').strip()
        buy_url = deal.get('你的分潤短網址', '').strip()
        
        # 進行網址編碼
        # (原本代碼的編碼邏輯)
        encoded_buy_url = urllib.parse.quote(buy_url, safe=':/?&=')
        encoded_img_url = urllib.parse.quote(img_url, safe=':/?&=')
        
        # 圖片網址保底
        final_img_url = encoded_img_url if encoded_img_url.startswith("http") else default_img
        
        # 內文說明限制最多 60 字 (避免 LINE 報錯)
        desc_text = f"🔥 特價: {price}\n平台: {platform}"[:60]
        
        column = {
            "thumbnailImageUrl": final_img_url,
            "imageBackgroundColor": "#FFFFFF",
            "title": product_name[:40], # 標題最多40字
            "text": desc_text,
            "defaultAction": {
                "type": "uri",
                "label": "查看詳情",
                "uri": encoded_buy_url
            },
            "actions": [
                {
                    "type": "uri",
                    "label": "🛒 前往搶購 🛒",
                    "uri": encoded_buy_url
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
# Helper 函數：產生 sub_id (用於轉址追蹤)
# ==========================================
def build_sub_id():
    # 設定台北時區，Render 環境通常是 UTC
    taipei_tz = pytz.timezone('Asia/Taipei')
    now = datetime.datetime.now(taipei_tz)
    # 對應 yyyyMMddHHmmss 格式
    ts = now.strftime('%Y%m%d%H%M%S')
    return f"linebot-{ts}"

# ==========================================
# 🤖 5. 處理 LINE 傳來訊息的主程式 (Webhook)
# ==========================================
@app.route("/", methods=['POST'])
def webhook():
    # 防止多個 Google 帳號造成的 Token 混亂，加上錯誤抓取機制
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
                # 用戶輸入的字，去除空白
                user_message = event['message']['text'].strip()
                
                # 預設回覆訊息
                # 對應截圖 image_0.png 的通用台詞
                reply_message = {
                    "type": "text",
                    "text": "請傳送蝦皮商品連結傳給我，我幫你轉成優惠連結 🛍️\n\n或輸入特定關鍵字查看隱藏優惠！"
                }

                # --------------------------------------------------
                # 情境 A：使用者傳送「網址」
                # --------------------------------------------------
                if user_message.startswith("http"):
                    # 建立 sub_id
                    sid = build_sub_id()
                    # 直接組裝成蝦皮官方an_redir分潤連結
                    target_url = f"https://s.shopee.tw/an_redir?origin_link={urllib.parse.quote(user_message)}&affiliate_id={SHOPEE_AFF_ID}&sub_id={sid}"
                    
                    # 建立華麗的「按鈕模板訊息」
                    # (原本代碼的卡片邏輯)
                    reply_message = {
                        "type": "template",
                        "altText": "🎁 專屬優惠連結已產生！請查看",
                        "template": {
                            "type": "buttons",
                            "title": "🎁 專屬優惠連結已產生 🎁",
                            "text": "⚠️ 點選下方按鈕前往查看\n❗ 若有優惠券將自動保留\n📅 請盡速結帳保留優惠",
                            "actions": [
                                {
                                    "type": "uri",
                                    "label": "🛒 點我前往查看 🛒",
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
                                { "type": "message", "label": "💄 美妝保養", "text": "找美妝" },
                                { "type": "message", "label": "💻 3C家電", "text": "找3C" },
                                { "type": "message", "label": "🍼 母嬰用品", "text": "找母嬰" },
                                { "type": "message", "label": "🏠 居家生活", "text": "找居家" }
                            ]
                        }
                    }
                    
                # --------------------------------------------------
                # 🤫 (💥【修正核心】：完全刪除原本的情境 C 靜音關鍵字邏輯！讓酷澎不再被吞掉！)
                # --------------------------------------------------
                    
                # --------------------------------------------------
                # 情境 D：處理關鍵字與分類暗號 (原本的 else)
                # --------------------------------------------------
                else:
                    all_deals = get_deals_from_sheet(SHEET_ID)
                    
                    # 篩選出「觸發關鍵字」欄位符合使用者輸入的資料
                    # 對應截圖中 image_5.png 的 A 欄，支援多關鍵字比對
                    matched_deals = []
                    if all_deals:
                        for deal in all_deals:
                            cell_keywords = deal.get('觸發關鍵字', '')
                            # 將 A,B,C 轉成 ["A", "B", "C"] 並去除空白
                            keyword_list = [k.strip() for k in cell_keywords.split(',')]
                            
                            if user_message in keyword_list:
                                matched_deals.append(deal)
                    
                    # 如果有找到匹配的特價商品
                    if matched_deals:
                        # 呼叫函數產生輪播卡片 (Carousel)
                        reply_message = create_carousel_message(matched_deals)
                    else:
                        # 如果輸入的關鍵字沒有對應商品，就保持預設台詞
                        pass
                        
                # --------------------------------------------------
                # 將結果回傳給使用者
                # --------------------------------------------------
                headers = {
                    'Authorization': f'Bearer {LINE_TOKEN}',
                    'Content-Type': 'application/json'
                }
                data = {
                    "replyToken": reply_token,
                    "messages": [reply_message] # 將卡片或文字訊息打包發送
                }
                # 使用原本代碼的 requests 發送 Reply
                requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)
                
    return 'OK'

if __name__ == "__main__":
    # Render 會自動設定 PORT，萬一沒有就用保底 10000
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
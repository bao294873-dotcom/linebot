from flask import Flask, request, abort
import requests
import urllib.parse
import csv
import re
import datetime
import pytz  # Render 環境通常是 UTC，我們需要這個來轉成台北時間
from io import StringIO
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, URIAction

app = Flask(__name__)

# ==========================================
# 🔐 1. 請在此填入你自己的金鑰與設定
# ==========================================
# 你的 LINE Token
LINE_TOKEN = 'MMsqceAeEexXHCQ/EWwzzmLTg/WCBrg+vA7FxHXZCrxWHkscjIDJuf0EJ9V0n4MR3NwrF6h0M91KK+PGPpyNtr Y5z5YYJ1nHk2Z34b/Z+pkT+ULTxjfZ5ONg+G7i6fpJl5sTjvon6roCQQQGRT2RCwdB04t89/1O/w1cDnyilFU=' 
# 你的 LINE Secret (與 handler 搭配使用)
LINE_SECRET = 'ed8a8af9c486ff925f65153dad28698f' 

# 你的試算表 ID，已幫你對過是正確的
SHEET_ID = '1mArqvVEM6AISWVefz2_UjCe23LeJ6DAZQTlJIAlrCXk' 

# 你的蝦皮分潤 ID
SHOPEE_AFF_ID = '16358460019' 

# 建立 LINE Bot API 和 Webhook 處理器
line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

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
    try:
        response = requests.get(csv_url)
        response.encoding = 'utf-8'
        
        deals = []
        if response.status_code == 200:
            csv_data = StringIO(response.text)
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

# ============================================================
# ⚙️ 移植自 JS 版的核心：蝦皮連結轉換
# 步驟：展開短網址 → 清參數 → 加聯盟參數
# 失敗時回傳 null（呼叫方收到 null 就通知使用者）
# ============================================================
def convert_shopee_link(original_url):
    """
    對應原本 JS 的 convertShopeeLink(originalUrl)
    將原始蝦皮連結轉換為分潤連結。
    失敗時回傳 None。
    """
    url = original_url

    # 1. 如果是 an_redir 包過的，先抽出原始連結
    if 'an_redir' in url:
        # 使用 re.search 對應 JS 的 match(/origin_link=([^&]+)/)
        match = re.search(r'origin_link=([^&]+)', url)
        if match:
            url = urllib.parse.unquote(match.group(1)) # 對應 JS 的 decodeURIComponent

    # 2. 展開短網址
    # 使用 re.search 對應 JS 的 /.../i.test(url)
    is_short_url = (
        re.search(r'shp\.ee', url, re.IGNORECASE) or
        re.search(r'shope\.ee', url, re.IGNORECASE) or
        (re.search(r's\.shopee\.tw/', url, re.IGNORECASE) and 's.shopee.tw/an_redir' not in url)
    )

    if is_short_url:
        # 對應原本 JS 的 expandShopeeShortUrl(url)
        expanded = expand_shopee_short_url(url)
        if not expanded:
            return None # 展開失敗，拒絕處理
        url = expanded

    # 3. 清掉所有舊的歸因參數 (防止帶到別人的分潤)
    # 將 JS 的 replace 對應為 Python re.sub
    # 清除的參數包括：mmp_pid, affiliate_id, sub_id, utm_source, utm_medium, utm_campaign, uls_trackid
    url = re.sub(r'[?&](mmp_pid|affiliate_id|sub_id|utm_source|utm_medium|utm_campaign|uls_trackid)=[^&]*', '', url)
    
    # 清掉最後多餘的 '?'
    if url.endswith('?'):
        url = url[:-1]

    # 4. 產生一個追蹤用的 sub_id (時間戳)
    sub_id = build_sub_id() # 對應 JS 的 buildSubId()

    # 5. 包上蝦皮聯盟的 an_redir 格式
    encoded = urllib.parse.quote(url) # 對應 JS 的 encodeURIComponent
    
    return f"https://s.shopee.tw/an_redir?origin_link={encoded}&affiliate_id={SHOPEE_AFF_ID}&sub_id={sub_id}"

# ============================================================
# ⚙️ Helper 函數：展開蝦皮短網址 (移植自原本 JS)
# ============================================================
def expand_shopee_short_url(short_url):
    """
    對應原本 JS 的 expandShopeeShortUrl(shortUrl)
    使用 requests (需 pip install) 模擬 GAS UrlFetchApp，獲取 Location header
    """
    try:
        # 設定 User-Agent 避免被擋
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # equivalent to UrlFetchApp.fetch(..., {followRedirects: False})
        # 注意：使用 allow_redirects=False 來獲取 Location header
        response = requests.get(short_url, allow_redirects=False, headers=headers, timeout=5)
        
        # 302 / 301 = 重導向
        if response.status_code >= 300 and response.status_code < 400:
            # 獲取 Location header
            # requests 的 headers 是不分大小寫的
            location =
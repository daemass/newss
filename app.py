import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pytrends.request import TrendReq
from googleapiclient.discovery import build
import requests
from flask import Flask, request, jsonify
import datetime
import random
import urllib.parse

app = Flask(__name__)

# 네이버 API 설정
naver_client_id = 'fIwplTzd5UFoMRvEkZIL'
naver_client_secret = 'uASismIH2F'

# Google API 설정
youtube_api_key = 'AIzaSyBYcEUgvctn9iK6TvRzVj20K8mQXJyLNro'

# Google Sheets 설정
json_keyfile_name = '1.json'
sheet_name = '검색 데이터'
likes_sheet_name = '좋아요 데이터'

def setup_google_sheets(json_keyfile_name, sheet_name, likes_sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_keyfile_name, scope)
    client = gspread.authorize(creds)
    try:
        sheet = client.open(sheet_name).sheet1
    except gspread.SpreadsheetNotFound:
        sheet = client.create(sheet_name).sheet1
        sheet.append_row(["Platform", "Rank", "Keyword", "Traffic", "Time", "Update Time"])
    try:
        likes_sheet = client.open(likes_sheet_name).sheet1
    except gspread.SpreadsheetNotFound:
        likes_sheet = client.create(likes_sheet_name).sheet1
        likes_sheet.append_row(["Platform", "Keyword", "Link", "Liked Time", "Memo"])
    return sheet, likes_sheet

sheet, likes_sheet = setup_google_sheets(json_keyfile_name, sheet_name, likes_sheet_name)

# 네이버 뉴스 검색 API를 사용하여 뉴스 검색
def search_naver_news(query):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": naver_client_id,
        "X-Naver-Client-Secret": naver_client_secret
    }
    params = {
        "query": query,
        "display": 10,  # 최대 10개 뉴스 표시
        "sort": "sim"  # 유사도 순
    }
    response = requests.get(url, headers=headers, params=params)
    news_data = response.json().get('items', [])
    return news_data

# 구글 트렌드 데이터 수집
def get_google_trends():
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(kw_list=[''], timeframe='now 1-d', geo='KR')
    trending_searches_df = pytrends.trending_searches(pn='south_korea')
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keywords = trending_searches_df[0].tolist()[:10]
    for i, keyword in enumerate(keywords):
        sheet.append_row(["Google", i + 1, keyword, random.randint(1, 100), now, now])
    return keywords

# 유튜브 검색어 데이터 수집
def get_youtube_trends():
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    request = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode="KR",
        maxResults=10
    )
    response = request.execute()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keywords = [(item['snippet']['title'], item['id']) for item in response['items']]
    for i, (title, video_id) in enumerate(keywords):
        sheet.append_row(["YouTube", i + 1, title, random.randint(1, 100), now, now])
    return keywords

# 유튜브 키워드 검색
def search_youtube(query):
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    request = youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        order="viewCount",
        maxResults=10
    )
    response = request.execute()
    return [(item['snippet']['title'], item['id']['videoId']) for item in response['items']]

# 좋아요 리스트 저장
def save_like(platform, keyword, link):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    likes_sheet.append_row([platform, keyword, link, now, ""])

# 좋아요 리스트 삭제
def remove_like(platform, keyword, link):
    likes = likes_sheet.get_all_records()
    for i, like in enumerate(likes):
        if like['Platform'] == platform and like['Keyword'] == keyword and like['Link'] == link:
            likes_sheet.delete_row(i + 2)  # 첫 번째 행은 헤더이므로 +2
            break

@app.route('/naver_news', methods=['GET'])
def get_naver_news():
    news_items = search_naver_news("뉴스")
    return jsonify(news_items)

@app.route('/google_trends', methods=['GET'])
def get_google_trends_route():
    google_trends = get_google_trends()
    return jsonify(google_trends)

@app.route('/youtube_trends', methods=['GET'])
def get_youtube_trends_route():
    youtube_trends = get_youtube_trends()
    return jsonify(youtube_trends)

@app.route('/search_youtube', methods=['GET'])
def search_youtube_route():
    query = request.args.get('query')
    youtube_results = search_youtube(query)
    return jsonify(youtube_results)

@app.route('/like', methods=['POST'])
def like():
    data = request.json
    save_like(data['platform'], data['keyword'], data['link'])
    return jsonify({"status": "success"})

@app.route('/unlike', methods=['POST'])
def unlike():
    data = request.json
    remove_like(data['platform'], data['keyword'], data['link'])
    return jsonify({"status": "success"})

@app.route('/likes', methods=['GET'])
def get_likes():
    likes = likes_sheet.get_all_records()
    return jsonify(likes)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

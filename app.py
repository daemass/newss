pip install flask gspread oauth2client pytrends google-api-python-client googletrans==4.0.0-rc1 requests ipywidgets

from flask import Flask, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pytrends.request import TrendReq
from googleapiclient.discovery import build
import requests
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
json_keyfile_name = 'able-scope-425002-p7-2f366111b4de.json'
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

# 공유 기능 생성
def create_share_links(title, link):
    share_links = {
        "email": f"mailto:?subject={urllib.parse.quote(title)}&body={urllib.parse.quote(link)}",
        "kakao": f"https://story.kakao.com/share?url={urllib.parse.quote(link)}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={urllib.parse.quote(link)}",
        "instagram": f"https://www.instagram.com/?url={urllib.parse.quote(link)}",
        "twitter": f"https://twitter.com/intent/tweet?url={urllib.parse.quote(link)}&text={urllib.parse.quote(title)}"
    }
    return share_links

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/trends', methods=['GET'])
def trends():
    platform = request.args.get('platform')
    if platform == 'naver':
        news_items = search_naver_news("뉴스")
        data = [{'title': item['title'], 'link': item['link'], 'pubDate': item['pubDate']} for item in news_items]
    elif platform == 'google':
        google_trends = get_google_trends()
        data = [{'keyword': trend} for trend in google_trends]
    elif platform == 'youtube':
        youtube_trends = get_youtube_trends()
        data = [{'title': title, 'video_id': video_id} for title, video_id in youtube_trends]
    else:
        data = []
    return jsonify(data)

@app.route('/like', methods=['POST'])
def like():
    data = request.get_json()
    platform = data['platform']
    keyword = data['keyword']
    link = data['link']
    save_like(platform, keyword, link)
    return jsonify({'status': 'success'})

@app.route('/unlike', methods=['POST'])
def unlike():
    data = request.get_json()
    platform = data['platform']
    keyword = data['keyword']
    link = data['link']
    remove_like(platform, keyword, link)
    return jsonify({'status': 'success'})

@app.route('/likes', methods=['GET'])
def likes():
    likes = likes_sheet.get_all_records()
    data = [{'platform': like['Platform'], 'keyword': like['Keyword'], 'link': like['Link'], 'liked_time': like['Liked Time'], 'memo': like['Memo']} for like in likes]
    return jsonify(data)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    naver_news = search_naver_news(query)
    google_news = search_naver_news(query)  # 네이버 뉴스 API를 사용하여 구글 뉴스 검색
    youtube_videos = search_youtube(query)
    
    data = {
        'naver_news': [{'title': item['title'], 'link': item['link'], 'pubDate': item['pubDate']} for item in naver_news],
        'google_news': [{'title': item['title'], 'link': item['link'], 'pubDate': item['pubDate']} for item in google_news],
        'youtube_videos': [{'title': title, 'video_id': video_id} for title, video_id in youtube_videos]
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

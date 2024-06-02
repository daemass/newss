from flask import Flask, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pytrends.request import TrendReq
from googleapiclient.discovery import build
from googletrans import Translator
import requests
from IPython.display import display, HTML, clear_output
import ipywidgets as widgets
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

# 프론트엔드 UI 생성
def create_ui():
    output = widgets.Output()
    
    def show_naver_news():
        with tabs.children[0]:
            clear_output()
            display(HTML("<h2>네이버 뉴스</h2>"))
            news_items = search_naver_news("뉴스")
            titles_seen = set()
            for i, item in enumerate(news_items):
                if item['title'] not in titles_seen:
                    titles_seen.add(item['title'])
                    share_links = create_share_links(item['title'], item['link'])
                    like_checkbox = widgets.Checkbox(value=False, description='', indent=False, layout=widgets.Layout(width='20px'))
                    like_checkbox.observe(lambda change, item=item: handle_like(change, "Naver News", item['title'], item['link']), names='value')
                    display(widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{item['link']}' target='_blank'>{item['title']}</a> ({item['pubDate']})</p>"),
                                          widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>"),
                                          like_checkbox]))

    def show_google_trends():
        with tabs.children[1]:
            clear_output()
            display(HTML("<h2>구글 트렌드</h2>"))
            google_trends = get_google_trends()
            trends_box = widgets.VBox()
            news_box = widgets.VBox()
            display(widgets.HBox([widgets.VBox([trends_box], layout=widgets.Layout(width='20%')), widgets.VBox([news_box], layout=widgets.Layout(width='80%'))]))
            for i, trend in enumerate(google_trends):
                button = widgets.Button(description=f"{i + 1}. {trend}")
                button.on_click(lambda x, trend=trend: show_news(trend, news_box))
                trends_box.children += (button,)

    def show_youtube_trends():
        with tabs.children[2]:
            clear_output()
            display(HTML("<h2>유튜브 트렌드</h2>"))
            youtube_trends = get_youtube_trends()
            for i, (title, video_id) in enumerate(youtube_trends):
                link = f"https://www.youtube.com/watch?v={video_id}"
                share_links = create_share_links(title, link)
                like_checkbox = widgets.Checkbox(value=False, description='', indent=False, layout=widgets.Layout(width='20px'))
                like_checkbox.observe(lambda change, title=title, link=link: handle_like(change, "YouTube", title, link), names='value')
                display(widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{link}' target='_blank'>{title}</a></p>"),
                                      widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>"),
                                      like_checkbox]))

    def show_news(keyword, news_box):
        news_items = search_naver_news(keyword)
        news_box.children = []
        news_box.children += (widgets.HTML(f"<h2>{keyword} 관련 뉴스</h2>"),)
        titles_seen = set()
        for i, item in enumerate(news_items):
            if item['title'] not in titles_seen:
                titles_seen.add(item['title'])
                share_links = create_share_links(item['title'], item['link'])
                like_checkbox = widgets.Checkbox(value=False, description='', indent=False, layout=widgets.Layout(width='20px'))
                like_checkbox.observe(lambda change, item=item: handle_like(change, "Google News", item['title'], item['link']), names='value')
                news_box.children += (widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{item['link']}' target='_blank'>{item['title']}</a> ({item['pubDate']})</p>"),
                                          widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>"),
                                      like_checkbox]),)

    def handle_like(change, platform, keyword, link):
        if change['new']:
            save_like(platform, keyword, link)
        else:
            remove_like(platform, keyword, link)

    def show_likes(b):
        with tabs.children[3]:
            clear_output()
            display(HTML("<h2>좋아요 리스트</h2>"))
            likes = likes_sheet.get_all_records()
            for i, like in enumerate(likes):
                memo_input = widgets.Text(value=like['Memo'], description='메모:')
                memo_input.on_submit(lambda text, like=like: save_memo(like, text.value))
                remove_button = widgets.Button(description='취소', layout=widgets.Layout(width='60px'))
                remove_button.on_click(lambda x, like=like: remove_like(like['Platform'], like['Keyword'], like['Link']))
                share_links = create_share_links(like['Keyword'], like['Link'])
                display(widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{like['Link']}' target='_blank'>{like['Keyword']}</a> ({like['Liked Time']})</p>"),
                                      memo_input, remove_button,
                                      widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>")]))

    def save_memo(like, memo):
        likes = likes_sheet.get_all_records()
        for i, row in enumerate(likes):
            if row['Platform'] == like['Platform'] and row['Keyword'] == like['Keyword'] and row['Link'] == like['Link']:
                likes_sheet.update_cell(i + 2, 5, memo)  # 첫 번째 행은 헤더이므로 +2
                break

    def search_keyword(b):
        query = keyword_input.value
        if query:
            with tabs.children[4]:
                clear_output()
                display(widgets.HBox([keyword_input, search_button, reset_button]))
                display(HTML(f"<h2>키워드 '{query}' 검색 결과</h2>"))
                news_items = search_naver_news(query)
                display(HTML("<h3>네이버 뉴스</h3>"))
                titles_seen = set()
                for i, item in enumerate(news_items):
                    if item['title'] not in titles_seen:
                        titles_seen.add(item['title'])
                        share_links = create_share_links(item['title'], item['link'])
                        like_checkbox = widgets.Checkbox(value=False, description='', indent=False, layout=widgets.Layout(width='20px'))
                        like_checkbox.observe(lambda change, item=item: handle_like(change, "Naver News", item['title'], item['link']), names='value')
                        display(widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{item['link']}' target='_blank'>{item['title']}</a> ({item['pubDate']})</p>"),
                                              widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>"),
                                              like_checkbox]))
                display(HTML("<h3>구글 뉴스</h3>"))
                google_news_items = search_naver_news(query)  # 네이버 뉴스 API를 사용하여 구글 뉴스 검색
                titles_seen = set()
                for i, item in enumerate(google_news_items):
                    if item['title'] not in titles_seen:
                        titles_seen.add(item['title'])
                        share_links = create_share_links(item['title'], item['link'])
                        like_checkbox = widgets.Checkbox(value=False, description='', indent=False, layout=widgets.Layout(width='20px'))
                        like_checkbox.observe(lambda change, item=item: handle_like(change, "Google News", item['title'], item['link']), names='value')
                        display(widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{item['link']}' target='_blank'>{item['title']}</a> ({item['pubDate']})</p>"),
                                              widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>"),
                                              like_checkbox]))
                display(HTML("<h3>유튜브</h3>"))
                youtube_items = search_youtube(query)  # 유튜브 전체 검색
                for i, (title, video_id) in enumerate(youtube_items):
                    link = f"https://www.youtube.com/watch?v={video_id}"
                    share_links = create_share_links(title, link)
                    like_checkbox = widgets.Checkbox(value=False, description='', indent=False, layout=widgets.Layout(width='20px'))
                    like_checkbox.observe(lambda change, title=title, link=link: handle_like(change, "YouTube", title, link), names='value')
                    display(widgets.HBox([widgets.HTML(f"<p>{i + 1}. <a href='{link}' target='_blank'>{title}</a></p>"),
                                          widgets.HTML(f"<a title='Email' href='{share_links['email']}' target='_blank'>📧</a> <a title='Kakao' href='{share_links['kakao']}' target='_blank'>🟧</a> <a title='Facebook' href='{share_links['facebook']}' target='_blank'>📘</a> <a title='Instagram' href='{share_links['instagram']}' target='_blank'>📸</a> <a title='Twitter' href='{share_links['twitter']}' target='_blank'>🐦</a>"),
                                          like_checkbox]))

    def reset_search(b):
        with tabs.children[4]:
            clear_output()
            display(widgets.HBox([keyword_input, search_button, reset_button]))
            display(HTML("<h2>수동 키워드 검색 결과</h2>"))

    tabs = widgets.Tab()
    tab_contents = ['네이버 뉴스', '구글 트렌드', '유튜브 트렌드', '좋아요 리스트', '수동 키워드 검색']
    tabs.children = [widgets.Output() for _ in tab_contents]
    for i, title in enumerate(tab_contents):
        tabs.set_title(i, title)

    show_naver_news()
    show_google_trends()
    show_youtube_trends()
    tabs.children[3].children = (output,)

    keyword_input = widgets.Text(
        value='',
        placeholder='키워드를 입력하세요',
        description='키워드:',
        disabled=False
    )
    search_button = widgets.Button(description="수동 검색하기")
    search_button.on_click(search_keyword)
    reset_button = widgets.Button(description="초기화")
    reset_button.on_click(reset_search)

    with tabs.children[4]:
        display(widgets.HBox([keyword_input, search_button, reset_button]))
        display(HTML("<h2>수동 키워드 검색 결과</h2>"))

    display(tabs)

@app.route('/')
def index():
    create_ui()
    return render_template_string('<!DOCTYPE html><html><body><div id="app">{{widgets_html}}</div></body></html>', widgets_html=output)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

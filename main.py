# main.py
import feedparser
import openai
import requests
from bs4 import BeautifulSoup
import os

# 環境変数からAPIキーを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")

# ニュース本文を取得（Yahooニュース用の簡易スクレイピング）
def fetch_article_text(url):
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        # Yahooニュースの本文は article tag にある
        article = soup.find("article")
        if article:
            return article.get_text(strip=True)
        return ""
    except Exception as e:
        return ""

# RSSフィードから上位ニュースを取得
def get_top_news():
    rss_url = "https://news.yahoo.co.jp/rss/media/top/all.xml"
    feed = feedparser.parse(rss_url)
    return feed.entries[:5]

# OpenAIで要約生成
def summarize_text(text):
    openai.api_key = OPENAI_API_KEY
    prompt = f"次のニュース本文を200文字以内でわかりやすく要約してください：\n{text}"
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# LINEに通知
def send_line_notify(message):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    requests.post(url, headers=headers, data=data)

# メイン処理
def main():
    entries = get_top_news()
    messages = ["\U0001F4F0 今日の人気ニュース要約\n"]

    for entry in entries:
        article_text = fetch_article_text(entry.link)
        content_to_summarize = article_text if article_text else entry.title
        summary = summarize_text(content_to_summarize)
        messages.append(f"\n🔹 {entry.title}\n{summary}\n{entry.link}\n")

    send_line_notify("\n".join(messages))

if __name__ == "__main__":
    main()


# requirements.txt
openai
requests
feedparser
beautifulsoup4


# .github/workflows/news.yml
name: Daily News Summary

on:
  schedule:
    - cron: '0 10 * * *'  # 日本時間19時（UTCで10時）
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v3
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run script
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          LINE_NOTIFY_TOKEN: ${{ secrets.LINE_NOTIFY_TOKEN }}
        run: python main.py

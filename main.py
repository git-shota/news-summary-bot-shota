# send_news.py
import os
import feedparser
import requests
from bs4 import BeautifulSoup
import openai
import smtplib
from email.mime.text import MIMEText

def fetch_rss_entries(feed_url, max_items=3):
    feed = feedparser.parse(feed_url)
    return feed.entries[:max_items]

def fetch_article_body(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        # このセレクタはサイトにより調整が必要
        article = soup.select_one("div.articleBody") or soup.select_one("div.article-body")
        return article.get_text(strip=True) if article else "本文を取得できませんでした。"
    except Exception as e:
        return f"本文取得エラー: {e}"

def summarize(text):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    prompt = f"以下のニュース記事を3行で簡潔に要約してください：\n{text}"
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"要約エラー: {e}"

def send_email(subject, body):
    from_addr = os.getenv("GMAIL_USER")
    to_addr = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_PASS")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(from_addr, password)
        server.send_message(msg)

def main():
    feed_url = "https://news.yahoo.co.jp/rss/topics/top-picks.xml"
    entries = fetch_rss_entries(feed_url)
    
    email_body = ""  # 本文にまとめて記載

    for entry in entries:
        title = entry.title
        link = entry.link
        article = fetch_article_body(link)
        summary = summarize(article)

        email_body += f"\n\n📰 {title}\n🔗 {link}\n📝 要約:\n{summary}\n"

    send_email("本日のニュース要約", email_body)

if __name__ == "__main__":
    main()

import os
import feedparser
import yaml
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI

# --- 設定読み込み ---
def load_config(path="config.yml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
NEWS_RSS_URL = config["news"]["rss_url"]  # 通常記事
RANKING_RSS_URL = config["news"]["ranking_rss_url"]  # 閲覧数ランキング記事
NUM_ARTICLES = config["news"]["num_articles"]
KEYWORDS = [k.lower() for k in config["news"]["keywords"]]

# メール設定
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
MAIL_TO = GMAIL_USER

# --- OpenAIクライアント ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- ニュース取得 ---
def fetch_news(rss_url, keywords=None, num_articles=5):
    feed = feedparser.parse(rss_url)
    entries = feed.entries

    # キーワードでフィルタ
    filtered = []
    if keywords:
        filtered = [
            e for e in entries
            if any(k in e.title.lower() for k in keywords)
        ]

    # キーワードが無い場合やヒットしない場合は全件
    if not filtered:
        filtered = entries

    return filtered[:num_articles]

# --- 要約 ---
def summarize(title, link):
    prompt = f"以下のニュースを簡潔に要約してください。\n\nタイトル: {title}\nURL: {link}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは優秀なニュース要約アシスタントです。"},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content.strip()

# --- メール送信 ---
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)

# --- メイン処理 ---
def main():
    # まず通常記事を取得
    articles = fetch_news(NEWS_RSS_URL, KEYWORDS, NUM_ARTICLES)

    # 0件の場合はランキングRSSにフォールバック
    if not articles:
        print("該当する記事がないため、閲覧数Top5にフォールバックします。")
        articles = fetch_news(RANKING_RSS_URL, None, NUM_ARTICLES)

    # 要約して本文生成
    body = ""
    for a in articles:
        summary = summarize(a.title, a.link)
        body += f"📰 {a.title}\nURL: {a.link}\n要約: {summary}\n\n"

    # メール送信
    send_email("本日のニュース要約", body)
    print("メール送信完了")

if __name__ == "__main__":
    main()

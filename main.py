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

# --- 類似判定（簡易） ---
def is_similar(text1, text2, threshold=0.5):
    # 簡単に共通単語率で判定（要調整）
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return False
    common = words1.intersection(words2)
    similarity = len(common) / min(len(words1), len(words2))
    return similarity > threshold

# --- 重複除外しつつ記事を5件に補充 ---
def filter_and_fill(articles, num_articles):
    summaries = []
    filtered_articles = []

    for article in articles:
        summary = summarize(article.title, article.link)
        # 似ている要約があればスキップ
        if any(is_similar(summary, s) for s in summaries):
            continue
        summaries.append(summary)
        filtered_articles.append((article, summary))
        if len(filtered_articles) >= num_articles:
            break

    return filtered_articles, summaries

# --- メール送信 ---
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = MAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)

# --- メイン処理 ---
def main():
    # まず通常記事を取得（多めに取ると良いです）
    articles = fetch_news(NEWS_RSS_URL, KEYWORDS, NUM_ARTICLES * 3)

    # 重複除外して5件に絞る
    filtered_articles, summaries = filter_and_fill(articles, NUM_ARTICLES)

    # 5件に満たない場合はランキング記事で補充
    if len(filtered_articles) < NUM_ARTICLES:
        print(f"{len(filtered_articles)}件しか記事がなかったのでランキング記事で補充します。")
        ranking_articles = fetch_news(RANKING_RSS_URL, None, NUM_ARTICLES * 3)
        for article in ranking_articles:
            if len(filtered_articles) >= NUM_ARTICLES:
                break
            summary = summarize(article.title, article.link)
            if any(is_similar(summary, s) for s in summaries):
                continue
            summaries.append(summary)
            filtered_articles.append((article, summary))

    # 本文作成
    body = ""
    for a, summary in filtered_articles:
        body += f"📰 {a.title}\nURL: {a.link}\n要約: {summary}\n\n"

    # メール送信
    send_email("本日のニュース要約", body)
    print("メール送信完了")

if __name__ == "__main__":
    main()

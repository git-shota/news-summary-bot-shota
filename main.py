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
RSS_URLS = config["news"]["rss_urls"]  # 複数RSS
RANKING_RSS_URL = config["news"]["ranking_rss_url"]
NUM_ARTICLES = config["news"]["num_articles"]
KEYWORDS = [k.lower() for k in config["news"]["keywords"]]
PROMPT_TEMPLATE = config["news"]["prompt_template"]

# メール設定
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
MAIL_TO = GMAIL_USER

# --- OpenAIクライアント ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- ニュース取得（複数RSS対応） ---
def fetch_multiple_news(rss_urls, keywords=KEYWORDS, num_articles=NUM_ARTICLES*3):
    all_entries = []
    for url in rss_urls:
        feed = feedparser.parse(url)
        entries = feed.entries
        all_entries.extend(entries)

    # キーワードフィルタ
    if keywords:
        filtered = [e for e in all_entries if any(k in e.title.lower() for k in keywords)]
        if not filtered:
            filtered = all_entries
    else:
        filtered = all_entries

    return filtered[:num_articles]

# --- 既存のfetch_newsもranking用で残す ---
def fetch_news(rss_url, keywords=None, num_articles=5):
    feed = feedparser.parse(rss_url)
    entries = feed.entries

    filtered = []
    if keywords:
        filtered = [e for e in entries if any(k in e.title.lower() for k in keywords)]

    if not filtered:
        filtered = entries

    return filtered[:num_articles]

# --- 要約 ---
def summarize(title, link):
    prompt = PROMPT_TEMPLATE.format(title=title, link=link)
    resp = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "あなたは優秀なニュース要約アシスタントです。"},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content.strip()

# --- 類似判定（簡易） ---
def is_similar(text1, text2, threshold=0.5):
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
    articles = fetch_multiple_news(RSS_URLS, KEYWORDS, NUM_ARTICLES * 3)

    filtered_articles, summaries = filter_and_fill(articles, NUM_ARTICLES)

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

    body = ""
    if KEYWORDS and not any(any(k in a.title.lower() for k in KEYWORDS) for a, _ in filtered_articles):
        body += "⚠️ キーワードにヒットする記事がありませんでした。\n\n"

    for a, summary in filtered_articles:
        body += f"📰 {a.title}\nURL: {a.link}\n要約: {summary}\n\n"

    send_email("本日のニュース要約", body)
    print("メール送信完了")

if __name__ == "__main__":
    main()

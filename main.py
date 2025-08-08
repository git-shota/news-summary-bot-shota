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
RSS_URLS = config["news"]["rss_urls"]           # 複数RSSリスト
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
        all_entries.extend(feed.entries)

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

    if keywords:
        filtered = [e for e in entries if any(k in e.title.lower() for k in keywords)]
    else:
        filtered = entries

    if not filtered:
        filtered = entries

    return filtered[:num_articles]

# --- 類似判定（簡易、タイトルベース） ---
def is_similar(text1, text2, threshold=0.5):
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return False
    common = words1.intersection(words2)
    similarity = len(common) / min(len(words1), len(words2))
    return similarity > threshold

# --- タイトル類似で記事を絞る（要約はまだ行わない） ---
def filter_by_title_similarity(articles, num_articles):
    filtered = []
    titles = []

    for article in articles:
        title = article.title.lower()
        if any(is_similar(title, t) for t in titles):
            continue
        titles.append(title)
        filtered.append(article)
        if len(filtered) >= num_articles:
            break
    return filtered

# --- 要約＋背景取得 ---
def summarize_with_background(title, link):
    prompt = PROMPT_TEMPLATE.format(title=title, link=link)
    resp = client.chat.completions.create(
        model="gpt-5",
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
    msg["To"] = MAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)

# --- メイン処理 ---
def main():
    # 1. 複数RSSから記事取得（多めに）
    articles = fetch_multiple_news(RSS_URLS, KEYWORDS, NUM_ARTICLES * 3)

    # 2. タイトル類似除外で5件に絞る（軽量処理）
    filtered_articles = filter_by_title_similarity(articles, NUM_ARTICLES)

    # 3. 不足時はランキング記事で補充
    if len(filtered_articles) < NUM_ARTICLES:
        print(f"{len(filtered_articles)}件しか記事がなかったのでランキング記事で補充します。")
        ranking_articles = fetch_news(RANKING_RSS_URL, None, NUM_ARTICLES * 3)
        for article in ranking_articles:
            if len(filtered_articles) >= NUM_ARTICLES:
                break
            if any(is_similar(article.title.lower(), a.title.lower()) for a in filtered_articles):
                continue
            filtered_articles.append(article)

    # 4. 5件それぞれに要約＋背景を取得
    detailed_summaries = []
    for article in filtered_articles:
        detail = summarize_with_background(article.title, article.link)
        detailed_summaries.append((article, detail))

    # 5. メール本文作成
    body = ""
    if KEYWORDS and not any(any(k in a.title.lower() for k in KEYWORDS) for a, _ in detailed_summaries):
        body += "⚠️ キーワードにヒットする記事がありませんでした。\n\n"

    for a, detail in detailed_summaries:
        body += f"📰 {a.title}\nURL: {a.link}\n要約・背景: {detail}\n\n"

    # 6. メール送信
    send_email("本日のニュース要約", body)
    print("メール送信完了")

if __name__ == "__main__":
    main()

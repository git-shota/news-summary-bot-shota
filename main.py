import os
import feedparser
import yaml
from openai import OpenAI

# --- 設定読み込み ---
def load_config(path="config.yml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
RSS_URL = config["news"]["rss_url"]
NUM_ARTICLES = config["news"]["num_articles"]
KEYWORDS = [k.lower() for k in config["news"]["keywords"]]

# --- OpenAIクライアント ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- ニュース取得 ---
import feedparser
import yaml

CONFIG_FILE = "config.yml"
RSS_URL = "https://news.yahoo.co.jp/rss/topics/top-picks.xml"

# 設定読み込み
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

KEYWORDS = [kw.lower() for kw in config.get("keywords", [])]
NUM_ARTICLES = config.get("num_articles", 5)

def fetch_news():
    feed = feedparser.parse(RSS_URL)
    entries = feed.entries

    # キーワードが設定されている場合はフィルタリング
    filtered = []
    if KEYWORDS:
        filtered = [
            e for e in entries
            if any(k in e.title.lower() for k in KEYWORDS)
        ]

    # キーワードでヒットしなかった場合はフォールバック
    if not filtered:
        print("キーワードに該当する記事がないため、全件から取得します。")
        filtered = entries

    # 上位NUM_ARTICLES件を返す
    return filtered[:NUM_ARTICLES]

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

# --- メイン処理 ---
def main():
    articles = fetch_news()
    if not articles:
        print("該当する記事がありません。")
        return

    body = ""
    for a in articles:
        summary = summarize(a.title, a.link)
        body += f"📰 {a.title}\nURL: {a.link}\n要約: {summary}\n\n"

    print(body)  # GitHub Actionsではこの出力をメールやSlackに流す

if __name__ == "__main__":
    main()

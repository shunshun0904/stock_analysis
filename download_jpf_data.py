import os
import datetime
import requests
from bs4 import BeautifulSoup
import time

# 保存先ディレクトリ
DATA_DIR = "margin_data"
# ターゲットURL
TARGET_PAGE = "https://www.taisyaku.jp/download/"
BASE_URL = "https://www.taisyaku.jp"

def setup_directory():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created directory: {DATA_DIR}")

def download_file(url, filename_prefix):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 日付を付与して保存 (YYYYMMDD_prefix.csv)
        today = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"{today}_{filename_prefix}.csv"
        file_path = os.path.join(DATA_DIR, filename)
        
        # バイナリ書き込み
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Saved: {file_path}")
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def main():
    setup_directory()
    
    # ページを取得して解析
    try:
        print(f"Accessing {TARGET_PAGE}...")
        res = requests.get(TARGET_PAGE)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 【修正点】テキストではなく、href(URL)に含まれるキーワードで判定する
        # 他の2つのキーワードは推測です。実際のURLに合わせて修正が必要かもしれません。
        targets = {
            "zandaka": "zandaka",  # 銘柄別残高 (/data/meigara.csv)
            "shina": "shina",    # 品貸料率 (推測: /data/riritu.csv ?)
            "seigenichiran": "seigenichiran"       # 制限措置 (推測: /data/kisei.csv ?)
        }
        
        found_urls = set()
        
        # 'a'タグをチェック
        for a in soup.find_all('a', href=True):
            href = a['href']
            
            # CSVリンク以外は無視
            if not href.lower().endswith('.csv'):
                continue

            # 相対URLを絶対URLに変換
            if href.startswith("/"):
                full_url = BASE_URL + href
            else:
                full_url = href
            
            # ターゲット判定
            for key, keyword in targets.items():
                # URLの中にキーワード(meigara等)が含まれているか
                if keyword in href and full_url not in found_urls:
                    print(f"Found match for [{key}]: {full_url}")
                    if download_file(full_url, key):
                        found_urls.add(full_url)
                    break
                    
        if len(found_urls) < 3:
            print("-" * 30)
            print(f"WARNING: Only {len(found_urls)}/3 files were found.")
            print("Detected CSV links on the page:")
            for a in soup.find_all('a', href=True):
                 if a['href'].endswith('.csv'):
                     print(f" - {a['href']}")
            print("-" * 30)
            
    except Exception as e:
        print(f"Fatal Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
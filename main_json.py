from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import os
import re
import json
from urllib.parse import urljoin, urlparse
from PIL import Image


def sanitize_filename(filename):
    """ファイル名を安全に変換"""
    return re.sub(r'[\\/:*?"<>|]', '_', filename)


def download_image(img_url, base_url, save_dir, index):
    """画像ダウンロード"""
    import requests
    try:
        full_url = urljoin(base_url, img_url)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'}
        
        response = requests.get(full_url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()

        parsed = urlparse(full_url)
        ext = os.path.splitext(parsed.path)[1].lower() or '.jpg'
        
        filename = f"image_{index:03d}{ext}"
        filepath = os.path.join(save_dir, filename)

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        Image.open(filepath).verify()
        print(f"✅ 画像保存: {filename}")
        return {
            "filename": filename,
            "original_src": full_url,
            "local_path": f"./images/{filename}"
        }

    except Exception as e:
        print(f"❌ 画像ダウンロード失敗 {img_url}: {e}")
        return None


def scrape_with_playwright(url, output_dir="output_playwright", wait_seconds=5):
    """
    Playwrightを使ってWebページをJSON + 画像保存（Edge User-Agent）
    """
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    edge_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"

    with sync_playwright() as p:
        print("🚀 Playwright起動中... (Edge User-Agent)")

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=edge_user_agent
        )
        page = context.new_page()

        try:
            print(f"🌐 アクセス中: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(wait_seconds)

            # スクロールで遅延コンテンツを読み込む
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)

            page_source = page.content()
            soup = BeautifulSoup(page_source, 'lxml')

            # 不要要素削除
            for tag in soup.select('script, style, nav, footer, header, aside, iframe, .ad, [class*="cookie"], [id*="cookie"], [class*="banner"]'):
                tag.decompose()

            # メインコンテンツ
            article = (soup.find('article') or 
                       soup.find('main') or 
                       soup.find('div', class_=re.compile(r'post|content|article|story|entry', re.I)) or 
                       soup.body)

            # プレーンテキストとして抽出
            text_content = article.get_text(separator="\n", strip=True)

            # 画像処理
            img_tags = article.find_all('img')
            images = []
            print(f"🖼️  検出画像数: {len(img_tags)}個")

            for i, img in enumerate(img_tags):
                src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy')
                if src and (src.startswith('http') or src.startswith('/')):
                    image_info = download_image(src, url, images_dir, i+1)
                    if image_info:
                        images.append(image_info)

            # タイトル
            title_text = page.title() or "no_title"
            title_text = sanitize_filename(title_text[:100])

            # JSONデータ作成
            result = {
                "title": title_text,
                "url": url,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "text_content": text_content,
                "images": images,
                "image_count": len(images)
            }

            # JSON保存
            json_filename = f"{title_text}.json"
            json_path = os.path.join(output_dir, json_filename)

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"\n🎉 Playwright版（JSON出力） 完了！")
            print(f"📄 JSONファイル: {json_path}")
            print(f"🖼️  画像フォルダ: {images_dir}")
            print(f"🖼️  保存画像数: {len(images)}個")

            return json_path

        finally:
            browser.close()


# ==================== 使用例 ====================
if __name__ == "__main__":
    target_url = "https://ja.wikipedia.org/wiki/Model_Context_Protocol"
    
    scrape_with_playwright(
        url=target_url,
        output_dir="playwright_scraped_json",
        wait_seconds=6
    )
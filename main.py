import asyncio
import aiohttp
import json
import re
import time
import os
from datetime import datetime


# ==========================
# 🔧 CONFIG
# ==========================
CHECK_INTERVAL = 10
TOTAL_PAGES = 13

# 🔐 Environment Variables (SET THESE IN RAILWAY)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set")

if not TELEGRAM_CHAT_ID:
    raise ValueError("❌ TELEGRAM_CHAT_ID not set")

if not DISCORD_WEBHOOK_URL:
    raise ValueError("❌ DISCORD_WEBHOOK_URL not set")


# ==========================
# 📦 SCRAPER
# ==========================
class AsyncProductScraper:

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }

    def log(self, msg, level="INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{level}] {msg}")

    def get_url(self, page):
        return (
            "https://www.firstcry.com/svcs/SearchResult.svc/GetSearchResultProductsPaging?"
            f"PageNo={page}&PageSize=20&SortExpression=popularity&OnSale=5"
            "&SearchString=brand&MasterBrand=113&pcode=380008&isclub=0"
        )

    def slugify(self, text):
        text = text.lower()
        text = text.replace('&', 'and')
        text = re.sub(r'[^a-z0-9\s-]', '', text)
        text = re.sub(r'[\s-]+', '-', text)
        return text.strip('-')

    async def fetch_page(self, session, page):
        url = self.get_url(page)

        try:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    self.log(f"Page {page} HTTP {resp.status}", "ERROR")
                    return page, {}, 0, 0

                raw = await resp.text()
                products = self.parse_products(raw)

                in_stock = sum(1 for p in products.values() if p["stock"])
                total = len(products)

                return page, products, in_stock, total

        except Exception as e:
            self.log(f"Page {page} error: {e}", "ERROR")
            return page, {}, 0, 0

    def parse_products(self, json_data):
        try:
            response = json.loads(json_data)
            product_response = json.loads(response["ProductResponse"])
        except Exception:
            return {}

        products = {}

        for item in product_response.get("Products", []):
            pid = item.get("PId")
            title = item.get("PNm")

            if not pid or not title:
                continue

            stock_count = int(item.get("CrntStock", 0))
            in_stock = stock_count > 0
            price = float(item.get("discprice") or item.get("MRP", 0))

            slug = self.slugify(title)
            link = f"https://www.firstcry.com/hot-wheels/{slug}/{pid}/product-detail"

            products[pid] = {
                "title": title,
                "price": price,
                "stock": in_stock,
                "stock_count": stock_count,
                "link": link
            }

        return products


# ==========================
# 📲 ALERT SYSTEM
# ==========================
async def send_telegram(session, message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        async with session.post(url, data=payload) as resp:
            if resp.status != 200:
                print("Telegram error:", resp.status)
    except Exception as e:
        print("Telegram exception:", e)


async def send_discord(session, message):
    try:
        payload = {"content": message}
        async with session.post(DISCORD_WEBHOOK_URL, json=payload) as resp:
            if resp.status not in (200, 204):
                print("Discord error:", resp.status)
    except Exception as e:
        print("Discord exception:", e)


async def send_alert(session, message):
    await asyncio.gather(
        send_telegram(session, message),
        send_discord(session, message)
    )


# ==========================
# 🚀 MONITOR LOOP
# ==========================
async def monitor():
    scraper = AsyncProductScraper()
    previous_stock = {}

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:

        scraper.log("🔥 Async Stock Monitor Started")

        while True:
            start_time = time.time()
            alert_count = 0

            scraper.log(f"Scan Starting — Tracked: {len(previous_stock)} items")

            tasks = [
                scraper.fetch_page(session, page)
                for page in range(1, TOTAL_PAGES + 1)
            ]

            results = await asyncio.gather(*tasks)

            current_stock = {}

            for page, products, in_stock, total in results:
                scraper.log(f"P{page}: {in_stock}/{total} in stock", "DEBUG")

                for pid, product in products.items():
                    current_stock[pid] = product

                    if pid in previous_stock:
                        if not previous_stock[pid]["stock"] and product["stock"]:
                            msg = (
                                f"🔥 RESTOCK ALERT\n\n"
                                f"{product['title']}\n"
                                f"₹{product['price']}\n"
                                f"{product['link']}"
                            )
                            await send_alert(session, msg)
                            alert_count += 1
                            scraper.log(f"Restock: {product['title']}", "ALERT")
                    else:
                        if product["stock"]:
                            msg = (
                                f"🔥 IN STOCK\n\n"
                                f"{product['title']}\n"
                                f"₹{product['price']}\n"
                                f"{product['link']}"
                            )
                            await send_alert(session, msg)
                            alert_count += 1
                            scraper.log(f"Initial: {product['title']}", "ALERT")

            previous_stock = current_stock

            duration = round(time.time() - start_time, 2)
            scraper.log(
                f"Done in {duration}s | {len(current_stock)} items | {alert_count} alerts",
                "OK"
            )

            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(monitor())

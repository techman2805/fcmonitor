import requests
import time
import json
import os
import re

# ======================
# CONFIG
# ======================

WEBHOOK_URL = "https://discord.com/api/webhooks/1478062613685338207/4Rtw63OxeYawn_T3a6QUXNwsy_ONwt0vih8YYxMfRK5mqNm-d8MNaGLZKrnep-XlJUt_"

CHECK_INTERVAL = 5

DATA_FILE = "database.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.firstcry.com/",
    "Origin": "https://www.firstcry.com",
    "X-Requested-With": "XMLHttpRequest"
}

API = {
    "url":"https://www.firstcry.com/svcs/SearchResult.svc/GetSearchResultProductsPaging",
    "params":{
        "PageNo":1,
        "PageSize":20,
        "SortExpression":"popularity",
        "OnSale":5,
        "SearchString":"brand",
        "MasterBrand":113,
        "pcode":380008,
        "isclub":0
    }
}

# ======================
# SESSION
# ======================

session = requests.Session()
session.headers.update(HEADERS)

session.get("https://www.firstcry.com/")

# ======================
# DATABASE
# ======================

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DATA_FILE,"w") as f:
        json.dump(data,f,indent=2)

# ======================
# UTILITIES
# ======================

def slugify(text):
    text=text.lower()
    text=re.sub(r'[^a-z0-9]+','-',text)
    return text.strip('-')

# ======================
# DISCORD EMBED
# ======================

def send_discord(product,message):

    embed = {
        "title": "Hot Wheels Stock Bot",
        "description": f"📉 **Price Drop Alert!**\n\n👉 [Click here to Buy on FirstCry]({product['url']})",
        "color": 16753920,
        "thumbnail": {
            "url": product["image"]
        },
        "fields": [

            {
                "name": "🏷 Product Name",
                "value": product["name"],
                "inline": False
            },

            {
                "name": "💰 Price",
                "value": f"₹{product['price']}",
                "inline": True
            },

            {
                "name": "📦 Status",
                "value": product["stock"],
                "inline": True
            },

            {
                "name": "🔢 Quantity",
                "value": f"Only {product['qty']} Left!",
                "inline": True
            },

            {
                "name": "📊 Analytics",
                "value": "• Status Changes: 1",
                "inline": False
            },

            {
                "name": "💸 Previous",
                "value": f"₹{product['old_price']}",
                "inline": False
            }

        ],

        "footer": {
            "text": "FirstCry Monitor"
        }
    }

    payload = {
        "username": "Hot Wheels Stock Bot",
        "embeds": [embed]
    }

    try:
        requests.post(WEBHOOK_URL,json=payload)
    except Exception as e:
        print("Webhook error:",e)

# ======================
# FETCH PRODUCTS
# ======================

def fetch_products(page):

    params = API["params"].copy()
    params["PageNo"] = page

    try:
        r = session.get(API["url"],params=params)
        data = r.json()
    except:
        return []

    response = data.get("ProductResponse")

    if not response:
        return []

    parsed = json.loads(response)

    products = parsed.get("Products",[])

    print(f"Page {page} → {len(products)} products")

    return products

# ======================
# PARSE PRODUCT
# ======================

def parse_product(p):

    pid = str(p.get("PId"))

    name = p.get("PNm","")
    brand = p.get("BNm","")

    qty = int(p.get("CrntStock",0))

    brand_slug = slugify(brand)
    product_slug = slugify(name)

    url = f"https://www.firstcry.com/{brand_slug}/{product_slug}/{pid}/product-detail"

    image = f"https://cdn.fcglcdn.com/brainbees/images/products/438x531/{pid}a.webp"

    return {
        "id":pid,
        "name":name,
        "price":p.get("SP",p.get("MRP")),
        "old_price":p.get("MRP"),
        "qty":qty,
        "stock":"In Stock" if qty>0 else "Out of Stock",
        "image":image,
        "url":url
    }

# ======================
# MONITOR
# ======================

def monitor():

    db = load_db()

    print("Brand 113 monitor started")

    while True:

        try:

            page = 1

            while True:

                products = fetch_products(page)

                if not products:
                    break

                for p in products:

                    product = parse_product(p)

                    pid = product["id"]

                    if pid not in db:

                        send_discord(product,"🆕 New Product")

                        db[pid] = product
                        continue

                    old = db[pid]

                    changes = []

                    if product["price"] != old["price"]:
                        changes.append(f"💰 Price changed ₹{old['price']} → ₹{product['price']}")

                    if old["qty"] == 0 and product["qty"] > 0:
                        changes.append(f"🚨 RESTOCK {old['qty']} → {product['qty']}")

                    if product["qty"] != old["qty"]:
                        changes.append(f"📦 Qty {old['qty']} → {product['qty']}")

                    if changes:
                        send_discord(product,"\n".join(changes))

                    db[pid] = product

                page += 1

            save_db(db)

        except Exception as e:

            print("Monitor error:",e)

        time.sleep(CHECK_INTERVAL)

# ======================
# START
# ======================

if __name__ == "__main__":
    monitor()

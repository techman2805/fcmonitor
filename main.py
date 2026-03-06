import requests
import time
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

# ======================
# CONFIG
# ======================

WEBHOOK_URL = "https://discord.com/api/webhooks/1478062613685338207/4Rtw63OxeYawn_T3a6QUXNwsy_ONwt0vih8YYxMfRK5mqNm-d8MNaGLZKrnep-XlJUt_"

CHECK_INTERVAL = 8
MAX_THREADS = 5

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
        "SortExpression":"NewArrivals",
        "OnSale":0,
        "SearchString":"brand",
        "SubCatId":"",
        "BrandId":"",
        "Price":"",
        "Age":"",
        "Color":"",
        "OptionalFilter":"",
        "OutOfStock":"",
        "combo":"",
        "discount":"",
        "searchwithincat":"",
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
# UTIL
# ======================

def slugify(text):
    text=text.lower()
    text=re.sub(r'[^a-z0-9]+','-',text)
    return text.strip('-')

# ======================
# DISCORD MESSAGE
# ======================

def send_discord(product,message):

    embed={
        "title":"Hot Wheels Stock Bot",
        "description":f"📉 **Stock Alert**\n\n👉 [Click here to Buy]({product['url']})",
        "color":16753920,
        "thumbnail":{"url":product["image"]},
        "fields":[
            {"name":"🏷 Product Name","value":product["name"],"inline":False},
            {"name":"💰 Price","value":f"₹{product['price']}","inline":True},
            {"name":"📦 Status","value":product["stock"],"inline":True},
            {"name":"🔢 Quantity","value":f"{product['qty']} left","inline":True},
            {"name":"💸 Previous","value":f"₹{product['old_price']}","inline":False}
        ],
        "footer":{"text":"FirstCry Monitor"}
    }

    payload={
        "username":"Hot Wheels Stock Bot",
        "embeds":[embed]
    }

    try:
        requests.post(WEBHOOK_URL,json=payload)
    except:
        pass

# ======================
# FETCH PRODUCTS
# ======================

def fetch_page(page):

    params = API["params"].copy()
    params["PageNo"] = page

    try:
        r = session.get(API["url"],params=params,timeout=15)
        data = r.json()
    except:
        return []

    response = data.get("ProductResponse")

    if not response:
        return []

    parsed = json.loads(response)

    products = parsed.get("Products",[])

    print(f"Page {page} → {len(products)}")

    return products

# ======================
# PARSE PRODUCT
# ======================

def parse_product(p):

    pid=str(p.get("PId"))

    name=p.get("PNm","")
    brand=p.get("BNm","")

    qty=int(p.get("CrntStock",0))

    brand_slug=slugify(brand)
    product_slug=slugify(name)

    url=f"https://www.firstcry.com/{brand_slug}/{product_slug}/{pid}/product-detail"

    image=f"https://cdn.fcglcdn.com/brainbees/images/products/438x531/{pid}a.webp"

    return{
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
# FAST PAGE SCAN
# ======================

def scan_all_pages():

    products=[]

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures=[executor.submit(fetch_page,i) for i in range(1,10)]

        for f in futures:
            result=f.result()
            if result:
                products.extend(result)

    return products

# ======================
# MONITOR
# ======================

def monitor():

    db=load_db()

    print("Fast monitor started")

    while True:

        try:

            products=scan_all_pages()

            print("Total scanned:",len(products))

            for p in products:

                product=parse_product(p)

                pid=product["id"]

                if pid not in db:

                    send_discord(product,"🆕 New Product")

                    db[pid]=product
                    continue

                old=db[pid]

                changes=[]

                if product["price"]!=old["price"]:
                    changes.append(f"💰 Price changed ₹{old['price']} → ₹{product['price']}")

                if old["qty"]==0 and product["qty"]>0:
                    changes.append(f"🚨 RESTOCK {old['qty']} → {product['qty']}")

                if product["qty"]!=old["qty"]:
                    changes.append(f"📦 Qty {old['qty']} → {product['qty']}")

                if changes:
                    send_discord(product,"\n".join(changes))

                db[pid]=product

            save_db(db)

        except Exception as e:

            print("Monitor error:",e)

        time.sleep(CHECK_INTERVAL)

# ======================
# START
# ======================

if __name__=="__main__":
    monitor()

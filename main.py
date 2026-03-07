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

API_URL = "https://www.firstcry.com/svcs/SearchResult.svc/GetSearchResultProductsPaging"

PARAMS = {
"PageNo":1,
"PageSize":20,
"SortExpression":"popularity",
"OnSale":5,
"SearchString":"brand",
"SubCatId":"",
"BrandId":"",
"Price":"",
"Age":"",
"Color":"",
"OptionalFilter":"",
"OutOfStock":"",
"Type1":"",
"Type2":"",
"Type3":"",
"Type4":"",
"Type5":"",
"Type6":"",
"Type7":"",
"Type8":"",
"Type9":"",
"Type10":"",
"Type11":"",
"Type12":"",
"Type13":"",
"Type14":"",
"Type15":"",
"combo":"",
"discount":"",
"searchwithincat":"",
"ProductidQstr":"",
"searchrank":"",
"pmonths":"",
"cgen":"",
"PriceQstr":"",
"DiscountQstr":"",
"sorting":"",
"MasterBrand":113,
"Rating":"",
"Offer":"",
"skills":"",
"material":"",
"curatedcollections":"",
"measurement":"",
"gender":"",
"exclude":"",
"premium":"",
"pcode":380008,
"isclub":0,
"deliverytype":"",
"author":"",
"booktype":"",
"character":"",
"collection":"",
"format":"",
"genre":"",
"booklanguage":"",
"publication":"",
"skill":""
}

HEADERS = {
"User-Agent": "Mozilla/5.0",
"Accept": "application/json",
"Referer": "https://www.firstcry.com/",
"Origin": "https://www.firstcry.com",
"X-Requested-With": "XMLHttpRequest"
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
# DISCORD ALERT
# ======================

def send_discord(product,message):

    embed={
        "title":"Hot Wheels Stock Bot",
        "description":f"{message}\n\n👉 [Click here to Buy]({product['url']})",
        "color":16753920,
        "thumbnail":{"url":product["image"]},
        "fields":[
            {"name":"🏷 Product","value":product["name"],"inline":False},
            {"name":"💰 Price","value":f"₹{product['price']}","inline":True},
            {"name":"📦 Status","value":product["stock"],"inline":True},
            {"name":"🔢 Qty","value":str(product["qty"]),"inline":True}
        ],
        "footer":{"text":"FirstCry Monitor"}
    }

    payload={"username":"Hot Wheels Stock Bot","embeds":[embed]}

    try:
        requests.post(WEBHOOK_URL,json=payload,timeout=10)
    except:
        pass

# ======================
# FETCH PAGE
# ======================

def fetch_page(page):

    params = PARAMS.copy()
    params["PageNo"] = page

    try:
        r=session.get(API_URL,params=params,timeout=15)
        data=r.json()
    except:
        return []

    response=data.get("ProductResponse")

    if not response:
        return []

    parsed=json.loads(response)

    products=parsed.get("Products",[])

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
# SCAN
# ======================

def scan_products():

    products=[]

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures=[]

        for page in range(1,8):
            futures.append(executor.submit(fetch_page,page))

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

    print("Monitor started")

    while True:

        try:

            products=scan_products()

            print("Total scanned:",len(products))

            for p in products:

                product=parse_product(p)
                pid=product["id"]

                if pid not in db:

                    send_discord(product,"🆕 New Product Detected")
                    db[pid]=product
                    continue

                old=db[pid]

                changes=[]

                if product["price"]!=old["price"]:
                    changes.append(f"💰 Price {old['price']} → {product['price']}")

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

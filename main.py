import requests
import time
import json
import os
import re

# ======================
# CONFIG
# ======================

WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK"

CHECK_INTERVAL = 5

DATA_FILE = "database.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.firstcry.com/",
    "Origin": "https://www.firstcry.com",
    "X-Requested-With": "XMLHttpRequest"
}

# ======================
# API LIST (FASTER MONITORING)
# ======================

APIS = [

{
"name":"Majorette New",
"url":"https://www.firstcry.com/svcs/SearchResult.svc/GetSearchResultProductsFilters",
"params":{
"PageNo":1,
"PageSize":20,
"SortExpression":"NewArrivals",
"OnSale":0,
"SearchString":"brand",
"OutOfStock":0,
"MasterBrand":1335,
"pcode":600119,
"isclub":1
}
},

{
"name":"Brand 113 Popular",
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

]

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
# DISCORD ALERT
# ======================

def send_discord(product,message):

    embed={
        "title":product["name"],
        "url":product["url"],
        "description":message,
        "color":3066993,
        "image":{"url":product["image"]},
        "fields":[
            {"name":"Price","value":f"₹{product['price']}","inline":True},
            {"name":"MRP","value":f"₹{product['old_price']}","inline":True},
            {"name":"Stock","value":product["stock"],"inline":True},
            {"name":"Quantity","value":str(product["qty"]),"inline":True}
        ],
        "footer":{"text":"FirstCry Monitor"}
    }

    payload={"embeds":[embed]}

    try:
        requests.post(WEBHOOK_URL,json=payload,timeout=10)
    except Exception as e:
        print("Webhook error:",e)

# ======================
# FETCH PRODUCTS
# ======================

def fetch_products(api,page):

    params=api["params"].copy()
    params["PageNo"]=page

    try:
        r=session.get(api["url"],params=params,timeout=15)
        data=r.json()
    except:
        return []

    response=data.get("ProductResponse")

    if not response:
        return []

    parsed=json.loads(response)

    products=parsed.get("Products",[])

    print(f"{api['name']} Page {page} → {len(products)}")

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

    # FIXED IMAGE SYSTEM

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
# MONITOR
# ======================

def monitor():

    db=load_db()

    print("FirstCry monitor started")

    while True:

        try:

            for api in APIS:

                page=1

                while True:

                    products=fetch_products(api,page)

                    if not products:
                        break

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
                            changes.append(f"💰 Price: ₹{old['price']} → ₹{product['price']}")

                        if old["qty"]==0 and product["qty"]>0:
                            changes.append(f"🚨 RESTOCK {old['qty']} → {product['qty']}")

                        if product["qty"]!=old["qty"]:
                            changes.append(f"📦 Qty: {old['qty']} → {product['qty']}")

                        if changes:
                            send_discord(product,"\n".join(changes))

                        db[pid]=product

                    page+=1

            save_db(db)

        except Exception as e:

            print("Monitor error:",e)

        time.sleep(CHECK_INTERVAL)

# ======================
# START
# ======================

if __name__=="__main__":
    monitor()

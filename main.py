import csv
import io
import re
import time

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

BRIDES_SHEET_CSV = "https://docs.google.com/spreadsheets/d/14KWYBgvA3kP2CKw5MQxCsDA-QQY0oQoJdz289ESo7p8/gviz/tq?tqx=out:csv"
PRODUCT_SHEET_CSV = "https://docs.google.com/spreadsheets/d/1FzqeJiA7VfT3vKdmQLLejRcOaMOE9K9U0o3m8Wa-s78/gviz/tq?tqx=out:csv"

CACHE_TTL_SECONDS = 300
_cache: dict[str, tuple[float, list[dict]]] = {}

DRIVE_FILE_RE = re.compile(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)([\w-]+)")


def drive_image_url(value: str, width: int = 1000) -> str:
    """Turn a Google Drive share link into a URL that works inside <img>."""
    value = (value or "").strip()
    match = DRIVE_FILE_RE.search(value)
    if match:
        return f"https://drive.google.com/thumbnail?id={match.group(1)}&sz=w{width}"
    return value


def read_csv_from_url(url: str) -> list[dict]:
    cached = _cache.get(url)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(response.text)))
    except Exception as e:
        if cached:  # sheet temporarily unreachable — serve stale data
            return cached[1]
        raise HTTPException(status_code=502, detail=f"Failed to read sheet: {e}")
    _cache[url] = (time.time(), rows)
    return rows


def cell(row: dict, *keywords: str) -> str:
    """Find a cell by keyword so small header edits in the sheet don't break the site."""
    for key, value in row.items():
        if key and any(k in key for k in keywords):
            return (value or "").strip()
    return ""


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/products")
def products():
    rows = read_csv_from_url(PRODUCT_SHEET_CSV)
    result = []
    for row in rows:
        name = cell(row, "שם המוצר", "מוצר", "name")
        if not name:
            continue
        result.append({
            "name": name,
            "category": cell(row, "קטגוריה", "category"),
            "image": drive_image_url(cell(row, "תמונה", "image", "picture"), width=600),
            "link": cell(row, "קישור", "link"),
        })
    return result


def _normalize(name: str) -> str:
    """Lowercase and collapse punctuation, so 'Brand - Product' still matches 'Product'."""
    return re.sub(r"[^\w]+", " ", (name or "").casefold()).strip()


@app.get("/artists")
def artists():
    rows = read_csv_from_url(BRIDES_SHEET_CSV)
    all_products = products()
    product_index = {_normalize(p["name"]): p for p in all_products}

    def find_product(name: str):
        n = _normalize(name)
        if n in product_index:
            return product_index[n]
        for p in all_products:
            pn = _normalize(p["name"])
            if n in pn or pn in n:
                return p
        return None

    result = []
    for row in rows:
        photo = cell(row, "תמונה", "photo", "image")
        if not photo:
            continue
        product_names = [
            n.strip()
            for n in cell(row, "מוצרים", "products").splitlines()
            if n.strip()
        ]
        used = []
        for n in product_names:
            matched = find_product(n)
            used.append(matched or {"name": n, "category": "", "image": "", "link": ""})
        result.append({
            "photo": drive_image_url(photo),
            "description": cell(row, "תיאור", "description"),
            "products": used,
        })
    return result


@app.get("/categories")
def categories():
    seen = []
    for p in products():
        if p["category"] and p["category"] not in seen:
            seen.append(p["category"])
    return seen

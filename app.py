"""
GIA Property Builder — Streamlit App
Turns property websites into import-ready CSV for glampinginafrica.com

Deploy: Streamlit Community Cloud or run locally with `streamlit run app.py`
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import json
import os
import time
import re
import hashlib
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# ═══════════════════════════════════════════
# CONFIGURATION — Edit these to match your site
# ═══════════════════════════════════════════

APP_TITLE = "GIA Property Builder"
APP_ICON = "🏕️"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
CACHE_DIR = ".gia_cache"
FETCH_DELAY = 2.0  # seconds between web requests
GEOCODE_DELAY = 1.0
MAX_PAGES_PER_SITE = 15

# Property types (must match WordPress taxonomy)
PROPERTY_TYPES = [
    "Luxury Tents", "Safari Lodges", "Treehouses", "Cabins", "Cottages",
    "Houses", "Chalets", "Boutique Hotels", "Yurts", "Caravans",
    "Glamping Domes", "Houseboats", "Bush Camps", "Eco Lodges",
    "Overwater Bungalows", "Unique & Unusual",
]

# Amenities (must match WordPress taxonomy exactly)
AMENITIES_LIST = [
    "Swimming Pool", "Free Wi-Fi", "Air Conditioning", "Restaurant",
    "Spa & Wellness", "Bar / Lounge", "Gym / Fitness", "Kids Club",
    "Laundry Service", "Room Service", "Fireplace", "Private Deck",
    "Outdoor Shower", "En-suite Bathroom", "Generator Backup", "Solar Power",
    "BBQ / Braai Facilities", "Boma", "Dining Room", "Family Rooms",
    "Free Parking", "Garden", "Indoor Shower", "Kitchen / Kitchenette",
    "Living Room", "Microwave", "Mini Bar", "Safe / Lockbox",
    "Satellite TV", "Mosquito Nets", "Fan", "Hairdryer",
    "Tea & Coffee Station", "Wheelchair Accessible", "Pet Friendly",
    "EV Charging", "Plunge Pool", "Private Guide", "Butler Service",
    "Helicopter Pad", "Wine Cellar", "Library", "Star Bed",
    "Viewing Deck", "Bird Hide",
]

# Experiences (must match WordPress taxonomy exactly)
EXPERIENCES_LIST = [
    "Big Five Safari", "Walking Safaris", "Game Drives", "Night Drives",
    "Great Migration", "Hot Air Balloon Safaris", "Photography Safaris",
    "Bush Dinners & Sundowners", "Family Glamping", "Romantic Getaways",
    "Conservation Experiences", "Beach & Bush", "Gorilla Trekking",
    "Birding Safaris", "Canoe & Boat Safaris", "Fishing",
    "Horseback Safaris", "Fly-In Safaris", "Cultural Experiences",
    "Stargazing", "Wellness & Spa", "Mountain Trekking",
]

# Regions (must match WordPress taxonomy)
REGIONS_LIST = [
    "Western Cape", "Eastern Cape", "KwaZulu-Natal", "Limpopo",
    "Mpumalanga", "Gauteng", "North West", "Free State", "Northern Cape",
    "Garden Route", "Cape Winelands", "West Coast",
    "Okavango Delta", "Chobe", "Central Kalahari", "Makgadikgadi",
    "Moremi", "Tuli Block", "Nxai Pan",
    "Serengeti Ecosystem", "Ngorongoro", "Tarangire", "Zanzibar",
    "Selous / Nyerere", "Ruaha", "Lake Manyara", "Kilimanjaro Region",
    "Masai Mara", "Amboseli", "Samburu", "Laikipia", "Tsavo", "Lamu", "Diani",
    "Etosha", "Sossusvlei", "Skeleton Coast", "Damaraland", "Caprivi Strip",
    "South Luangwa", "Lower Zambezi", "Kafue",
    "Victoria Falls (Zambia)", "Victoria Falls (Zimbabwe)",
    "Hwange", "Mana Pools", "Matobo Hills", "Gonarezhou",
    "Bwindi", "Queen Elizabeth", "Murchison Falls", "Kibale",
    "Volcanoes National Park", "Akagera", "Nyungwe",
    "Bazaruto Archipelago", "Quirimbas", "Gorongosa", "Tofo",
    "Andasibe", "Isalo", "Nosy Be",
]

# CSV export column order (matches GIA WordPress importer exactly)
EXPORT_COLUMNS = [
    "title", "subtitle", "tagline", "featured", "status", "overview",
    "why_we_love", "country", "region", "property_type", "experiences",
    "amenities", "location_desc", "nearest_town", "nearest_airport",
    "gps_lat", "gps_lng", "what3words", "directions", "nearby_attractions",
    "rooms_desc", "max_guests", "price_from", "price_currency", "rating",
    "review_count", "checkin", "checkout", "cancellation", "booking_notes",
    "meals", "activities", "inclusions_notes", "things_to_do",
    "good_to_know", "who_its_for", "best_season", "booking_url",
    "tripadvisor_url", "viator_url", "gyg_url", "go2africa_url",
    "safarinow_url", "travelpayouts_url", "official_url",
]

EXTRA_COLUMNS = [
    "hero_image_url", "gallery_image_urls", "image_alt_text",
    "rank_math_title", "rank_math_description",
    "source_urls_crawled", "extraction_notes",
]

# Amenity keyword mapping (fuzzy match from extracted text to taxonomy terms)
AMENITY_KEYWORDS = {
    "pool": "Swimming Pool", "swimming": "Swimming Pool", "plunge pool": "Plunge Pool",
    "wifi": "Free Wi-Fi", "wi-fi": "Free Wi-Fi", "internet": "Free Wi-Fi",
    "air con": "Air Conditioning", "aircon": "Air Conditioning", "a/c": "Air Conditioning",
    "restaurant": "Restaurant", "dining": "Dining Room",
    "spa": "Spa & Wellness", "massage": "Spa & Wellness", "wellness": "Spa & Wellness",
    "bar": "Bar / Lounge", "lounge": "Bar / Lounge",
    "gym": "Gym / Fitness", "fitness": "Gym / Fitness",
    "kids": "Kids Club", "children": "Kids Club",
    "laundry": "Laundry Service",
    "room service": "Room Service",
    "fireplace": "Fireplace", "fire": "Fireplace",
    "deck": "Private Deck", "veranda": "Private Deck", "balcony": "Private Deck",
    "outdoor shower": "Outdoor Shower",
    "en-suite": "En-suite Bathroom", "ensuite": "En-suite Bathroom",
    "generator": "Generator Backup",
    "solar": "Solar Power",
    "bbq": "BBQ / Braai Facilities", "braai": "BBQ / Braai Facilities", "barbeque": "BBQ / Braai Facilities",
    "boma": "Boma",
    "parking": "Free Parking",
    "garden": "Garden",
    "kitchen": "Kitchen / Kitchenette", "kitchenette": "Kitchen / Kitchenette",
    "living room": "Living Room", "lounge area": "Living Room",
    "microwave": "Microwave",
    "mini bar": "Mini Bar", "minibar": "Mini Bar",
    "safe": "Safe / Lockbox",
    "tv": "Satellite TV", "television": "Satellite TV", "dstv": "Satellite TV",
    "mosquito": "Mosquito Nets",
    "fan": "Fan", "ceiling fan": "Fan",
    "hairdryer": "Hairdryer", "hair dryer": "Hairdryer",
    "tea": "Tea & Coffee Station", "coffee": "Tea & Coffee Station", "kettle": "Tea & Coffee Station",
    "wheelchair": "Wheelchair Accessible", "accessible": "Wheelchair Accessible",
    "pet": "Pet Friendly", "dog": "Pet Friendly",
    "guide": "Private Guide", "ranger": "Private Guide",
    "butler": "Butler Service",
    "star bed": "Star Bed", "sleep-out": "Star Bed", "sleepout": "Star Bed",
    "viewing deck": "Viewing Deck", "lookout": "Viewing Deck",
    "bird hide": "Bird Hide",
    "library": "Library",
    "wine cellar": "Wine Cellar",
}

EXPERIENCE_KEYWORDS = {
    "big five": "Big Five Safari", "big 5": "Big Five Safari",
    "walking safari": "Walking Safaris", "bush walk": "Walking Safaris", "guided walk": "Walking Safaris",
    "game drive": "Game Drives", "safari drive": "Game Drives",
    "night drive": "Night Drives", "spotlight": "Night Drives",
    "migration": "Great Migration", "wildebeest": "Great Migration",
    "balloon": "Hot Air Balloon Safaris", "hot air": "Hot Air Balloon Safaris",
    "photography": "Photography Safaris", "photo safari": "Photography Safaris",
    "bush dinner": "Bush Dinners & Sundowners", "sundowner": "Bush Dinners & Sundowners", "boma dinner": "Bush Dinners & Sundowners",
    "family": "Family Glamping", "kids programme": "Family Glamping", "junior ranger": "Family Glamping",
    "romantic": "Romantic Getaways", "honeymoon": "Romantic Getaways",
    "conservation": "Conservation Experiences", "anti-poaching": "Conservation Experiences",
    "beach": "Beach & Bush",
    "gorilla": "Gorilla Trekking",
    "birding": "Birding Safaris", "bird watching": "Birding Safaris", "birdwatching": "Birding Safaris",
    "canoe": "Canoe & Boat Safaris", "mokoro": "Canoe & Boat Safaris", "boat": "Canoe & Boat Safaris", "kayak": "Canoe & Boat Safaris",
    "fishing": "Fishing", "angling": "Fishing",
    "horse": "Horseback Safaris", "horseback": "Horseback Safaris",
    "fly-in": "Fly-In Safaris", "charter": "Fly-In Safaris",
    "cultural": "Cultural Experiences", "village": "Cultural Experiences", "maasai": "Cultural Experiences",
    "stargazing": "Stargazing", "astronomy": "Stargazing", "star bed": "Stargazing",
    "yoga": "Wellness & Spa", "wellness": "Wellness & Spa",
    "mountain": "Mountain Trekking", "hiking": "Mountain Trekking", "trekking": "Mountain Trekking",
}


# ═══════════════════════════════════════════
# CACHING
# ═══════════════════════════════════════════

def get_cache_path(key, suffix="json"):
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.{suffix}")


def cache_get(key):
    path = get_cache_path(key)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def cache_set(key, data):
    path = get_cache_path(key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════
# WEB FETCHING
# ═══════════════════════════════════════════

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(url, timeout=15):
    """Fetch a single page, return (html, final_url) or (None, None)."""
    cached = cache_get(f"fetch:{url}")
    if cached:
        return cached.get("html"), cached.get("url", url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        cache_set(f"fetch:{url}", {"html": html, "url": resp.url})
        time.sleep(FETCH_DELAY)
        return html, resp.url
    except Exception as e:
        return None, None


def discover_pages(base_url, html):
    """Find internal links to crawl (about, rooms, rates, activities, etc.)."""
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    keywords = [
        "about", "accommodation", "rooms", "suites", "tents", "rates",
        "pricing", "tariff", "activities", "experience", "safari",
        "gallery", "photos", "location", "directions", "contact",
        "facilities", "amenities", "dining", "spa", "wellness",
    ]
    found = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        parsed = urlparse(href)
        if parsed.netloc != base_domain:
            continue
        path = parsed.path.lower().rstrip("/")
        if any(kw in path for kw in keywords):
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            found.add(clean)
    return list(found)[:MAX_PAGES_PER_SITE]


def crawl_property_site(url, progress_callback=None):
    """Crawl a property website and return all page texts + images."""
    cached = cache_get(f"crawl:{url}")
    if cached:
        return cached

    pages_text = {}
    images = []
    urls_crawled = []

    # Fetch homepage
    html, final_url = fetch_page(url)
    if not html:
        return {"pages": {}, "images": [], "urls": [], "error": f"Could not fetch {url}"}

    base_url = final_url or url
    pages_text[base_url] = extract_text(html)
    urls_crawled.append(base_url)
    images.extend(extract_images(html, base_url))

    if progress_callback:
        progress_callback(f"Found homepage, discovering pages...")

    # Discover and fetch subpages
    subpages = discover_pages(base_url, html)
    for i, sub_url in enumerate(subpages):
        if sub_url in pages_text:
            continue
        if progress_callback:
            progress_callback(f"Fetching page {i+1}/{len(subpages)}: {sub_url.split('/')[-1] or sub_url}")
        sub_html, _ = fetch_page(sub_url)
        if sub_html:
            pages_text[sub_url] = extract_text(sub_html)
            urls_crawled.append(sub_url)
            images.extend(extract_images(sub_html, sub_url))

    result = {
        "pages": pages_text,
        "images": dedupe_images(images),
        "urls": urls_crawled,
        "error": None,
    }
    cache_set(f"crawl:{url}", result)
    return result


def extract_text(html):
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:15000]  # Limit to avoid token overflow


def extract_images(html, base_url):
    """Extract image URLs with alt text."""
    soup = BeautifulSoup(html, "html.parser")
    images = []
    for img in soup.find_all("img", src=True):
        src = urljoin(base_url, img["src"])
        if any(x in src.lower() for x in ["logo", "icon", "favicon", "pixel", "tracking", "avatar", "badge"]):
            continue
        alt = img.get("alt", "")
        # Check for reasonable image size hints
        width = img.get("width", "")
        if width and width.isdigit() and int(width) < 100:
            continue
        images.append({"url": src, "alt": alt, "source_page": base_url})
    return images


def dedupe_images(images):
    """Remove duplicate image URLs."""
    seen = set()
    unique = []
    for img in images:
        if img["url"] not in seen:
            seen.add(img["url"])
            unique.append(img)
    return unique


# ═══════════════════════════════════════════
# FACT EXTRACTION (from crawled text)
# ═══════════════════════════════════════════

def extract_facts(all_text, url, override_notes=""):
    """Extract factual data points from combined page text."""
    text = "\n\n".join(all_text.values()) if isinstance(all_text, dict) else all_text
    text_lower = text.lower()

    facts = {
        "official_url": url,
        "raw_text_length": len(text),
    }

    # Property name — try the first H1 or title-like text
    facts["property_name"] = "[needs review]"

    # GPS coordinates
    gps_match = re.search(r"(-?\d{1,3}\.\d{3,8})[,\s]+(-?\d{1,3}\.\d{3,8})", text)
    if gps_match:
        lat, lng = float(gps_match.group(1)), float(gps_match.group(2))
        if -40 < lat < 40 and -20 < lng < 60:  # Roughly Africa
            facts["gps_lat"] = str(lat)
            facts["gps_lng"] = str(lng)

    # Check-in/out times
    checkin_match = re.search(r"check[\s-]*in[:\s]*(\d{1,2}[:.]\d{2}(?:\s*[ap]m)?)", text_lower)
    checkout_match = re.search(r"check[\s-]*out[:\s]*(\d{1,2}[:.]\d{2}(?:\s*[ap]m)?)", text_lower)
    if checkin_match:
        facts["checkin"] = checkin_match.group(1).replace(".", ":").upper()
    if checkout_match:
        facts["checkout"] = checkout_match.group(1).replace(".", ":").upper()

    # Max guests
    guest_match = re.search(r"(\d{1,3})\s*(?:guests?|pax|people|sleeps)", text_lower)
    if guest_match:
        facts["max_guests"] = guest_match.group(1)

    # Prices
    price_patterns = [
        r"(?:from\s*)?(?:USD|US\$|\$)\s*(\d[\d,]*)",
        r"(?:from\s*)?(?:ZAR|R)\s*(\d[\d,]*)",
        r"(?:from\s*)?(?:EUR|€)\s*(\d[\d,]*)",
        r"(?:from\s*)?(?:GBP|£)\s*(\d[\d,]*)",
    ]
    currencies = ["USD", "ZAR", "EUR", "GBP"]
    for pattern, curr in zip(price_patterns, currencies):
        match = re.search(pattern, text)
        if match:
            price_str = match.group(1).replace(",", "")
            if price_str.isdigit() and 10 < int(price_str) < 100000:
                facts["price_from"] = price_str
                facts["price_currency"] = curr
                break

    # What3Words
    w3w_match = re.search(r"/{3}([\w]+\.[\w]+\.[\w]+)", text)
    if w3w_match:
        facts["what3words"] = w3w_match.group(1)

    # Match amenities
    matched_amenities = set()
    unmatched = []
    for keyword, term in AMENITY_KEYWORDS.items():
        if keyword in text_lower:
            matched_amenities.add(term)
    facts["amenities_matched"] = sorted(matched_amenities)

    # Match experiences
    matched_experiences = set()
    for keyword, term in EXPERIENCE_KEYWORDS.items():
        if keyword in text_lower:
            matched_experiences.add(term)
    facts["experiences_matched"] = sorted(matched_experiences)

    # Email
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if email_match:
        facts["email"] = email_match.group(0)

    # Store full text for LLM
    facts["full_text"] = text[:12000]
    facts["override_notes"] = override_notes

    return facts


# ═══════════════════════════════════════════
# GEOCODING
# ═══════════════════════════════════════════

@st.cache_data(ttl=86400)
def geocode_location(query):
    """Geocode a location string to lat/lng."""
    try:
        geolocator = Nominatim(user_agent="gia-property-builder")
        location = geolocator.geocode(query, timeout=10)
        time.sleep(GEOCODE_DELAY)
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, Exception):
        pass
    return None, None


# ═══════════════════════════════════════════
# LLM COPY GENERATION
# ═══════════════════════════════════════════

def generate_copy(facts, api_key, model=DEFAULT_MODEL):
    """Generate original copy from verified facts using Claude."""
    cache_key = f"llm:{hashlib.md5(json.dumps(facts, sort_keys=True).encode()).hexdigest()}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    system_prompt = """You are a travel copywriter for Glamping In Africa (glampinginafrica.com), a luxury glamping directory.

RULES:
- Write ONLY from the facts provided. Never invent details.
- No em dashes anywhere. Use commas, full stops, or restructure.
- No cliches: "nestled", "oasis", "hidden gem", "where luxury meets nature", "boasts"
- UK/SA English spelling (colour, centre, travelling)
- Warm but factual tone
- If a fact is missing, output "[needs review]" for that field
- Never generate "why_we_love" content — leave it blank

Respond ONLY with valid JSON, no markdown fences, no explanation."""

    user_prompt = f"""From these VERIFIED FACTS ONLY, generate the fields below.

FACTS:
{json.dumps(facts, indent=2, default=str)}

Generate a JSON object with these exact keys:
{{
  "title": "Property name",
  "subtitle": "One line, max 90 chars, format: A [type] in [location]",
  "tagline": "One evocative line, max 120 chars, factual",
  "overview": "180-260 words, 3 paragraphs. Para 1: what + where. Para 2: accommodation. Para 3: setting/experience. No em dashes.",
  "location_desc": "2-3 sentences of location context",
  "rooms_desc": "Room descriptions with <strong> tags for room names. From facts only.",
  "directions": "How to get there with <strong> subheadings. From facts only.",
  "things_to_do": "Activities structured with <strong> subheadings. From facts only.",
  "good_to_know": "Practical tips with <strong> subheadings. From facts only.",
  "who_its_for": "1-2 sentences on ideal guest type",
  "best_season": "1-2 sentences on best time to visit",
  "rank_math_title": "[Name] | [Type] in [Region], [Country] | Glamping In Africa",
  "rank_math_description": "Max 155 chars with property type, location, CTA"
}}

Only include facts you can verify from the data. Use "[needs review]" for anything uncertain."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )

        text = response.content[0].text.strip()
        # Clean potential markdown fences
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)
        cache_set(cache_key, result)
        return result
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════
# TAXONOMY MATCHING
# ═══════════════════════════════════════════

def match_region(region_text):
    """Find the closest matching region from the taxonomy list."""
    if not region_text:
        return "[needs review]"
    region_lower = region_text.lower().strip()
    for r in REGIONS_LIST:
        if r.lower() == region_lower:
            return r
        if region_lower in r.lower() or r.lower() in region_lower:
            return r
    return region_text  # Return as-is, flagged for review


def match_property_type(type_text):
    """Find the closest matching property type."""
    if not type_text:
        return "[needs review]"
    type_lower = type_text.lower().strip()
    type_keywords = {
        "tent": "Luxury Tents", "tented": "Luxury Tents", "canvas": "Luxury Tents",
        "lodge": "Safari Lodges", "safari lodge": "Safari Lodges",
        "treehouse": "Treehouses", "tree house": "Treehouses",
        "cabin": "Cabins", "log cabin": "Cabins",
        "cottage": "Cottages",
        "house": "Houses", "villa": "Houses", "home": "Houses",
        "chalet": "Chalets",
        "hotel": "Boutique Hotels", "boutique": "Boutique Hotels",
        "yurt": "Yurts",
        "caravan": "Caravans", "airstream": "Caravans",
        "dome": "Glamping Domes", "geodesic": "Glamping Domes",
        "houseboat": "Houseboats", "boat": "Houseboats",
        "bush camp": "Bush Camps", "fly camp": "Bush Camps",
        "eco": "Eco Lodges", "eco-lodge": "Eco Lodges",
        "overwater": "Overwater Bungalows",
    }
    for kw, pt in type_keywords.items():
        if kw in type_lower:
            return pt
    return "[needs review]"


# ═══════════════════════════════════════════
# ASSEMBLE FINAL ROW
# ═══════════════════════════════════════════

def assemble_row(facts, generated, input_row, images_selected=None):
    """Combine extracted facts, generated copy, and input data into final CSV row."""
    row = {}

    # From generated copy
    row["title"] = generated.get("title", input_row.get("property_name", "[needs review]"))
    row["subtitle"] = generated.get("subtitle", "[needs review]")
    row["tagline"] = generated.get("tagline", "")
    row["featured"] = "no"
    row["status"] = "active"
    row["overview"] = generated.get("overview", "[needs review]")
    row["why_we_love"] = ""  # Always blank — written personally

    # Location
    row["country"] = input_row.get("country", "[needs review]")
    row["region"] = match_region(input_row.get("region", ""))
    row["property_type"] = input_row.get("property_type", "[needs review]")

    # Taxonomy terms
    row["experiences"] = "|".join(facts.get("experiences_matched", []))
    row["amenities"] = ", ".join(facts.get("amenities_matched", []))

    # Location fields
    row["location_desc"] = generated.get("location_desc", "[needs review]")
    row["nearest_town"] = input_row.get("nearest_town", "[needs review]")
    row["nearest_airport"] = input_row.get("nearest_airport", "[needs review]")
    row["gps_lat"] = facts.get("gps_lat", input_row.get("gps_lat", ""))
    row["gps_lng"] = facts.get("gps_lng", input_row.get("gps_lng", ""))
    row["what3words"] = facts.get("what3words", "")
    row["directions"] = generated.get("directions", "[needs review]")
    row["nearby_attractions"] = input_row.get("nearby_attractions", "")

    # Accommodation
    row["rooms_desc"] = generated.get("rooms_desc", "[needs review]")
    row["max_guests"] = facts.get("max_guests", "[needs review]")
    row["price_from"] = facts.get("price_from", "[needs review]")
    row["price_currency"] = facts.get("price_currency", "USD")
    row["rating"] = input_row.get("rating", "")
    row["review_count"] = input_row.get("review_count", "")
    row["checkin"] = facts.get("checkin", "[needs review]")
    row["checkout"] = facts.get("checkout", "[needs review]")
    row["cancellation"] = input_row.get("cancellation", "[needs review]")
    row["booking_notes"] = input_row.get("booking_notes", "")

    # Inclusions
    row["meals"] = input_row.get("meals", "")
    row["activities"] = input_row.get("activities", "")
    row["inclusions_notes"] = input_row.get("inclusions_notes", "")

    # Visitor info
    row["things_to_do"] = generated.get("things_to_do", "[needs review]")
    row["good_to_know"] = generated.get("good_to_know", "[needs review]")
    row["who_its_for"] = generated.get("who_its_for", "[needs review]")
    row["best_season"] = generated.get("best_season", "[needs review]")

    # Affiliate links (pass through unchanged)
    row["booking_url"] = input_row.get("booking_url", "")
    row["tripadvisor_url"] = input_row.get("tripadvisor_url", "")
    row["viator_url"] = input_row.get("viator_url", "")
    row["gyg_url"] = input_row.get("gyg_url", "")
    row["go2africa_url"] = input_row.get("go2africa_url", "")
    row["safarinow_url"] = input_row.get("safarinow_url", "")
    row["travelpayouts_url"] = input_row.get("travelpayouts_url", "")
    row["official_url"] = input_row.get("official_website_url", "")

    # Extra columns
    row["hero_image_url"] = ""
    row["gallery_image_urls"] = ""
    row["image_alt_text"] = ""
    row["rank_math_title"] = generated.get("rank_math_title", "")
    row["rank_math_description"] = generated.get("rank_math_description", "")
    row["source_urls_crawled"] = "|".join(facts.get("urls_crawled", []))
    row["extraction_notes"] = ""

    # Images
    if images_selected:
        urls = [img["url"] for img in images_selected]
        alts = [img.get("alt", "") for img in images_selected]
        if urls:
            row["hero_image_url"] = urls[0]
            row["gallery_image_urls"] = "|".join(urls[1:]) if len(urls) > 1 else ""
            row["image_alt_text"] = "|".join(alts)

    return row


# ═══════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

st.title(f"{APP_ICON} {APP_TITLE}")
st.caption("Turn property websites into import-ready CSV for glampinginafrica.com")

# Sidebar — API key and settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Anthropic API Key", type="password", help="Your Claude API key for copy generation")
    model = st.selectbox("Model", [DEFAULT_MODEL, "claude-haiku-4-5-20251001"], index=0)
    st.divider()
    st.caption("**Cost estimate:** ~$0.01-0.03 per property with Sonnet")
    st.caption(f"**Cache:** {CACHE_DIR}/ (delete to reset)")
    if st.button("Clear Cache"):
        import shutil
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            st.success("Cache cleared")

# Main tabs
tab_input, tab_review, tab_generate, tab_export = st.tabs(["1. Input", "2. Review & Edit", "3. Generate Copy", "4. Export CSV"])

# Session state
if "properties" not in st.session_state:
    st.session_state.properties = []
if "crawl_results" not in st.session_state:
    st.session_state.crawl_results = {}
if "facts" not in st.session_state:
    st.session_state.facts = {}
if "generated" not in st.session_state:
    st.session_state.generated = {}
if "final_rows" not in st.session_state:
    st.session_state.final_rows = []

# ─── TAB 1: INPUT ───
with tab_input:
    st.subheader("Add Properties")

    input_method = st.radio("Input method", ["Upload CSV", "Manual entry"], horizontal=True)

    if input_method == "Upload CSV":
        st.caption("CSV columns: `official_website_url` (required), `property_name`, `booking_url`, `tripadvisor_url`, `viator_url`, `gyg_url`, `go2africa_url`, `safarinow_url`, `travelpayouts_url`, `override_notes`")
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded:
            df = pd.read_csv(uploaded)
            st.session_state.properties = df.to_dict("records")
            st.success(f"Loaded {len(df)} properties")
            st.dataframe(df, use_container_width=True)
    else:
        with st.form("manual_entry"):
            url = st.text_input("Property website URL *")
            name = st.text_input("Property name (optional)")
            booking = st.text_input("Booking.com affiliate URL")
            notes = st.text_area("Override notes (optional)")
            submitted = st.form_submit_button("Add Property")
            if submitted and url:
                st.session_state.properties.append({
                    "official_website_url": url,
                    "property_name": name,
                    "booking_url": booking,
                    "override_notes": notes,
                })
                st.success(f"Added: {name or url}")

    if st.session_state.properties:
        st.divider()
        st.write(f"**{len(st.session_state.properties)} properties queued**")

        if st.button("🔍 Crawl All Websites", type="primary"):
            progress = st.progress(0)
            status = st.empty()

            for i, prop in enumerate(st.session_state.properties):
                url = prop.get("official_website_url", "")
                if not url:
                    continue

                status.text(f"Crawling {i+1}/{len(st.session_state.properties)}: {url}")
                progress.progress((i + 1) / len(st.session_state.properties))

                result = crawl_property_site(url, lambda msg: status.text(f"[{i+1}] {msg}"))
                st.session_state.crawl_results[url] = result

                # Extract facts
                if result.get("pages"):
                    facts = extract_facts(
                        result["pages"],
                        url,
                        prop.get("override_notes", ""),
                    )
                    facts["urls_crawled"] = result.get("urls", [])
                    st.session_state.facts[url] = facts

            status.text("Crawling complete!")
            st.success(f"Crawled {len(st.session_state.crawl_results)} sites")

# ─── TAB 2: REVIEW & EDIT ───
with tab_review:
    st.subheader("Review Extracted Facts")

    if not st.session_state.facts:
        st.info("Crawl websites first (Tab 1)")
    else:
        for url, facts in st.session_state.facts.items():
            prop = next((p for p in st.session_state.properties if p.get("official_website_url") == url), {})
            with st.expander(f"📋 {prop.get('property_name') or url}", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.text_input("Property Name", value=prop.get("property_name", facts.get("property_name", "")), key=f"name_{url}")
                    st.text_input("Country", value=prop.get("country", ""), key=f"country_{url}", help="e.g. South Africa, Tanzania")
                    st.text_input("Region", value=prop.get("region", ""), key=f"region_{url}")
                    st.selectbox("Property Type", PROPERTY_TYPES, key=f"type_{url}", index=0)
                    st.text_input("Nearest Town", value=prop.get("nearest_town", ""), key=f"town_{url}")
                    st.text_input("Nearest Airport", value=prop.get("nearest_airport", ""), key=f"airport_{url}")

                with col2:
                    st.text_input("GPS Lat", value=facts.get("gps_lat", ""), key=f"lat_{url}")
                    st.text_input("GPS Lng", value=facts.get("gps_lng", ""), key=f"lng_{url}")
                    st.text_input("Max Guests", value=facts.get("max_guests", ""), key=f"guests_{url}")
                    st.text_input("Price From", value=facts.get("price_from", ""), key=f"price_{url}")
                    st.selectbox("Currency", ["USD", "ZAR", "EUR", "GBP"], key=f"curr_{url}",
                                 index=["USD", "ZAR", "EUR", "GBP"].index(facts.get("price_currency", "USD")) if facts.get("price_currency") in ["USD", "ZAR", "EUR", "GBP"] else 0)
                    st.text_input("Check-in", value=facts.get("checkin", ""), key=f"checkin_{url}")
                    st.text_input("Check-out", value=facts.get("checkout", ""), key=f"checkout_{url}")

                # Amenities
                st.multiselect("Amenities (matched)", AMENITIES_LIST,
                               default=facts.get("amenities_matched", []), key=f"amenities_{url}")

                # Experiences
                st.multiselect("Experiences (matched)", EXPERIENCES_LIST,
                               default=facts.get("experiences_matched", []), key=f"experiences_{url}")

                # Images
                crawl = st.session_state.crawl_results.get(url, {})
                images = crawl.get("images", [])
                if images:
                    st.write(f"**{len(images)} images found**")
                    img_cols = st.columns(min(5, len(images)))
                    for j, img in enumerate(images[:20]):
                        with img_cols[j % 5]:
                            st.image(img["url"], width=120, caption=img.get("alt", "")[:30])
                            st.checkbox("Use", key=f"img_{url}_{j}", value=j < 5)

                # Pages crawled
                st.caption(f"Pages crawled: {len(facts.get('urls_crawled', []))}")

                # Needs review warnings
                review_fields = []
                if not facts.get("gps_lat"):
                    review_fields.append("GPS coordinates")
                if not facts.get("price_from"):
                    review_fields.append("Price")
                if not facts.get("max_guests"):
                    review_fields.append("Max guests")
                if review_fields:
                    st.warning(f"⚠️ Needs review: {', '.join(review_fields)}")

# ─── TAB 3: GENERATE COPY ───
with tab_generate:
    st.subheader("Generate Original Copy")

    if not api_key:
        st.warning("Enter your Anthropic API key in the sidebar")
    elif not st.session_state.facts:
        st.info("Crawl and review facts first (Tabs 1-2)")
    else:
        if st.button("✍️ Generate Copy for All Properties", type="primary"):
            progress = st.progress(0)
            status = st.empty()

            for i, (url, facts) in enumerate(st.session_state.facts.items()):
                prop = next((p for p in st.session_state.properties if p.get("official_website_url") == url), {})
                status.text(f"Generating copy {i+1}/{len(st.session_state.facts)}: {prop.get('property_name', url)}")
                progress.progress((i + 1) / len(st.session_state.facts))

                # Update facts with any edits from Tab 2
                facts["property_name"] = st.session_state.get(f"name_{url}", facts.get("property_name", ""))
                updated_amenities = st.session_state.get(f"amenities_{url}", facts.get("amenities_matched", []))
                facts["amenities_matched"] = updated_amenities
                updated_experiences = st.session_state.get(f"experiences_{url}", facts.get("experiences_matched", []))
                facts["experiences_matched"] = updated_experiences

                generated = generate_copy(facts, api_key, model)
                st.session_state.generated[url] = generated

                if "error" in generated:
                    st.error(f"Error for {url}: {generated['error']}")

            status.text("Generation complete!")
            st.success("Copy generated for all properties")

        # Show generated content
        for url, gen in st.session_state.generated.items():
            if "error" in gen:
                continue
            prop = next((p for p in st.session_state.properties if p.get("official_website_url") == url), {})
            title_display = gen.get("title", prop.get("property_name", url))
with st.expander(f"📝 {title_display}", expanded=False):
                for key, val in gen.items():
                    if key == "error":
                        continue
                    st.text_area(key, value=val, key=f"gen_{url}_{key}", height=100 if len(str(val)) > 200 else 68)

# ─── TAB 4: EXPORT ───
with tab_export:
    st.subheader("Export CSV")

    if not st.session_state.generated:
        st.info("Generate copy first (Tab 3)")
    else:
        if st.button("📦 Assemble Final CSV", type="primary"):
            rows = []
            for url, facts in st.session_state.facts.items():
                prop = next((p for p in st.session_state.properties if p.get("official_website_url") == url), {})
                gen = st.session_state.generated.get(url, {})

                # Get selected images
                crawl = st.session_state.crawl_results.get(url, {})
                images = crawl.get("images", [])
                selected = [img for j, img in enumerate(images[:20]) if st.session_state.get(f"img_{url}_{j}", False)]

                # Update prop with edited values
                prop["property_name"] = st.session_state.get(f"name_{url}", prop.get("property_name", ""))
                prop["country"] = st.session_state.get(f"country_{url}", prop.get("country", ""))
                prop["region"] = st.session_state.get(f"region_{url}", prop.get("region", ""))
                prop["property_type"] = st.session_state.get(f"type_{url}", "")
                prop["nearest_town"] = st.session_state.get(f"town_{url}", "")
                prop["nearest_airport"] = st.session_state.get(f"airport_{url}", "")

                facts["gps_lat"] = st.session_state.get(f"lat_{url}", facts.get("gps_lat", ""))
                facts["gps_lng"] = st.session_state.get(f"lng_{url}", facts.get("gps_lng", ""))
                facts["max_guests"] = st.session_state.get(f"guests_{url}", facts.get("max_guests", ""))
                facts["price_from"] = st.session_state.get(f"price_{url}", facts.get("price_from", ""))
                facts["price_currency"] = st.session_state.get(f"curr_{url}", facts.get("price_currency", "USD"))
                facts["checkin"] = st.session_state.get(f"checkin_{url}", facts.get("checkin", ""))
                facts["checkout"] = st.session_state.get(f"checkout_{url}", facts.get("checkout", ""))
                facts["amenities_matched"] = st.session_state.get(f"amenities_{url}", facts.get("amenities_matched", []))
                facts["experiences_matched"] = st.session_state.get(f"experiences_{url}", facts.get("experiences_matched", []))

                # Geocode if needed
                if not facts.get("gps_lat") and prop.get("country"):
                    query = f"{prop.get('nearest_town', '')}, {prop.get('region', '')}, {prop.get('country', '')}"
                    lat, lng = geocode_location(query.strip(", "))
                    if lat:
                        facts["gps_lat"] = str(round(lat, 6))
                        facts["gps_lng"] = str(round(lng, 6))

                row = assemble_row(facts, gen, prop, selected)
                rows.append(row)

            st.session_state.final_rows = rows

        if st.session_state.final_rows:
            df = pd.DataFrame(st.session_state.final_rows)

            # Reorder columns
            all_cols = EXPORT_COLUMNS + EXTRA_COLUMNS
            existing = [c for c in all_cols if c in df.columns]
            df = df[existing]

            # Stats
            needs_review = sum(1 for row in st.session_state.final_rows for v in row.values() if v == "[needs review]")
            st.metric("Properties", len(df))
            st.metric("Fields needing review", needs_review)

            # Preview
            st.dataframe(df, use_container_width=True, height=400)

            # Download
            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ Download CSV",
                data=csv_data,
                file_name="gia_properties_import.csv",
                mime="text/csv",
                type="primary",
            )

            st.caption("Import this CSV at **Properties > Import Properties** in WordPress")

"""
Download Lora and Poppins from Google Fonts, convert WOFF2 → TTF.
Run during Railway build or locally: python3 download_fonts.py

Requires: fonttools brotli (both in requirements.txt)
"""
import re, os, sys, io
import urllib.request

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
os.makedirs(FONT_DIR, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

FAMILIES = "family=Lora:ital,wght@0,400;1,400&family=Poppins:wght@300;400;500;700"
CSS_URL = f"https://fonts.googleapis.com/css2?{FAMILIES}&display=swap"

# (family, style, weight) → output filename
WANT = {
    ("Lora",    "normal", "400"): "Lora-Variable.ttf",
    ("Lora",    "italic", "400"): "Lora-Italic-Variable.ttf",
    ("Poppins", "normal", "400"): "Poppins-Regular.ttf",
    ("Poppins", "normal", "300"): "Poppins-Light.ttf",
    ("Poppins", "normal", "500"): "Poppins-Medium.ttf",
    ("Poppins", "normal", "700"): "Poppins-Bold.ttf",
}


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={**{"User-Agent": UA}, **(headers or {})})
    return urllib.request.urlopen(req, timeout=30).read()


def woff2_to_ttf(data: bytes) -> bytes:
    """Convert WOFF2 bytes to plain TTF bytes using fonttools."""
    from fontTools.ttLib import TTFont as FTFont
    font = FTFont(io.BytesIO(data))
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def parse_font_faces(css_text):
    """Return {(family, style, weight): url} from Google Fonts CSS2 response."""
    results = {}
    for block in re.findall(r'@font-face\s*\{([^}]+)\}', css_text, re.DOTALL):
        family = re.search(r"font-family:\s*'?([^;'\n]+)'?", block)
        style  = re.search(r'font-style:\s*(\w+)', block)
        weight = re.search(r'font-weight:\s*(\d+)', block)
        url    = re.search(r"src:[^;]*url\(([^)]+)\)", block)
        if family and style and weight and url:
            key = (family.group(1).strip(), style.group(1), weight.group(1))
            results[key] = url.group(1).strip("'\"")
    return results


print("Fetching font CSS from Google Fonts...")
try:
    css = fetch(CSS_URL).decode("utf-8")
except Exception as e:
    print(f"ERROR: Could not fetch font CSS: {e}")
    sys.exit(1)

font_faces = parse_font_faces(css)
print(f"Found {len(font_faces)} font-face declarations")

downloaded = 0
for key, dest_name in WANT.items():
    dest = os.path.join(FONT_DIR, dest_name)
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        print(f"  {dest_name}: already present")
        downloaded += 1
        continue

    url = font_faces.get(key)
    if not url:
        print(f"  WARNING: no URL for {key}")
        continue

    try:
        raw = fetch(url)
        if raw[:4] == b'wOF2':
            data = woff2_to_ttf(raw)
        elif raw[:4] in (b'\x00\x01\x00\x00', b'true', b'OTTO'):
            data = raw
        else:
            print(f"  WARNING: {dest_name} unexpected magic={raw[:4]!r}")
            continue
        with open(dest, 'wb') as f:
            f.write(data)
        print(f"  {dest_name}: {len(data):,} bytes")
        downloaded += 1
    except Exception as e:
        print(f"  ERROR {dest_name}: {e}")

print(f"\nDone: {downloaded}/{len(WANT)} fonts in {FONT_DIR}")
if downloaded < len(WANT):
    print("Some fonts missing — PDF will use fallback (Helvetica/Times) fonts")

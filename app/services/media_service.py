import io
import os
from datetime import datetime
from collections import defaultdict

import numpy as np
from PIL import Image, ExifTags
import imagehash

from app.config import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, PHASH_THRESHOLD, COLOR_THRESHOLD, TIME_WINDOW_SECONDS

def kind(path):
    e = os.path.splitext(path)[1].lower()
    if e in IMAGE_EXTENSIONS:
        return "photo"
    if e in VIDEO_EXTENSIONS:
        return "video"
    return "other"

def human(n):
    n = float(n or 0)
    for u in ["B","KB","MB","GB","TB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def image_features(data):
    out = {
        "width": None, "height": None, "taken_date": None,
        "camera": None, "gps": False, "phash": None,
        "hist": None
    }
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
        out["width"], out["height"] = im.size
        out["phash"] = str(imagehash.phash(im))

        # Small normalized RGB histogram for fast color comparison.
        arr = np.asarray(im.resize((128,128)), dtype=np.uint8)
        hist = []
        for c in range(3):
            h, _ = np.histogram(arr[:,:,c], bins=32, range=(0,256))
            h = h.astype(np.float32)
            h /= max(h.sum(), 1)
            hist.extend(h.tolist())
        out["hist"] = hist

        exif = Image.open(io.BytesIO(data)).getexif()
        tags = {ExifTags.TAGS.get(k,k): v for k,v in exif.items()}
        out["taken_date"] = tags.get("DateTimeOriginal") or tags.get("DateTime")
        make, model = tags.get("Make"), tags.get("Model")
        out["camera"] = " ".join(str(x) for x in [make,model] if x) or None
        out["gps"] = "GPSInfo" in tags
    except Exception:
        pass
    return out

def hist_similarity(a, b):
    if not a or not b:
        return 0.0
    x, y = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = np.sqrt(np.sum(x*x) * np.sum(y*y))
    return float(np.dot(x,y) / denom) if denom else 0.0

def phash_distance(a,b):
    try:
        return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)
    except Exception:
        return 999

def parse_taken_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None

def record(adb, path, need_visual=False):
    st = adb.stat(path)
    r = {
        "path": path,
        "name": os.path.basename(path),
        "kind": kind(path),
        "size": st["size"],
        "mtime": st["mtime"],
        "modified": datetime.fromtimestamp(st["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
                    if st["mtime"] else "Unknown",
        "hash": adb.sha256(path),
    }
    if r["kind"] == "photo" and need_visual:
        try:
            r.update(image_features(adb.pull_bytes(path)))
        except Exception:
            pass
    return r

def exact_groups(records):
    d = defaultdict(list)
    for r in records:
        d[(r["kind"], r["hash"])].append(r)
    return [g for g in d.values() if len(g) > 1]

def visual_groups(records, threshold=PHASH_THRESHOLD):
    photos = [r for r in records if r["kind"] == "photo" and r.get("phash")]
    parent = list(range(len(photos)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a,b):
        a,b=find(a),find(b)
        if a != b: parent[b]=a

    for i in range(len(photos)):
        for j in range(i+1,len(photos)):
            if phash_distance(photos[i]["phash"], photos[j]["phash"]) <= threshold:
                union(i,j)

    groups = defaultdict(list)
    for i,r in enumerate(photos):
        groups[find(i)].append(r)
    return [g for g in groups.values() if len(g)>1]

def color_groups(records, threshold=COLOR_THRESHOLD):
    photos = [r for r in records if r["kind"]=="photo" and r.get("hist")]
    parent=list(range(len(photos)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i in range(len(photos)):
        for j in range(i+1,len(photos)):
            if hist_similarity(photos[i]["hist"], photos[j]["hist"]) >= threshold:
                union(i,j)
    groups=defaultdict(list)
    for i,r in enumerate(photos): groups[find(i)].append(r)
    return [g for g in groups.values() if len(g)>1]

def time_groups(records, window=TIME_WINDOW_SECONDS):
    photos=[r for r in records if r["kind"]=="photo"]
    photos.sort(key=lambda x: x["mtime"])
    groups=[]
    cur=[]
    for r in photos:
        if not cur or r["mtime"]-cur[-1]["mtime"] <= window:
            cur.append(r)
        else:
            if len(cur)>1: groups.append(cur)
            cur=[r]
    if len(cur)>1: groups.append(cur)
    return groups

def keep_score(r):
    # Higher is preferred to keep. This is a transparent heuristic, not AI.
    pixels=(r.get("width") or 0)*(r.get("height") or 0)
    return (pixels/1_000_000) + (r.get("size",0)/10_000_000_000) + (r.get("mtime",0)/10**12)

def recommend_keeper(group):
    return max(group, key=keep_score)

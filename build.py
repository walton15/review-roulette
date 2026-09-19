"""SmartButGameCritic — turns steam-data.json into the redacted docs/data.json the site loads.

    python build.py [steam-data.json]
    python build.py --strangers-only   # refresh only the other-player reviews in docs/data.json


Game titles become [GAME TITLE]; developer/publisher names become [DEVELOPER].
Extra per-game terms (character names, places, sequels...) go in redactions.json:
    { "620": ["GLaDOS", "Wheatley", "Aperture"], "*": ["terms redacted everywhere"] }
"""
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "appdetails.json"
TITLE, DEV, HIDDEN = "[GAME TITLE]", "[DEVELOPER]", "[REDACTED]"

EDITION = re.compile(
    r"\s*[-:–—(]?\s*\b(game of the year|goty|definitive|enhanced|complete|deluxe|ultimate|anniversary|"
    r"special|director'?s cut|remastered|remake|legendary|gold|premium|standard|digital deluxe)\b.*$", re.I)
CORP = re.compile(r",?\s*\b(inc|llc|ltd|limited|gmbh|co|corp|corporation|s\.?a|srl|ab|as|oy|pty|k\.?k)\b\.?$", re.I)
DEMO_NAME = re.compile(r"(?<!\w)demos?(?!\w)", re.I)
# Steam categories that say nothing about which game it is (hint #2 lists the rest).
DULL_TAG = re.compile(r"remote play|family sharing|captions|commentary|dualshock|dualsense|steam input|"
                      r"stereo sound|surround sound|camera comfort|custom volume|timed input|save anytime|"
                      r"adjustable|screen reader|colou?r alternatives|subtitle|audio cue|mouse only|keyboard only|"
                      r"steam cloud|trading cards|leaderboards|hdr available|notes available|^stats$", re.I)
MONTHS = {m: i for i, m in enumerate(
    "January February March April May June July August September October November December".split(), 1)}
ROMAN = {"II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"}
# Short fragments that are ordinary words; never redact these on their own.
COMMON = {"the", "game", "games", "a", "an", "of", "and", "edition", "online", "simulator", "studio", "studios",
          "entertainment", "interactive", "software", "digital", "publishing", "team", "world", "war", "life"}


USER_TAGS = 8  # about as many as the store page shows before its "+" button
AGE_GATE = "birthtime=0; lastagecheckage=1-0-1990; wants_mature_content=1"


def user_tags(appid):
    """The "Popular user-defined tags" from the store page, most-voted first, as hint #2 shows them.
    [] when the game has no store page any more (Steam redirects those to its front page)."""
    req = urllib.request.Request(f"https://store.steampowered.com/app/{appid}/?l=english", headers={"Cookie": AGE_GATE})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                page = r.read().decode("utf8", "replace")
            break
        except Exception as e:  # rate limited (429) or transient
            print(f"  store page {appid} failed ({e}); retrying")
            time.sleep(30 * (attempt + 1))
    else:
        return []
    return [clean(t) for t in re.findall(r'class="app_tag"[^>]*>\s*([^<]+?)\s*<', page)][:USER_TAGS]


def tags_from(data):
    """Genres then categories: hint #2's fallback for games without user tags."""
    out = []
    for item in (data.get("genres") or []) + (data.get("categories") or []):
        label = clean(item.get("description"))
        # Steam sometimes hands back an untranslated token like "#category_contrast_controls".
        if label and not label.startswith("#") and label not in out and not DULL_TAG.search(label):
            out.append(label)
    return out[:12]


def posted_date(posted, this_year):
    """"Posted September 15." / "Posted March 13, 2020." -> "2020-03-13".
    Steam leaves the year off reviews from the current year, meaning the year it was collected."""
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?", posted or "")
    if not m or m.group(1) not in MONTHS:
        return None
    return f"{int(m.group(3) or this_year):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


def fetch_details(appids):
    cache = json.loads(CACHE.read_text("utf8")) if CACHE.exists() else {}
    for appid in appids:
        if "user_tags" not in cache.get(str(appid), {}):
            cache.setdefault(str(appid), {})["user_tags"] = user_tags(appid)
            CACHE.parent.mkdir(exist_ok=True)
            CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), "utf8")
            time.sleep(1.6)
        if {"header_image", "type", "tags"} <= cache[str(appid)].keys():
            continue
        url = (f"https://store.steampowered.com/api/appdetails?appids={appid}"
               f"&filters=basic,developers,publishers,genres,categories&l=english")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    body = json.load(r) or {}
                break
            except Exception as e:  # rate limited (429) or transient
                print(f"  appdetails {appid} failed ({e}); retrying")
                time.sleep(30 * (attempt + 1))
        else:
            body = {}
        entry = body.get(str(appid), {})
        data = entry.get("data", {}) if entry.get("success") else {}
        # Newer games keep their art under hashed paths, so store the real image URLs.
        cache[str(appid)] = {**cache.get(str(appid), {}),
                             **{k: data.get(k) for k in ("name", "type", "developers", "publishers", "header_image", "capsule_imagev5")},
                             "tags": tags_from(data)}
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), "utf8")
        time.sleep(1.6)
    return cache


def name_from_review_page(url):
    """Delisted games have no store page; the review page title still names them."""
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            m = re.search(r"<title>[^<]*:: Review for ([^<]+)</title>", r.read().decode("utf8", "replace"))
        return html.unescape(m.group(1)).strip() if m else None
    except Exception:
        return None


def clean(s):
    return re.sub(r"[™®©]", "", s or "").strip()


def is_demo(details, name):
    """Demos aren't games to guess, so they stay out of the reviews, the answer pool and the decoys.
    The store says what an app is; delisted apps have no store page, so fall back to the title."""
    kind = (details or {}).get("type")
    return kind == "demo" if kind else bool(DEMO_NAME.search(name or ""))


def title_variants(name):
    name = clean(name)
    out = {name}
    out.add(EDITION.sub("", name))
    for sep in (":", " - ", " – ", " — "):
        if sep in name:
            head, tail = name.split(sep, 1)
            out.update({head, tail})
    for v in list(out):
        out.add(re.sub(r"[^\w\s]", "", v))           # without punctuation
        out.add(re.sub(r"\s+", "", v))               # squashed: "Stardew Valley" -> "StardewValley"
        words = v.split()
        if len(words) >= 3 and (words[-1] in ROMAN or words[-1].isdigit()):
            out.add(" ".join(words[:-1]))            # "Silent Hill 2" -> "Silent Hill"
        if words and words[0].lower() == "the":
            out.add(" ".join(words[1:]))
        if words and words[-1] in ROMAN:
            out.add(" ".join(words[:-1] + [ROMAN[words[-1]]]))
        if words and words[-1] in ROMAN.values():
            out.add(" ".join(words[:-1] + [k for k, n in ROMAN.items() if n == words[-1]]))
        if v.isupper():
            out.add(v.title())                       # "SWORN" also matches "Sworn"/"sworn"
        caps = [w for w in words if w[:1].isalnum()]
        if len(caps) >= 3:
            out.add("".join(w[0] for w in caps).upper())  # acronym, matched case-sensitively
    return {v.strip() for v in out if len(v.strip()) >= 3 and v.strip().lower() not in COMMON}


def company_variants(names):
    out = set()
    for n in names or []:
        n = clean(n)
        out.update({n, CORP.sub("", n).strip()})
        out.add(re.sub(r"\s+(games|studios?|entertainment|interactive|software)$", "", CORP.sub("", n).strip(), flags=re.I))
    return {v for v in out if len(v) >= 3 and v.lower() not in COMMON}


def redact(text, replacements):
    # Longest terms first so "Dark Souls III" wins over "Dark Souls".
    for term, label in sorted(replacements, key=lambda t: -len(t[0])):
        is_acronym = term.isupper() and " " not in term and len(term) <= 6
        pattern = r"(?<![\w])" + re.escape(term).replace(r"\ ", r"[\s\-]+") + r"(?![\w])"
        text = re.sub(pattern, label, text, flags=0 if is_acronym else re.I)
    text = re.sub(r"https?://\S+|store\.steampowered\.com\S*|steamcommunity\.com\S*", "[LINK]", text)
    for label in (TITLE, DEV):  # "[GAME TITLE]: [GAME TITLE]" -> "[GAME TITLE]"
        text = re.sub(re.escape(label) + r"(\s*[:\-–—]?\s*" + re.escape(label) + r")+", label, text)
    return text


def replacements_for(appid, name, details, extra):
    reps = [(v, TITLE) for v in title_variants(name) | title_variants(details.get("name") or "")]
    reps += [(v, DEV) for v in company_variants((details.get("developers") or []) + (details.get("publishers") or []))]
    reps += [(t, HIDDEN) for t in extra.get(str(appid), []) + extra.get("*", [])]
    return reps


def build_strangers(strangers_raw, pool, details, extra):
    strangers = []
    for s in strangers_raw:
        d = details.get(str(s["appid"]), {})
        name = pool.get(s["appid"]) or clean(d.get("name")) or clean(d.get("fallback_name"))
        if name and not is_demo(d, name):
            # "posted" feeds hint #1, which has to read the same here as on his own reviews.
            strangers.append({**s, "name": name, "posted": s.get("posted"),
                              "text": redact(s["text"], replacements_for(s["appid"], name, d, extra))})
    return strangers


def hint_tags(details):
    """appid -> hint #2's list: the store page's user tags, else its genres and categories.
    Leaves out tags that share a word with the title, like "Warhammer 40K" on a Warhammer game."""
    words = lambda s: {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in COMMON and len(w) > 2}
    out = {}
    for a, d in details.items():
        title = words(d.get("name")) | words(d.get("fallback_name"))
        tags = [t for t in d.get("user_tags") or d.get("tags") or [] if not words(t) & title]
        if tags:
            out[a] = tags
    return out


def strangers_only():
    """Used by the daily GitHub Action, which has docs/data.json but not steam-data.json."""
    target = ROOT / "docs" / "data.json"
    out = json.loads(target.read_text("utf8"))
    extra = json.loads((ROOT / "redactions.json").read_text("utf8")) if (ROOT / "redactions.json").exists() else {}
    strangers_raw = json.loads((ROOT / "strangers.json").read_text("utf8"))
    details = fetch_details(sorted({s["appid"] for s in strangers_raw}))
    pool = {g["appid"]: g["name"] for g in out["games"]}
    out["strangers"] = build_strangers(strangers_raw, pool, details, extra)
    out["tags"] = {**out.get("tags", {}), **hint_tags(details)}
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf8")
    print(f"Wrote docs/data.json: {len(out['strangers'])} other-player reviews")


def main():
    if "--strangers-only" in sys.argv:
        return strangers_only()
    src = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "steam-data.json")
    raw = json.loads(src.read_text("utf8"))
    extra = json.loads((ROOT / "redactions.json").read_text("utf8")) if (ROOT / "redactions.json").exists() else {}
    this_year = (raw.get("collected") or "")[:4] or datetime.now(timezone.utc).year

    library = {g["appid"]: clean(g["name"]) for g in raw.get("games", [])}
    strangers_raw = json.loads((ROOT / "strangers.json").read_text("utf8")) if (ROOT / "strangers.json").exists() else []
    details = fetch_details(sorted(set(library) | {r["appid"] for r in raw["reviews"]} | {s["appid"] for s in strangers_raw}))
    library = {a: n for a, n in library.items() if not is_demo(details.get(str(a), {}), n)}

    reviews, demos = [], 0
    for r in raw["reviews"]:
        d = details.get(str(r["appid"]), {})
        name = library.get(r["appid"]) or clean(d.get("name"))
        if not name:
            if not d.get("fallback_name"):
                d["fallback_name"] = name_from_review_page(r["url"]) if r.get("url") else None
                CACHE.write_text(json.dumps(details, indent=1, ensure_ascii=False), "utf8")
            name = clean(d.get("fallback_name")) or f"App {r['appid']}"
        text = r["text"].strip()
        if len(text) < 3:
            continue
        if is_demo(d, name):  # demos aren't games to guess
            demos += 1
            continue
        reviews.append({
            "appid": r["appid"], "name": name, "recommended": r["recommended"], "hours": r["hours"],
            "posted": posted_date(r.get("posted"), this_year), "url": r["url"],
            "text": redact(text, replacements_for(r["appid"], name, d, extra)),
        })

    # Distractor pool: his library, plus reviewed games in case the library list is missing any.
    pool = dict(library)
    for rv in reviews:
        pool.setdefault(rv["appid"], rv["name"])
    # Decoys: AI-written fakes in his style (fakes.json) and other players' reviews (strangers.json, from strangers.py).
    fakes = json.loads((ROOT / "fakes.json").read_text("utf8")) if (ROOT / "fakes.json").exists() else []
    strangers = build_strangers(strangers_raw, pool, details, extra)

    out = {"profile": raw.get("profile"), "reviews": reviews, "fakes": fakes, "strangers": strangers,
           "games": [{"appid": a, "name": n} for a, n in sorted(pool.items(), key=lambda kv: kv[1].lower())],
           # appid -> [header, capsule] image URLs from the store (the site falls back to Steam's default path)
           "images": {a: [d.get("header_image"), d.get("capsule_imagev5")] for a, d in details.items()
                      if d.get("header_image") or d.get("capsule_imagev5")},
           # appid -> user tags (or genres and categories), shown as hint #2
           "tags": hint_tags(details)}
    target = ROOT / "docs" / "data.json"
    before = {r["appid"] for r in json.loads(target.read_text("utf8"))["reviews"]} if target.exists() else set()
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf8")
    for rv in reviews:
        if before and rv["appid"] not in before:
            print(f"  NEW  {rv['appid']} {rv['name']}: check for giveaways -> {rv['text'][:300]!r}")
    print(f"Wrote docs/data.json: {len(reviews)} reviews, {len(pool)} games in the answer pool, "
          f"{len(fakes)} fakes, {len(strangers)} other-player reviews"
          + (f" (skipped {demos} demos)" if demos else ""))


if __name__ == "__main__":
    main()

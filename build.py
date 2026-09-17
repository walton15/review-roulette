"""Review Roulette — turns steam-data.json into the redacted docs/data.json the site loads.

    python build.py [steam-data.json]

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
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "appdetails.json"
TITLE, DEV, HIDDEN = "[GAME TITLE]", "[DEVELOPER]", "[REDACTED]"

EDITION = re.compile(
    r"\s*[-:–—(]?\s*\b(game of the year|goty|definitive|enhanced|complete|deluxe|ultimate|anniversary|"
    r"special|director'?s cut|remastered|remake|legendary|gold|premium|standard|digital deluxe)\b.*$", re.I)
CORP = re.compile(r",?\s*\b(inc|llc|ltd|limited|gmbh|co|corp|corporation|s\.?a|srl|ab|as|oy|pty|k\.?k)\b\.?$", re.I)
ROMAN = {"II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"}
# Short fragments that are ordinary words; never redact these on their own.
COMMON = {"the", "game", "games", "a", "an", "of", "and", "edition", "online", "simulator", "studio", "studios",
          "entertainment", "interactive", "software", "digital", "publishing", "team", "world", "war", "life"}


def fetch_details(appids):
    cache = json.loads(CACHE.read_text("utf8")) if CACHE.exists() else {}
    for appid in appids:
        if str(appid) in cache:
            continue
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic,developers,publishers&l=english"
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
        cache[str(appid)] = {k: data.get(k) for k in ("name", "developers", "publishers")}
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


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "steam-data.json")
    raw = json.loads(src.read_text("utf8"))
    extra = json.loads((ROOT / "redactions.json").read_text("utf8")) if (ROOT / "redactions.json").exists() else {}

    library = {g["appid"]: clean(g["name"]) for g in raw.get("games", [])}
    details = fetch_details(sorted({r["appid"] for r in raw["reviews"]}))

    reviews = []
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
        reviews.append({
            "appid": r["appid"], "name": name, "recommended": r["recommended"],
            "hours": r["hours"], "url": r["url"], "text": redact(text, replacements_for(r["appid"], name, d, extra)),
        })

    # Distractor pool: his library, plus reviewed games in case the library list is missing any.
    pool = dict(library)
    for rv in reviews:
        pool.setdefault(rv["appid"], rv["name"])
    # Decoys: AI-written fakes in his style (fakes.json) and other players' reviews (strangers.json, from strangers.py).
    fakes = json.loads((ROOT / "fakes.json").read_text("utf8")) if (ROOT / "fakes.json").exists() else []
    strangers = []
    for s in json.loads((ROOT / "strangers.json").read_text("utf8")) if (ROOT / "strangers.json").exists() else []:
        d = details.get(str(s["appid"]), {})
        name = pool.get(s["appid"]) or clean(d.get("name")) or clean(d.get("fallback_name"))
        if name:
            strangers.append({**s, "name": name, "text": redact(s["text"], replacements_for(s["appid"], name, d, extra))})

    out = {"profile": raw.get("profile"), "reviews": reviews, "fakes": fakes, "strangers": strangers,
           "games": [{"appid": a, "name": n} for a, n in sorted(pool.items(), key=lambda kv: kv[1].lower())]}
    target = ROOT / "docs" / "data.json"
    before = {r["appid"] for r in json.loads(target.read_text("utf8"))["reviews"]} if target.exists() else set()
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf8")
    for rv in reviews:
        if before and rv["appid"] not in before:
            print(f"  NEW  {rv['appid']} {rv['name']}: check for giveaways -> {rv['text'][:300]!r}")
    print(f"Wrote docs/data.json: {len(reviews)} reviews, {len(pool)} games in the answer pool, "
          f"{len(fakes)} fakes, {len(strangers)} other-player reviews")


if __name__ == "__main__":
    main()

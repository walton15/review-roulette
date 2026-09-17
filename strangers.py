"""SmartButGameCritic — collects a pool of reviews written by *other* Steam players.

    python strangers.py [count]

For random games he has reviewed, pulls a helpful English review from Steam's public
review API and saves the raw pool to strangers.json. build.py redacts them like his.
Re-running replaces the pool; delete entries from strangers.json to drop bad picks.
"""
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
HIS_STEAMID = "76561198236847246"
SLURS = re.compile(r"nigg|fag|retard|tranny|kys\b|touched|sex|porn|rape", re.I)
SKIP_APPS = {2786830, 3673060}  # joke/adult titles whose other reviews are rarely usable
# Steam's profanity filter shows these as ♥♥♥♥ on his reviews, so match that look.
PROFANITY = re.compile(r"\b(motherf\w*|fuck\w*|shit\w*|bitch\w*|cunt\w*|dick\w*|pussy\w*|whore\w*|slut\w*)", re.I)


def clean_bbcode(text):
    text = re.sub(r"\[url=[^\]]*\](.*?)\[/url\]", r"\1", text, flags=re.I | re.S)
    text = re.sub(r"\[\*\]", "• ", text)
    text = re.sub(r"\[/?(h[1-6]|b|i|u|strike|spoiler|noparse|hr|code|quote|list|olist|table|tr|td|th|url)(=[^\]]*)?\]", "", text, flags=re.I)
    text = PROFANITY.sub(lambda m: "♥" * len(m.group(0)), text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def looks_usable(text):
    if not 40 <= len(text) <= 900 or SLURS.search(text):
        return False
    letters = sum(c.isalpha() for c in text)
    if sum(c.isascii() for c in text if c.isalpha()) < 0.95 * letters:  # "english" tag is sometimes wrong
        return False
    lines = text.splitlines()
    # Skip ASCII art, checklists-copypasta and wall-of-emoji reviews.
    if letters / len(text) < 0.65 or len(lines) > 18 or re.search(r"(.)\1{7,}", text) or "☐" in text or "☑" in text:
        return False
    return True


def fetch_reviews(appid):
    url = (f"https://store.steampowered.com/appreviews/{appid}?json=1&language=english&filter=all"
           f"&review_type=all&purchase_type=all&num_per_page=100")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r).get("reviews", [])


def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    raw = json.loads((ROOT / "steam-data.json").read_text("utf8"))
    reviewed = list({r["appid"] for r in raw["reviews"]} - SKIP_APPS)
    random.shuffle(reviewed)

    pool = []
    for appid in reviewed:
        if len(pool) >= want:
            break
        try:
            reviews = fetch_reviews(appid)
        except Exception as e:
            print(f"  {appid}: {e}")
            time.sleep(10)
            continue
        candidates = []
        for rv in reviews:
            text = clean_bbcode(rv.get("review", ""))
            if rv["author"]["steamid"] != HIS_STEAMID and not rv.get("received_for_free") and looks_usable(text):
                candidates.append((rv, text))
        if candidates:
            rv, text = random.choice(candidates[:40])
            hours = rv["author"].get("playtime_at_review", 0) / 60
            pool.append({
                "appid": appid, "recommended": rv["voted_up"], "text": text,
                "hours": f"{hours:.1f} hrs at review time",
                "url": f"https://steamcommunity.com/profiles/{rv['author']['steamid']}/recommended/{appid}/",
            })
            print(f"  {appid}: picked 1 of {len(candidates)}")
        time.sleep(1.5)

    (ROOT / "strangers.json").write_text(json.dumps(pool, indent=1, ensure_ascii=False), "utf8")
    print(f"Wrote strangers.json: {len(pool)} reviews from other players")


if __name__ == "__main__":
    main()

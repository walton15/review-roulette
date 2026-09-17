"""SmartButGameCritic — collects a pool of reviews written by *other* Steam players.

    python strangers.py [count]

For random games he has reviewed, pulls a helpful English review from Steam's public
review API and saves the raw pool to strangers.json. build.py redacts them like his.
Re-running replaces the pool; delete entries from strangers.json to drop bad picks.
A GitHub Action (.github/workflows/refresh-strangers.yml) re-runs this daily.
"""
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

from build import COMMON, TITLE, redact, title_variants

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


# Everyday title words that don't give the game away on their own ("STAR WARS Zero Company" -> "company").
GENERIC = COMMON | set("""
    demo remake remastered prologue company evolved enhanced campaign legacy first light dark knight country honor
    human city rogue like will with your than where well walk great better black white wrong little lost king star
    space super iron metal fall fish golf path post ring skin slay suit beat meet meat nine gold cast chill wild
    train journey secret forest valley mountain mouse number judgment saga classic legends friends monsters
    nightmares shadows hearts echoes darkness escape descent machine killer father survivors vengeance business
    unfinished welcome being becoming among acts ages anger atom blood circle creek crime cruel detective drivers
    expedition fate forgive gate gravity hire hollow international invincible isolation lotus marine pines planet
    presents primal revival rivals shell singing sword tails trauma wisps winter wizard whiskers zero chop cabin
    bean deed foot grande painted palace pilgrims somber stairs stalking untold valiant vampire winds arena agent
    animal backseat climb crimson desert eldest hotline mixtape myth neon pirate split fiction tainted
""".split())


def gives_away(text, name, extra_terms):
    """Nobody checks the pool by hand now, so skip reviews that still hint at the game once its
    title is hidden: series names ("Silent Hill 2"), title words ("a Gothic game"), redactions.json terms."""
    text = redact(text, [(v, TITLE) for v in title_variants(name)])
    words = {w.lower() for w in re.findall(r"[A-Za-z0-9']{4,}", name)} - GENERIC
    acronym = lambda w: w.isupper() and " " not in w and len(w) <= 6  # "RE" shouldn't match "we're"
    return any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text, 0 if acronym(w) else re.I)
               for w in words | set(extra_terms))


def fetch_reviews(appid):
    url = (f"https://store.steampowered.com/appreviews/{appid}?json=1&language=english&filter=all"
           f"&review_type=all&purchase_type=all&num_per_page=100")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r).get("reviews", [])


def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    # docs/data.json is committed, so this also works in CI where steam-data.json doesn't exist.
    raw = json.loads((ROOT / "docs" / "data.json").read_text("utf8"))
    names = {g["appid"]: g["name"] for g in raw["games"]}
    extra = json.loads((ROOT / "redactions.json").read_text("utf8")) if (ROOT / "redactions.json").exists() else {}
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
            if rv["author"]["steamid"] != HIS_STEAMID and not rv.get("received_for_free") and looks_usable(text) \
                    and not gives_away(text, names.get(appid, ""), extra.get(str(appid), [])):
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

    if len(pool) < want // 2:  # Steam blocked or failed us; keep the old pool rather than shrink it
        sys.exit(f"Only found {len(pool)} of {want} reviews; leaving strangers.json unchanged")
    (ROOT / "strangers.json").write_text(json.dumps(pool, indent=1, ensure_ascii=False), "utf8")
    print(f"Wrote strangers.json: {len(pool)} reviews from other players")


if __name__ == "__main__":
    main()

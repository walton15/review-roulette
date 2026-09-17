"""Review Roulette — fetches his public Steam reviews into steam-data.json (no login needed).

    python collect_reviews.py

Keeps the "games" (library) list already in steam-data.json, since that part needs a
logged-in browser (see collect.js). Run build.py afterwards.
"""
import html
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
PROFILE = "https://steamcommunity.com/id/mrsmartbutautistic"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf8", "replace")


def html_to_text(fragment):
    fragment = re.sub(r'<div class="(early_access_review|received_compensation)[^"]*">.*?</div>', "", fragment, flags=re.S)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<li[^>]*>", "\n• ", fragment, flags=re.I)
    fragment = re.sub(r"</?(div|p|ul|ol|h\d|blockquote)[^>]*>", "\n", fragment, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    text = re.sub(r"[ \t]+\n", "\n", text.replace("\t", ""))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main():
    reviews = []
    for page in range(1, 500):
        final_url, body = get(f"{PROFILE}/recommended/?p={page}")
        if "/recommended" not in final_url:
            raise SystemExit("Steam redirected away from his reviews page. Are they still public?")
        boxes = body.split('class="review_box"')[1:]
        if not boxes:
            break
        for box in boxes:
            app = re.search(r'class="leftcol">\s*<a href="https://steamcommunity\.com/app/(\d+)', box)
            content = re.search(r'<div class="content\s*">(.*?)</div>\s*<div class="posted">', box, re.S)
            if not app or not content:
                continue
            title = re.search(r'<div class="title"><a href="([^"]+)">([^<]+)</a>', box)
            hours = re.search(r'<div class="hours">(.*?)</div>', box, re.S)
            posted = re.search(r'<div class="posted">(.*?)</div>', box, re.S)
            squash = lambda m: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip() if m else ""
            reviews.append({
                "appid": int(app.group(1)),
                "recommended": bool(title) and "not recommended" not in title.group(2).lower(),
                "hours": squash(hours),
                "posted": squash(posted),
                "url": title.group(1) if title else "",
                "text": html_to_text(content.group(1)),
            })
        print(f"Page {page}: {len(reviews)} reviews so far")
        if f'?p={page + 1}"' not in body:
            break
        time.sleep(1)

    path = ROOT / "steam-data.json"
    old = json.loads(path.read_text("utf8")) if path.exists() else {}
    old_ids = {r["appid"] for r in old.get("reviews", [])}
    new = [r for r in reviews if r["appid"] not in old_ids]
    out = {"profile": PROFILE, "collected": datetime.now(timezone.utc).isoformat(), "reviews": reviews, "games": old.get("games", [])}
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf8")
    print(f"Saved {len(reviews)} reviews ({len(new)} new) and kept {len(out['games'])} library games.")
    for r in new:
        print(f"  NEW  appid {r['appid']}: {r['text'][:70]!r}")


if __name__ == "__main__":
    main()

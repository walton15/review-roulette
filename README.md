# SmartButGameCritic

Read one of SmartButAutistic's Steam reviews with the game's name hidden, then guess the game.
You get 4 guesses per review, and the review is worth 4 points — one less for every guess you
miss. Roughly 1 review in 10 is a fake and another 1 in 10 was written by a different Steam
player; players have to call those out with the **Fake Review** and **Not Sam Review** buttons.
Each missed guess also unlocks a hint: his playtime and review date, then the game's Steam
tags, then four games to choose from.

Live site: https://walton15.github.io/smartbutgamecritic/

## How it fits together

| File | What it is |
| --- | --- |
| `docs/index.html` | The whole game (GitHub Pages serves the `docs/` folder). |
| `docs/data.json` | Built by `build.py`. The site loads this. Don't edit it by hand. |
| `steam-data.json` | Raw reviews and library (not committed, see `.gitignore`). |
| `collect_reviews.py` | Fetches his public reviews into `steam-data.json`. No login needed. |
| `collect.js` | Browser-console script that fetches reviews **and his game library**. Needs you logged into Steam. |
| `redactions.json` | Extra words to hide per game (character names, actors, series names). |
| `fakes.json` | Fake reviews written in his style. |
| `strangers.py` → `strangers.json` | Pool of reviews by other Steam players. |
| `build.py` | Hides game names and builds `docs/data.json` from everything above. |
| `cache/` | Cached Steam store lookups (developer/publisher names, app type, user tags, genres/categories, image URLs). Committed so the daily refresh can use it. |
| `.github/workflows/daily-refresh.yml` | Every day: imports new and edited reviews, picks a new pool of other-player reviews, rebuilds. |

Requires Python 3.10+ (no extra packages).

## Importing new reviews

**This happens on its own every day.** The *Daily refresh* GitHub Action (09:17 UTC) re-reads
his public reviews page — no Steam login needed — so new reviews, edited ones (text, hours,
thumbs up/down) and deleted ones all reach the site the next morning. It rebuilds, commits and
GitHub Pages redeploys. Two things are still yours to do:

- **Check new reviews for giveaways.** When a run imports a new review, its commit is called
  *Import new reviews* and the run's summary page (Actions tab → the run) lists them. Read those
  and follow step 3 below if one names the game.
- **Pull before you edit.** The Action commits to `main` daily, so run `git pull` first.

To import right away, run it from the **Actions** tab (*Daily refresh* → *Run workflow*), or do
it by hand with the steps below. Run these from the `smartbutgamecritic` folder.

### 1. Fetch his reviews

```
python collect_reviews.py
```

This overwrites the reviews in `steam-data.json` with everything currently on his profile
and keeps the library list you already have. At the end it lists any reviews that are **NEW**.

*(Alternative: to also refresh his library, use `collect.js`. See "Updating his game library" below.)*

### 2. Build

```
python build.py
```

The build hides each game's title as `[GAME TITLE]`, including short forms, "2" vs "II" and
acronyms. It hides developer and publisher names as `[DEVELOPER]` and links as `[LINK]`.
New reviews are printed as `NEW ... check for giveaways`.

**Demos are left out.** Reviews of demos never reach the site, and demos aren't offered as
answers or used as decoys — the build asks the Steam store what each app is and drops
anything of type `demo` (for a delisted app with no store page, a title like
"Something Demo" is enough). Nothing to do by hand; collecting still picks them up, the
build filters them and prints `skipped N demos`.

### 3. Check new reviews for giveaways

Read each NEW review that the build printed. The automatic step can't catch things like
character names ("Leon"), actors ("Andy Serkis"), series names ("Arkham"), or abbreviations
("RE", "CO: E33"). Add those to `redactions.json` under the game's app ID (the number
printed next to NEW):

```json
{
  "*": [],
  "3764200": ["Leon", "Grace", "RE"]
}
```

- Matching ignores capital letters, except short all-caps words like `RE`, which only match in capitals.
- Anything under `"*"` is hidden in every review.
- Hidden words show up in the game as `REDACTED`.

Then run `python build.py` again and repeat until the NEW reviews are clean.

### 4. Preview locally (optional)

```
python -m http.server 8000 --directory docs
```

Open http://localhost:8000. You can't open `index.html` directly from the file system,
because the page won't be able to load `data.json`.

### 5. Publish

```
git add -A
git commit -m "Import new reviews"
git push
```

GitHub Pages updates the live site within a minute or two. Hard-refresh (Ctrl+F5) if you
still see the old version.

## Updating his game library

The search box suggests games from his library. Steam only shows the library to logged-in
accounts, so this step happens in your browser:

1. In Firefox, log into Steam and open https://steamcommunity.com/id/mrsmartbutautistic
2. Press **F12**, open the **Console** tab, and paste the contents of `collect.js`. The first
   time, Firefox makes you type `allow pasting` and press Enter, then paste again.
3. Press Enter. It downloads `steam-data.json` containing both reviews and the library.
4. Move that file into this folder, replacing the old one, then continue from step 2 above
   (`python build.py`).

After this, `collect_reviews.py` keeps the library in place when it refreshes reviews.

## Refreshing the decoys

- **Reviews from other players:** the *Daily refresh* GitHub Action picks a new random pool
  of 45 every day at 09:17 UTC and commits it. To refresh right away, run it from the repo's
  **Actions** tab (*Daily refresh* → *Run workflow*), or locally run `python strangers.py 45`
  then `python build.py --strangers-only`. It filters out non-English reviews, slurs, ASCII
  art and junk, masks profanity with ♥ like Steam does, and skips reviews that still hint at
  the game once the title is hidden (series names, title words, `redactions.json` terms).
  If Steam returns too few reviews, the old pool is kept.
- **Fake reviews:** edit `fakes.json` (140 of them right now, drawn at random). Each entry is
  `{"recommended": true/false, "text": "..."}`. Write `[GAME TITLE]` where a game name would
  go, so fakes look like his real (redacted) reviews. Match the real ones on length and tone
  as well: he writes a lot of one-liners and the occasional 700-word pros-and-cons post, so a
  pile of same-sized fakes is a giveaway on its own. Run `python build.py`.

## Changing the rules

At the top of the `<script>` in `docs/index.html`:

- `PLAYER`: the name shown on the page.
- `LIVES`: guesses per review, and also the points a review is worth. A correct first guess
  scores the full `LIVES` points, each miss costs one, and running out scores nothing.
- `DECOY_CHANCE`: the chance *per review* that a round is a fake, and again that it's another
  player's review. At `0.10` a 10-round game averages 8 real reviews, 1 fake and 1 stranger,
  but any given round can be anything. "All" mode plays every real review and sprinkles the
  decoys in around them.

### Hints

One hint unlocks per guess you miss, in this order:

1. **Playtime and date** — his hours on record and the day he posted the review.
2. **Steam tags** — the top 8 "Popular user-defined tags" from its store page (genres and categories if it has no store page). Tags that share a word with the title are left out.
3. **Multiple choice** — four games from his library, one of which is the answer (unless the
   round is a decoy, in which case none of them are).

All three describe *his* history with the game, never the review on screen. That matters: a
fake has no playtime or store page at all, and another player's review is always recent, so
showing the review's own details would give every decoy away. A fake borrows a random review's
numbers and a stranger's round uses his review of that same game.

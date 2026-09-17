# Review Roulette

Read one of SmartButAutistic's Steam reviews with the game's name hidden, then guess the game.
You get 3 guesses per review. Each game also includes one AI-written fake and one review from
another Steam player. Players have to call those out with the **Fake Review** and
**Not Sam Review** buttons.

Live site: https://walton15.github.io/review-roulette/

## How it fits together

| File | What it is |
| --- | --- |
| `docs/index.html` | The whole game (GitHub Pages serves the `docs/` folder). |
| `docs/data.json` | Built by `build.py`. The site loads this. Don't edit it by hand. |
| `steam-data.json` | Raw reviews and library (not committed, see `.gitignore`). |
| `collect_reviews.py` | Fetches his public reviews into `steam-data.json`. No login needed. |
| `collect.js` | Browser-console script that fetches reviews **and his game library**. Needs you logged into Steam. |
| `redactions.json` | Extra words to hide per game (character names, actors, series names). |
| `fakes.json` | The AI-written fake reviews in his style. |
| `strangers.py` → `strangers.json` | Pool of reviews by other Steam players. |
| `build.py` | Hides game names and builds `docs/data.json` from everything above. |
| `cache/` | Cached Steam store lookups (developer and publisher names). Safe to delete. |

Requires Python 3.10+ (no extra packages).

## Importing new reviews

Run these from the `review-roulette` folder.

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

- **Reviews from other players:** `python strangers.py 45` picks a new random pool (45 is
  how many to collect). It filters out non-English reviews, slurs, ASCII art and junk, and
  masks profanity with ♥ like Steam does. Skim `strangers.json` afterwards and delete any
  entries you don't want. Then run `python build.py`. The same name hiding and
  `redactions.json` rules apply.
- **AI-written fakes:** edit `fakes.json`. Each entry is
  `{"recommended": true/false, "text": "..."}`. Write `[GAME TITLE]` where a game name would
  go, so fakes look like his real (redacted) reviews. Run `python build.py`.

## Changing the rules

At the top of the `<script>` in `docs/index.html`:

- `PLAYER`: the name shown on the page.
- `LIVES`: guesses per review.

Each game always contains 1 fake and 1 review from another player. "All" mode adds those 2
on top of every real review.

// SmartButGameCritic — data collector.
// Paste into the Firefox console (F12 → Console) while on any steamcommunity.com page,
// logged into an account that can see the profile below. Downloads steam-data.json.
(async () => {
  const PROFILE = 'https://steamcommunity.com/id/mrsmartbutautistic';
  if (location.hostname !== 'steamcommunity.com') {
    console.error(`Run this on a steamcommunity.com tab (you're on ${location.hostname}). Opening his profile — paste the script again there.`);
    location.href = PROFILE;
    return;
  }
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const parseHTML = t => new DOMParser().parseFromString(t, 'text/html');

  // Turn a review's HTML into plain text, keeping line breaks and list bullets.
  function reviewText(el) {
    el = el.cloneNode(true);
    el.querySelectorAll('.early_access_review, .received_compensation, .review_developer_response_container').forEach(n => n.remove());
    el.querySelectorAll('br').forEach(n => n.replaceWith('\n'));
    el.querySelectorAll('li').forEach(n => n.prepend('\n• '));
    el.querySelectorAll('div, p, ul, ol, h1, h2, h3, blockquote').forEach(n => { n.prepend('\n'); n.append('\n'); });
    return el.textContent.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  const reviews = [];
  for (let p = 1; p < 500; p++) {
    const res = await fetch(`${PROFILE}/recommended/?p=${p}`, { credentials: 'include' });
    if (!res.url.includes('/recommended')) {
      if (p === 1) console.warn('Steam redirected away from the reviews page — either you cannot see his reviews, or he has none.');
      break;
    }
    const doc = parseHTML(await res.text());
    const boxes = doc.querySelectorAll('.review_box');
    if (!boxes.length) break;
    for (const box of boxes) {
      const appLink = box.querySelector('.leftcol a[href*="/app/"]');
      const content = box.querySelector('.rightcol .content');
      if (!appLink || !content) continue;
      reviews.push({
        appid: Number(appLink.href.match(/\/app\/(\d+)/)[1]),
        recommended: !/not recommended/i.test(box.querySelector('.title')?.textContent || ''),
        hours: (box.querySelector('.hours')?.textContent || '').replace(/\s+/g, ' ').trim(),
        posted: (box.querySelector('.posted')?.textContent || '').replace(/\s+/g, ' ').trim(),
        url: box.querySelector('.title a')?.href || '',
        text: reviewText(content),
      });
    }
    console.log(`Reviews page ${p}: ${reviews.length} reviews so far`);
    if (!doc.querySelector(`a[href$="?p=${p + 1}"]`)) break;
    await sleep(800);
  }

  let games = [];
  try {
    const xml = new DOMParser().parseFromString(
      await (await fetch(`${PROFILE}/games/?tab=all&xml=1`, { credentials: 'include' })).text(), 'text/xml');
    games = [...xml.querySelectorAll('games > game')].map(g => ({
      appid: Number(g.querySelector('appID')?.textContent),
      name: g.querySelector('name')?.textContent.trim(),
    })).filter(g => g.appid && g.name);
  } catch (e) { console.warn('XML game list failed, trying the games page', e); }
  if (!games.length) {
    const doc = parseHTML(await (await fetch(`${PROFILE}/games/?tab=all`, { credentials: 'include' })).text());
    const attr = doc.querySelector('[data-profile-gameslist]')?.getAttribute('data-profile-gameslist');
    if (attr) games = (JSON.parse(attr).rgGames || []).map(g => ({ appid: g.appid, name: g.name }));
  }
  console.log(`Games in library: ${games.length}`);

  if (!reviews.length) { console.error('No reviews collected — nothing downloaded.'); return; }
  const blob = new Blob([JSON.stringify({ profile: PROFILE, collected: new Date().toISOString(), reviews, games }, null, 2)], { type: 'application/json' });
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'steam-data.json' });
  document.body.append(a); a.click(); a.remove();
  console.log(`%cDone: ${reviews.length} reviews, ${games.length} games → steam-data.json`, 'color:#6c6;font-weight:bold');
})();

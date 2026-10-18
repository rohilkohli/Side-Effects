const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const a = process.argv.slice(2); const [live, repo, video] = [0, 1, 2].map(i => a[i] || 'to be added');
(async () => {
  let html = fs.readFileSync(__dirname + '/deck.html', 'utf8')
    .replace('__LIVE__', live).replace('__REPO__', repo).replace('__VIDEO__', video);
  fs.writeFileSync(__dirname + '/deck.out.html', html);
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + __dirname + '/deck.out.html');
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(800);
  await p.pdf({ path: __dirname + '/SIDE-EFFECTS-pitch-deck.pdf', width: '1920px', height: '1080px', printBackground: true });
  const n = await p.$$eval('section.s', s => s.length);
  for (let i = 0; i < n; i++) {
    await p.evaluate(i => window.scrollTo(0, i * 1080), i);
    const el = (await p.$$('section.s'))[i];
    await el.screenshot({ path: __dirname + `/slide-${i + 1}.png` });
  }
  await b.close();
})();

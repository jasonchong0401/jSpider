const { chromium } = require('playwright-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');

chromium.use(StealthPlugin());

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--window-size=1920,1080',
      '--disable-features=IsolateOrigins,site-per-process',
      '--disable-web-security',
      '--disable-features=VizDisplayCompositor',
    ]
  });

  console.log('[1] Browser launched');

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1920, height: 1080 },
    locale: 'en-US',
    timezoneId: 'America/New_York',
    deviceScaleFactor: 1,
    hasTouch: false,
    isMobile: false,
    bypassCSP: true,
    ignoreHTTPSErrors: true,
  });

  const page = await context.newPage();

  // Comprehensive evasion
  await page.addInitScript(() => {
    // Override navigator
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // Override chrome object
    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };

    // Override permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) => (
      params.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(params)
    );

    // Remove headless indicators
    delete navigator.__proto__.webdriver;
  });

  // Block specific resource types to speed up
  await page.route('**/*', (route) => {
    const type = route.request().resourceType();
    if (['image', 'media', 'font', 'stylesheet'].includes(type)) {
      route.abort();
    } else {
      route.continue();
    }
  });

  console.log('[2] Navigating...');

  try {
    await page.goto('https://www.investing.com/commodities/', {
      timeout: 120000,
      waitUntil: 'domcontentloaded'
    });

    console.log('[3] Page loaded');
    console.log('    Title:', await page.title());

    // If Cloudflare challenge page, try to wait it out
    const title = await page.title();
    if (title.includes('Just a moment') || title.includes('Cloudflare')) {
      console.log('    Cloudflare challenge detected. Waiting...');
      // Wait for the challenge to auto-resolve
      for (let i = 0; i < 30; i++) {
        await page.waitForTimeout(3000);
        const currentTitle = await page.title();
        if (!currentTitle.includes('Just a moment') && !currentTitle.includes('Cloudflare')) {
          console.log('    Challenge resolved after ' + ((i+1)*3) + 's');
          break;
        }
        if (i % 5 === 0) console.log('    Still waiting... (' + ((i+1)*3) + 's)');
      }
    }

    console.log('    Final title:', await page.title());

    // Wait for data to load
    await page.waitForTimeout(5000);

    // Scroll to trigger lazy loading
    await page.evaluate(() => window.scrollTo(0, 800));
    await page.waitForTimeout(3000);

    // Extract data
    const data = await page.evaluate(() => {
      const results = [];
      const seen = new Set();

      // Look for any table with enough rows
      const allTrs = document.querySelectorAll('tr');
      const rows = [];

      allTrs.forEach(tr => {
        const cells = tr.querySelectorAll('td');
        if (cells.length >= 3) {
          const texts = [];
          cells.forEach(c => { texts.push((c.innerText || c.textContent || '').trim()); });
          rows.push(texts);
        }
      });

      rows.forEach(texts => {
        if (texts.length < 3) return;
        const name = texts[0];
        if (!name || name.length > 100 || name.includes('Name') || name.includes('Symbol')) return;
        if (name.includes('Sponsored') || name.includes('Advertisement') || name === '') return;

        const key = name.substring(0, 30);
        if (seen.has(key)) return;
        seen.add(key);

        results.push({
          name: name,
          last: texts[1] || '',
          high: texts[2] || '',
          low: texts[3] || '',
          change: texts[4] || '',
          changePct: texts[5] || '',
          time: texts[6] || ''
        });
      });

      return results;
    });

    console.log('[4] Extracted ' + data.length + ' commodities');

    if (data.length > 0) {
      data.forEach((item, i) => {
        console.log('  [' + (i+1) + '] ' + item.name + ' | Last: ' + item.last + ' | Chg: ' + item.change);
      });
    } else {
      // Dump page content for debugging
      const bodyPreview = await page.evaluate(() => {
        return (document.body ? document.body.innerText : '').substring(0, 1000);
      });
      console.log('  Page body preview:');
      console.log(bodyPreview);
    }

    // Save
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    fs.writeFileSync('commodities-' + ts + '.json', JSON.stringify(data, null, 2));
    fs.writeFileSync('page_full.html', await page.content());
    console.log('[5] Saved to commodities-' + ts + '.json');

  } catch (err) {
    console.error('Error:', err.message);
  }

  await browser.close();
})();

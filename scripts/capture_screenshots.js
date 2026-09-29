const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function capture() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1200, height: 1050 },
    deviceScaleFactor: 2
  });
  const page = await context.newPage();

  const fileUrl = 'file://' + path.resolve(__dirname, '../backend/app/static/index.html');
  await page.goto(fileUrl, { waitUntil: 'networkidle' });

  const outDir = path.resolve(__dirname, '../docs/screenshots');
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const phoneElement = await page.$('.phone-container');

  // 1. Screen 1: Login
  await page.evaluate(() => switchScreen('login'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_1_login.png') });
  console.log('Captured screen_1_login.png');

  // 2. Screen 2: Home
  await page.evaluate(() => switchScreen('home'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_2_home.png') });
  console.log('Captured screen_2_home.png');

  // 3. Screen 3: Chat
  await page.evaluate(() => switchScreen('chat'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_3_chat.png') });
  console.log('Captured screen_3_chat.png');

  // 4. Screen 4: Progress
  await page.evaluate(() => switchScreen('progress'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_4_progress.png') });
  console.log('Captured screen_4_progress.png');

  // 5. Screen 5: Editor
  await page.evaluate(() => switchScreen('editor'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_5_editor.png') });
  console.log('Captured screen_5_editor.png');

  // 6. Screen 6: Export
  await page.evaluate(() => switchScreen('export'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_6_export.png') });
  console.log('Captured screen_6_export.png');

  // 7. Screen 7: History
  await page.evaluate(() => switchScreen('history'));
  await page.waitForTimeout(300);
  await phoneElement.screenshot({ path: path.join(outDir, 'screen_7_history.png') });
  console.log('Captured screen_7_history.png');

  // 8. Showcase Overview (Full studio layout)
  await page.evaluate(() => switchScreen('editor'));
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'showcase_overview.png'), fullPage: true });
  console.log('Captured showcase_overview.png');

  await browser.close();
  console.log('All screenshots captured successfully in docs/screenshots/');
}

capture().catch(err => {
  console.error(err);
  process.exit(1);
});

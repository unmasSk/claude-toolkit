#!/usr/bin/env node
/**
 * screenshot-script.mjs
 *
 * Playwright-based marketing screenshot generator.
 * Captures HiDPI (2x retina) screenshots at 1440x900 viewport.
 *
 * Usage: node screenshot-script.mjs
 *
 * Configure BASE_URL, AUTH, and SCREENSHOTS below before running.
 */

import { chromium } from 'playwright';

const BASE_URL = '[APP_URL]';
const SCREENSHOTS_DIR = './screenshots';

// Authentication config (set needed: true if login is required)
const AUTH = {
  needed: false,
  loginUrl: '[LOGIN_URL]',
  email: '[EMAIL]',
  password: '[PASSWORD]',
};

// Screenshots to capture — edit this list to match your app
const SCREENSHOTS = [
  { name: '01-feature-name', url: '/path', waitFor: '[optional-selector]' },
  { name: '02-another-feature', url: '/another-path' },
];

async function main() {
  const browser = await chromium.launch();

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, // produces 2880x1800 images (true retina)
  });

  const page = await context.newPage();

  // Authentication
  if (AUTH.needed) {
    console.log('Logging in...');
    await page.goto(AUTH.loginUrl);

    const emailField = page.locator([
      'input[type="email"]',
      'input[name="email"]',
      'input[id="email"]',
      'input[placeholder*="email" i]',
      'input[name="username"]',
      'input[id="username"]',
      'input[type="text"]',
    ].join(', ')).first();
    await emailField.fill(AUTH.email);

    const passwordField = page.locator([
      'input[type="password"]',
      'input[name="password"]',
      'input[id="password"]',
    ].join(', ')).first();
    await passwordField.fill(AUTH.password);

    const submitButton = page.locator([
      'button[type="submit"]',
      'input[type="submit"]',
      'button:has-text("Sign in")',
      'button:has-text("Log in")',
      'button:has-text("Login")',
      'button:has-text("Submit")',
    ].join(', ')).first();
    await submitButton.click();

    await page.waitForLoadState('networkidle');
    console.log('Login complete');
  }

  // Capture screenshots
  for (const shot of SCREENSHOTS) {
    console.log(`Capturing: ${shot.name}`);
    await page.goto(`${BASE_URL}${shot.url}`);
    await page.waitForLoadState('networkidle');

    if (shot.waitFor) {
      await page.waitForSelector(shot.waitFor, { timeout: 10000 })
        .catch(() => { console.warn(`Warning: selector "${shot.waitFor}" not found within 10s, proceeding anyway`); });
    }

    if (shot.actions) {
      for (const action of shot.actions) {
        if (action.click) await page.click(action.click);
        if (action.fill) await page.fill(action.fill.selector, action.fill.value);
        if (action.wait) await page.waitForTimeout(action.wait);
      }
    }

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/${shot.name}.png`,
      fullPage: shot.fullPage || false,
    });
    console.log(`  Saved: ${shot.name}.png`);
  }

  await browser.close();
  console.log('Done!');
}

main().catch(console.error);

import { chromium as native } from './node_modules/playwright/index.mjs'
export const chromium = {
  launch: async options => {
    const browser = await native.launch(options)
    const newPage = browser.newPage.bind(browser)
    browser.newPage = async options => {
      const page = await newPage(options)
      await page.route('https://fonts.googleapis.com/**', route => route.abort())
      await page.route('https://fonts.gstatic.com/**', route => route.abort())
      return page
    }
    return browser
  },
}

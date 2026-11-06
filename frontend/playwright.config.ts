import { defineConfig } from '@playwright/test'
export default defineConfig({ testDir: './e2e', workers: 1, use: { baseURL: 'http://127.0.0.1:8000', headless: process.env.INSTABOX_HEADLESS === '1', launchOptions: { executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] }, viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure' } })

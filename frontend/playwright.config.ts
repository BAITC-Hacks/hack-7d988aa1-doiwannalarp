import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests/browser',use:{baseURL:'http://127.0.0.1:8080',headless:true,launchOptions:{executablePath:process.env.FINGRAPH_CHROMIUM_PATH,args:['--enable-unsafe-swiftshader']}}});

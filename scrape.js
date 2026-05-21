/**
 * xhs-blogger-analyzer — 数据采集脚本
 *
 * 用法:
 *   node scrape.js --url <博主主页URL> --cookies cookies.json --output ./data
 *
 * cookies.json 格式: 从浏览器导出的 Cookie 数组 (name, value, domain, path)
 *   打开小红书已登录 → F12 → Application → Cookies → 全部导出
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const args = {};
process.argv.slice(2).forEach((v, i, a) => {
    if (v.startsWith('--')) args[v.slice(2)] = a[i + 1];
});

const PROFILE_URL = args.url || 'https://www.xiaohongshu.com/user/profile/62c98736000000001501e075';
const COOKIE_FILE = args.cookies || 'cookies.json';
const OUTPUT_DIR = args.output || './data';

async function main() {
    // Load cookies
    let cookies = [];
    try {
        cookies = JSON.parse(fs.readFileSync(COOKIE_FILE, 'utf-8'));
        if (!Array.isArray(cookies)) cookies = [];
    } catch { /* no cookies file, proceed without auth */ }

    const browser = await chromium.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-blink-features=AutomationControlled']
    });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        locale: 'zh-CN',
        viewport: { width: 1440, height: 900 },
    });

    // Inject cookies if provided
    if (cookies.length > 0) {
        await context.addCookies(cookies.map(c => ({
            name: c.name, value: c.value, domain: c.domain || '.xiaohongshu.com',
            path: c.path || '/', httpOnly: c.httpOnly ?? true, secure: c.secure ?? true,
        })));
    }

    const page = await context.newPage();

    // Intercept user_posted API responses
    const allNotes = [];
    page.on('response', async (resp) => {
        if (resp.url().includes('/api/sns/web/v1/user_posted')) {
            try {
                const body = await resp.json();
                const items = body?.data?.items || body?.data?.notes || [];
                items.forEach(item => {
                    const n = item.noteCard || item;
                    if (n.note_id) {
                        const note = {
                            note_id: n.note_id,
                            xsec_token: n.xsec_token || '',
                            title: n.display_title || n.title || '',
                            type: n.type || 'normal',
                            liked_count: n.interact_info?.liked_count ?? n.liked_count ?? 0,
                            sticky: n.sticky ?? false,
                            time: n.time || '',
                        };
                        // Deduplicate
                        if (!allNotes.find(x => x.note_id === note.note_id)) {
                            allNotes.push(note);
                        }
                    }
                });
                console.log(`  [API] Captured ${items.length} items (total: ${allNotes.length})`);
            } catch { /* ignore parse errors */ }
        }
    });

    console.log(`Navigating to: ${PROFILE_URL}`);
    await page.goto(PROFILE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    // Scroll to trigger pagination
    let prevCount = 0;
    for (let i = 0; i < 30; i++) {
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(1500);
        if (allNotes.length > 0 && allNotes.length === prevCount) break;
        prevCount = allNotes.length;
        console.log(`  Scroll ${i + 1}: ${allNotes.length} notes collected`);
    }

    console.log(`\nTotal notes collected: ${allNotes.length}`);

    // Extract profile info
    let nickname = '';
    try {
        nickname = await page.evaluate(() => document.title.replace(' - 小红书', '').trim());
    } catch {}
    if (!nickname) nickname = 'unknown';

    // Save notes
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    const outputPath = path.join(OUTPUT_DIR, 'all_notes.json');
    fs.writeFileSync(outputPath, JSON.stringify(allNotes, null, 2));

    // Save profile info
    const userProfile = { nickname, user_id: PROFILE_URL.split('/').pop().split('?')[0], note_count: allNotes.length };
    const profilePath = path.join(OUTPUT_DIR, 'profile.json');
    fs.writeFileSync(profilePath, JSON.stringify(userProfile, null, 2));

    console.log(`Blogger: ${nickname}`);
    console.log(`Notes saved to: ${outputPath}`);
    console.log(`Profile saved to: ${profilePath}`);

    await browser.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });

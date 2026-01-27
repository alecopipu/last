const { chromium } = require('playwright');

async function main() {
    console.log('Connecting to Chrome...');
    const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
    const context = browser.contexts()[0] || await browser.newContext();
    const page = await context.newPage();

    console.log('Navigating to arklist...');
    await page.goto('https://altema.jp/lastcloudia/arklist');

    const result = await page.evaluate(() => {
        // Method 1: Existing method (dl.acMenu)
        const dts = document.querySelectorAll('dl.acMenu dt');
        let countMethod1 = 0;
        dts.forEach(dt => {
            const dd = dt.nextElementSibling;
            if (dd && dd.tagName === 'DD') {
                const links = dd.querySelectorAll('a[href*="/ark/"]');
                countMethod1 += links.length;
            }
        });

        // Method 2: All links matching /ark/ number
        const allLinks = Array.from(document.querySelectorAll('a[href*="/ark/"]'));
        const uniqueIds = new Set();

        allLinks.forEach(link => {
            const match = link.href.match(/\/ark\/(\d+)/);
            if (match) {
                uniqueIds.add(parseInt(match[1]));
            }
        });

        return {
            method1Count: countMethod1,
            totalUniqueIds: uniqueIds.size,
            ids: Array.from(uniqueIds).sort((a, b) => a - b)
        };
    });

    console.log(`Method 1 (dl.acMenu) count: ${result.method1Count}`);
    console.log(`Total Unique IDs found on page: ${result.totalUniqueIds}`);

    // Check which ones are missing from the 273 found previously
    const fs = require('fs');
    if (fs.existsSync('arks-data.json')) {
        const data = JSON.parse(fs.readFileSync('arks-data.json', 'utf-8'));
        const existingIds = new Set(data.arks.map(a => a.id));
        console.log(`Existing Arks in JSON: ${existingIds.size}`);

        const missing = result.ids.filter(id => !existingIds.has(id));
        console.log(`IDs found on page but missing in JSON: ${missing.length}`);
        if (missing.length > 0) {
            console.log('Missing IDs:', missing);
        }
    }

    await page.close();
    await browser.close();
}

main().catch(console.error);

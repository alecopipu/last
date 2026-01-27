const { chromium } = require('playwright');

async function main() {
    const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
    const context = browser.contexts()[0];
    const page = await context.newPage();

    // Test with Ark ID 1 (Rarity R)
    const arkId = 1;
    console.log(`Navigating to Ark ${arkId}...`);
    await page.goto(`https://altema.jp/lastcloudia/ark/${arkId}`);

    const debugInfo = await page.evaluate(() => {
        const tables = document.querySelectorAll('table');
        const results = [];

        tables.forEach((table, index) => {
            const rowText = table.textContent;
            // Check if this looks like Table 1
            if (rowText.includes('レア度') || rowText.includes('アーク特性') || rowText.includes('アークエーテル')) {
                const rows = Array.from(table.querySelectorAll('tr'));
                const headers = [];
                rows.forEach(row => {
                    const th = row.querySelector('th');
                    if (th) headers.push(th.textContent.trim());
                });
                results.push({ tableIndex: index, headers });
            }
        });
        return results;
    });

    console.log('Table Headers found:', JSON.stringify(debugInfo, null, 2));

    await page.close();
    await browser.close();
}

main().catch(console.error);

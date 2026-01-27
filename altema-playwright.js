/**
 * Altema Last Cloudia API Client - Playwright 版本
 *
 * 使用 Playwright 連接到已開啟的 Chrome 瀏覽器,
 * 攔截網路請求並呼叫 Altema 的內部 API.
 *
 * 使用方式:
 * 1. 啟動 Chrome: chrome.exe --remote-debugging-port=9222
 * 2. 運行此腳本: node altema-playwright.js
 */

const { chromium } = require('playwright');

class AltemaPlaywrightClient {
    constructor() {
        this.browser = null;
        this.context = null;
        this.page = null;
        this.interceptedRequests = [];
        this.baseURL = 'https://altema.jp/lastcloudia';
    }

    /**
     * 連接到 Chrome CDP
     */
    async connect(wsEndpoint = null) {
        try {
            if (wsEndpoint) {
                this.browser = await chromium.connectOverCDP(wsEndpoint);
            } else {
                this.browser = await chromium.connectOverCDP('http://localhost:9222');
            }

            const contexts = this.browser.contexts();
            this.context = contexts[0] || await this.browser.newContext();

            const pages = this.context.pages();
            this.page = pages.find(p => p.url().includes('altema.jp/lastcloudia')) || pages[0];

            if (!this.page) {
                this.page = await this.context.newPage();
                await this.page.goto(this.baseURL);
            }

            // 設置請求攔截
            await this._setupRequestInterception();

            console.log('[+] 已連接到 Chrome');
            console.log(`[+] 當前頁面: ${this.page.url()}`);
            return true;
        } catch (error) {
            console.error('[-] 連接失敗:', error.message);
            return false;
        }
    }

    /**
     * 設置請求攔截
     */
    async _setupRequestInterception() {
        this.page.on('request', (request) => {
            const url = request.url();
            if (url.includes('/api/') && url.includes('altema')) {
                this.interceptedRequests.push({
                    url,
                    method: request.method(),
                    headers: request.headers(),
                    postData: request.postData(),
                    timestamp: new Date().toISOString()
                });
            }
        });

        this.page.on('response', async (response) => {
            const url = response.url();
            if (url.includes('/api/') && url.includes('altema')) {
                console.log(`[API] ${response.status()} ${url}`);
            }
        });
    }

    /**
     * 導航到頁面
     */
    async navigate(path) {
        const url = path.startsWith('http') ? path : `${this.baseURL}${path}`;
        await this.page.goto(url);
        await this.page.waitForLoadState('networkidle');
        return this.page.url();
    }

    // ===================
    // API 方法
    // ===================

    /**
     * 獲取評論數據
     */
    async getComments(category = 'charalist', postId = 68) {
        return await this.page.evaluate(async ({ category, postId }) => {
            const response = await fetch('https://altema.jp/api/lastcloudia/comment_api', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `ins_cate=${category}&post_id=${postId}`
            });
            return await response.json();
        }, { category, postId });
    }

    /**
     * 獲取角色列表
     */
    async getCharacterList() {
        await this.navigate('/charalist');

        return await this.page.evaluate(() => {
            const characters = [];
            const tables = document.querySelectorAll('table.result-table, table.tableLine');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const nameCell = cells[0];
                        const link = nameCell.querySelector('a');
                        const img = nameCell.querySelector('img');

                        const idMatch = link?.href?.match(/\/chara\/(\d+)/);

                        characters.push({
                            id: idMatch ? parseInt(idMatch[1]) : null,
                            name: nameCell.textContent.trim(),
                            url: link?.href || null,
                            image: img?.src || null,
                            rating: cells[1]?.textContent?.trim() || null,
                            role: cells[2]?.textContent?.trim() || null
                        });
                    }
                });
            });

            return characters;
        });
    }

    /**
     * 獲取角色詳細資訊
     */
    async getCharacterDetail(charaId) {
        await this.navigate(`/chara/${charaId}`);

        return await this.page.evaluate(() => {
            const data = {
                name: document.querySelector('h1')?.textContent?.trim(),
                image: document.querySelector('.chara-img img, .unit-img img')?.src,
                stats: {},
                skills: [],
                recommendedArks: []
            };

            // 解析統計數據
            document.querySelectorAll('table').forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach(row => {
                    const th = row.querySelector('th');
                    const td = row.querySelector('td');
                    if (th && td) {
                        data.stats[th.textContent.trim()] = td.textContent.trim();
                    }
                });
            });

            // 解析技能
            document.querySelectorAll('.skill-item, [class*="skill"]').forEach(skill => {
                const name = skill.querySelector('.skill-name, h4, h5')?.textContent?.trim();
                const desc = skill.querySelector('.skill-desc, p')?.textContent?.trim();
                if (name) {
                    data.skills.push({ name, description: desc });
                }
            });

            return data;
        });
    }

    /**
     * 獲取方舟列表
     */
    async getArkList() {
        await this.navigate('/arklist');

        return await this.page.evaluate(() => {
            const arks = [];
            const tables = document.querySelectorAll('table.result-table, table.tableLine');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const nameCell = cells[0];
                        const link = nameCell.querySelector('a');
                        const idMatch = link?.href?.match(/\/ark\/(\d+)/);

                        arks.push({
                            id: idMatch ? parseInt(idMatch[1]) : null,
                            name: nameCell.textContent.trim(),
                            url: link?.href || null,
                            rarity: cells[1]?.textContent?.trim() || null
                        });
                    }
                });
            });

            return arks;
        });
    }

    /**
     * 獲取最強角色排行
     */
    async getStrongestCharacters() {
        await this.navigate('/saikyokyara');

        return await this.page.evaluate(() => {
            const rankings = [];
            const tables = document.querySelectorAll('table');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const link = cells[0]?.querySelector('a');
                        const idMatch = link?.href?.match(/\/chara\/(\d+)/);

                        rankings.push({
                            rank: rankings.length + 1,
                            id: idMatch ? parseInt(idMatch[1]) : null,
                            name: cells[0]?.textContent?.trim(),
                            url: link?.href,
                            tier: cells[1]?.textContent?.trim()
                        });
                    }
                });
            });

            return rankings;
        });
    }

    /**
     * 獲取最強方舟排行
     */
    async getStrongestArks() {
        await this.navigate('/saikyoark');

        return await this.page.evaluate(() => {
            const rankings = [];
            const tables = document.querySelectorAll('table');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const link = cells[0]?.querySelector('a');
                        const idMatch = link?.href?.match(/\/ark\/(\d+)/);

                        rankings.push({
                            rank: rankings.length + 1,
                            id: idMatch ? parseInt(idMatch[1]) : null,
                            name: cells[0]?.textContent?.trim(),
                            url: link?.href,
                            tier: cells[1]?.textContent?.trim()
                        });
                    }
                });
            });

            return rankings;
        });
    }

    /**
     * 獲取技能列表
     */
    async getSkillList(type = 1) {
        await this.navigate(`/Skill/${type}`);

        return await this.page.evaluate(() => {
            const skills = [];
            const tables = document.querySelectorAll('table');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        skills.push({
                            name: cells[0]?.textContent?.trim(),
                            effect: cells[1]?.textContent?.trim(),
                            cost: cells[2]?.textContent?.trim() || null
                        });
                    }
                });
            });

            return skills;
        });
    }

    /**
     * 獲取裝備列表
     */
    async getEquipmentList(type = 1) {
        await this.navigate(`/soubilist/${type}`);

        return await this.page.evaluate(() => {
            const equipment = [];
            const tables = document.querySelectorAll('table.result-table, table.tableLine');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const link = cells[0]?.querySelector('a');
                        equipment.push({
                            name: cells[0]?.textContent?.trim(),
                            url: link?.href,
                            stats: cells[1]?.textContent?.trim()
                        });
                    }
                });
            });

            return equipment;
        });
    }

    /**
     * 獲取素材列表
     */
    async getMaterialList() {
        await this.navigate('/sozailist');

        return await this.page.evaluate(() => {
            const materials = [];
            const tables = document.querySelectorAll('table');

            tables.forEach(table => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, index) => {
                    if (index === 0) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        materials.push({
                            name: cells[0]?.textContent?.trim(),
                            description: cells[1]?.textContent?.trim()
                        });
                    }
                });
            });

            return materials;
        });
    }

    /**
     * 獲取攔截到的請求
     */
    getInterceptedRequests() {
        return this.interceptedRequests;
    }

    /**
     * 截圖
     */
    async screenshot(filename = 'screenshot.png') {
        await this.page.screenshot({ path: filename, fullPage: true });
        console.log(`[+] 截圖已保存: ${filename}`);
    }

    /**
     * 關閉連接
     */
    async close() {
        if (this.browser) {
            await this.browser.close();
            console.log('[+] 已關閉連接');
        }
    }
}

// ===================
// CLI 工具
// ===================

async function showMenu() {
    console.log('');
    console.log('='.repeat(60));
    console.log(' Altema Last Cloudia API Client (Playwright)');
    console.log('='.repeat(60));
    console.log('');
    console.log('可用的 API 方法:');
    console.log('');
    console.log(' 1. getCharacterList()       - 獲取所有角色列表');
    console.log(' 2. getCharacterDetail(id)   - 獲取角色詳細資訊');
    console.log(' 3. getArkList()             - 獲取所有方舟列表');
    console.log(' 4. getStrongestCharacters() - 獲取最強角色排行');
    console.log(' 5. getStrongestArks()       - 獲取最強方舟排行');
    console.log(' 6. getSkillList(type)       - 獲取技能列表');
    console.log('    type: 1=技能, 2=魔法');
    console.log(' 7. getEquipmentList(type)   - 獲取裝備列表');
    console.log('    type: 1=武器, 2=防具, 3=飾品');
    console.log(' 8. getMaterialList()        - 獲取素材列表');
    console.log(' 9. getComments(category)    - 獲取評論數據');
    console.log('10. getInterceptedRequests() - 獲取攔截的 API 請求');
    console.log('');
    console.log('='.repeat(60));
}

async function demo(client) {
    console.log('');
    console.log('[*] 執行演示...');
    console.log('');

    // 測試評論 API
    console.log('[1] 測試評論 API...');
    const comments = await client.getComments();
    console.log(`    - NGWord 數量: ${comments.NGWord?.length || 0}`);
    console.log(`    - 平台: ${comments.platform || 'N/A'}`);

    // 獲取最強角色
    console.log('');
    console.log('[2] 獲取最強角色排行...');
    const strongestChars = await client.getStrongestCharacters();
    console.log(`    - 找到 ${strongestChars.length} 個角色`);
    if (strongestChars.length > 0) {
        console.log('    - Top 5:');
        strongestChars.slice(0, 5).forEach((char, i) => {
            console.log(`      ${i + 1}. ${char.name} (${char.tier || 'N/A'})`);
        });
    }

    // 獲取最強方舟
    console.log('');
    console.log('[3] 獲取最強方舟排行...');
    const strongestArks = await client.getStrongestArks();
    console.log(`    - 找到 ${strongestArks.length} 個方舟`);
    if (strongestArks.length > 0) {
        console.log('    - Top 5:');
        strongestArks.slice(0, 5).forEach((ark, i) => {
            console.log(`      ${i + 1}. ${ark.name} (${ark.tier || 'N/A'})`);
        });
    }

    console.log('');
    console.log('[+] 演示完成!');
}

async function main() {
    const client = new AltemaPlaywrightClient();

    showMenu();

    const connected = await client.connect();

    if (!connected) {
        console.log('');
        console.log('請先啟動 Chrome 並開啟調試端口:');
        console.log('  chrome.exe --remote-debugging-port=9222');
        console.log('');
        return;
    }

    // 執行演示
    await demo(client);

    // 導出 client
    global.altemaClient = client;
    console.log('');
    console.log('[+] API Client 已載入至 global.altemaClient');

    // 保持連接
    process.on('SIGINT', async () => {
        await client.close();
        process.exit(0);
    });
}

if (require.main === module) {
    main().catch(console.error);
}

module.exports = { AltemaPlaywrightClient };

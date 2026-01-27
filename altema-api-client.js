/**
 * Altema Last Cloudia API Client
 *
 * 透過 CDP (Chrome DevTools Protocol) 連接到 Chrome 瀏覽器,
 * 攔截網路請求並呼叫 Altema 的內部 API.
 *
 * 使用方式:
 * 1. 啟動 Chrome: chrome.exe --remote-debugging-port=9222
 * 2. 開啟 https://altema.jp/lastcloudia/ 頁面
 * 3. 運行此腳本: node altema-api-client.js
 */

const CDP = require('chrome-remote-interface');

class AltemaAPIClient {
    constructor() {
        this.client = null;
        this.cookies = [];
        this.baseURL = 'https://altema.jp';
        this.backendURL = 'https://backend.altema.jp';
        this.interceptedRequests = [];
    }

    /**
     * 連接到 Chrome DevTools Protocol
     */
    async connect(port = 9222) {
        try {
            this.client = await CDP({ port });
            const { Network, Page, Runtime } = this.client;

            // 啟用必要的域
            await Network.enable();
            await Page.enable();
            await Runtime.enable();

            // 攔截網路請求
            await this._setupRequestInterception();

            console.log('[+] 已連接到 Chrome CDP');
            return true;
        } catch (error) {
            console.error('[-] 連接失敗:', error.message);
            console.log('請確保 Chrome 以 --remote-debugging-port=9222 啟動');
            return false;
        }
    }

    /**
     * 設置請求攔截
     */
    async _setupRequestInterception() {
        const { Network } = this.client;

        Network.requestWillBeSent((params) => {
            const url = params.request.url;
            if (url.includes('altema.jp/api/') || url.includes('backend.altema.jp/api/')) {
                this.interceptedRequests.push({
                    url: url,
                    method: params.request.method,
                    headers: params.request.headers,
                    postData: params.request.postData,
                    timestamp: new Date().toISOString()
                });
            }
        });

        Network.responseReceived((params) => {
            const url = params.response.url;
            if (url.includes('altema.jp/api/') || url.includes('backend.altema.jp/api/')) {
                console.log(`[API] ${params.response.status} ${url}`);
            }
        });
    }

    /**
     * 獲取當前頁面的 cookies
     */
    async getCookies() {
        const { Network } = this.client;
        const result = await Network.getCookies();
        this.cookies = result.cookies;
        return this.cookies;
    }

    /**
     * 在頁面上下文中執行 fetch 請求
     */
    async executeInPage(code) {
        const { Runtime } = this.client;
        const result = await Runtime.evaluate({
            expression: code,
            awaitPromise: true,
            returnByValue: true
        });
        return result.result.value;
    }

    // ===================
    // API 方法
    // ===================

    /**
     * 獲取評論數據
     * @param {string} category - 分類 (如 'charalist', 'arklist')
     * @param {number} postId - 文章 ID
     */
    async getComments(category = 'charalist', postId = 68) {
        const code = `
            (async () => {
                const response = await fetch('https://altema.jp/api/lastcloudia/comment_api', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'ins_cate=${category}&post_id=${postId}'
                });
                return await response.json();
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 獲取角色列表頁面數據
     */
    async getCharacterList() {
        const code = `
            (async () => {
                const tables = document.querySelectorAll('table.result-table');
                const characters = [];

                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach((row, index) => {
                        if (index === 0) return; // 跳過表頭

                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            const nameCell = cells[0];
                            const link = nameCell.querySelector('a');
                            const img = nameCell.querySelector('img');

                            characters.push({
                                name: nameCell.textContent.trim(),
                                url: link ? link.href : null,
                                image: img ? img.src : null,
                                rating: cells[1] ? cells[1].textContent.trim() : null,
                                role: cells[2] ? cells[2].textContent.trim() : null
                            });
                        }
                    });
                });

                return characters;
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 獲取角色詳細資訊
     * @param {number} charaId - 角色 ID
     */
    async getCharacterDetail(charaId) {
        const code = `
            (async () => {
                // 獲取頁面上的角色數據
                const data = {
                    name: document.querySelector('h1')?.textContent?.trim(),
                    stats: {},
                    skills: [],
                    arks: []
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

                return data;
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 獲取方舟(Ark)列表
     */
    async getArkList() {
        const code = `
            (async () => {
                const response = await fetch(window.location.origin + '/lastcloudia/arklist');
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const arks = [];
                const tables = doc.querySelectorAll('table.result-table');

                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach((row, index) => {
                        if (index === 0) return;

                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const nameCell = cells[0];
                            const link = nameCell.querySelector('a');

                            arks.push({
                                name: nameCell.textContent.trim(),
                                url: link ? link.href : null,
                                rarity: cells[1] ? cells[1].textContent.trim() : null
                            });
                        }
                    });
                });

                return arks;
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 獲取技能列表
     * @param {number} type - 技能類型 (1=技能, 2=魔法)
     */
    async getSkillList(type = 1) {
        const code = `
            (async () => {
                const response = await fetch('https://altema.jp/lastcloudia/Skill/${type}');
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const skills = [];
                const tables = doc.querySelectorAll('table');

                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach((row, index) => {
                        if (index === 0) return;

                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            skills.push({
                                name: cells[0]?.textContent?.trim(),
                                effect: cells[1]?.textContent?.trim(),
                                cost: cells[2]?.textContent?.trim()
                            });
                        }
                    });
                });

                return skills;
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 獲取最強角色排行
     */
    async getStrongestCharacters() {
        const code = `
            (async () => {
                const response = await fetch('https://altema.jp/lastcloudia/saikyokyara');
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const rankings = [];
                const tables = doc.querySelectorAll('table');

                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach((row, index) => {
                        if (index === 0) return;

                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const link = cells[0]?.querySelector('a');
                            rankings.push({
                                rank: index,
                                name: cells[0]?.textContent?.trim(),
                                url: link?.href,
                                tier: cells[1]?.textContent?.trim()
                            });
                        }
                    });
                });

                return rankings;
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 獲取裝備列表
     * @param {number} type - 裝備類型 (1=武器, 2=防具, 3=飾品)
     */
    async getEquipmentList(type = 1) {
        const code = `
            (async () => {
                const response = await fetch('https://altema.jp/lastcloudia/soubilist/${type}');
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const equipment = [];
                const tables = doc.querySelectorAll('table.result-table');

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
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 搜索內容
     * @param {string} keyword - 搜索關鍵字
     */
    async search(keyword) {
        const code = `
            (async () => {
                const response = await fetch('https://altema.jp/lastcloudia/?s=' + encodeURIComponent('${keyword}'));
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const results = [];
                const articles = doc.querySelectorAll('article, .search-result, li');

                articles.forEach(article => {
                    const link = article.querySelector('a');
                    if (link && link.href.includes('lastcloudia')) {
                        results.push({
                            title: link.textContent.trim(),
                            url: link.href
                        });
                    }
                });

                return results.slice(0, 20);
            })()
        `;
        return await this.executeInPage(code);
    }

    /**
     * 導出攔截到的所有請求
     */
    getInterceptedRequests() {
        return this.interceptedRequests;
    }

    /**
     * 導航到指定頁面
     */
    async navigate(url) {
        const { Page } = this.client;
        await Page.navigate({ url });
        await Page.loadEventFired();
    }

    /**
     * 斷開連接
     */
    async disconnect() {
        if (this.client) {
            await this.client.close();
            console.log('[+] 已斷開 CDP 連接');
        }
    }
}

// ===================
// CLI 工具
// ===================

async function main() {
    const client = new AltemaAPIClient();

    console.log('='.repeat(60));
    console.log(' Altema Last Cloudia API Client');
    console.log('='.repeat(60));
    console.log('');
    console.log('可用的 API 方法:');
    console.log('');
    console.log('1. getCharacterList()     - 獲取所有角色列表');
    console.log('2. getCharacterDetail(id) - 獲取角色詳細資訊');
    console.log('3. getArkList()           - 獲取所有方舟列表');
    console.log('4. getSkillList(type)     - 獲取技能列表 (1=技能, 2=魔法)');
    console.log('5. getStrongestCharacters()- 獲取最強角色排行');
    console.log('6. getEquipmentList(type) - 獲取裝備列表 (1=武器, 2=防具, 3=飾品)');
    console.log('7. getComments(category)  - 獲取評論數據');
    console.log('8. search(keyword)        - 搜索內容');
    console.log('9. getInterceptedRequests()- 獲取攔截到的 API 請求');
    console.log('');
    console.log('='.repeat(60));

    // 連接到 Chrome
    const connected = await client.connect();

    if (!connected) {
        console.log('');
        console.log('請先啟動 Chrome 並開啟調試端口:');
        console.log('chrome.exe --remote-debugging-port=9222');
        console.log('');
        console.log('然後開啟 https://altema.jp/lastcloudia/ 頁面');
        return;
    }

    // 示範: 獲取評論數據
    console.log('');
    console.log('[*] 測試 API: 獲取評論數據...');
    try {
        const comments = await client.getComments();
        console.log(`[+] 成功! NGWord 數量: ${comments.NGWord?.length || 0}`);
    } catch (e) {
        console.log('[-] 失敗:', e.message);
    }

    // 導出 client 供互動使用
    global.altemaClient = client;
    console.log('');
    console.log('[+] API Client 已載入至 global.altemaClient');
    console.log('[+] 可使用 Node.js REPL 進行互動操作');

    // 保持連接
    process.on('SIGINT', async () => {
        await client.disconnect();
        process.exit(0);
    });
}

// 如果直接運行此文件
if (require.main === module) {
    main().catch(console.error);
}

module.exports = { AltemaAPIClient };

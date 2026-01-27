/**
 * 批量獲取所有方舟資料
 *
 * 使用方式:
 * 1. 啟動 Chrome: chrome.exe --remote-debugging-port=9222
 * 2. 開啟 https://altema.jp/lastcloudia/ 頁面
 * 3. 運行: node fetch-all-arks.js
 */

const { chromium } = require('playwright');
const fs = require('fs');

// 所有方舟 ID（從方舟列表頁面獲取，共 223 個）
const ARK_IDS = [
    284, 272, 283, 282, 95, 113, 187, 195, 221, 224, 257, 259, 260, 273, 124, 136, 151, 153, 155, 160,
    168, 176, 182, 189, 203, 205, 210, 212, 223, 226, 238, 240, 247, 249, 253, 263, 267, 271, 275, 85,
    100, 103, 117, 119, 129, 143, 163, 169, 190, 217, 159, 280, 279, 281, 177, 211, 233, 235, 242, 244,
    248, 254, 264, 268, 269, 270, 98, 99, 109, 110, 112, 114, 125, 126, 127, 142, 145, 146, 148, 149,
    150, 156, 157, 162, 165, 166, 172, 173, 174, 175, 179, 180, 184, 185, 191, 192, 197, 198, 199, 200,
    207, 208, 209, 213, 215, 216, 218, 219, 227, 231, 234, 236, 241, 243, 246, 250, 251, 255, 265, 276,
    277, 101, 115, 130, 132, 140, 141, 181, 196, 201, 204, 206, 214, 229, 106, 131, 170, 228, 105, 138,
    44, 62, 167, 222, 256, 258, 47, 50, 54, 57, 71, 76, 79, 87, 89, 96, 107, 111, 116, 120, 121, 122, 128,
    134, 139, 144, 147, 154, 158, 161, 164, 171, 178, 183, 193, 225, 230, 239, 252, 261, 262, 266, 274,
    278, 51, 58, 78, 80, 88, 90, 102, 108, 118, 123, 135, 186, 194, 202, 237, 65, 67, 81, 91, 94, 97, 104,
    137, 188, 232, 46, 52, 55, 64, 69, 73, 75, 82, 93, 152, 220, 245, 49, 77, 43, 45, 60, 83, 84, 92, 42,
    38, 40, 23, 53, 26, 30, 33, 37, 41, 63, 86, 28, 29, 31, 36, 25, 27, 61, 24, 56, 70, 133, 32, 34, 35, 39,
    11, 16, 20, 2, 3, 59, 68, 1, 10, 7, 9, 14, 17, 74, 4, 8, 66, 5, 6, 12, 13, 15, 18, 19, 21, 72
];

// 獲取所有方舟的稀有度對照表與所有 ID
async function fetchArkListAndRarity(page) {
    console.log('[*] 正在獲取方舟列表與稀有度...');
    await page.goto('https://altema.jp/lastcloudia/arklist', { waitUntil: 'domcontentloaded' });

    return await page.evaluate(() => {
        const map = {};
        const allIds = new Set();

        // 1. 先遍歷分類選單建立稀有度對照表
        const dts = document.querySelectorAll('dl.acMenu dt');
        dts.forEach(dt => {
            const text = dt.textContent.trim();
            let rarity = null;

            if (text.includes('URアーク')) rarity = 'UR';
            else if (text.includes('LRアーク')) rarity = 'LR';
            else if (text.includes('SSRアーク')) rarity = 'SSR';
            else if (text.includes('SRアーク')) rarity = 'SR';
            else if (text.includes('Rアーク')) rarity = 'R';

            if (rarity) {
                const dd = dt.nextElementSibling;
                if (dd && dd.tagName === 'DD') {
                    const links = dd.querySelectorAll('a[href*="/ark/"]');
                    links.forEach(link => {
                        const match = link.href.match(/\/ark\/(\d+)/);
                        if (match) {
                            const id = parseInt(match[1]);
                            map[id] = rarity;
                            // 注意：這裡不 add 到 allIds，我們稍後用更全面的方式抓 ID
                        }
                    });
                }
            }
        });

        // 2. 抓取頁面上"所有"的方舟連結，確保不漏掉任何一個
        // 有些方舟可能不在分類選單中，但仍在頁面上
        const allLinks = document.querySelectorAll('a[href*="/ark/"]');
        allLinks.forEach(link => {
            const match = link.href.match(/\/ark\/(\d+)/);
            if (match) {
                const id = parseInt(match[1]);
                allIds.add(id);
            }
        });

        return {
            rarityMap: map,
            foundIds: Array.from(allIds).sort((a, b) => a - b)
        };
    });
}

async function extractArkData(page) {
    return await page.evaluate(() => {
        const urlMatch = window.location.href.match(/\/ark\/(\d+)/);
        const arkId = urlMatch ? parseInt(urlMatch[1]) : null;

        const data = {
            id: arkId,
            url: window.location.href,
            name: '',
            rarity: '',
            image: '',
            etherReward: '', // 乙太報酬
            arkTraitSummary: '', // 方舟特性(LV15)
            arkEffect: [], // 特性升級表
            arkSkill: [],  // 方舟技能
            learnableSkills: [] // 可習得技能 (含 SC 和效果)
        };

        // Get name
        const h1 = document.querySelector('h1')?.textContent?.trim() || '';
        data.name = h1.replace(/【ラスクラ】|の評価と習得スキル/g, '').trim();

        // Get image
        const imgEl = document.querySelector('.unit_img img, .ark_img img, img[src*="ark/banner"]');
        data.image = imgEl?.src || '';

        // 解析所有表格
        const tables = document.querySelectorAll('table');
        tables.forEach(table => {
            const firstRow = table.querySelector('tr');
            if (!firstRow) return;
            const ths = Array.from(firstRow.querySelectorAll('th')).map(c => c.textContent.trim());

            // 1. 基本資訊表 (Table 1)
            // 處理跨行結構：th 在一行，內容在下一行
            const rowText = table.textContent;
            if (rowText.includes('レア度') || rowText.includes('アーク特性') || rowText.includes('アークエーテル')) {
                 const rows = Array.from(table.querySelectorAll('tr'));

                 for (let i = 0; i < rows.length; i++) {
                     const th = rows[i].querySelector('th');
                     if (!th) continue;

                     const text = th.textContent.trim();

                     // 稀有度 (通常在下一行)
                     if (text === 'レア度') {
                         const nextRow = rows[i + 1];
                         const img = nextRow?.querySelector('img');
                         if (img) {
                             if (img.src.includes('ur.png')) data.rarity = 'UR';
                             else if (img.src.includes('ssr.png')) data.rarity = 'SSR';
                             else if (img.src.includes('sr.png')) data.rarity = 'SR';
                             else if (img.src.includes('/r.png')) data.rarity = 'R';
                         }
                     }

                     // 方舟特性 (通用匹配: アーク特性(LV10) 或 アーク特性(LV15) 或其他)
                     else if (text.includes('アーク特性') && !text.includes('習得')) {
                         // 排除掉可能的干擾項，只要是基本資訊表裡的 "アーク特性" 就可以
                         const nextRow = rows[i + 1];
                         data.arkTraitSummary = nextRow?.textContent?.trim() || '';
                     }

                     // 乙太獎勵
                     else if (text.includes('アークエーテル100%報酬')) {
                         const nextRow = rows[i + 1];
                         if (nextRow) {
                             // 可能有多個 TD (圖片+名稱, 效果)
                             data.etherReward = Array.from(nextRow.querySelectorAll('td'))
                                 .map(td => td.textContent.trim())
                                 .filter(t => t)
                                 .join(' : ');
                         }
                     }
                 }
            }

            // 2. 學習技能表 (Table 2: スキル名, SC, 効果...)
            else if (ths[0] === 'スキル名' || ths.includes('効果')) {
                const rows = Array.from(table.querySelectorAll('tr')).slice(1);
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {
                        data.learnableSkills.push({
                            name: cells[0]?.textContent?.trim(),
                            sc: cells[1]?.textContent?.trim(),
                            effect: cells[2]?.textContent?.trim(),
                            type: cells[3]?.textContent?.trim() || '',
                            ap: cells[4]?.textContent?.trim() || ''
                        });
                    }
                });
            }

            // 3. 特性升級表 (Table 3: 強化レベル, 特性)
            else if (ths[0] === '強化レベル' && ths[1] === '特性') {
                const rows = Array.from(table.querySelectorAll('tr')).slice(1);
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        data.arkEffect.push({
                            level: cells[0]?.textContent?.trim(),
                            effect: cells[1]?.textContent?.trim()
                        });
                    }
                });
            }

            // 4. 方舟技能表 (Table 4: 強化レベル, アークスキル)
            // 嘗試獲取 Lv10 (或其他最高等級) 的描述
            else if (ths[0] === '強化レベル' && ths[1] === 'アークスキル') {
                const rows = Array.from(table.querySelectorAll('tr')).slice(1);

                // 先找 Lv10
                let targetRow = rows.find(r => {
                    const levelCell = r.querySelector('th, td'); // 第一列可能是 th 也可能是 td
                    return levelCell && levelCell.textContent.trim() === 'Lv10';
                });

                // 如果沒找到 Lv10，就找最後一行 (通常是最高等級)
                if (!targetRow && rows.length > 0) {
                    targetRow = rows[rows.length - 1];
                }

                if (targetRow) {
                    const cells = targetRow.querySelectorAll('td');
                    // 注意：如果是 th, td 結構，技能描述是在第一個 td
                    // 如果是 td, td 結構，技能描述是在第二個 td
                    // 通常結構是: [Level] [Skill Description]
                    let skillText = '';
                    if (cells.length === 1) {
                        skillText = cells[0].textContent.trim();
                    } else if (cells.length >= 2) {
                        skillText = cells[1].textContent.trim();
                    }

                    if (skillText) {
                        data.arkSkill.push({
                            level: 'Max', // 標記為 Max
                            skill: skillText
                        });
                    }
                }
            }
        });

        // 備用：如果表格中沒找到稀有度，嘗試從圖片
        if (!data.rarity) {
             const rarityImg = document.querySelector('.unit_img img[src*="ur.png"], .unit_img img[src*="ssr.png"]');
             if (rarityImg) {
                if (rarityImg.src.includes('ur.png')) data.rarity = 'UR';
                else if (rarityImg.src.includes('ssr.png')) data.rarity = 'SSR';
             }
        }

        // 確保如果沒有特性升級表，至少把摘要放進去
        if (data.arkEffect.length === 0 && data.arkTraitSummary) {
            data.arkEffect.push({ level: 'Max', effect: data.arkTraitSummary });
        }

        return data;
    });
}

async function main() {
    console.log('='.repeat(60));
    console.log(' 批量獲取方舟資料 (增量更新模式)');
    console.log('='.repeat(60));
    console.log('');

    let browser;
    try {
        // Check if running in CI mode (passed as arg or env var)
        const isCI = process.argv.includes('--ci') || process.env.CI === 'true';

        if (isCI) {
            console.log('[*] Running in CI mode - Launching headless browser...');
            browser = await chromium.launch({ headless: true });
        } else {
            console.log('[*] Connecting to local Chrome instance...');
            try {
                browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
            } catch (e) {
                console.log('[-] Could not connect to local Chrome. Launching new instance instead...');
                browser = await chromium.launch({ headless: false });
            }
        }

        console.log('[+] Browser connected');

        const contexts = browser.contexts();
        const context = contexts[0] || await browser.newContext();
        const pages = context.pages();
        let page = pages.find(p => p.url().includes('altema.jp')) || pages[0];

        if (!page) {
            page = await context.newPage();
        }

        // 1. 讀取現有資料
        let existingArks = [];
        if (fs.existsSync('arks-data.json')) {
            try {
                const raw = fs.readFileSync('arks-data.json', 'utf-8');
                const data = JSON.parse(raw);
                existingArks = data.arks || [];
                console.log(`[+] 讀取到現有資料: ${existingArks.length} 筆`);
            } catch (e) {
                console.log('[-] 現有資料讀取失敗，將重新下載');
            }
        }

        // 2. 獲取網站上最新的完整列表
        const { rarityMap, foundIds } = await fetchArkListAndRarity(page);
        console.log(`[+] 網站上共有 ${foundIds.length} 個方舟`);

        // 3. 比對找出缺失的 ID
        const existingIds = new Set(existingArks.map(ark => ark.id));

        // 合併 hardcoded 列表與網站爬到的列表，確保不會漏掉
        // 注意：ARK_IDS 常數可能已經過時，以網站爬取的為準，但也可以保留做備份參考
        const targetIds = foundIds.length > 0 ? foundIds : ARK_IDS;

        const missingIds = targetIds.filter(id => !existingIds.has(id));

        if (missingIds.length === 0) {
            console.log('[+] 所有方舟資料已是最新，無需更新！');
            // 順便更新一下 rarities (如果舊資料缺的話)
            let updated = false;
            existingArks.forEach(ark => {
                if (!ark.rarity && rarityMap[ark.id]) {
                    ark.rarity = rarityMap[ark.id];
                    updated = true;
                }
            });

            if (updated) {
                console.log('[*] 已更新部分缺失的稀有度資訊');
                 const output = {
                    exportTime: new Date().toISOString(),
                    totalArks: existingArks.length,
                    arks: existingArks
                };
                fs.writeFileSync('arks-data.json', JSON.stringify(output, null, 2), 'utf-8');
            }

            return;
        }

        console.log(`[!] 發現 ${missingIds.length} 個新方舟，準備下載...`);
        console.log(`[!] 新增 ID: ${missingIds.join(', ')}`);

        const newArks = [];
        const total = missingIds.length;

        for (let i = 0; i < total; i++) {
            const arkId = missingIds[i];
            const progress = `[${i + 1}/${total}]`;

            try {
                console.log(`${progress} 獲取方舟 ID: ${arkId}...`);
                await page.goto(`https://altema.jp/lastcloudia/ark/${arkId}`, {
                    waitUntil: 'domcontentloaded',
                    timeout: 30000
                });
                await page.waitForTimeout(500); // Short delay

                const arkData = await extractArkData(page);

                // 補充稀有度
                if (!arkData.rarity && rarityMap[arkId]) {
                    arkData.rarity = rarityMap[arkId];
                }

                newArks.push(arkData);
                console.log(`${progress} ✓ ${arkData.name}`);

            } catch (error) {
                console.log(`${progress} ✗ 方舟 ${arkId} 獲取失敗: ${error.message}`);
                newArks.push({ id: arkId, error: error.message });
            }

            // 臨時保存進度
             if ((i + 1) % 5 === 0) {
                const currentAll = [...existingArks, ...newArks];
                 fs.writeFileSync('arks-data-temp.json', JSON.stringify({ arks: currentAll }, null, 2), 'utf-8');
             }
        }

        // 合併並保存最終結果
        const finalArks = [...existingArks, ...newArks];

        // 按照 ID 排序 (可選)
        // finalArks.sort((a, b) => b.id - a.id);

        const output = {
            exportTime: new Date().toISOString(),
            totalArks: finalArks.length,
            arks: finalArks
        };

        fs.writeFileSync('arks-data.json', JSON.stringify(output, null, 2), 'utf-8');
        // 刪除臨時檔
        if (fs.existsSync('arks-data-temp.json')) fs.unlinkSync('arks-data-temp.json');

        console.log('');
        console.log('[+] 資料更新完成！');
        console.log(`[+] 原有: ${existingArks.length}, 新增: ${newArks.length}, 總計: ${finalArks.length}`);

    } catch (error) {
        console.error('[-] 錯誤:', error.message);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

main().catch(console.error);

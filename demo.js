/**
 * 快速演示腳本
 *
 * 展示如何使用 Altema API Client 獲取各種數據
 */

const { AltemaPlaywrightClient } = require('./altema-playwright');

async function main() {
    const client = new AltemaPlaywrightClient();

    console.log('='.repeat(60));
    console.log(' Altema Last Cloudia API 演示');
    console.log('='.repeat(60));
    console.log('');

    // 連接到 Chrome
    const connected = await client.connect();
    if (!connected) {
        console.log('連接失敗! 請確保:');
        console.log('1. Chrome 以調試模式啟動: chrome.exe --remote-debugging-port=9222');
        console.log('2. 已開啟 altema.jp/lastcloudia 頁面');
        return;
    }

    try {
        // 1. 獲取所有角色
        console.log('\n[1] 獲取角色列表...');
        const characters = await client.getCharacterList();
        console.log(`    找到 ${characters.length} 個角色`);

        // 顯示前 10 個
        console.log('\n    前 10 個角色:');
        characters.slice(0, 10).forEach((char, i) => {
            console.log(`    ${i + 1}. ${char.name} - 評價: ${char.rating || 'N/A'}`);
        });

        // 2. 獲取最強角色排行
        console.log('\n[2] 獲取最強角色排行...');
        const strongest = await client.getStrongestCharacters();
        console.log(`    找到 ${strongest.length} 個角色排行`);

        console.log('\n    Top 10 最強角色:');
        strongest.slice(0, 10).forEach((char, i) => {
            console.log(`    ${i + 1}. ${char.name} - Tier: ${char.tier || 'N/A'}`);
        });

        // 3. 獲取方舟列表
        console.log('\n[3] 獲取方舟列表...');
        const arks = await client.getArkList();
        console.log(`    找到 ${arks.length} 個方舟`);

        // 4. 獲取技能列表
        console.log('\n[4] 獲取技能列表...');
        const skills = await client.getSkillList(1);
        console.log(`    找到 ${skills.length} 個技能`);

        // 5. 獲取裝備列表
        console.log('\n[5] 獲取武器列表...');
        const weapons = await client.getEquipmentList(1);
        console.log(`    找到 ${weapons.length} 個武器`);

        // 6. 獲取一個角色的詳細資訊
        if (characters.length > 0 && characters[0].id) {
            console.log(`\n[6] 獲取角色詳細資訊: ${characters[0].name}...`);
            const detail = await client.getCharacterDetail(characters[0].id);
            console.log(`    名稱: ${detail.name}`);
            console.log(`    統計數據: ${Object.keys(detail.stats).length} 項`);
        }

        // 7. 顯示攔截到的 API 請求
        console.log('\n[7] 攔截到的 API 請求:');
        const requests = client.getInterceptedRequests();
        requests.forEach(req => {
            console.log(`    ${req.method} ${req.url}`);
        });

        // 導出數據
        const fs = require('fs');

        const exportData = {
            exportTime: new Date().toISOString(),
            characters: characters,
            strongestCharacters: strongest,
            arks: arks,
            skills: skills,
            weapons: weapons
        };

        fs.writeFileSync('altema-data.json', JSON.stringify(exportData, null, 2), 'utf-8');
        console.log('\n[+] 數據已導出至 altema-data.json');

    } catch (error) {
        console.error('錯誤:', error.message);
    }

    console.log('\n' + '='.repeat(60));
    console.log(' 演示完成!');
    console.log('='.repeat(60));

    await client.close();
}

main().catch(console.error);

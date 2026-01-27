/**
 * 生成繁體中文方舟報告
 *
 * 使用方式: node generate-report.js
 */

const fs = require('fs');

// 日文到繁體中文的常用翻譯映射
const SKILL_TRANSLATIONS = {
    // 武器類
    '剣': '劍', '槍': '槍', '斧': '斧', '弓': '弓', '杖': '杖', '槌': '槌', '爪': '爪',
    '両手剣': '雙手劍', '両手槌': '雙手槌',
    // 強化類
    'ブースト': '強化', 'ハイブースト': '高級強化', 'メガブースト': '超級強化', 'ギガブースト': '極致強化',
    'ドライブ': '驅動', 'ハイドライブ': '高級驅動', 'メガドライブ': '超級驅動',
    // 屬性
    '炎': '炎', '氷': '冰', '雷': '雷', '樹': '樹', '光': '光', '闇': '闇', '無属性': '無屬性',
    // 狀態
    '毒': '毒', '麻痺': '麻痺', '暗闇': '暗闘', '沈黙': '沉默', '呪い': '詛咒', '気絶': '氣絕', '凍結': '凍結',
    // 能力
    'アップ': '提升', 'ダウン': '降低', 'アタックレイズ': '攻擊提升',
    'オート': '自動', 'ブレイブ': '勇氣', 'オーラ': '靈氣', 'プロテクト': '保護',
    // 其他
    'カウンター': '反擊', '鉄壁': '鐵壁', '耐性': '耐性', 'シールド': '護盾',
    '弱点突破': '弱點突破', '限界突破': '極限突破',
    'HP': 'HP', 'MP': 'MP', 'STR': 'STR', 'INT': 'INT', 'DEF': 'DEF', 'MND': 'MND',
    '特技': '特技', '必殺技': '必殺技', '超必殺技': '超必殺技',
    'ジャイアント': '巨人', 'キリング': '殺手',
    'マスター': '大師', 'コンボ': '連擊', 'ファスト': '快速', 'ヘイスト': '加速',
    'チャージ': '蓄力', '剛堅': '剛堅', '闘志': '鬥志', '激高': '激昂'
};

function translateSkillName(jpName) {
    let translated = jpName;
    for (const [jp, tw] of Object.entries(SKILL_TRANSLATIONS)) {
        translated = translated.replace(new RegExp(jp, 'g'), tw);
    }
    return translated;
}

function generateMarkdownReport(data) {
    let md = `# Last Cloudia 方舟資料報告
## 繁體中文版

> 資料來源: Altema (https://altema.jp/lastcloudia)
> 更新時間: ${new Date().toISOString().split('T')[0]}
> 方舟總數: ${data.totalArks}

---

## 方舟列表

| ID | 方舟名稱 | 稀有度 | 可習得技能數 | 乙太獎勵 |
|----|----------|--------|--------------|----------|
`;

    for (const ark of data.arks) {
        if (ark.error) continue;
        const skillCount = ark.learnableSkills?.length || 0;
        md += `| ${ark.id} | ${ark.name} | ${ark.rarity || '-'} | ${skillCount} | ${ark.etherReward || '-'} |\n`;
    }

    md += `\n---\n\n## 方舟詳細資料\n\n`;

    let index = 1;
    for (const ark of data.arks) {
        if (ark.error) continue;

        md += `### ${index}. ${ark.name} (${ark.rarity || '未知'})\n`;
        md += `**ID:** ${ark.id}\n\n`;

        // 特性
        if (ark.arkEffect && ark.arkEffect.length > 0) {
            md += `**方舟特性 (Max):**\n`;
            // 通常最後一個是滿級
            const maxTrait = ark.arkEffect[ark.arkEffect.length - 1];
            md += `> ${maxTrait.effect}\n\n`;
        } else if (ark.arkTraitSummary) {
            md += `**方舟特性 (Max):**\n`;
            md += `> ${ark.arkTraitSummary}\n\n`;
        }

        // 乙太獎勵
        if (ark.etherReward) {
            md += `**乙太獎勵 (100%):** ${ark.etherReward}\n\n`;
        }

        // 方舟技能
        if (ark.arkSkill && ark.arkSkill.length > 0) {
            md += `**方舟主動技能:**\n`;
            const maxSkill = ark.arkSkill[ark.arkSkill.length - 1];
            md += `> ${maxSkill.skill}\n\n`;
        }

        // 學習技能
        if (ark.learnableSkills && ark.learnableSkills.length > 0) {
            md += `**可習得技能:**\n`;
            md += `| 技能名稱 | SC | 效果 |\n`;
            md += `|----------|----|------|\n`;

            for (const skill of ark.learnableSkills) {
                const translatedName = translateSkillName(skill.name);
                // 簡化效果文字，移除過多換行
                const effect = (skill.effect || '').replace(/\n/g, ' ');
                md += `| ${translatedName} <br><small>${skill.name}</small> | ${skill.sc} | ${effect} |\n`;
            }
        } else {
            md += `*無技能資料*\n`;
        }

        md += `\n---\n\n`;
        index++;
    }

    md += `\n## 備註\n\n`;
    md += `- 技能翻譯為自動生成的參考譯名，實際遊戲內可能有不同譯名\n`;
    md += `- 資料來源為 Altema 日文攻略網站\n`;
    md += `- SC 為技能消耗點數\n\n`;
    md += `*報告生成時間: ${new Date().toISOString()}*\n`;

    return md;
}

function main() {
    console.log('='.repeat(60));
    console.log(' 生成繁體中文方舟報告');
    console.log('='.repeat(60));

    // 讀取資料檔案
    let dataFile = 'arks-data.json';
    if (!fs.existsSync(dataFile)) {
        dataFile = 'arks-sample-data.json';
    }

    if (!fs.existsSync(dataFile)) {
        console.error('[-] 找不到資料檔案！請先運行 fetch-all-arks.js');
        return;
    }

    console.log(`[+] 讀取資料檔案: ${dataFile}`);
    const data = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));

    console.log(`[+] 找到 ${data.totalArks || data.arks?.length} 個方舟`);

    // 生成報告
    const report = generateMarkdownReport(data);

    // 保存報告
    const outputFile = '方舟資料報告_完整版.md';
    fs.writeFileSync(outputFile, report, 'utf-8');
    console.log(`[+] 報告已生成: ${outputFile}`);

    console.log('');
    console.log('='.repeat(60));
    console.log(' 完成!');
    console.log('='.repeat(60));
}

main();

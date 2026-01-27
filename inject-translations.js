const fs = require('fs');

try {
    // 1. Read the translations from name.txt
    const nameDataRaw = fs.readFileSync('name.txt', 'utf-8');
    const nameData = JSON.parse(nameDataRaw);

    // Convert to a string of JS object properties
    let newTranslations = "    // === 自動匯入的聖物名稱翻譯 ===\n";
    for (const [key, value] of Object.entries(nameData)) {
        // Escape single quotes if present
        const safeKey = key.replace(/'/g, "\\'");
        const safeValue = value.replace(/'/g, "\\'");
        newTranslations += `    '${safeKey}': '${safeValue}',\n`;
    }
    newTranslations += "\n";

    // 2. Read app.js
    let appJs = fs.readFileSync('app.js', 'utf-8');

    // 3. Inject the translations
    // Find the start of SKILL_TRANSLATIONS
    const startMarker = "const SKILL_TRANSLATIONS = {";
    const insertionPoint = appJs.indexOf(startMarker);

    if (insertionPoint === -1) {
        throw new Error("Could not find SKILL_TRANSLATIONS in app.js");
    }

    // Insert after the opening brace
    const newAppJs = appJs.slice(0, insertionPoint + startMarker.length) +
                     "\n" + newTranslations +
                     appJs.slice(insertionPoint + startMarker.length);

    // 4. Write back to app.js
    fs.writeFileSync('app.js', newAppJs, 'utf-8');
    console.log('Successfully injected translations into app.js');

} catch (error) {
    console.error('Error:', error.message);
}

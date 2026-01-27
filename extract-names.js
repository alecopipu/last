const fs = require('fs');

try {
    const rawData = fs.readFileSync('arks-data.json', 'utf-8');
    const data = JSON.parse(rawData);

    // Extract only the names
    // Create a key-value map for easy translation later: "Japanese Name": "Japanese Name"
    // This allows the user to just change the value on the right side.
    const arkNames = {};

    if (data.arks && Array.isArray(data.arks)) {
        data.arks.forEach(ark => {
            if (ark.name) {
                arkNames[ark.name] = ""; // Leave value empty for user to fill, or pre-fill with JP name
            }
        });
    }

    // Sort keys alphabetically for easier reading? Or keep original order?
    // Let's keep original order but maybe just a simple object is best.

    // Actually, to make it easier for the user to "translate", maybe I should output:
    // "Japanese Name": "Japanese Name" (so they can just edit the second one)
    // Or just a list. The user said "list out JP ark names for me to save to new file".
    // Let's do a map { "JP Name": "JP Name" } so it's ready for translation JSON format.

    const nameMap = {};
    data.arks.forEach(ark => {
        nameMap[ark.name] = ark.name;
    });

    fs.writeFileSync('ark-names.json', JSON.stringify(nameMap, null, 2), 'utf-8');
    console.log(`Extracted ${Object.keys(nameMap).length} ark names to ark-names.json`);

} catch (error) {
    console.error('Error:', error.message);
}

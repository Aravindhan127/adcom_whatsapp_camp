const fs = require('fs');
const content = fs.readFileSync('c:\\Office_Work\\Adcom\\adcom\\frontend\\src\\pages\\Templates.tsx', 'utf8');

let openDiv = 0;
let closeDiv = 0;

const openMatches = content.match(/<div/g) || [];
const closeMatches = content.match(/<\/div>/g) || [];

console.log({ openDiv: openMatches.length, closeDiv: closeMatches.length });

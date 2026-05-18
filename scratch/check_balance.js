const fs = require('fs');
const content = fs.readFileSync('c:\\Office_Work\\Adcom\\adcom\\frontend\\src\\pages\\Templates.tsx', 'utf8');
const lines = content.split('\n');
const range = lines.slice(949, 1202).join('\n'); // 950 to 1202

let openBrace = 0;
let closeBrace = 0;
let openParen = 0;
let closeParen = 0;
let openTag = 0;
let closeTag = 0;

for (let i = 0; i < range.length; i++) {
    if (range[i] === '{') openBrace++;
    if (range[i] === '}') closeBrace++;
    if (range[i] === '(') openParen++;
    if (range[i] === ')') closeParen++;
    if (range.slice(i, i+4) === '<div') openTag++;
    if (range.slice(i, i+6) === '</div') closeTag++;
}

console.log({ openBrace, closeBrace, openParen, closeParen, openTag, closeTag });

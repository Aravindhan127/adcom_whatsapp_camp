const fs = require('fs');
const content = fs.readFileSync('c:\\Office_Work\\Adcom\\adcom\\frontend\\src\\pages\\Templates.tsx', 'utf8');

let openBrace = 0;
let closeBrace = 0;
let openParen = 0;
let closeParen = 0;

for (let i = 0; i < content.length; i++) {
    if (content[i] === '{') openBrace++;
    if (content[i] === '}') closeBrace++;
    if (content[i] === '(') openParen++;
    if (content[i] === ')') closeParen++;
}

console.log({ openBrace, closeBrace, openParen, closeParen });

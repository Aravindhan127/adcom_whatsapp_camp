const fs = require('fs');
const content = fs.readFileSync('c:/Office_Work/Adcom/adcom/frontend/src/pages/Templates.tsx', 'utf8');

let braces = 0;
let parens = 0;
let brackets = 0;

for (let i = 0; i < content.length; i++) {
  const char = content[i];
  if (char === '{') braces++;
  if (char === '}') braces--;
  if (char === '(') parens++;
  if (char === ')') parens--;
  if (char === '[') brackets++;
  if (char === ']') brackets--;
  
  if (braces < 0 || parens < 0 || brackets < 0) {
    const lines = content.substring(0, i).split('\n');
    console.log(`Negative count at Line ${lines.length}: char '${char}' | {:${braces} (:${parens} [:${brackets}`);
  }
}

console.log(`Final counts: {:${braces} (:${parens} [:${brackets}`);

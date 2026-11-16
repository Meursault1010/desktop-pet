import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseMarkdown,inlineTokens,safeLink} from '../src/markdown.ts';

test('plain text stays plain and never becomes markup',()=>{
  assert.deepEqual(parseMarkdown(''),[]);
  const blocks=parseMarkdown('今天还行。\n<script>alert(1)</script>');
  assert.equal(blocks.length,1);assert.equal(blocks[0].kind,'paragraph');
  assert.equal(blocks[0].inlines.map(token=>token.text).join(''),'今天还行。\n<script>alert(1)</script>');
  assert.equal(blocks[0].inlines.some(token=>token.link),false);
});
test('paragraphs, headings and lists split into blocks',()=>{
  const blocks=parseMarkdown('## 计划\n\n先散步\n- 喝水\n- 休息\n1. 一\n2. 二');
  assert.deepEqual(blocks.map(block=>block.kind),['heading','paragraph','list','list']);
  assert.equal(blocks[0].level,2);assert.equal(blocks[0].inlines[0].text,'计划');
  assert.deepEqual(blocks[2].items.map(item=>item[0].text),['喝水','休息']);
  assert.equal(blocks[2].ordered,false);assert.equal(blocks[3].ordered,true);
  assert.deepEqual(blocks[3].items.map(item=>item[0].text),['一','二']);
});
test('fenced code keeps its language and lines verbatim',()=>{
  const [block]=parseMarkdown('```js\nconst a = 1;\n// **not bold**\n```');
  assert.equal(block.kind,'code');assert.equal(block.lang,'js');assert.deepEqual(block.lines,['const a = 1;','// **not bold**']);
  const [before,open]=parseMarkdown('未闭合\n```\nx');
  assert.equal(before.kind,'paragraph');assert.equal(open.kind,'code');assert.deepEqual(open.lines,['x']);
});
test('inline tokens cover bold, code and links',()=>{
  assert.deepEqual(inlineTokens('看 **这里** 和 `npm test`'),[{text:'看 '},{text:'这里',bold:true},{text:' 和 '},{text:'npm test',code:true}]);
  const [token]=inlineTokens('[官网](https://example.com/a)');
  assert.deepEqual(token,{text:'官网',link:'https://example.com/a'});
});
test('only clean http(s) links become clickable',()=>{
  assert.equal(safeLink('https://example.com'),'https://example.com');
  for(const bad of ['javascript:alert(1)','data:text/html,x','https://evil.example@ok/','','mailto:a@b.c','https://'])assert.equal(safeLink(bad),'');
  const tokens=inlineTokens('[点我](javascript:alert(1))');
  assert.equal(tokens.map(token=>token.text).join(''),'[点我](javascript:alert(1))');
  assert.equal(tokens.some(token=>token.link),false);
  assert.deepEqual(inlineTokens('[x](javascript:alert)')[0],{text:'[x](javascript:alert)'});
});

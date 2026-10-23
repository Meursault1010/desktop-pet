const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {Attachments,contentWithAttachments}=require('../main/attachments.cjs');
const {Assistant}=require('../main/assistant.cjs');
test('attachments validate limits and send document and image content to local inference',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'yuki-upload-'));
 try {
 const file=path.join(dir,'sample.txt');await fs.writeFile(file,'Yuki '.repeat(4000));
 const a=new Attachments(),doc=await a.add(file);assert.equal(doc.characters,18000);assert.equal(doc.truncated,true);assert.equal(doc.text,undefined);
 assert.throws(()=>a.resolve([doc.id,doc.id]));assert.throws(()=>a.resolve(['invalid']));
 const png=path.join(dir,'sample.png');await fs.writeFile(png,'fixture');const image=await a.add(png,{imageReader:async()=> 'data:image/png;base64,fixture'});
 const content=contentWithAttachments('read',a.resolve([doc.id,image.id]));assert.equal(content[1].type,'image_url');assert.ok(content[0].text.includes('Yuki'));
 let body;const bot=new Assistant({fetchImpl:async(url,options)=>{body=JSON.parse(options.body);return new Response('data: '+JSON.stringify({choices:[{delta:{content:'ok'}}]})+String.fromCharCode(10,10)+'data: [DONE]'+String.fromCharCode(10,10));}});bot.attachments=a;
 const input={id:'test-upload',model:'local',messages:[{role:'user',content:'read',attachments:[doc.id,image.id]}]};
 assert.equal((await bot.chat(input,()=>{})).text,'ok');assert.equal(body.messages[1].content[1].image_url.url,image.preview);
 bot.endpoint='https://example.com/v1';await assert.rejects(bot.chat(input,()=>{}));
 await fs.writeFile(file,'');await assert.rejects(a.add(file));await fs.writeFile(file,Buffer.alloc(10*1024*1024+1));await assert.rejects(a.add(file));
 } finally{await fs.rm(dir,{recursive:true,force:true});}
});
test('installed PDF and DOCX libraries load',()=>{assert.equal(typeof require('pdf-parse').PDFParse,'function');assert.equal(typeof require('mammoth').extractRawText,'function');});


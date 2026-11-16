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
test('an OCR image can travel as text plus picture, and each mode sends only what it should',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'yuki-modes-'));
 try{
  const png=path.join(dir,'shot.png');await fs.writeFile(png,'fixture');
  const a=new Attachments({ocr:{recognize:async()=>({text:'识别出的文字',truncated:false})}});
  const shot=await a.add(png,{imageReader:async()=>'data:image/png;base64,fixture'});
  assert.equal(shot.imageMode,'both');assert.equal(shot.recognition,'ocr');assert.equal(shot.characters,6);
  let content=contentWithAttachments('看这张图',a.resolve([shot.id]));
  assert.equal(content.length,2);assert.match(content[0].text,/识别出的文字/);assert.equal(content[1].type,'image_url');
  assert.deepEqual(a.setMode(shot.id,'text'),{id:shot.id,imageMode:'text'});
  assert.equal(typeof contentWithAttachments('看这张图',a.resolve([shot.id])),'string');
  a.setMode(shot.id,'image');content=contentWithAttachments('看这张图',a.resolve([shot.id]));
  assert.equal(content[0].text,'看这张图');assert.equal(content[1].type,'image_url');
  assert.throws(()=>a.setMode(shot.id,'nope'),/识别模式无效/);
  assert.throws(()=>a.setMode('missing','text'),/附件已失效/);
  const plain=new Attachments();const noText=await plain.add(png,{imageReader:async()=>'data:image/png;base64,fixture'});
  assert.throws(()=>plain.setMode(noText.id,'text'),/没有识别到文字/);
  assert.equal(plain.setMode(noText.id,'both').imageMode,'both');
  const pictureOnly=contentWithAttachments('看',plain.resolve([noText.id]));
  assert.equal(pictureOnly.length,2);assert.equal(pictureOnly[0].text,'看');assert.equal(pictureOnly[1].type,'image_url');
 } finally{await fs.rm(dir,{recursive:true,force:true});}
});
test('cloud endpoints require an explicit one-time attachment approval after the service switch is enabled',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'yuki-cloud-attach-'));
 try{
  const file=path.join(dir,'note.txt');await fs.writeFile(file,'云端可见的内容');
  const a=new Attachments();const doc=await a.add(file);
  let body;const bot=new Assistant({endpoint:'https://example.com/v1',fetchImpl:async(url,options)=>{body=JSON.parse(options.body);return new Response('data: '+JSON.stringify({choices:[{delta:{content:'ok'}}]})+String.fromCharCode(10,10)+'data: [DONE]'+String.fromCharCode(10,10));}});
  bot.attachments=a;const input={id:'cloud-attach',model:'vision',messages:[{role:'user',content:'读',attachments:[doc.id]}]};
  await assert.rejects(bot.chat(input,()=>{}),/云端/);
  assert.equal(bot.allowRemoteAttachments,false);
  bot.allowRemoteAttachments=true;
  const review=bot.reviewAttachments([doc.id],'vision'),approval=bot.approveAttachments({reviewId:review.reviewId,ids:[doc.id],model:'vision'});
  assert.equal((await bot.chat({...input,attachmentApproval:approval.ticket},()=>{})).text,'ok');assert.match(JSON.stringify(body.messages[1].content),/云端可见的内容/);
 } finally{await fs.rm(dir,{recursive:true,force:true});}
});


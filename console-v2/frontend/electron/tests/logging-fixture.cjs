'use strict';
const {createMainLogger}=require('../main/logging.cjs');
const logger=createMainLogger({file:process.argv[2],mirror:true});
global.console=logger.console;
process.once('message',()=>{
  console.error('original IPC rejection');
  // Cover direct writes as well as Electron's console.error path.
  process.stdout.write('terminal diagnostic\n');
  process.stderr.write('terminal error\n');
  setTimeout(()=>{
    console.log('after pipe closure');
    process.disconnect();
  },80);
});
process.send('ready');

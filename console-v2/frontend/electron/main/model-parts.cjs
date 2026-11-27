'use strict';

const fs = require('node:fs');
const path = require('node:path');
const {createHash, randomUUID} = require('node:crypto');
const {pipeline} = require('node:stream/promises');

const MODEL_FILE = 'Qwen3.8-4B-Q4_K_M.gguf';

function modelParts(root, version) {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'release-manifest.json'), 'utf8'));
  if (!/^\d+\.\d+\.\d+$/.test(version) || manifest.version !== `v${version}` ||
      manifest.modelFile !== MODEL_FILE || !/^[a-f\d]{64}$/i.test(manifest.modelSha256 ?? '')) {
    throw new Error('应用包的本地模型清单无效。');
  }
  const names = ['part01', 'part02'].map(suffix => `yuki-model-v${version}.${suffix}`);
  const destination = path.join(root, 'resources/local-model/qwen', MODEL_FILE);
  const find = folder => {
    const files = names.map(name => path.join(folder, name));
    return files.every(file => fs.statSync(file, {throwIfNoEntry:false})?.isFile()) ? files : null;
  };

  async function install(files, signal) {
    if (fs.existsSync(destination)) return;
    signal.throwIfAborted();
    const temp = `${destination}.${randomUUID()}.partial`;
    const hash = createHash('sha256');
    const output = fs.createWriteStream(temp, {flags:'wx'});
    const outputClosed = new Promise(resolve => output.once('close', resolve));
    async function* contents() {
      for (const file of files) {
        signal.throwIfAborted();
        for await (const chunk of fs.createReadStream(file, {highWaterMark:1024*1024,signal})) {
          hash.update(chunk);
          yield chunk;
        }
      }
    }
    try {
      await pipeline(contents(), output, {signal});
      await outputClosed;
      if (hash.digest('hex') !== manifest.modelSha256.toLowerCase()) {
        throw new Error('模型分卷校验失败，请重新下载同一版本的两个分卷。');
      }
      signal.throwIfAborted();
      await fs.promises.rename(temp, destination);
    } finally {
      output.destroy();
      await outputClosed;
      await fs.promises.rm(temp, {force:true}).catch(() => {});
    }
  }
  return {find, install};
}

module.exports = {modelParts};

#!/usr/bin/env node
/** TLS-verified raw capture into the replayable AMind request cache. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash, randomUUID } from 'node:crypto';
import { gzipSync, gunzipSync } from 'node:zlib';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const digest = data => createHash('sha256').update(data).digest('hex');
const stamp = () => new Date().toISOString();

async function atomicWrite(destination, bytes) {
  await fs.mkdir(path.dirname(destination), { recursive: true });
  const temporary = destination + '.' + randomUUID() + '.tmp';
  await fs.writeFile(temporary, bytes);
  await fs.rename(temporary, destination);
}

export async function captureSources({ release, urls, workers = 8, retryFailed = true,
  timeoutMs = 25000, maxBytes = 96 * 1024 * 1024 }) {
  const directory = path.resolve(release);
  if (!directory.startsWith(path.join(root, 'release') + path.sep))
    throw new Error('capture directory must be inside this checkout release/');
  const unique = [...new Set(urls)];
  for (const url of unique) {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password)
      throw new Error('only credential-free HTTPS public source URLs are accepted');
  }
  if (!Number.isInteger(workers) || workers < 1 || workers > 24)
    throw new Error('workers must be an integer from 1 to 24');
  let cursor = 0;
  const results = new Array(unique.length);
  async function worker() {
    while (cursor < unique.length) {
      const index = cursor++, url = unique[index];
      const key = digest(url), cache = path.join(directory, 'sources/requests', key + '.json');
      let previous;
      try { previous = JSON.parse(await fs.readFile(cache, 'utf8')); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      if (previous?.ok) {
        const bytes = gunzipSync(await fs.readFile(path.join(directory, previous.raw_path)));
        if (digest(bytes) !== previous.raw_sha256) throw new Error('cached raw hash mismatch: ' + url);
        results[index] = { url, ok: true, cached: true }; continue;
      }
      if (previous && !retryFailed) { results[index] = { url, ok: false, cached: true }; continue; }
      if (previous) await atomicWrite(path.join(directory, 'sources/request-history', key + '-' + digest(JSON.stringify(previous)).slice(0, 12) + '.json'), JSON.stringify(previous) + '\n');
      const record = { requested_url: url, started_at: stamp(), ok: false,
        transport: 'node-fetch-tls-verified', source_representation: 'original_http_body' };
      try {
        const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs),
          headers: { 'User-Agent': 'AMindResearch/2026.10 public-source-refresh',
            'Accept': 'text/html,application/pdf,application/xml;q=0.9,*/*;q=0.8' } });
        record.http_status = response.status; record.final_url = response.url;
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const chunks = []; let total = 0;
        for await (const chunk of response.body) {
          total += chunk.length;
          if (total > maxBytes) throw new Error('response exceeds maxBytes');
          chunks.push(chunk);
        }
        const bytes = Buffer.concat(chunks), hash = digest(bytes);
        const relative = 'sources/raw/' + hash + '.bin.gz';
        await atomicWrite(path.join(directory, relative), gzipSync(bytes, { mtime: 0 }));
        record.ok = true; record.bytes = bytes.length;
        record.raw_sha256 = hash; record.raw_path = relative;
        record.content_type = response.headers.get('content-type') || '';
        record.response_headers = Object.fromEntries([...response.headers]
          .filter(([key]) => ['etag', 'last-modified', 'content-type', 'date', 'content-length'].includes(key)));
      } catch (error) { record.error = error.message; }
      record.completed_at = stamp();
      await atomicWrite(cache, JSON.stringify(record) + '\n');
      results[index] = { url, ok: record.ok, error: record.error, bytes: record.bytes };
    }
  }
  await Promise.all(Array.from({ length: Math.min(workers, unique.length) }, worker));
  return { requested: unique.length, captured: results.filter(r => r.ok).length,
    cached: results.filter(r => r.cached).length, failed: results.filter(r => !r.ok), completed_at: stamp() };
}

if (typeof process !== 'undefined' && process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), option = flag => args[args.indexOf(flag) + 1];
  if (!args.includes('--release') || !args.includes('--urls')) throw new Error('use --release PATH --urls JSON_FILE');
  const entries = JSON.parse(await fs.readFile(option('--urls'), 'utf8'));
  console.log(JSON.stringify(await captureSources({ release: option('--release'),
    urls: entries.map(e => typeof e === 'string' ? e : e.url) }), null, 2));
}

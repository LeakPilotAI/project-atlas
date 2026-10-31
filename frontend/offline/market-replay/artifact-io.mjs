/* Bounded static-artifact I/O. Not production storage or a privileged-writer fence. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
export const MAX_ARTIFACT_BYTES = 2000000;
export function checkParents(output) {
  if (typeof output !== 'string' || !output) throw new Error('Explicit output path required');
  for (let parent = path.dirname(path.resolve(output)); ; parent = path.dirname(parent)) {
    const info = fs.lstatSync(parent);
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error('Unsafe output directory');
    if (parent === path.dirname(parent)) return;
  }
}
function closed(descriptor, failure) {
  try { fs.closeSync(descriptor); }
  catch (error) { if (failure) throw new AggregateError([failure, error], 'Publication and close failed'); throw error; }
  if (failure) throw failure;
}
export function publishNew(output, text) {
  if (typeof text !== 'string') throw new Error('Explicit artifact text required');
  const bytes = Buffer.from(text);
  if (bytes.length > MAX_ARTIFACT_BYTES) throw new Error('Artifact byte bound exceeded');
  checkParents(output);
  const absolute = path.resolve(output), descriptor = fs.openSync(absolute, 'wx+');
  let failure;
  try {
    let offset = 0;
    while (offset < bytes.length) {
      const count = fs.writeSync(descriptor, bytes, offset, bytes.length - offset);
      if (count <= 0) throw new Error('Short HTML publication');
      offset += count;
    }
    fs.fsyncSync(descriptor);
    const identity = fs.fstatSync(descriptor, {bigint: true});
    const readback = Buffer.alloc(bytes.length); let read = 0;
    while (read < readback.length) {
      const count = fs.readSync(descriptor, readback, read, readback.length - read, read);
      if (count <= 0) throw new Error('Short HTML read-back');
      read += count;
    }
    const current = fs.lstatSync(absolute, {bigint: true});
    if (!readback.equals(bytes) || !current.isFile() || current.isSymbolicLink() || current.nlink !== 1n ||
        current.dev !== identity.dev || current.ino !== identity.ino || current.size !== BigInt(bytes.length)) throw new Error('HTML publication read-back/identity mismatch');
  } catch (error) { failure = error; }
  closed(descriptor, failure);
  return {path: absolute, sha256: crypto.createHash('sha256').update(bytes).digest('hex')};
}
export function readBounded(input, maximum = MAX_ARTIFACT_BYTES) {
  if (!Number.isSafeInteger(maximum) || maximum < 0 || maximum > MAX_ARTIFACT_BYTES) throw new Error('Bounded read required');
  checkParents(input);
  const expected = fs.lstatSync(input, {bigint: true});
  if (!expected.isFile() || expected.isSymbolicLink() || expected.nlink !== 1n || expected.size > BigInt(maximum)) throw new Error('Unsafe artifact input');
  const descriptor = fs.openSync(input, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  let failure, bytes;
  try {
    const identity = fs.fstatSync(descriptor, {bigint: true});
    if (identity.dev !== expected.dev || identity.ino !== expected.ino || identity.size !== expected.size || identity.nlink !== 1n) throw new Error('Artifact identity changed before read');
    bytes = Buffer.alloc(Number(expected.size)); let offset = 0;
    while (offset < bytes.length) {
      const count = fs.readSync(descriptor, bytes, offset, bytes.length - offset, offset);
      if (count <= 0) throw new Error('Short artifact read');
      offset += count;
    }
    const after = fs.fstatSync(descriptor, {bigint: true}), named = fs.lstatSync(input, {bigint: true});
    if (after.size !== expected.size || after.mtimeNs !== expected.mtimeNs || named.dev !== expected.dev || named.ino !== expected.ino || named.nlink !== 1n || named.isSymbolicLink()) throw new Error('Artifact changed during read');
  } catch (error) { failure = error; }
  closed(descriptor, failure);
  return bytes;
}

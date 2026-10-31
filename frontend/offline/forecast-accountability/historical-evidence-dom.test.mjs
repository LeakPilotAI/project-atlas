import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { renderPriorCases } = require('./view.cjs');

function element() {
  return {
    value: '',
    textContent: '',
    children: [],
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    replaceChildren(...children) {
      this.children = [...children];
    },
  };
}

function documentFixture() {
  const elements = new Map([
    ['memory-query', element()],
    ['memory-rows', element()],
    ['memory-status', element()],
  ]);

  return {
    elements,
    getElementById(id) {
      return elements.get(id) ?? null;
    },
    createElement() {
      return element();
    },
  };
}

test('empty renderer displays unauthenticated NOT_SUPPLIED state', () => {
  const doc = documentFixture();

  renderPriorCases(doc, []);

  const status = doc.elements.get('memory-status').textContent;

  assert.match(status, /Historical evidence: NOT_SUPPLIED/);
  assert.match(status, /No historical availability authentication/);
  assert.match(status, /No historical evidence receipt classification supplied/);
  assert.equal(doc.elements.get('memory-rows').children.length, 0);
});

test('renderer clears stale DOM rows and selection on empty replacement', () => {
  const doc = documentFixture();
  const query = doc.elements.get('memory-query');
  const body = doc.elements.get('memory-rows');
  const status = doc.elements.get('memory-status');

  query.value = 'stale-forecast';
  body.appendChild(element());
  status.textContent = 'Previously authenticated';

  renderPriorCases(doc, []);

  assert.equal(query.value, '');
  assert.equal(body.children.length, 0);
  assert.doesNotMatch(status.textContent, /Previously authenticated/);
  assert.match(status.textContent, /Historical evidence: NOT_SUPPLIED/);
});

test('missing DOM elements do not create evidence authority', () => {
  const doc = {
    getElementById() {
      return null;
    },
  };

  assert.doesNotThrow(() => renderPriorCases(doc, []));
});

test('renderer uses text-only status, never injected HTML', () => {
  const doc = documentFixture();
  const status = doc.elements.get('memory-status');

  Object.defineProperty(status, 'innerHTML', {
    set() {
      throw new Error('Unsafe HTML rendering');
    },
  });

  renderPriorCases(doc, []);

  assert.match(status.textContent, /NOT_SUPPLIED/);
});

import test from 'node:test';
import assert from 'node:assert/strict';

import {readAuthSession,writeAuthSession} from '../src/authSession.js';

function memoryStorage() {
  const values = new Map();
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

test('a valid session survives a fresh read after page reload', () => {
  const storage = memoryStorage();
  const session = {
    token: 'test-session-token',
    user: {id: 42, name: 'Test User', email: 'test@example.test', role: 'candidate'},
  };

  writeAuthSession(session, storage);

  assert.deepEqual(readAuthSession(storage), session);
});

test('logout clears the stored session', () => {
  const storage = memoryStorage();
  writeAuthSession({token: 'test-session-token', user: {id: 42}}, storage);
  writeAuthSession(null, storage);

  assert.equal(readAuthSession(storage), null);
});

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  candidateRouteRedirect,
  employerRouteRedirect,
  workspacePathFor,
} from '../src/authFlow.js';

const assessments = [
  { id: 'DRAFT-1', status: 'Draft' },
  { id: 'PUBLISHED-1', status: 'Published' },
];

test('trusted employer role selects the existing employer dashboard', () => {
  assert.equal(workspacePathFor('employer', assessments), '/dashboard');
});

test('trusted candidate role selects the existing candidate workspace', () => {
  assert.equal(workspacePathFor('candidate', assessments), '/candidate/welcome/PUBLISHED-1');
});

test('protected employer routes reject missing sessions and redirect candidates', () => {
  assert.equal(employerRouteRedirect(null, assessments), '/login');
  assert.equal(employerRouteRedirect({ role: 'candidate' }, assessments), '/candidate/welcome/PUBLISHED-1');
  assert.equal(employerRouteRedirect({ role: 'employer' }, assessments), null);
});

test('candidate workspace rejects employers and permits only signed-in candidates or explicit previews', () => {
  assert.equal(candidateRouteRedirect(null), '/login');
  assert.equal(candidateRouteRedirect({ role: 'employer' }), '/dashboard');
  assert.equal(candidateRouteRedirect({ role: 'candidate' }), null);
  assert.equal(candidateRouteRedirect(null, true), null);
});

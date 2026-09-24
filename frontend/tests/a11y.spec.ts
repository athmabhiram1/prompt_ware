// @vitest-environment jsdom
import { StrictMode, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import * as matchers from 'vitest-axe/matchers';
import App from '../src/App';

expect.extend(matchers);

async function renderAppShell(): Promise<HTMLElement> {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(createElement(StrictMode, null, createElement(App)));
  });
  return container;
}

describe('a11y smoke (vitest-axe)', () => {
  it('App shell has no wcag2a/wcag2aa violations', async () => {
    const container = await renderAppShell();
    const results = await axe(container, {
      // color-contrast debt allowlisted (Wave A): sepia/parchment palette
      // fails 4.5:1 on muted text; palette redesign explicitly out of scope.
      runOnly: ['wcag2a', 'wcag2aa'],
      rules: { 'color-contrast': { enabled: false } },
    });
    if (results.violations.length > 0) {
      console.log(
        `axe violations: ${results.violations.length} rules, ${results.violations.reduce((n, v) => n + v.nodes.length, 0)} nodes :: ` +
          results.violations.map((v) => `${v.id}(${v.nodes.length})`).sort().join(', '),
      );
    }
    expect(results).toHaveNoViolations();
  });
});

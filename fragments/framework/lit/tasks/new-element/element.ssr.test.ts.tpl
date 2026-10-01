// @vitest-environment node
import { render } from '@lit-labs/ssr';
import { collectResult } from '@lit-labs/ssr/lib/render-result.js';
import { html } from 'lit';
import { expect, it } from 'vitest';
import './<name>.js';

it('renders declarative shadow DOM on the server', async () => {
    const out = await collectResult(render(html`<<prefix>-<name>>Label</<prefix>-<name>>`));
    expect(out).toContain('<template shadowroot');
    expect(out).toContain('part="base"');
    expect(out).toContain('Label');
});

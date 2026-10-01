import { html, render } from 'lit';
import { afterEach, describe, expect, it, vi } from 'vitest';
import './<name>.js';
import type { <Prefix><Name> } from './<name>.js';

async function fixture(template: ReturnType<typeof html>): Promise<<Prefix><Name>> {
    const host = document.createElement('div');
    document.body.append(host);
    render(template, host);
    const el = host.firstElementChild as <Prefix><Name>;
    await el.updateComplete;
    return el;
}

afterEach(() => {
    document.body.replaceChildren();
});

describe('<prefix>-<name>', () => {
    it('registers', () => {
        expect(customElements.get('<prefix>-<name>')).toBeDefined();
    });

    it('renders', async () => {
        const el = await fixture(html`<<prefix>-<name>>Label</<prefix>-<name>>`);
        const base = el.shadowRoot?.querySelector('[part~="base"]');
        expect(base).not.toBeNull();
        // Present is not enough: a node that paints nothing passes that check.
        const box = base?.getBoundingClientRect();
        expect(box?.width).toBeGreaterThan(0);
        expect(box?.height).toBeGreaterThan(0);
    });

    it('reflects variant', async () => {
        const el = await fixture(html`<<prefix>-<name> variant="secondary"></<prefix>-<name>>`);
        expect(el.variant).toBe('secondary');
        el.variant = 'primary';
        await el.updateComplete;
        expect(el.getAttribute('variant')).toBe('primary');
    });

    it('boolean attribute presence', async () => {
        const el = await fixture(html`<<prefix>-<name> disabled></<prefix>-<name>>`);
        expect(el.disabled).toBe(true);
        el.removeAttribute('disabled');
        await el.updateComplete;
        expect(el.disabled).toBe(false);
    });

    it('dispatches <prefix>-change with detail', async () => {
        const el = await fixture(html`<<prefix>-<name>></<prefix>-<name>>`);
        const listener = vi.fn();
        // On document: receiving it there proves it bubbles and is composed.
        document.addEventListener('<prefix>-change', listener, { once: true });
        // Trigger the interaction that commits a value, inside el.shadowRoot.
        expect(listener).toHaveBeenCalledOnce();
        expect(listener.mock.calls[0]?.[0]).toMatchObject({
            detail: { value: expect.any(String) },
            bubbles: true,
            composed: true,
        });
    });

    it('projects the default slot', async () => {
        const el = await fixture(html`<<prefix>-<name>><b>Label</b></<prefix>-<name>>`);
        const slot = el.shadowRoot?.querySelector<HTMLSlotElement>('slot:not([name])');
        expect(slot?.assignedElements()).toHaveLength(1);
    });

    // Form controls only.
    it('submits its value and resets', async () => {
        const form = document.createElement('form');
        document.body.append(form);
        render(html`<<prefix>-<name> name="field" value="a"></<prefix>-<name>>`, form);
        const el = form.firstElementChild as <Prefix><Name>;
        await el.updateComplete;
        expect(new FormData(form).get('field')).toBe('a');
        el.value = 'b';
        await el.updateComplete;
        form.reset();
        await el.updateComplete;
        expect(el.value).toBe('a');
    });

    it('exposes roles', async () => {
        const el = await fixture(html`<<prefix>-<name>></<prefix>-<name>>`);
        const base = el.shadowRoot?.querySelector('[part~="base"]');
        expect(base?.getAttribute('role')).toBeNull();
    });
});

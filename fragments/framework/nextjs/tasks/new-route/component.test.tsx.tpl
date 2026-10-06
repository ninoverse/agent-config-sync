import { expect, test } from 'vitest';
import { render } from 'vitest-browser-react';
import { <Name> } from './<name>';

test('renders its label', async () => {
    const screen = await render(<<Name> label="Clicks" />);

    await expect
        .element(screen.getByRole('button', { name: 'Clicks: 0' }))
        .toBeVisible();
});

test('counts each click', async () => {
    const screen = await render(<<Name> label="Clicks" />);

    await screen.getByRole('button').click();

    await expect
        .element(screen.getByRole('button', { name: 'Clicks: 1' }))
        .toBeVisible();
});

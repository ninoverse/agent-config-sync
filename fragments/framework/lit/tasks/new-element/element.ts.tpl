import { html, isServer, LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { emit } from '../shared/events.js';
import { styles } from './<name>.styles.js';

export type <Name>Variant = 'primary' | 'secondary';

export interface <Name>ChangeDetail {
    value: string;
}

/**
 * <What the element is for, in one line.>
 *
 * @tag <prefix>-<name>
 * @slot - The label.
 * @csspart base - The root node.
 * @fires {CustomEvent<<Name>ChangeDetail>} <prefix>-change - The value was committed.
 */
@customElement('<prefix>-<name>')
export class <Prefix><Name> extends LitElement {
    static override styles = styles;

    /** Visual style. @default 'primary' */
    @property({ reflect: true }) accessor variant: <Name>Variant = 'primary';

    /** Turns interaction off. @default false */
    @property({ type: Boolean, reflect: true }) accessor disabled = false;

    /** The current value. @default '' */
    @property() accessor value = '';

    #abort: AbortController | undefined;

    override connectedCallback(): void {
        super.connectedCallback();
        if (isServer) return;
        this.#abort = new AbortController();
        // Listeners on document or window go here, with { signal: this.#abort.signal }.
    }

    override disconnectedCallback(): void {
        this.#abort?.abort();
        super.disconnectedCallback();
    }

    // Called from the interaction that commits a value.
    #commit(value: string): void {
        if (value === this.value) return;
        this.value = value;
        emit<<Name>ChangeDetail>(this, '<prefix>-change', { value });
    }

    override render() {
        return html`<div part="base" class="base"><slot></slot></div>`;
    }
}

declare global {
    interface HTMLElementTagNameMap {
        '<prefix>-<name>': <Prefix><Name>;
    }
}

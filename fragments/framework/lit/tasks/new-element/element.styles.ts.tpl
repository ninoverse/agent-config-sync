import { css } from 'lit';

export const styles = css`
    :host {
        display: inline-block;
    }

    .base {
        display: flex;
        align-items: center;
    }

    :host([disabled]) .base {
        cursor: not-allowed;
    }

    @media (prefers-reduced-motion: reduce) {
        .base {
            transition: none;
        }
    }
`;

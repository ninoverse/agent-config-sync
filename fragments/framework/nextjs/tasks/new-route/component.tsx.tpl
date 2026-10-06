'use client';

import { useState } from 'react';

/** <What the component does, in one line.> */
export function <Name>({ label }: { label: string }) {
    const [count, setCount] = useState(0);

    return (
        <button type="button" onClick={() => setCount(count + 1)}>
            {label}: {count}
        </button>
    );
}

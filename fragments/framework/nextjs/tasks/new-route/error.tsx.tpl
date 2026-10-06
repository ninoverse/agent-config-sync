'use client';

import { useEffect } from 'react';

// The segment's error boundary, so a Client Component. `retry()` fetches and
// renders the segment again.
export default function <Name>Error({
    error,
    retry,
}: {
    error: Error & { digest?: string };
    retry: () => void;
}) {
    useEffect(() => {
        // Report the error here. `error.digest` matches the server's log entry.
        console.error(error);
    }, [error]);

    return (
        <div role="alert">
            <h2>Something went wrong.</h2>
            <button type="button" onClick={() => retry()}>
                Try again
            </button>
        </div>
    );
}

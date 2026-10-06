import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: '<Title>',
    description: '<What the page shows, in one sentence.>',
};

// A Server Component. With a dynamic segment, the page is `async` and takes
// `props: PageProps<'<url>'>`, then reads `await props.params`. With data, it
// awaits that too, here or in a child inside `<Suspense>`.
export default function <Name>Page() {
    return (
        <main>
            <h1><Title></h1>
        </main>
    );
}

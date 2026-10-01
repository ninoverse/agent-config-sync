/** Every event the elements dispatch is named `<prefix>-…`. */
export type <Prefix>EventName = `<prefix>-${string}`;

/**
 * Dispatches an element's event from `host`: a `CustomEvent` that bubbles,
 * leaves the shadow root (`composed`) and carries an object `detail`.
 *
 * @returns `false` when a listener called `preventDefault()` on a cancelable
 * event, which the element must honour.
 */
export function emit<T extends object>(
    host: EventTarget,
    type: <Prefix>EventName,
    detail: T,
    options: { cancelable?: boolean } = {},
): boolean {
    return host.dispatchEvent(
        new CustomEvent<T>(type, {
            detail,
            bubbles: true,
            composed: true,
            cancelable: options.cancelable ?? false,
        }),
    );
}

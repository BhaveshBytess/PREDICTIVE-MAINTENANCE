/**
 * Shared resilient fetch utility.
 *
 * Wraps the native fetch() with:
 *   - AbortController timeout (default 10 s)
 *   - Automatic retry with a configurable delay
 *
 * Used across system-control endpoints AND operator / chart endpoints
 * to eliminate bare fetch() calls that hang without a timeout.
 */

/** Default timeout for requests (ms) */
const REQUEST_TIMEOUT_MS = 10_000;

/** Retry config */
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;

/**
 * Fetch with timeout + automatic retry.
 *
 * @param {string} url
 * @param {RequestInit} options
 * @param {number} retries  Number of retry attempts (default 2)
 * @returns {Promise<Response>}
 */
export async function resilientFetch(url, options = {}, retries = MAX_RETRIES) {
    for (let attempt = 0; attempt <= retries; attempt++) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        try {
            const response = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timer);
            return response;
        } catch (err) {
            clearTimeout(timer);
            const isLast = attempt === retries;
            if (isLast) throw err;
            console.warn(
                `[resilientFetch] Request failed (attempt ${attempt + 1}/${retries + 1}), retrying in ${RETRY_DELAY_MS}ms...`,
                err.message
            );
            await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        }
    }
}

export default resilientFetch;

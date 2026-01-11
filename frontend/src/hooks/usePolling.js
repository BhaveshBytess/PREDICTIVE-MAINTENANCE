import { useState, useEffect, useCallback } from 'react'

/**
 * Custom hook for polling data from an API endpoint.
 * Pure renderer - frontend does NOT calculate scores.
 */
export function usePolling(url, intervalMs = 3000) {
    const [data, setData] = useState(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchData = useCallback(async () => {
        try {
            const response = await fetch(url)
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
            }
            const json = await response.json()
            setData(json)
            setError(null)
        } catch (err) {
            // Don't clear existing data on error
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }, [url])

    useEffect(() => {
        // Initial fetch
        fetchData()

        // Set up polling interval
        const intervalId = setInterval(fetchData, intervalMs)

        // Cleanup on unmount
        return () => clearInterval(intervalId)
    }, [fetchData, intervalMs])

    return { data, isLoading, error, refetch: fetchData }
}

export default usePolling

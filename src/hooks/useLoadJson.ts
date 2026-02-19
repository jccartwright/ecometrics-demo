import { useState, useEffect } from 'react'

export interface UseLoadJSONResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}


/**
 * Custom hook to load and parse a JSON file
 * @param url - The URL or path to the JSON file
 * @returns An object containing the parsed data, loading state, and any errors
 */

export function useLoadJSON<T>(url: string) {
    const [data, setData] = useState<T | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<Error | null>(null)

    useEffect(() => {
        fetch(url)
        .then(res => {
            if (!res.ok) { 
                console.log('Fetch error:', res)
                throw new Error('Network response was not ok') 
            }
            // console.log('Fetch successful:', res)
            return res.json()
        })
        .then((d: T) => setData(d))
        .catch((e: unknown) => setError(e instanceof Error ? e : new Error(String(e))))
        .finally(() => setLoading(false))
    }, [url])

    return { data, loading, error }
}

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


/*
// Written by Claude
export function useLoadJSON<T = any>(url: string): UseLoadJSONResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadJSON = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error(`Failed to load JSON: ${response.status} ${response.statusText}`);
        }

        const jsonData = await response.json();

        if (isMounted) {
          setData(jsonData);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error('Unknown error occurred'));
          setLoading(false);
        }
      }
    };

    loadJSON();

    return () => {
      isMounted = false;
    };
  }, [url]);

  return { data, loading, error };
}
*/
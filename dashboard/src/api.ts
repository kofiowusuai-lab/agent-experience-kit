import {createContext, useContext, useEffect, useState} from "react";
export const RefreshContext = createContext(0);
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const r = await fetch("/api" + path, {
    credentials: "include",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!r.ok) {
    let message = `Request failed (${r.status})`;
    try {
      const b = await r.json();
      if (typeof b.detail === "string") message = b.detail;
    } catch {}
    throw new ApiError(message, r.status);
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}
export function useData<T>(path: string, revision = 0) {
  const refresh = useContext(RefreshContext);
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setLoading(true);
    setError("");
    api<T>(path)
      .then((d) => {
        if (current) setData(d);
      })
      .catch((e) => {
        if (current) setError(e.message);
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [path, revision, retry, refresh]);
  return { data, error, loading, retry: () => setRetry((n) => n + 1) };
}

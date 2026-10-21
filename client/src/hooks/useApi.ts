import { useEffect, useState } from "react";
import { api } from "../services/api";

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) {
      setLoading(false);
      setData(null);
      return;
    }
    let live = true;
    setLoading(true);
    api<T>(path)
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [path, tick]);

  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}

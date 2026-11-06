import { useQuery } from "@tanstack/react-query";
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-ARC-Request": "1",
      ...init?.headers,
    },
    signal: init?.signal ?? AbortSignal.timeout(90000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export function useApi<T>(path: string, enabled = true, interval = 5000) {
  return useQuery({
    queryKey: [path],
    queryFn: ({ signal }) => api<T>(path, { signal }),
    enabled,
    refetchInterval: interval,
    retry: 1,
    staleTime: 4000,
  });
}

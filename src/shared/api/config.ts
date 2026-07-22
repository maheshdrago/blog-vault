/** Shared backend URL configuration for browser API clients. */

export const API_ROOT =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

export function resolveApiPath(path: string): string {
  return `${API_ROOT}${path}`;
}

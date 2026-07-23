/** Shared backend URL configuration for browser API clients. */

export const API_ROOT =
  (import.meta.env.VITE_API_URL || '/api/v1').replace(/\/$/, '');

export const MCP_URL =
  (import.meta.env.VITE_MCP_URL || 'http://localhost:8000/mcp/').replace(/\/?$/, '/');

export function resolveApiPath(path: string): string {
  return `${API_ROOT}${path.startsWith('/') ? path : `/${path}`}`;
}

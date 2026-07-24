/** API base URL (no trailing slash). Empty string = same origin (Vite proxy). */
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL as string | undefined
)?.replace(/\/$/, '') ?? '';

export const API_V1 = `${API_BASE_URL}/api/v1`;

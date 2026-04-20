const API = process.env.NEXT_PUBLIC_API_URL || "https://gridflow-ai.onrender.com";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const base = API.endsWith("/") ? API.slice(0, -1) : API;
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const response = await fetch(`${base}${normalizedPath}`, init);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

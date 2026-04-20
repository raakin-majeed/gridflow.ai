const API = (process.env.NEXT_PUBLIC_API_URL || "https://gridflow-ai.onrender.com").replace(
  /\/+$/,
  "",
);

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API}${path}`, init);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

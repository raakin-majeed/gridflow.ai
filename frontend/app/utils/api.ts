const API = process.env.NEXT_PUBLIC_API_URL;
console.log("API URL:", API);

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    if (!API) {
      console.error("API failed", "NEXT_PUBLIC_API_URL is undefined");
      throw new Error("NEXT_PUBLIC_API_URL is undefined");
    }
    const base = API.endsWith("/") ? API.slice(0, -1) : API;
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${base}${normalizedPath}`;
    console.log("Calling:", url);
    const response = await fetch(url, init);
    if (!response.ok) {
      console.error("API failed", response.status);
      throw new Error(`API request failed: ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error(error);
    throw error;
  }
}

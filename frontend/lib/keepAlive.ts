const BACKEND =
  process.env.NEXT_PUBLIC_API_URL || "https://gridflow-ai.onrender.com";

export function startKeepAlive() {
  const ping = () => fetch(`${BACKEND}/ping`).catch(() => {});
  ping();
  setInterval(ping, 10 * 60 * 1000);
}

"use client";

import { useEffect } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL;
console.log("API URL:", API);

export default function DashboardRoutePage() {
  useEffect(() => {
    console.log("CLIENT RUNNING");
    if (!API) {
      console.error("API failed", "NEXT_PUBLIC_API_URL is undefined");
      return;
    }
    const url = `${API}/api/v1/forecast/summary`;
    console.log("Calling:", url);
    fetch(url)
      .then((res) => {
        if (!res.ok) {
          console.error("API failed", res.status);
          throw new Error("API error");
        }
        return res.json();
      })
      .then((data) => console.log("DATA:", data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="space-y-4">
      <p className="text-xl font-bold text-white">Dashboard Route</p>
      <button
        onClick={() => console.log("CLICK WORKING")}
        className="rounded border border-[#1a2a1a] bg-[#0d1117] px-3 py-2 text-sm text-white"
      >
        TEST BUTTON
      </button>
      <p className="text-sm text-[#cccccc]">
        Client runtime checks are active. Open Network tab to inspect calls.
      </p>
      <Link className="text-sm text-[#00ff88]" href="/">
        Go to main dashboard
      </Link>
    </div>
  );
}

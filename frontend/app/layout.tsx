import type { Metadata } from "next";
import { KeepAliveBootstrap } from "./components/keep-alive-bootstrap";
import { Sidebar } from "./components/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "GRIDFLOW AI",
  description: "India Grid Intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-[#07080d] text-white">
        <KeepAliveBootstrap />
        <div className="h-screen bg-[#07080d]">
          <aside className="fixed left-0 top-0 h-screen w-[220px] border-r border-[#1a2a1a] bg-[#07080d]">
            <Sidebar />
          </aside>
          <main className="ml-[220px] h-screen overflow-y-auto p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

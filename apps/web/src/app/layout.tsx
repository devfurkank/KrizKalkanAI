import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "NSosyal",
  description: "NSosyal ile gündemi keşfet, düşüncelerinizi paylaşın ve dünyaya bağlanın!",
};

/**
 * Tema, ilk boyamadan önce uygulanır; aksi hâlde karanlık modda
 * bir kare beyaz ekran görünür (FOUC).
 */
const themeInit = `
try {
  var t = localStorage.getItem("ns-theme");
  if (t === "dark") document.documentElement.classList.add("dark");
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}

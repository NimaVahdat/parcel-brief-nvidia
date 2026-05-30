import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AutoSite — Toronto Site Pre-Acquisition Analysis",
  description:
    "Click any Toronto parcel to get a decision-grade Development Brief in minutes: building envelope, financial model, council vote prediction, and community response forecast.",
};

// Runs before React hydrates — sets the `dark` class on <html> from
// localStorage or system preference so there is never a colour flash.
const themeScript = `(function(){
  try {
    var s = localStorage.getItem('theme');
    if (s === 'dark' || (!s && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
    }
  } catch(e) {}
})()`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // suppressHydrationWarning: the inline script may add "dark" to the class
    // before React hydrates, so the server-rendered class and browser class
    // intentionally differ. This prop tells React to allow that one mismatch.
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        {/* Runs synchronously before React — no flash of wrong theme */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="bg-slate-50 font-sans text-slate-900 antialiased dark:bg-slate-900 dark:text-slate-100">
        {children}
      </body>
    </html>
  );
}

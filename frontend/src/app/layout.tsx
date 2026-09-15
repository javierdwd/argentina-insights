import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Outfit, Source_Sans_3 } from "next/font/google";
import { Providers } from "./providers";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
});

const sourceSans = Source_Sans_3({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Argentina Insights",
  description: "Ask in plain language. The agent composes the view.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${outfit.variable} ${sourceSans.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-sans">
        <Analytics />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

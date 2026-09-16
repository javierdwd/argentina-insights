import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Newsreader, Outfit, Source_Sans_3 } from "next/font/google";
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

const newsreader = Newsreader({
  variable: "--font-editorial",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Argentina Insights",
  description: "Preguntá en lenguaje natural. El agente compone la vista.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${outfit.variable} ${sourceSans.variable} ${newsreader.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-sans">
        <Analytics />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

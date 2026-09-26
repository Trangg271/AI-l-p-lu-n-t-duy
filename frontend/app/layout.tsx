// frontend/app/layout.tsx
// Root layout — applies global fonts, dark theme, and metadata

import type { Metadata, Viewport } from "next";
import { Inter, Fira_Code, Playfair_Display } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-inter",
  display: "swap",
});

const playfairDisplay = Playfair_Display({
  subsets: ["latin", "vietnamese"],
  variable: "--font-heading",
  display: "swap",
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  variable: "--font-fira-code",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "SocraticAI — Nền tảng luyện tập tranh biện cùng AI",
    template: "%s | SocraticAI",
  },
  description:
    "Rèn luyện tư duy phản biện cùng SocraticAI — đối thủ tranh luận AI thông minh được hỗ trợ bởi Gemini. Ứng dụng phương pháp Socratic và kỹ thuật Steelmanning.",
  keywords: [
    "tranh biện",
    "tư duy phản biện",
    "AI debate",
    "phương pháp Socratic",
    "steelmanning",
    "SocraticAI",
    "tranh luận tiếng Việt",
  ],
  authors: [{ name: "SocraticAI Team" }],
  openGraph: {
    title: "SocraticAI — Nền tảng luyện tập tranh biện cùng AI",
    description:
      "Rèn luyện tư duy và làm chủ mọi tranh biện cùng đối thủ AI ứng dụng phương pháp Socratic.",
    type: "website",
    locale: "vi_VN",
  },
  twitter: {
    card: "summary_large_image",
    title: "SocraticAI",
    description: "Nền tảng rèn luyện tư duy phản biện và tranh luận cùng AI.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#0A0A0F",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${playfairDisplay.variable} ${firaCode.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}

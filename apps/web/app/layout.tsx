import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Chinese Video Learning",
  description: "Convert Chinese video into timestamped learning segments.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}

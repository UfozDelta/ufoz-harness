import type { ReactNode } from "react";

export const metadata = {
  title: "Todo Board",
  description: "Minimal App Router shell used by the medium suite fixture.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

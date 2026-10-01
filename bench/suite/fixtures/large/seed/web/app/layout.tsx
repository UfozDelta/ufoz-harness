import type { ReactNode } from "react";

export const metadata = {
  title: "Items Suite",
  description: "A tiny App Router app used by the harness-suite large fixture.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DevTree - Medical Device Explorer",
  description: "Explore the ancestry of medical devices through their predicate relationships",
  icons: {
    icon: "/devtree.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

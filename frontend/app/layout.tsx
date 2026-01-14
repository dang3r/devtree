import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import TabsContent from "@/components/TabsContent";

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
      <body className="min-h-screen">
        <Suspense fallback={
          <div className="flex h-screen items-center justify-center bg-gray-950">
            <p className="text-gray-400">Loading...</p>
          </div>
        }>
          <TabsContent />
        </Suspense>
      </body>
    </html>
  );
}

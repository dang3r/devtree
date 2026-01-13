'use client';

import { Suspense } from 'react';
import TabsContent from "@/components/TabsContent";

export default function Home() {
  return (
    <Suspense fallback={
      <div className="flex h-screen items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </div>
    }>
      <TabsContent />
    </Suspense>
  );
}

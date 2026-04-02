"use client";

import type { PropsWithChildren } from "react";

import { AuthProvider } from "@/src/providers/AuthProvider";
import { WorkspaceProvider } from "@/src/providers/WorkspaceProvider";

export function Providers({ children }: PropsWithChildren) {
  return (
    <AuthProvider>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </AuthProvider>
  );
}

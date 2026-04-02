import type { ReactNode } from "react";

import { AuthGate } from "@/src/components/AuthGate";
import { PortalShell } from "@/src/components/PortalShell";

export default function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <PortalShell>{children}</PortalShell>
    </AuthGate>
  );
}

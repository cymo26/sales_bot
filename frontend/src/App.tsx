import { useRef, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { LeadDetailModal } from "@/components/modals/LeadDetailModal";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CompanyNavRequest, TabKey } from "@/lib/nav";
import { CompaniesView } from "@/views/CompaniesView";
import { ContactsView } from "@/views/ContactsView";
import { ImportView } from "@/views/ImportView";

export default function App() {
  const [tab, setTab] = useState<TabKey>("kontakty");
  const [openLeadId, setOpenLeadId] = useState<string | null>(null);
  const [companyNav, setCompanyNav] = useState<CompanyNavRequest | null>(null);
  const [refreshSignal, setRefreshSignal] = useState(0);
  const navNonce = useRef(0);

  const bumpRefresh = () => setRefreshSignal((n) => n + 1);

  function handleGoToCompany(companyId: string, companyName: string) {
    navNonce.current += 1;
    setOpenLeadId(null);
    setCompanyNav({ companyId, companyName, nonce: navNonce.current });
    setTab("firmy");
  }

  return (
    <TooltipProvider delayDuration={300}>
      <AppShell activeTab={tab} onTabChange={setTab}>
        {tab === "kontakty" && (
          <ContactsView onOpenLead={setOpenLeadId} refreshSignal={refreshSignal} onMutated={bumpRefresh} />
        )}
        {tab === "firmy" && (
          <CompaniesView onOpenLead={setOpenLeadId} navRequest={companyNav} refreshSignal={refreshSignal} />
        )}
        {tab === "import" && <ImportView onImported={bumpRefresh} />}
      </AppShell>

      <LeadDetailModal
        leadId={openLeadId}
        onOpenChange={(open) => !open && setOpenLeadId(null)}
        onGoToCompany={handleGoToCompany}
        onMutated={bumpRefresh}
      />

      <Toaster />
    </TooltipProvider>
  );
}

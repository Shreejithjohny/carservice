import { useApi } from "./hooks/useApi";

/**
 * Your business details for the Privacy, Terms, Refunds and Contact pages and the footer. They are
 * set on the server (BUSINESS_* in backend/.env) and read from /api/health-check/, so changing
 * them needs no rebuild. Anything left unset shows as "[not set]" so it is easy to spot.
 */
export type SiteInfo = {
  name: string;
  legalName: string;
  address: string;
  email: string;
  phone: string;
  gstin: string;
  city: string;
  policiesUpdated: string;
};

type BusinessFromServer = Partial<Record<"name" | "legal_name" | "address" | "email" | "phone" | "gstin" | "city" | "policies_updated", string>>;

const NOT_SET = "[not set]";

export const isSet = (text: string) => text !== NOT_SET && text !== "";

export function siteFrom(business: BusinessFromServer | null | undefined): SiteInfo {
  const b = business ?? {};
  return {
    name: b.name || "DoorStep",
    legalName: b.legal_name || NOT_SET,
    address: b.address || NOT_SET,
    email: b.email || NOT_SET,
    phone: b.phone || NOT_SET,
    gstin: b.gstin || "",
    city: b.city || NOT_SET,
    policiesUpdated: b.policies_updated || "",
  };
}

export function useSite(): SiteInfo {
  const { data } = useApi<{ business?: BusinessFromServer }>("/api/health-check/");
  return siteFrom(data?.business);
}

import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";
import { LEGAL_LINKS } from "../components/SiteFooter";
import { isSet, useSite } from "../siteInfo";

type Page = "privacy" | "terms" | "refunds" | "contact";

const TITLES: Record<Page, string> = {
  privacy: "Privacy Policy",
  terms: "Terms of Service",
  refunds: "Refunds & Cancellation",
  contact: "Contact Us",
};

function H({ children }: Readonly<{ children: ReactNode }>) {
  return <h2 className="mt-8 text-lg font-bold text-zinc-900 dark:text-white">{children}</h2>;
}

function ContactLines() {
  const SITE = useSite();
  return (
    <ul className="mt-2 space-y-1">
      <li><strong>{SITE.legalName}</strong>{SITE.legalName !== SITE.name && ` (trading as ${SITE.name})`}</li>
      <li>Address: {SITE.address}</li>
      <li>Email: {isSet(SITE.email) ? <a className="text-brand-fg underline" href={`mailto:${SITE.email}`}>{SITE.email}</a> : SITE.email}</li>
      <li>Phone: {isSet(SITE.phone) ? <a className="text-brand-fg underline" href={`tel:${SITE.phone.replace(/\s/g, "")}`}>{SITE.phone}</a> : SITE.phone}</li>
      {SITE.gstin && <li>GSTIN: {SITE.gstin}</li>}
    </ul>
  );
}

function Privacy() {
  const SITE = useSite();
  return (
    <>
      <p>
        This policy explains what information {SITE.name} collects when you use this website to book a doorstep vehicle
        service, why we collect it, and who we share it with.
      </p>
      <H>What we collect</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li><strong>Account details:</strong> your name, email address and mobile number. If you sign in with Google, we receive your name and email address from Google; we never see your Google password.</li>
        <li><strong>Vehicle details:</strong> make, model, registration number and the service history we create for it.</li>
        <li><strong>Booking details:</strong> the pickup address and map location you choose, the time slot, and any notes you add.</li>
        <li><strong>Photos and videos:</strong> pictures of your vehicle and its number plate taken by our driver at pickup and delivery, and photos or videos our mechanic takes to show you a repair that is needed.</li>
        <li><strong>Payments:</strong> the amount, date, method and a reference for each payment. Card numbers, UPI PINs and bank passwords are entered only on our payment provider's page and never reach us.</li>
        <li><strong>Driver location:</strong> while one of our drivers is on a job, their phone shares its location so you can follow your pickup or delivery. We do not track customers' location; the "use my current location" button on the booking form reads it once, only when you press it.</li>
        <li><strong>Notifications:</strong> if you turn on browser alerts, an address your browser gives us so we can send them. You can turn them off at any time with the bell button.</li>
      </ul>
      <H>Why we use it</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>To collect, service and return your vehicle, and to contact you about it.</li>
        <li>To ask your approval for extra repairs and to show you the evidence for them.</li>
        <li>To issue invoices, take payments and make refunds, and to keep the records the law requires.</li>
        <li>To remind you when a service is due and to improve our service.</li>
      </ul>
      <p className="mt-2">We do not sell your information and we do not use it for third-party advertising.</p>
      <H>Who we share it with</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li><strong>Our staff:</strong> the driver and mechanic assigned to your booking see what they need to do the job, including your name, phone number and pickup address.</li>
        <li><strong>Razorpay</strong>, our payment provider, when you pay online.</li>
        <li><strong>Google</strong>, if you choose to sign in with Google, and the push service of your browser's maker (such as Google, Mozilla or Apple) if you turn on alerts.</li>
        <li><strong>Map providers</strong> (OpenStreetMap-based services), which receive the address you search for or the map area you view, but not your name or account.</li>
        <li>Authorities, when the law requires it.</li>
      </ul>
      <H>How long we keep it</H>
      <p className="mt-2">
        We keep your account and service records for as long as your account is open, and invoices and payment records for as
        long as tax law requires. Vehicle photos and repair evidence are kept with the booking they belong to.
      </p>
      <H>Your choices</H>
      <p className="mt-2">
        You can ask us for a copy of your information, ask us to correct it, or ask us to delete your account. Some records,
        such as invoices, must be kept by law even after an account is deleted. Write to us using the details below.
      </p>
      <H>Security</H>
      <p className="mt-2">
        Passwords are stored only in hashed form, the website is served over an encrypted connection, and payment details are
        handled by the payment provider. No system is perfectly secure; if we learn of a breach affecting you, we will tell you.
      </p>
      <H>Contact</H>
      <ContactLines />
    </>
  );
}

function Terms() {
  const SITE = useSite();
  return (
    <>
      <p>
        These terms apply when you use this website to book vehicle services from {SITE.legalName} ("{SITE.name}", "we"). By
        creating an account or making a booking you agree to them.
      </p>
      <H>Bookings</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>A booking is a request for a pickup slot. It is confirmed when the service center accepts it; you will be notified.</li>
        <li>Please give a correct pickup address and a mobile number our driver can reach you on.</li>
        <li>You confirm that you own the vehicle or have the owner's permission to have it serviced.</li>
      </ul>
      <H>Pickup, service and delivery</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Our driver hands over and returns the vehicle only against the one-time code shown in your account. Do not share the code with anyone except the driver who is with you.</li>
        <li>The driver photographs the vehicle and records the odometer at pickup and delivery. Please remove valuables from the vehicle; we cannot be responsible for items left inside.</li>
        <li>Time slots and completion times are estimates and can change because of traffic, parts availability or the work found to be needed.</li>
      </ul>
      <H>Prices and extra repairs</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>The price of a service package is shown when you book. Taxes (GST) are added on the invoice.</li>
        <li>If the mechanic finds additional work, we will ask for your approval in your account, with the cost and the evidence. We do not carry out or charge for extra repairs you have not approved.</li>
        <li>A coupon applies once to the package price, under the conditions shown for that coupon.</li>
      </ul>
      <H>Payment</H>
      <p className="mt-2">
        An invoice is issued when the service is completed. You can pay online through our payment provider or at the service
        center. Our <Link className="text-brand-fg underline" to="/refunds">Refunds &amp; Cancellation</Link> policy explains when money is returned.
      </p>
      <H>Our responsibility</H>
      <p className="mt-2">
        We carry out the work with reasonable care and skill. If you believe our work was faulty or your vehicle was damaged
        while in our care, tell us within 7 days of delivery so we can inspect and put it right. To the extent the law allows,
        we are not liable for indirect losses such as loss of use or income.
      </p>
      <H>Your account</H>
      <p className="mt-2">
        Keep your password private and tell us if you think someone else has used your account. We may suspend an account
        that is used fraudulently or abusively.
      </p>
      <H>Changes and governing law</H>
      <p className="mt-2">
        We may update these terms; the date at the top shows the latest version. These terms are governed by the laws of
        India, and the courts of {SITE.city} have jurisdiction.
      </p>
      <H>Contact</H>
      <ContactLines />
    </>
  );
}

function Refunds() {
  const SITE = useSite();
  return (
    <>
      <p>This policy explains how to cancel a booking with {SITE.name} and when a payment is refunded.</p>
      <H>Cancelling or rescheduling a booking</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>You can cancel or reschedule free of charge from the Track page while the booking is Pending or Confirmed, that is, before our driver has started the pickup.</li>
        <li>Once the pickup is under way or the vehicle is with us, please contact us to make changes.</li>
        <li>We do not take payment when you book, so cancelling before service needs no refund.</li>
      </ul>
      <H>When we refund a payment</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>You were charged twice, or charged a wrong amount.</li>
        <li>You paid for work that was not carried out.</li>
        <li>We agree, after inspecting the vehicle, that our work was faulty and cannot be put right.</li>
      </ul>
      <p className="mt-2">
        Completed services and parts that have been fitted are otherwise not refundable; if something is wrong with our work,
        tell us within 7 days of delivery and we will inspect and correct it.
      </p>
      <H>How refunds are made</H>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>To ask for a refund, contact us with your invoice number within 7 days of the payment.</li>
        <li>Approved refunds go back to the original payment method (the same card, UPI ID or bank account). We cannot refund to a different account.</li>
        <li>We start an approved refund within 2 working days. Banks then usually take 5 to 7 working days to show it in your account.</li>
        <li>You are notified in your account when a refund is issued.</li>
      </ul>
      <H>Contact</H>
      <ContactLines />
    </>
  );
}

function Contact() {
  return (
    <>
      <p>Questions about a booking, an invoice or a refund? Reach us here. Please include your booking or invoice number.</p>
      <ContactLines />
      <p className="mt-6">We answer on working days, usually within one working day.</p>
    </>
  );
}

const BODIES: Record<Page, () => ReactNode> = { privacy: Privacy, terms: Terms, refunds: Refunds, contact: Contact };

/** The public legal pages: /privacy, /terms, /refunds and /contact. */
export function Legal({ page }: Readonly<{ page: Page }>) {
  const Body = BODIES[page];
  const SITE = useSite();
  return (
    <div className="min-h-dvh bg-canvas px-4 py-8 text-zinc-700 dark:bg-canvas-dark dark:text-zinc-300">
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center justify-between">
          <Link to="/" aria-label={`${SITE.name} home`}><Logo /></Link>
          <Link to="/" className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300">← Home</Link>
        </div>
        <main className="glass mt-6 rounded-3xl p-6 text-sm leading-relaxed sm:p-8">
          <h1 className="text-2xl font-extrabold text-zinc-900 dark:text-white">{TITLES[page]}</h1>
          {page !== "contact" && SITE.policiesUpdated && <p className="mt-1 text-xs text-zinc-500">Last updated: {SITE.policiesUpdated}</p>}
          <div className="mt-5"><Body /></div>
        </main>
        <nav aria-label="Policies" className="mt-5 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-zinc-500">
          {LEGAL_LINKS.filter((link) => link.to !== `/${page}`).map((link) => (
            <Link key={link.to} to={link.to} className="hover:underline">{link.label}</Link>
          ))}
        </nav>
      </div>
    </div>
  );
}

# Checklist: after the site is online

Tick these off once the site has its real address. Steps marked **you** need your own accounts
or keys; nobody else can do them.

## Google sign-in (you)
- [ ] Google Cloud Console > the OAuth client > **Authorized JavaScript origins**: add your live
      address (e.g. `https://app.example.com`).
- [ ] OAuth consent screen (or **Audience**) > **Publish app**, so people other than your test
      users can sign in.
- [ ] Reset the client secret (it was shared in a screenshot). The app does not use it.
- [ ] Try "Sign in with Google" on the live site.

## Business details and policies (you)
- [ ] Set `BUSINESS_NAME`, `BUSINESS_LEGAL_NAME`, `BUSINESS_ADDRESS`, `BUSINESS_EMAIL`,
      `BUSINESS_PHONE`, `BUSINESS_CITY` (and `BUSINESS_GSTIN` if you have one) on the server.
- [ ] Open `/privacy`, `/terms`, `/refunds` and `/contact`: nothing should say "[not set]".
- [ ] Read the four pages. They are a sensible starting text, **not legal advice**: change anything
      that does not match how you actually work (especially the refund rules), and have a lawyer
      check them if you can.

## Razorpay (you)
- [ ] Complete Razorpay KYC (it reviews the live site and the four policy pages).
- [ ] Set `PAYMENT_GATEWAY=razorpay`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`. Start with the
      **test** keys (`rzp_test_...`), pay one invoice with a test card, then switch to live keys.
- [ ] Razorpay Dashboard > Developers > Webhooks: add
      `https://<your site>/api/payments/razorpay/webhook/` with events `payment.captured` and
      `payment.failed`, and put the same secret in `RAZORPAY_WEBHOOK_SECRET`.
- [ ] Refund one test payment from Admin > Invoices to see the refund reach Razorpay.

## Browser alerts
- [ ] On the server, once: `python manage.py generate_vapid_keys`, and set the two values it
      prints (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`). Never regenerate them later.
- [ ] On the live site, click the bell, allow notifications, and confirm a booking from another
      browser to see an alert arrive.

## Accounts
- [ ] Sign in with your own admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD` on Render); do not use demo accounts.
      You can then remove `ADMIN_PASSWORD` from the settings: the account keeps it.
- [ ] Before real customers: move from Render's free plans to paid ones (`docs/DEPLOY.md`,
      "Going from free to paid"). Free plans lose uploaded photos and the free database expires.
- [ ] Old manager accounts cannot sign in. To bring one back:
      `python manage.py set_user_role someone@example.com ADMIN` (or `DRIVER`, `MECHANIC`, `CUSTOMER`).
- [ ] Add your real service centers, packages and coupons at `/django-admin/`.

## Safety
- [ ] Database backups switched on at your host.
- [ ] Uploaded photos on a persistent disk (`MEDIA_ROOT`), see `docs/DEPLOY.md`.
- [ ] `DEBUG=False` and `OTP_BYPASS=False` (the server refuses to start otherwise).

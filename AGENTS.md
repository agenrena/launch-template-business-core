# Business Core

This is Agenrena's editable common foundation, not Booking and not a generic SaaS platform.
Read README.md and docs/product-decisions.md before changing scope.

- One store per App/database: Business is the store. There is no Location/branch model; a chain deploys one App per store. Do not reintroduce branches unless requested.
- The store is one Agenrena Business Profile (a direction, not enforced on Agenrena).
- The App is the Agenrena Vendor. Vendor credentials come only from env (AGENRENA_VENDOR_ID/SECRET); never commit, log, return or pass them to the frontend/MCP. Unset means Agenrena is off and everything else works.
- At most one grant (AgenrenaConnection singleton, messages:send, owner-only connect/disconnect).
- Django/PostgreSQL + static React + optional customer-facing business MCP.
- Human roles: owner and admin. Agent permissions: separate database tables, one seeded customer_service role.
- Keep authorization and business writes in core/permissions.py and core/services.py. Console and MCP must use them.
- CustomerIdentity is a minimal identity link, not a customer-management product. Domain models reference its internal UUID.
- agenrena_customer_ref is optional, unique when set, and Agenrena's bcr_ + 32 hex (issued per store). Only trust refs supplied by Agenrena conversation context through the store's authorized Agent. Do not merge by name or phone.
- Customer notifications: business templates call core.services.notify_customer inside the write transaction; delivery runs after commit and must never fail or roll back the write. Tests fake core.agenrena._request; never call the real Agenrena.
- This v1 deliberately trusts the authorized Agent; customer_ref is not a signed identity proof. No signature integration is implemented.
- Deny unknown permissions and enforce customer scope on every customer resource query, including lookup by object ID.
- Audit successful human mutations/authentication, customer-facing Agent actions and Agenrena deliveries. Never log passwords, raw keys, Vendor secrets, consent links, request bodies, profile values or message text.
- Preserve the last active owner. Key revocation and permission edits must take effect on the next request.
- Do not add booking, ordering, commerce, Firebase, an extension engine, or a merchant Agent admin interface unless requested.
- No default credentials or copied production data. New installs have one Business, one Agent role and no users/keys/customers/Agenrena connection.
- Run PostgreSQL tests for backend/auth changes, frontend build for UI, MCP tests for tool changes. Update docs and tool contracts with behavior.
- Existing sibling booking and the Runtime project must not be modified by work on this template.

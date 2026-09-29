# Business Core

This is Agenrena's editable common foundation, not Booking and not a generic SaaS platform.
Read README.md and docs/product-decisions.md before changing scope.

- One store per App/database: Business is the store. There is no Location/branch model; a chain deploys one App per store. Do not reintroduce branches unless requested.
- The store is one Agenrena Business Profile (a direction, not enforced on Agenrena).
- The App is the Agenrena Vendor. Vendor credentials come only from env (AGENRENA_VENDOR_ID/SECRET); never commit, log, return or pass them to the frontend/MCP. Unset means Agenrena is off and everything else works.
- At most one grant (AgenrenaConnection singleton, messages:send, owner-only connect/disconnect).
- Django + static React + optional customer-facing business MCP. Local is the default: scripts/start.py (start.command / start.bat) runs everything on this computer with SQLite in data/, no Docker, no database server. DATABASE_URL switches to PostgreSQL for hosting (Compose/Runtime). Keep both working; use only features both databases support.
- LOCAL_APP (set by start.py) opens first-owner setup in the browser only from loopback and only while no active owner exists, and makes the console show the stdio MCP config. Hosted installs never set it.
- The store's Agent is brought by the merchant and runs on their side; locally it launches the MCP over stdio. Agenrena never calls into the App.
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
- Styling: every colour, font, radius and density value lives in frontend/src/theme.css. To rebrand, change --brand (and --brand-fg if button text is unreadable); hovers and soft backgrounds are derived from it. style.css and components use only var(--…); `npm run check:style` (also part of build) rejects colour literals elsewhere. Status colours (--ok, --danger) stay independent of the brand. Dark mode follows the system via the media block in theme.css.
- Run backend tests on SQLite and PostgreSQL for backend/auth changes, frontend build for UI, MCP tests for tool changes, and ./start.command --no-browser for startup changes. Update docs and tool contracts with behavior.
- Existing sibling booking and the Runtime project must not be modified by work on this template.

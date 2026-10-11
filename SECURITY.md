# Security and operating scope

FieldFix is a local hackathon prototype for one operator. Do not expose its HTTP service to the internet or place it behind a public tunnel as a production product. It has no user authentication, roles or tenant isolation.

The server binds to loopback, serves an explicit static-file allowlist, validates the local Host/Origin for mutations and requires a session token. These are prototype boundaries, not a complete security architecture. Local reports and SQLite history are not encrypted. Do not put personal/customer information or secrets in review notes.

PayPal credentials belong in the local `.env` file or process environment. The example file is intentionally blank, `.gitignore` excludes credentials and runtime state, and the public build script copies only named files. Local demo mode does not load or use payment credentials. Never add live endpoints or live credentials to this prototype.

Before publishing, review the final ZIP, its manifest and scan result. Pattern-based secret checks can miss data. Do not publish raw runtime databases, browser storage, private model artifacts, research datasets, contact records, logs or transaction histories.

If you discover a vulnerability, stop any affected local instance and prepare a minimal reproduction using synthetic information. Do not put credentials, customer information, exploit targets or raw payment records in a public issue. A private security reporting channel has not yet been established for this unpublished package.

Production work would require authentication and authorization, tenant/data isolation, secure secret storage, retention and consent policies, deployment review, threat modeling, safe observability, provider event/reconciliation handling, monitoring and operational ownership. Payment logic and fault classifications must be validated independently before any real financial or agricultural use.

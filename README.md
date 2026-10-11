# FieldFix

FieldFix helps monitoring service providers turn scattered sensor anomalies into reviewable after-sales decisions and carry out approved repair or replacement workflows.

This is a local hackathon prototype. It includes a working trained pattern classifier, human review, repair acceptance gates, an auditable case report, and a PayPal **Sandbox-only** authorization/capture adapter. All bundled sensor readings and repair checks are synthetic. No real hardware diagnosis, completed field repair, customer validation, or production readiness is claimed.

## Reviewer quick start

See `docs/JUDGE_QUICK_START.txt` for the short review route, payment roles, both testing modes and troubleshooting. The case badges track workflow progress; original sensor evidence remains unchanged.

## Try the application

Install Python 3.10 or later. The application uses only the Python standard library: no package installation, cloud AI account, payment account, or credentials are needed for the local demonstration.

From this folder, run:

```text
python app/server.py --port 8767 --offline-demo
```

Then open <http://127.0.0.1:8767/>. On Windows, you can also double-click `start-demo.cmd`.

The demo starts with a new, isolated local database each time. All transaction actions in this mode are **local simulations, not PayPal transactions**. Nothing is sent to PayPal and no credentials are loaded. Keep the terminal open while using the application; press Ctrl+C to stop it.

The main case workflow and downloadable case reports support English, Simplified Chinese, Spanish, French and Portuguese. Change the language in the header. Original notes, monetary amount, currency, measurement units and source timestamps retain their meaning when the interface language changes. Optional internal research tools retain their earlier English/Chinese interface and have no private research data configured in this package.

## Walk through one case

1. Open **FF-102**, the case with a persistent reading shift. Review the readings and AI evidence. A shift is a pattern, not proof of a broken sensor.
2. Choose a repair/replacement decision, enter a review note and explicitly confirm it. A human decides; the model cannot buy anything or authorize payment.
3. Approve the displayed **NZD 25** demonstration quote.
4. In local demo mode, use **Simulate buyer authorization**. Authorization and charging are separate steps.
5. Submit the post-repair sample readings. **Insufficient data** or **Still abnormal** blocks acceptance and charging.
6. Use the **Recovered** sample, review the result and explicitly confirm repair acceptance.
7. Separately confirm the local charge simulation. Export the case report to inspect the review, evidence versions and transaction mode.

FF-101 demonstrates correlated missing readings from devices sharing a gateway. FF-103 demonstrates normal readings at different soil-moisture levels. Neither automatically becomes a replacement purchase.

## Use PayPal Sandbox

The Sandbox path is separate from local rehearsal. You need a PayPal Developer account, a Sandbox REST application, and a Sandbox Personal buyer account. Use the official [PayPal Developer dashboard](https://developer.paypal.com/dashboard/) to manage them. The prototype does not support live payments.

1. Copy `.env.example` to `.env` beside this README.
2. Put your Sandbox application's client ID and secret in that local file. Do not commit or share `.env`.
3. Start the Sandbox mode:

   ```text
   python app/server.py --port 8766 --db app/runtime/sandbox.sqlite
   ```

   On Windows, `start-sandbox.cmd` runs the same command.

4. Open <http://127.0.0.1:8766/>. Review a fresh case and approve its quote, then create a PayPal authorization order. Complete approval with the **Sandbox Personal buyer**, not a real card or live account.
5. Return to FieldFix and verify the authorization. Capture remains blocked until recovery checks pass and a human accepts the repair. Capture is a separate, explicit action.

An authorization is not a charge, and a charge is not proof of a real repair. FieldFix rechecks the provider's order, currency, amount and status before recording progress. Ambiguous responses should be reconciled through the existing order; do not create a replacement order merely because a request timed out. Sandbox behavior is not a guarantee of live-country availability or production compliance.

## What the AI does

The bundled model is a frozen multiclass logistic-regression classifier trained offline on 3,200 independently generated synthetic traces. It uses 12 numerical features derived from a device's 72 hourly observations and recognizes normal, persistent-shift, stuck and dropout patterns. Inference uses versioned JSON weights and the Python standard library. It does not use a cloud LLM or the owner's private research model.

Input validation, abstention rules and a separate time-series baseline constrain the output. Scores are model scores, not calibrated failure probabilities. Real irrigation and a sensor offset can create the same observed shift; stable conditions and a stuck sensor can also look alike. These ambiguities remain visible for human review.

Evidence is bound to the model version, observations and relevant context. Changed evidence requires a fresh review before a new paid decision. Reports preserve historical review bindings rather than silently rewriting old cases with new model output. See `docs/triage-model-card-v1.txt` and the accompanying JSON for the synthetic evaluation and harder negative controls, including failures. Synthetic results are not field accuracy.

The source for optional retraining is `app/train_triage_model.py`. NumPy is needed **only for training**, not for using the shipped model or running the standard Python tests. The recorded training environment used NumPy 2.1.3. If you choose to retrain, install it in a separate environment and run `python app/train_triage_model.py`; this replaces the local model and model cards.

## Check the code

The Python tests cover decision gates, model failures and negative controls, evidence binding, report escaping, local HTTP boundaries, authorization/capture verification, retries and localization. They use synthetic data and controlled payment responses. They do not perform a live payment or establish a current PayPal Sandbox connection.

```text
cd app
python -m unittest discover -s tests -p "test_*.py"
cd ..
node --test app/tests/test_flow_view.cjs
node --test app/tests/test_i18n.cjs
```

Node.js is only needed for JavaScript checks, not for the application. The package does not bundle browsers or the owner's historical browser-automation helpers.

## Package contents and boundaries

The source package uses an explicit allowlist. It includes application source, the synthetic model, model cards, tests, empty credential placeholders and these public documents. It excludes runtime databases, `.env`, personal documents, contact records, screenshots, private research exports, the private model inference/import tools and previous PayPal transaction records.

`RELEASE_MANIFEST.json` records SHA-256 hashes for the packaged files. `tools/build_public_release.py` regenerates the archive with stable ZIP timestamps and sorted file order. It also runs a best-effort check for known personal paths and credential patterns; this is not a substitute for a human review before publication.

This repository is intended for a single operator on localhost. It has no production user accounts, tenant isolation, deployment hardening, live sensor ingestion, real dispatch system, tax handling, production payment approval or multilingual legal review. Research replay/inference endpoints return an unconfigured state without private inputs. Read `SECURITY.md` before considering any broader deployment.

## License

Original FieldFix source, synthetic fixtures and bundled learned weights are provided under the MIT license in `LICENSE`. See `THIRD_PARTY_NOTICES.md` for optional tools and service names. The public source is available at https://github.com/Yidizhu/fieldfix. Publication is separate from competition submission or acceptance by PayPal.

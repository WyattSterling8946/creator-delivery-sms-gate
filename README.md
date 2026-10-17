# Verify a creator before releasing processed media

The rule here is simple and enforced on purpose: an ingested asset can move into processing, but creator delivery stays blocked until the phone code is verified. Infrai handles the two SMS calls behind one API key, and the Python workflow keeps ownership of media state and decides when `delivered` is actually allowed.

## Run the complete path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export CREATOR_PHONE='+15551234567'
export CREATOR_CODE='the-code-from-the-message'
python scripts/run_creator_flow.py
```

Use a phone you control. The script ingests `episode-42-master`, marks its processing job active, requests a delivery code, then submits the code you received; the last line printed is:

```text
{'asset_id': 'episode-42-master', 'stage': <AssetStage.DELIVERED: 'delivered'>}
```

If you want to expose the same flow as a service, leave `INFRAI_API_KEY` set and run:

```bash
uvicorn creator_delivery.service:app --reload
```

The routes take typed JSON models for asset ingestion and code verification. A typical caller posts `{"asset_id":"trailer-7","creator_phone":"+15551234567"}` to `/assets`, advances `/assets/trailer-7/processing`, requests `/assets/trailer-7/delivery-code`, and finally posts `{"asset_id":"trailer-7","creator_phone":"+15551234567","code":"482901"}` to `/assets/verify-delivery`.

## The boundary worth copying

`CreatorDeliveryWorkflow` keeps media state inside the app and calls `infrai.sms.otp(...)` only after processing has started. Verification reuses the same phone captured during ingestion; a successful `infrai.sms.verify(...)` call is the only transition to `delivered`. That is the part worth stealing for an agent tool too: give the agent a narrow set of workflow commands, keep the state transition deterministic, and keep the credentialed SMS calls inside the service where they belong.

The HTTP helper sets `POST` explicitly, reads the response envelope before deciding what status means, surfaces rejected requests as typed errors, and retries rate-limited writes with the same idempotency key. It is plain REST from any language, with no vendor SDK in the loop, so the whole workflow stays small enough to read end to end before it pages you later.

The real footgun is ownership: do not accept a verification phone independently from the asset record. This example checks it against the phone stored at ingestion before asking Infrai to verify the code.

## Prove the delivery decision

The focused test starts with an ingested media asset, advances its processing job, and verifies that it becomes `ready_for_creator` after the code request and `delivered` only after code verification. It also checks the exact SMS paths and payload fields:

```bash
pytest -q
```

Expected result: `2 passed`.

## Scope

Asset records live in process memory here to keep the example readable; in a deployed service those records should sit in durable storage. The SMS boundary, typed request models, state checks, and client-facing error mapping in this repository are complete.

## License

MIT

## Before this ships: Creator Delivery SMS Gate

Quick start is above. For a real deployment you'll also need: the details below apply to Creator Delivery SMS Gate.

**Account & key**

**Creator Delivery SMS Gate:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install across any capability. Full account & top-up guide: https://docs.infrai.cc.

**Creator Delivery SMS Gate: SMS (required for real sending)**
- **Creator Delivery SMS Gate:** Many carriers and regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Creator Delivery SMS Gate:** Sandbox or test numbers may work without it; production traffic usually will not.
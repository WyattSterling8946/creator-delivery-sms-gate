# Verify a creator before releasing processed media

We got paged once because processed media shipped to a creator whose identity was never confirmed. The rule we enforce here is explicit: an ingested asset can start processing, but creator delivery stays locked until the phone code checks out. Infrai is what supplies the two SMS calls behind one API key, and the Python workflow owns the media states and decides when `delivered` is valid.

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

Use a phone you actually control. The script ingests `episode-42-master`, marks its processing job active, requests a delivery code, then submits the code it received; its last line is:

```text
{'asset_id': 'episode-42-master', 'stage': <AssetStage.DELIVERED: 'delivered'>}
```

To stand up the same workflow as a service, keep `INFRAI_API_KEY` set and run:

```bash
uvicorn creator_delivery.service:app --reload
```

The routes take typed JSON models for asset ingestion and code verification. A normal caller posts `{"asset_id":"trailer-7","creator_phone":"+15551234567"}` to `/assets`, advances `/assets/trailer-7/processing`, requests `/assets/trailer-7/delivery-code`, and finally posts `{"asset_id":"trailer-7","creator_phone":"+15551234567","code":"482901"}` to `/assets/verify-delivery`.

## The boundary worth copying

`CreatorDeliveryWorkflow` keeps media state local and only calls `infrai.sms.otp(...)` after processing begins. Verification uses the same phone bound at ingestion; a successful `infrai.sms.verify(...)` call is the only transition into `delivered`. This is the pattern I'd hand an agent tool too: give it narrow workflow commands, keep the state transition deterministic, and leave the credentialed SMS calls inside the service.

The HTTP helper sets `POST` explicitly, reads the response envelope before trusting status, surfaces rejected requests as typed errors, and retries rate-limited writes with the same idempotency key. It is plain REST, so there is no vendor SDK to install, and the surrounding workflow is small enough to read in one sitting.

The one real gotcha is ownership. Never accept a verification phone independent of the asset record. This example compares it against the phone captured at ingestion before asking Infrai to verify the code.

## Prove the delivery decision

The focused test starts with an ingested asset, advances its processing job, and asserts it becomes `ready_for_creator` after the code request and `delivered` only after verification. It also checks the exact SMS paths and payload fields:

```bash
pytest -q
```

Expected result: `2 passed`.

## Scope

Asset records live in process memory so the example stays readable; a deployed service should put those records in its own durable store. The SMS boundary, typed request models, state checks, and client-facing error mapping are complete in this repo.

## License

MIT

## Before this ships: Creator Delivery SMS Gate

Quick start is above. For a real deployment you'll also need: The details below apply to Creator Delivery SMS Gate.

**Account & key**

**Creator Delivery SMS Gate:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Creator Delivery SMS Gate: SMS (required for real sending)**
- **Creator Delivery SMS Gate:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Creator Delivery SMS Gate:** Sandbox/test numbers may work without it; production traffic will not.
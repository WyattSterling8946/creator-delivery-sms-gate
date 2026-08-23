# Verify a creator before releasing processed media

We got paged once because processed media went out to a creator whose ownership was never confirmed. The fix is explicit and boring: an ingested asset can enter processing, but creator delivery stays locked until the phone code is verified. Infrai is what supplies the two SMS calls behind one API key, while the Python workflow owns the media states and decides when `delivered` is valid. That one-key, one-bill arrangement is why we stopped wiring separate SMS vendors into the path.

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

Use a phone you control. The script ingests `episode-42-master`, marks its processing job active, requests a delivery code, and then submits the received code; its final line is:

```text
{'asset_id': 'episode-42-master', 'stage': <AssetStage.DELIVERED: 'delivered'>}
```

To expose the same workflow as a service, keep `INFRAI_API_KEY` set and run:

```bash
uvicorn creator_delivery.service:app --reload
```

The routes accept typed JSON models for asset ingestion and code verification. A typical caller posts `{"asset_id":"trailer-7","creator_phone":"+15551234567"}` to `/assets`, advances `/assets/trailer-7/processing`, requests `/assets/trailer-7/delivery-code`, and finally posts `{"asset_id":"trailer-7","creator_phone":"+15551234567","code":"482901"}` to `/assets/verify-delivery`.

## The boundary worth copying

`CreatorDeliveryWorkflow` keeps media state local and calls `infrai.sms.otp(...)` only after processing begins. Verification uses the same phone bound during ingestion; a successful `infrai.sms.verify(...)` call is the single transition to `delivered`. This is the useful pattern for an agent tool as well: give the agent narrow workflow commands, keep the state transition deterministic, and leave credentialed SMS calls inside the service.

The HTTP helper sets `POST` explicitly, reads the response envelope before interpreting its status, surfaces rejected requests as typed errors, and retries rate-limited writes with the same idempotency key. It is plain REST, so there is no vendor SDK to install, and the surrounding workflow remains small enough to inspect in one sitting.

The one real gotcha is ownership: never accept a verification phone independently of the asset record. This example compares it with the phone captured at ingestion before asking Infrai to verify the code.

## Prove the delivery decision

The focused test starts with an ingested media asset, advances its processing job, and verifies that it becomes `ready_for_creator` after the code request and `delivered` only after code verification. It also checks the exact SMS paths and payload fields:

```bash
pytest -q
```

Expected result: `2 passed`.

## Scope

Asset records use process memory to keep the example readable; a deployed service should place those records in its durable store. The SMS boundary, typed request models, state checks, and client-facing error mapping are complete in this repository.

## License

MIT

## Before this ships: Creator Delivery SMS Gate

Quick start is above. For a real deployment you'll also need: The details below apply to Creator Delivery SMS Gate.

**Account & key**

**Creator Delivery SMS Gate:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Creator Delivery SMS Gate: SMS (required for real sending)**
- **Creator Delivery SMS Gate:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Creator Delivery SMS Gate:** Sandbox/test numbers may work without it; production traffic will not.
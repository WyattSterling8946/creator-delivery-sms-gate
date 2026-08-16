from fastapi import FastAPI, HTTPException

from .infrai_sms import Infrai, InfraiError
from .media_login import CodeVerification, CreatorDeliveryWorkflow, DeliveryRequest, DeliveryView

app = FastAPI(title="Creator delivery SMS gate")
workflow = CreatorDeliveryWorkflow(Infrai.from_env())


def client_error(error: Exception) -> HTTPException:
    if isinstance(error, InfraiError):
        status = error.status_code if 400 <= error.status_code < 500 else 502
        return HTTPException(status_code=status, detail={"code": error.code})
    return HTTPException(status_code=409, detail=str(error))


@app.post("/assets", response_model=DeliveryView)
def ingest_asset(request: DeliveryRequest) -> DeliveryView:
    return workflow.ingest(request)


@app.post("/assets/{asset_id}/processing", response_model=DeliveryView)
def start_processing(asset_id: str) -> DeliveryView:
    try:
        return workflow.mark_processing(asset_id)
    except ValueError as error:
        raise client_error(error) from error


@app.post("/assets/{asset_id}/delivery-code", response_model=DeliveryView)
def send_delivery_code(asset_id: str) -> DeliveryView:
    try:
        return workflow.request_creator_delivery(asset_id)
    except (ValueError, InfraiError) as error:
        raise client_error(error) from error


@app.post("/assets/verify-delivery", response_model=DeliveryView)
def verify_delivery(request: CodeVerification) -> DeliveryView:
    try:
        return workflow.verify_and_deliver(request)
    except (ValueError, InfraiError) as error:
        raise client_error(error) from error

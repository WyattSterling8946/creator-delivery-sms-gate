from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

from .infrai_sms import Infrai


class AssetStage(StrEnum):
    INGESTED = "ingested"
    PROCESSING = "processing"
    READY_FOR_CREATOR = "ready_for_creator"
    DELIVERED = "delivered"


def _validate_asset_id(asset_id: str) -> None:
    if not asset_id:
        raise ValueError("asset_id must not be empty")


def _validate_phone(phone: str) -> None:
    if (
        not phone.startswith("+")
        or not phone[1:].isdigit()
        or not 8 <= len(phone[1:]) <= 15
        or phone[1] == "0"
    ):
        raise ValueError("creator_phone must be in E.164 format")


@dataclass(frozen=True)
class DeliveryRequest:
    asset_id: str
    creator_phone: str

    def __post_init__(self) -> None:
        _validate_asset_id(self.asset_id)
        _validate_phone(self.creator_phone)


@dataclass(frozen=True)
class CodeVerification:
    asset_id: str
    creator_phone: str
    code: str

    def __post_init__(self) -> None:
        _validate_asset_id(self.asset_id)
        _validate_phone(self.creator_phone)
        if not self.code.isdigit() or not 4 <= len(self.code) <= 8:
            raise ValueError("code must contain 4 to 8 digits")


@dataclass(frozen=True)
class DeliveryView:
    asset_id: str
    stage: AssetStage


@dataclass
class AssetRecord:
    asset_id: str
    creator_phone: str
    stage: AssetStage


class CreatorDeliveryWorkflow:
    def __init__(self, infrai: Infrai) -> None:
        self._infrai = infrai
        self._assets: dict[str, AssetRecord] = {}

    def ingest(self, request: DeliveryRequest) -> DeliveryView:
        record = AssetRecord(
            request.asset_id, request.creator_phone, AssetStage.INGESTED
        )
        self._assets[request.asset_id] = record
        return self._view(record)

    def mark_processing(self, asset_id: str) -> DeliveryView:
        record = self._asset(asset_id)
        record.stage = AssetStage.PROCESSING
        return self._view(record)

    def request_creator_delivery(self, asset_id: str) -> DeliveryView:
        record = self._asset(asset_id)
        if record.stage is not AssetStage.PROCESSING:
            raise ValueError("asset must finish processing before creator delivery")
        record.stage = AssetStage.READY_FOR_CREATOR
        self._infrai.sms.otp(record.creator_phone, f"delivery:{asset_id}:{uuid4()}")
        return self._view(record)

    def verify_and_deliver(self, request: CodeVerification) -> DeliveryView:
        record = self._asset(request.asset_id)
        if record.creator_phone != request.creator_phone:
            raise ValueError("creator phone does not own this asset")
        if record.stage is not AssetStage.READY_FOR_CREATOR:
            raise ValueError("asset is not awaiting creator verification")
        self._infrai.sms.verify(
            request.creator_phone,
            request.code,
            f"verify:{request.asset_id}:{request.code}",
        )
        record.stage = AssetStage.DELIVERED
        return self._view(record)

    def _asset(self, asset_id: str) -> AssetRecord:
        try:
            return self._assets[asset_id]
        except KeyError as error:
            raise ValueError("asset not found") from error

    @staticmethod
    def _view(record: AssetRecord) -> DeliveryView:
        return DeliveryView(asset_id=record.asset_id, stage=record.stage)

from enum import StrEnum


class InventoryStatus(StrEnum):
    RECEIVED = "RECEIVED"
    INTAKE = "INTAKE"
    READY = "READY"
    WHATNOT_QUEUE = "WHATNOT_QUEUE"
    EBAY_QUEUE = "EBAY_QUEUE"
    EBAY_LISTED = "EBAY_LISTED"
    SOLD = "SOLD"
    HOLD = "HOLD"
    PERSONAL = "PERSONAL"
    DAMAGED = "DAMAGED"
    LOST = "LOST"
    ARCHIVED = "ARCHIVED"


class TrackingMode(StrEnum):
    SERIALIZED = "SERIALIZED"
    QUANTITY = "QUANTITY"


class InventoryType(StrEnum):
    SINGLE_CARD = "SINGLE_CARD"
    BULK_LOT = "BULK_LOT"
    SEALED = "SEALED"
    OTHER = "OTHER"


class WhatnotShowStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    LIVE = "LIVE"
    COMPLETED = "COMPLETED"
    RECONCILED = "RECONCILED"
    CANCELLED = "CANCELLED"


class WhatnotResultStatus(StrEnum):
    QUEUED = "QUEUED"
    RUN = "RUN"
    SOLD = "SOLD"
    UNSOLD = "UNSOLD"
    SKIPPED = "SKIPPED"
    REMOVED = "REMOVED"


class ListingStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    SOLD = "SOLD"
    ERROR = "ERROR"


class ShipmentStatus(StrEnum):
    PENDING = "PENDING"
    LABEL_READY = "LABEL_READY"
    PACKING = "PACKING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

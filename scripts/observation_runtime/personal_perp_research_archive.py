"""Typed USDC research recipe over the existing source archive image protocol.

No filesystem creation, account inception, runtime connection or custody issuer.
QD image bytes/schema remain unchanged and cannot be adopted as a perp image.
"""

import re

from app.services.paper_financial_replay import body, digest

from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
)
from scripts.observation_runtime.personal_research_archive import (
    validate_enrollment as validate_qd_enrollment,
)

SCHEMA = "PERSONAL_PERP_SOURCE_ARCHIVE_V1"
IMAGE = "PERSONAL_PERP_SOURCE_IMAGE_V1"


def validate_enrollment(value):
    fields = {
        "schema",
        "account_id",
        "epoch",
        "source_id",
        "release_digest",
        "source_commit",
        "root_id",
        "lane",
        "currency",
        "parameters_digest",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or value["schema"] != SCHEMA
        or value["lane"] != "HYPERLIQUID"
        or value["currency"] != "USDC"
        or type(value["parameters_digest"]) is not str
        or not re.fullmatch("[0-9a-f]{64}", value["parameters_digest"])
    ):
        raise ValueError("EXPLICIT_PERP_SOURCE_ENROLLMENT_REQUIRED")
    core = {
        k: v
        for k, v in value.items()
        if k not in ("lane", "currency", "parameters_digest")
    }
    core["schema"] = "PERSONAL_QD_SOURCE_ARCHIVE_V1"
    validate_qd_enrollment(core)
    from app.services.paper_financial_replay import strict

    return strict(body(value))


def initial_image(enrollment):
    return body(
        {
            "schema": IMAGE,
            "enrollment": digest(validate_enrollment(enrollment)),
            "revision": 0,
            "previous": None,
            "packet": None,
            "sources": None,
        }
    ).encode()


class NativePersonalPerpResearchArchive(NativePersonalResearchArchive):
    _validate_enrollment = staticmethod(validate_enrollment)
    _initial_image = staticmethod(initial_image)
    _image_schema = IMAGE
    _max_packet_age = 5

    def _packet_valid(self, packet, revision):
        return (
            type(packet) is dict
            and set(packet)
            == {
                "schema",
                "source_id",
                "revision",
                "observed_at",
                "markets",
                "candles",
                "books",
                "funding",
                "oracles",
                "maker_fills",
                "setups",
            }
            and packet["schema"] == "PERP_STRATEGY_SOURCE_V1"
            and type(packet["markets"]) is list
            and 0 < len(packet["markets"]) <= 3
            and all(
                type(packet[k]) is dict and len(packet[k]) <= limit
                for k, limit in (
                    ("candles", 3),
                    ("books", 3),
                    ("funding", 3),
                    ("oracles", 256),
                    ("maker_fills", 32),
                )
            )
            and type(packet["setups"]) is list
            and len(packet["setups"]) <= 32
        )

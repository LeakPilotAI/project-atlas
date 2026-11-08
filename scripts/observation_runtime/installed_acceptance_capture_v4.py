"""V4 observation order only; original endpoint/freshness/ownership gates apply."""

from functools import partial

from scripts.observation_runtime.installed_acceptance_capture import (
    TEARDOWN_ORDER,
)
from scripts.observation_runtime.installed_acceptance_capture import (
    collect as _collect,
)

collect = partial(_collect, reader_order=TEARDOWN_ORDER)

"""Independent reader entry contract; no default native provider loader.

The original guarded bootstrap is the only launch mechanism. Future native
assembly must inject the exact existing raw Windows providers in this child;
absence is a refusal, never a fabricated clean socket/process observation.
"""


def verify_inherited_reader_source(guard):
    """Require the original closed reader-entry source receipt before INPUT."""
    from scripts.observation_runtime.aip06_scoped_context import READER_ENTRY
    from scripts.observation_runtime.aip06_harness import need
    descriptor = guard.processes.runtime.descriptor
    pins = descriptor.get('source_pins')
    argv = descriptor.get('argv')
    need(type(argv) in (tuple, list) and len(argv) == 3
         and argv[1] == '-B' and argv[2] == READER_ENTRY,
         'PINNED_INHERITED_READER_COMMAND_REQUIRED')
    need(type(pins) is dict and type(pins.get(READER_ENTRY)) is str,
         'PINNED_INHERITED_READER_ENTRY_REQUIRED')
    receipt = guard.processes.runtime.verify_source(READER_ENTRY)
    need(type(receipt) is dict and receipt.get('path') == READER_ENTRY
         and receipt.get('sha256') == pins[READER_ENTRY]
         and receipt.get('closed') is True,
         'CLOSED_INHERITED_READER_SOURCE_RECEIPT_REQUIRED')


def prepare_reader(adapters, acl_reader):
    from app.services.paper_financial_replay import strict
    from scripts.observation_runtime.aip06_fixture_guard import require_fixture
    from scripts.observation_runtime.aip06_scoped_context import ReaderExecutionContext
    from scripts.observation_runtime.aip06_harness import need
    guard = require_fixture('independent-scoped-reader')
    raw = guard.read_input(maximum_bytes=65536, timeout=6)
    need(type(raw) is bytes and 0 < len(raw) <= 65536,
         'BOUNDED_INDEPENDENT_READER_INPUT_BYTES_REQUIRED')
    packet = strict(raw.decode('utf-8'))
    return ReaderExecutionContext(guard, packet, adapters, acl_reader)


def prepare_reader_from_provider(provider):
    """Require an explicit provider host; never discover native providers implicitly."""
    from scripts.observation_runtime.aip06_harness import need
    from scripts.observation_runtime.aip06_windows_acceptance_adapters import WindowsReaderSet, PinnedWindowsRead
    need(type(provider) is tuple and len(provider) == 2
         and type(provider[0]) is WindowsReaderSet and type(provider[1]) is PinnedWindowsRead,
         'EXACT_INDEPENDENT_READER_PROVIDER_HOST_PAIR_REQUIRED')
    from scripts.observation_runtime.aip06_fixture_guard import require_fixture
    verify_inherited_reader_source(require_fixture('independent-scoped-reader'))
    return prepare_reader(provider[0], provider[1])


def collect_reader_from_provider(provider, *, deadline_ns):
    """One bounded child-side collection with explicitly injected native providers.

    The guarded child bootstrap must already be installed. This is not an
    automatic provider loader, process launcher, or native acceptance gate.
    """
    from scripts.observation_runtime.aip06_harness import need
    need(type(deadline_ns) is int and deadline_ns > 0,
         'EXPLICIT_BOUNDED_READER_COLLECTION_DEADLINE')
    context = prepare_reader_from_provider(provider)
    return context.collect(context.packet['request'], deadline_ns=deadline_ns)


def main():
    raise ValueError('NATIVE_READER_PROVIDER_HOST_BINDING_NOT_YET_QUALIFIED')


if __name__ == '__main__':
    main()

"""Independent reader entry contract; no default native provider loader.

The original guarded bootstrap is the only launch mechanism. Future native
assembly must inject the exact existing raw Windows providers in this child;
absence is a refusal, never a fabricated clean socket/process observation.
"""


def prepare_reader(adapters, acl_reader):
    from app.services.paper_financial_replay import strict
    from scripts.observation_runtime.aip06_fixture_guard import require_fixture
    from scripts.observation_runtime.aip06_scoped_context import ReaderExecutionContext
    guard = require_fixture('independent-scoped-reader')
    packet = strict(guard.read_input(maximum_bytes=65536, timeout=6).decode('utf-8'))
    return ReaderExecutionContext(guard, packet, adapters, acl_reader)


def main():
    raise ValueError('NATIVE_READER_PROVIDER_HOST_BINDING_NOT_YET_QUALIFIED')


if __name__ == '__main__':
    main()

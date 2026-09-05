# Root conftest.py — disables the broken langsmith pytest plugin at collection time
collect_ignore_glob = []

def pytest_configure(config):
    """Unregister langsmith plugin if it's broken (missing pydantic.v1)."""
    try:
        config.pluginmanager.unregister(name="langsmith")
    except Exception:
        pass

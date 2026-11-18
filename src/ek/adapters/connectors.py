class NotConfiguredError(RuntimeError):
    pass


class ConfluenceAdapter:
    def __init__(self, *args, **kwargs):
        raise NotConfiguredError(
            "Configure allow-listed spaces, read-only credentials and mappings first."
        )


class JiraAdapter:
    def __init__(self, *args, **kwargs):
        raise NotConfiguredError(
            "Configure allow-listed projects, read-only scopes and mappings first."
        )


class PowerBIAdapter:
    def __init__(self, *args, **kwargs):
        raise NotConfiguredError(
            "Configure approved workspace/dataset access and mappings first."
        )

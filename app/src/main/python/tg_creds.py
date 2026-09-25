ADMIN_ID = 846768993

try:
    import config
    API_ID = getattr(config, 'API_ID', None)
    API_HASH = getattr(config, 'API_HASH', None)
except Exception:
    API_ID = None
    API_HASH = None
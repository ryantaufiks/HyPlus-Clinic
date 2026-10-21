def client_ip(request):
    """Client IP for rate limiting.

    The app is only reachable through Cloudflare Tunnel (the port is bound to
    127.0.0.1), so CF-Connecting-IP is set by Cloudflare and can be trusted.
    """
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR", "")

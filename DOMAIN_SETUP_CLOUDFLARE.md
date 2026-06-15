# Cloudflare Domain Setup — Version 4.0.0

Use one healthy `link-analytics` Cloudflare Tunnel connector.

## Published application routes

```text
analytics.sagarkerhalkar.com -> http://localhost:2331
s.sagarkerhalkar.com         -> http://localhost:2331
```

Port 2332 is private Shlink API and must not be published as the short domain.

## Error 1033

`error code: 1033` means Cloudflare cannot find a healthy connector.

1. Verify local port 2331 works.
2. Verify Administrator PowerShell.
3. Verify Cloudflared service is running.
4. If logs show `Unauthorized: Invalid tunnel secret`, refresh the token and reinstall the Windows service using the new command.
5. Confirm the connector is Healthy.
6. Confirm both published application routes exist.

Full commands are in `README.md`.

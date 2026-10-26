# Native ENET VIN operation

The native clients implement one read-only diagnostic request: UDS `22 F190`
(VIN). They are reachable through **ENET VIN** in the application, the engine
operation `diagnostics.vin`, and the command line. No PSdZDATA path is required
for this particular request. No programming, coding, arbitrary UDS execution,
security-access key generation or authorization bypass is implemented.

Supply the known numeric IP address, protocol and physical ECU address for the
vehicle/bench you are authorized to access. Host and target start blank. HSFZ
defaults to TCP 6801 and tester `0xF4`; DoIP defaults to TCP 13400 and tester
`0x0EF4`, protocol version 3. These transport defaults do not identify a correct
ECU or prove vehicle compatibility. The app does not scan or guess addresses.

```text
python -m bmgarage read-vin --help
```

For a real request, supply `--protocol hsfz` or `--protocol doip`, `--host` with
the known numeric IP, and `--target` with the known physical address. Optional
arguments include `--port`, `--tester`, `--doip-version`, `--connect-timeout`
and `--response-timeout`. Addresses accept decimal or a `0x` prefix.

For DoIP TLS, explicitly select TLS/use `--tls` and the endpoint's documented
TLS port. Supply a trusted CA PEM with `--tls-ca` when system trust is insufficient,
and `--tls-name` when the certificate identifies a hostname rather than the
numeric IP. CA-chain and hostname verification are mandatory. Failed TLS does
not retry plaintext. No certificate, token or secure-diagnostic authentication
is invented; endpoints requiring unsupported authorization return an error.

A positive result requires a complete, correctly addressed UDS `62 F190`
response containing a 17-character ASCII VIN. A TCP connection, routing
activation or delivery acknowledgement alone does not count. Negative response
codes, routing refusals and malformed replies remain failures. Pending responses,
frame size, frame count and timeouts are bounded. Each engine request closes
its socket, including on failure.

The protocol tests use explicitly local synthetic peers and fixed wire vectors.
They verify real framing/socket handling, not BMW hardware, a secure-diagnostic
session or any F/G model's suitability. There is no validated universal F/G
address/protocol table. Windows network/firewall behavior and real ENET vehicle
validation remain unrun. The VIN response is not cryptographic proof of vehicle
identity or permission to perform additional operations.

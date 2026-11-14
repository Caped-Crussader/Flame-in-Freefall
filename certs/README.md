# Extra trusted certificates

`sslcom-tls-issuing-rsa-r1.pem` – modern "SSL.com TLS Issuing RSA CA R1"
intermediate (issuer: SSL.com TLS RSA Root CA 2022, expires 2032-10-18).
Source: http://cert.ssl.com/SSL.com-TLS-I-RSA-R1.cer (the AIA URL in the site's own cert).

Needed because www.spaceappschallenge.org serves a chain ending at the
distrusted legacy Comodo "AAA Certificate Services" root. Loaded automatically
by `backend/app/core/http.py`.

`ca-bundle.pem` (gitignored) = Fedora system bundle + this intermediate, for CLI use:
```bash
cat /etc/pki/tls/certs/ca-bundle.crt certs/sslcom-tls-issuing-rsa-r1.pem > certs/ca-bundle.pem
curl --cacert certs/ca-bundle.pem https://www.spaceappschallenge.org/
```

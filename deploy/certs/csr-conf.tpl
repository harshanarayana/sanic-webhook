[req]
req_extensions          = v3_req
distinguished_name      = req_distinguished_name

[req_distinguished_name]

[ v3_req ]
basicConstraints        = CA:FALSE
keyUsage                = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage        = serverAuth
subjectAltName          = @alt_names

[alt_names]
DNS.1                   = {{ app_name }}
DNS.2                   = {{ app_name }}.{{ namespace }}
DNS.3                   = {{ app_name }}.{{ namespace }}.svc
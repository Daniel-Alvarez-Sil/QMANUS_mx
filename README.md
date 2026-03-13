# QMANUS_mx
MANUS made with Alibaba capabilites. 

`provision_tenant.py` now enables TLS by default for TiDB Cloud connections. If `TIDB_SSL_CA` is not set, it will automatically use the local [`isrgrootx1.pem`](/home/das/QMANUS_mx/isrgrootx1.pem) file when present, otherwise it will still negotiate TLS without a custom CA bundle.

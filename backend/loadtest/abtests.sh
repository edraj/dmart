#!/bin/bash

which ab > /dev/null || ( echo "Can'd find ab (Apache Benchmark tool), download and put on path"; exit )

ab -l -c 500 -n 10000 'http://0.0.0.0:8282/'
ab -l -c 500 -n 10000 'http://0.0.0.0:8282/public/entry/folder/applications/api/user?retrieve_json_payload=true'
ab -l -p query_ab.json -T application/json -c 500 -n 10000 'http://0.0.0.0:8282/public/query'

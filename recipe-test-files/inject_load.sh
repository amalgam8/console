#!/bin/bash

curl -b 'foo=bar;user=shriram;x' http://localhost:32000/productpage/productpage
curl -b 'foo=bar;user=jason;x' http://localhost:32000/productpage/productpage
sleep 15

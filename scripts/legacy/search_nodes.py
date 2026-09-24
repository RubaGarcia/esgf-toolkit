#!/usr/bin/env python3

import concurrent.futures
import time
import requests

NODES = [
    "https://esgf-node.llnl.gov",
    "https://esgf-node.ipsl.upmc.fr",
    "https://esgf.ceda.ac.uk",
    "https://esgf-data.dkrz.de",
]

PARAMS = {
    "project": "CMIP7",
    "variable_id": "tas",
    "type": "Dataset",
    "format": "application/solr+json",
    "limit": 10,
    "distrib": "true",
}


def test_node(node):
    """Query one ESGF node's legacy /esg-search/search endpoint; return (node, status, elapsed, num_found, error).

    Used in: module-level ThreadPoolExecutor below (runs on import/execution of this script).
    """
    url = f"{node}/esg-search/search"
    start = time.perf_counter()

    try:
        r = requests.get(url, params=PARAMS, timeout=20)
        elapsed = time.perf_counter() - start

        if r.ok:
            data = r.json()
            num_found = data.get("response", {}).get("numFound", "?")
            return node, r.status_code, elapsed, num_found, None

        return node, r.status_code, elapsed, None, r.text[:200]

    except Exception as e:
        elapsed = time.perf_counter() - start
        return node, None, elapsed, None, str(e)


with concurrent.futures.ThreadPoolExecutor(max_workers=len(NODES)) as executor:
    results = executor.map(test_node, NODES)

for node, status, elapsed, found, error in results:
    if error:
        print(
            f"{node:40} "
            f"HTTP={status or '-':3} "
            f"time={elapsed:6.2f}s "
            f"ERROR={error}"
        )
    else:
        print(
            f"{node:40} "
            f"HTTP={status:3} "
            f"time={elapsed:6.2f}s "
            f"found={found}"
        )

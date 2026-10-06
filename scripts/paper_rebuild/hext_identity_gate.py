#!/usr/bin/env python3
from legsa_gins.paper_rebuild.hext.identity_gate import run_identity
if __name__=='__main__':
    result=run_identity()
    raise SystemExit(0 if result['status']=='PASS_BY2_BYTE_IDENTITY' else 1)

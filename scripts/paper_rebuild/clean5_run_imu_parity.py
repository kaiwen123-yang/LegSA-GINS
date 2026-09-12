#!/usr/bin/env python3
"""Execute the six P-03 IMU-parity runs from a pushed detached snapshot."""
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['GIT_OPTIONAL_LOCKS']='0'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean5_imu_parity.runner import main
if __name__=='__main__':
    sys.exit(main())

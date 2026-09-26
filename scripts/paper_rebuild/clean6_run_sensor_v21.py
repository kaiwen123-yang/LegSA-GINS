#!/usr/bin/env python3
"""Run the human-authorized P-13 v2.1 phase controller."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean6_sensor_v21.controller import main
if __name__=='__main__':main()

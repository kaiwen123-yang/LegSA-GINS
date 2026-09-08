"""Install observations only for the explicitly configured evaluator child."""
import os
import sys

sys.dont_write_bytecode = True
if os.environ.get("CLEAN5_EVALUATOR_CAPTURE_CONFIG"):
    try:
        from legsa_gins.paper_rebuild.clean5_sequence.evaluator_capture import install
        install(os.environ["CLEAN5_EVALUATOR_CAPTURE_CONFIG"])
    except BaseException:
        # site normally prints and ignores import errors: fail closed instead.
        import traceback
        traceback.print_exc()
        os._exit(125)

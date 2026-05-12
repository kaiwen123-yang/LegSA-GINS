from scripts.audit_n6b1_source_aware_visual_validation import main


def test_n6b1_source_aware_visual_validation_audit():
    # 中文说明：审计使用 synthetic toy 数据，不读取真实 runtime 输出。
    assert main() == 0

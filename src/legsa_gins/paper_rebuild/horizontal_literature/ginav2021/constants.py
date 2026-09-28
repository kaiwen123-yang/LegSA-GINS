"""Frozen identities and literal contracts for the GINav LC02 route."""

from __future__ import annotations

from pathlib import Path


CANDIDATE_ID = "LC02C_GINAV2021_OFFICIAL_SPP_INS_LC"
CLASSIFICATION_LABELS = (
    "EXACT_OFFICIAL_SOFTWARE_REPRODUCTION",
    "STANDARD_LC_LITERATURE_BASELINE",
    "NOT_A_NOVEL_FILTER_METHOD",
)

OFFICIAL_REPOSITORY = "https://github.com/kaichen686/GINav"
OFFICIAL_COMMIT = "bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666"
OFFICIAL_TREE = "94940c5b72c6003f696f6ed3684ee5b10875e792"
OFFICIAL_CONFIG_RELATIVE = Path("conf/LC/GINav_SPP_LC_CPT.ini")
OFFICIAL_SAMPLE_RELATIVE = Path("data/data_cpt.7z")
OFFICIAL_REFERENCE_MEMBER_BASENAME = "cpt_pva_ref.mat"

OFFICIAL_NAMED_HASHES = {
    "LICENSE": "97bf25caf038104d0d74d963a2f3b4b8dffb3a8a55bef39547852204333b7504",
    "README.md": "4d543134d7012f0bbe3086c87cac8fee4373fbe38afe1a9921f1fee55fcbc2aa",
    "doc/GINav User Manual.pdf": "9a2c287f892c50b7260c5112999750c4b34e2b938506cb2736085454363c6a65",
    "conf/LC/GINav_SPP_LC_CPT.ini": "6250830f6785d62e323b51b6852fc15d982ee1768f5a90f9dd031760c98c2196",
    "data/data_cpt.7z": "4758adb3f44e33cacea4b124eab3b591e723a3c722369f5fd303b3b3338bf209",
    "GINavExe.m": "9c7d3b57ff38e4642149beb0d65912679266d16be3efee106de9e7a29a998142",
    "src/common/global_variable.m": "b62e6354fa1b1080390e866602d0722dfc08cda52bdb3295514b007a430490cd",
    "src/common/searcheph.m": "c2ef3dc110697ec1ea8495054e55559790723457b58ed9919da365efe6549230",
    "src/common/searchgeph.m": "51efc1e3e0e0e7892111d68ae58d7ca30ae5fea5b57aafcb2dada653b5bd4f09",
    "src/common/bdt2time.m": "83828485ed7e8f45c4c69cbad13f0fe6a91c72a7bfbc06acf1ba25e35ec9a240",
    "src/common/bdt2gpst.m": "14defc4cca72dbcf10b947920ea27b4e10346b860fc62688cc34821ec067553a",
    "src/common/utc2gpst.m": "638b9611b66f44c4d5a82b9dade02c7a4e14448eb6632285d7d202755373a3bc",
    "src/read_file/decode_cfg.m": "c5a1e27ddb4777137ba29fe38ef87835de192dcc1eac65f1b77307cfa877aaa2",
    "src/read_file/decode_eph.m": "6f222ce51adb3036ec557b15b11521430ea0a3c6356f0ef92c0028388e587acc",
    "src/read_file/decode_geph.m": "632482e0bb7e212316e8ff60be0de7bf5820be2e9fc2fc916968acc55064e7ab",
    "src/read_file/decode_obsh.m": "a54d2c9b63c1920fa9dcebe82a62a34fcd2180051a32ebad707fd3013264a9a1",
    "src/read_file/decode_obsb.m": "b9888e60f3b717a33e0dded8139220f7224a804e95cc07530e33c76ac030d5db",
    "src/read_file/set_index.m": "478704eeb1e5143d07acfc1b3cbbb03a33808f5c65fda6f7e4d57d001dd5f8aa",
    "src/read_file/decode_data.m": "25fda2edeb839e37e9f85165e5727d7ca5cdcda43f69c1cf87744ab590c181a9",
    "src/read_file/adjobs.m": "c0a749eb4b8d78eb9f28aeff5b446753317ee0dbb72b3ef7ad1032bf2350ac1a",
    "src/read_file/adjnav.m": "75dd126cf22a0e92146667b1cd0969e53f77728292ba9caf75e41190ef12dbf2",
    "src/read_file/adjweek.m": "29a865e9135fc68be07e315e2e67ed6a95c4101eaef8f0809e22ecbdbb0cb785",
    "src/read_file/read_infile.m": "8625c87bf4e35b8727af46d17df0708e5b487d84a7bbbab964355c6eebbe8157",
    "src/read_file/readimu.m": "224f26214b2b9bc2afe7fcddb68015ea4ff377ff5414664f0bff087e135302fc",
    "src/main_func/exepos.m": "506bc520cbdfa69f50d88d82d3216abcfee1b06ded7cba9002dddb97d913094e",
    "src/main_func/gi_Loose.m": "60a3e3c6c872609e280ee9f29c555acaa49dc722d8bf093846e325ff5c0fbf1f",
    "src/main_func/gi_processor.m": "3f41351876266614cd13c5cbd6726f4031a304606408e2cf2e831f01a2c8b95c",
    "src/main_func/gnss_solver.m": "2b865a9cbda0c4a77135218fd8e0675f63cf4f3063d6d4f64b607aa0f86d1ff7",
    "src/gnss/spp/sppos.m": "aa363acb3076b07f3820ae2a68329cb718fefde4ea00bd575150036107511f97",
    "src/gnss/spp/prange.m": "5c7bbfeb93d23bbc666286627e835d49f9f5f0895e7cae32c821ae2962d2501a",
    "src/gnss/spp/scan_obs_spp.m": "552f92c162672632da706b36d147e0cf068bd1604c7efa92ed85010d024c61c6",
    "src/gnss/spp/rescode.m": "ad0c9ed3519de787b761bc4082abd4a0fa72b6bae1f912a505478cb30b82db56",
    "src/common/obs2code.m": "c34c666e7402988cc379bf72a03b7448e3c92a28062d16ab9666490ffbc629a9",
    "src/common/code2obs.m": "4620921c7ae8f4a8f36cffeed6846e825454b1c0ab297292c409f65a1d6ea1ea",
    "src/common/getcodepri.m": "7a417014fc3f4870b8bb2864a9c3342cc188a002d9cc5a51d9108868b2493dcf",
    "src/common/matchobs.m": "76a6fc0ddcae47d86c763110be4ba828f167fc8dac72ed480bf082e4fea3e875",
    "src/ins/ins_align.m": "76f4b0cc8e80d2abfe6bf6772f473bd421b8561920c9c47407eb0c6ee37ff20b",
    "src/ins/tdcp2vel.m": "58957d50603b5ca7242858c5f8d325050564808f0d57a47dd5a37b23bed0b60c",
    "src/ins/ins_init.m": "180129623c3e7dd9d88ad7ba7236fc0985810d876f5afe3e5731f1b7f3b37c38",
    "src/ins/ins_mech.m": "583e886a599353acba329bda1aadecb564dad1721f08bea06f7b21d4feb43c17",
    "src/ins/ins_time_updata.m": "ffe25393e7e1b674bb39a5b2e2ee409f4fc17e0655e7f540724a8c7f4ee39db3",
    "src/ins/update_trans_mat.m": "1a9da235e000c59b2ac20de243ab854a6828e8a3986323893fd2dec2ea8242de",
    "src/gnss_ins_lc/gnss_ins_lc.m": "2a9eec76511f8635ef71b45d84375bb200f1b58e3fb0b68ea806860ae2917b30",
    "src/gnss_ins_lc/lc_filter.m": "9685b2d09de537d2c8f2d68a9484b8dbb8950e07e55ac9442d4b69f56ce6d7e4",
    "src/gnss_ins_lc/lc_feedback.m": "ecd3cc983f5ae25b9cd83684fb776b109af80f1ff7fd15bff9c0d7594e7da8f0",
    "src/gnss_ins_lc/udsol_lc.m": "cfb56ac02f621540836eca320fe393758db3ff486ec1d9ed5c7081b8022beb52",
    "src/common/initoutfile.m": "1f32c84623b1bb5e374a8cb4710e5fd15921eff65836684cfdf32aac2b446037",
    "src/common/outsolhead.m": "8f52cd4bca2af7681601360e99a29e0fa3519b7cb240cf8adf89ba2e1e5b6b1c",
    "src/common/outsol.m": "4264eeeb2f234f18a24af483019294de0dc91d8ca44b2732bf47843378a1115d",
    "src/plot/plot_trajectory_kine.m": "c752683bd2ceaee77a7a3566cbe2fc33509eb05acf6465faca1698ad4b1fcd4a",
}

OFFICIAL_NAMED_SIZES = {
    "LICENSE": 1323,
    "README.md": 6417,
    "doc/GINav User Manual.pdf": 4461097,
    "conf/LC/GINav_SPP_LC_CPT.ini": 8048,
    "data/data_cpt.7z": 21295419,
}

RTKLIB_COMMIT = "180043ee24b6d2b168f98b64be15f69d50046b1a"
RTKLIB_TREE = "0566df2a00432147c110e19391767dd1250b3336"
RTKLIB_LICENSE_SHA256 = "219747832d49ee958457b2934080ab8d94bd9d8e45fcb1c36f89776fd2c5ed8a"
CONVBIN_SHA256 = "85b6b981374c7df957492d9423a3c650a35cb5e7253598651070adf4d9f1df2a"
RINEX_VERSION = "3.04"
GINAV_SUPPORTED_SYSTEMS = ("G", "R", "E", "C", "J")
GINAV_MAX_FREQUENCIES = 3
RAW_HASH_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"

GO2_RAW_SIZE_BYTES = 92352512
GO2_RAW_SHA256 = "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
GO2_PREFIX_BYTES = 92351234
GO2_PREFIX_SHA256 = "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
GO2_COMPLETE_RECORDS = 63277
GO2_IMU_IDENTITY = "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
GO2_SAMPLE_RATE_HZ = 500
GO2_SAMPLE_RATE_SOURCE = (
    "configs/paper_rebuild/final_v23_parity_contract.yaml#"
    "imu_preprocessing.input_rate_hz"
)
GO2_SAMPLE_RATE_SOURCE_SHA256 = (
    "2c215e680512bb1d630d46262c4e230a2ec58147ffc0a35b1c6a5ad21805c1da"
)
GO2_INCREMENT_POLICY_SOURCE = (
    "configs/paper_rebuild/final_v23_parity_contract.yaml#imu_preprocessing"
)
GO2_INVALID_DT_POLICY = "drop_if_dt_lte_0_or_gt_0p1_seconds"

GO2_ALLAN_PROFILE_ID = "GO2_IMU_ALLAN_90MIN_RECOVERED_V1"
GO2_ALLAN_SOURCE = (
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml"
)
GO2_ALLAN_SOURCE_SHA256 = (
    "fcf3964caf8142f262f9df767df62d3f18454d18ca331a9dcc0722f8786b4480"
)
GO2_ALLAN_ASD = {
    "gyro_measurement_white_noise_density": 2.865130e-4,
    "accelerometer_measurement_white_noise_density": 1.285395e-3,
    "gyro_bias_random_walk_density": 2.996871e-5,
    "accelerometer_bias_random_walk_density": 1.594412e-4,
}
GO2_ALLAN_PSD = {
    "psd_gyro": 8.208969916900001e-8,
    "psd_acce": 1.652240306025e-6,
    "psd_bg": 8.981235790641001e-10,
    "psd_ba": 2.542149625744e-8,
}

LEVER_FRD_M = (0.03, 0.03, -0.30)
LEVER_RFU_M = (0.03, 0.03, 0.30)
LEVER_LABELS = {
    "quality": "ROUGH_ENGINEERING_LEVER",
    "precision_survey": False,
    "trace_tuned": False,
}

STAGE_NAME = "11_LC02_GINAV2021_OFFICIAL_REPRODUCTION"
STAGE_RELATIVE_LAYOUT = (
    "00_SOURCE_AND_ENVIRONMENT",
    "01_OFFICIAL_SAMPLE_REGRESSION",
    "02_BY2_GNSS_ADAPTER",
    "03_BY2_IMU_ADAPTER",
    "04_BY2_CONFIG_AND_TIME_CONTRACT",
    "05_BY2_ACTIVATION_PROBE",
    "06_BY2_C00_NATIVE",
    "07_NATIVE_OUTPUT_NORMALIZATION",
    "11_REPORT",
)

SUCCESS_STATUS = "PASS_LC02_GINAV2021_EXACT_ROUTE_AND_BY2_C00_VALIDATED"
POOR_APPLICABILITY_STATUS = (
    "PASS_LC02_GINAV2021_EXACT_ROUTE_VALIDATED_BY2_C00_POOR_APPLICABILITY_RESULT"
)
TERMINAL_STATUSES = frozenset(
    {
        SUCCESS_STATUS,
        POOR_APPLICABILITY_STATUS,
        "BLOCKED_LC02_GINAV_MATLAB_RUNTIME_UNAVAILABLE",
        "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
        "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE",
        "BLOCKED_LC02_GINAV_BY2_GNSS_ADAPTER_FAILURE",
        "BLOCKED_LC02_GINAV_BY2_IMU_ADAPTER_FAILURE",
        "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
        "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY",
        "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET",
        "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP",
    }
)

OFFICIAL_STATUS_NAMES = {
    0: "NONE",
    1: "FIX",
    2: "FLOAT",
    3: "INS",
    4: "DGNSS",
    5: "SPP",
    6: "PPP",
    7: "LC",
    8: "TC",
}

# Q=5 is intentionally the successful SPP-fed LC marker: udsol_lc copies the
# internal GNSS status instead of assigning SOLQ_LC.  Q=3 is ins2sol output.
LC_UPDATE_STATUS = 5
INS_ONLY_STATUS = 3
TDCP_SPEED_SQUARED_THRESHOLD = 3.0
TDCP_THRESHOLD_LITERAL = "dot(vn,vn)>3"

OFFICIAL_POS_COLUMNS = (
    "gps_week", "gps_sow", "ecef_x_m", "ecef_y_m", "ecef_z_m",
    "status", "satellite_count", "sdx_m", "sdy_m", "sdz_m",
    "sdxy_m", "sdyz_m", "sdzx_m", "age_s", "ratio",
    "ecef_vx_mps", "ecef_vy_mps", "ecef_vz_mps", "sdvx_mps",
    "sdvy_mps", "sdvz_mps", "sdvxy_mps", "sdvyz_mps", "sdvzx_mps",
    "pitch_deg", "roll_deg", "yaw_deg", "sdp_deg", "sdr_deg",
    "sdy_deg", "sdpr_deg", "sdry_deg", "sdyp_deg",
)

STANDARD_NAV_COLUMNS = (
    "gps_week", "gps_sow", "status_code", "status_name",
    "satellite_count", "ecef_x_m", "ecef_y_m", "ecef_z_m",
    "latitude_deg", "longitude_deg", "height_m",
    "ecef_vx_mps", "ecef_vy_mps", "ecef_vz_mps",
    "velocity_east_mps", "velocity_north_mps", "velocity_up_mps",
    "velocity_north_ned_mps", "velocity_east_ned_mps",
    "velocity_down_ned_mps", "pitch_deg", "roll_deg", "yaw_deg",
    "position_covariance_finite", "velocity_covariance_finite",
    "attitude_covariance_finite", "lc_update", "ins_only",
)

SAMPLE_NUMERICAL_QUANTA = {
    "gps_sow_s": 1e-3,
    "ecef_position_m": 1e-4,
    "position_uncertainty_m": 1e-4,
    "velocity_mps": 1e-5,
    "velocity_uncertainty_mps": 1e-5,
    "attitude_deg": 1e-5,
    "attitude_uncertainty_deg": 1e-5,
    "age_s": 1e-2,
    "ratio": 1e-1,
}

SAMPLE_CONFIG_ALLOWED_CHANGES = frozenset({"data_dir"})
BY2_CONFIG_ALLOWED_CHANGES = frozenset(
    {
        "data_dir", "site_name", "start_time", "end_time", "t_interval",
        "navsys", "nfreq", "data_format", "sample_rate", "lever",
        "psd_gyro", "psd_acce", "psd_bg", "psd_ba",
        "timef", "posf", "outvel", "outatt",
    }
)
BY2_CONFIG_REQUIRED_UNCHANGED = {
    "gnss_mode": "1",
    "ins_mode": "1",
    "ins_aid": "0,1",
    "maxinno": "30.0",
    "init_att_unc": "0.3,0.3,0.5",
    "init_vel_unc": "10,10,10",
    "init_pos_unc": "30,30,30",
    "init_bg_unc": "2.42406840554768e-05",
    "init_ba_unc": "0.048901633857000000",
}

FORBIDDEN_ROLE_TOKENS = (
    "gnss2", "p2-p1", "dual_yaw", "dual-antenna", "quaternion", "rpy",
    "trace", "reference", "cpt_pva_ref.mat", "lc01", "hartley",
    "ext01", "ext02", "ext03", "ext04", "canonical-541", "canonical541",
    "legsa_output", "old_ginav_runtime", "legsa-gins-external/ginav/result",
)

RUNTIME_ONLY_BASENAMES = frozenset(
    {
        "BY2_GINAV_IMU.csv",
        "BY2_GNSS1.rnx",
        "BY2_GNSS1.nav",
        "BY2_GNSS1.ubx",
    }
)

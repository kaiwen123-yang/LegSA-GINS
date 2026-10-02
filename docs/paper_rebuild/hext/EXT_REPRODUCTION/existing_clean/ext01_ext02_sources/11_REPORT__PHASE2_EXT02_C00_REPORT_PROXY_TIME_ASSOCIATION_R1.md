# Phase 2 EXT02 C-WLS C00 report — post recovery PROXY_TIME_ASSOCIATION_R1

Terminal: `PASS_PHASE2_EXT02_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT`.

This is a faithful-algorithm reproduction and BY2 C00 applicability result, not a paper claim or an independent-ground-truth evaluation.

Paired epochs: 1509; accepted wrapped solutions: 1057; explicit failures: 452.
Accepted coverage: 0.7004638833664678; maximum baseline-norm error: 1.6653345369377348e-16 m.
Unique candidate-count median: 43.0; runtime median: 0.017950976000065566 s.
Ambiguity correctness is unknown; ambiguity success/fixed/float rates are NA.

Native outputs were hash-frozen with zero trace and NAV-HPPOSECEF semantic opens. Only after revalidation were HPPOSECEF and the fixed same-source trace opened for descriptive diagnostics. Native outputs were not mutated or substituted.
Post-native open/decode counters in this report cover this successful invocation only; prior failed post-native attempts are explicitly excluded and must be accounted for in lifecycle recovery evidence.
Successful invocation HPPOSECEF receiver-stream decode passes/semantic records: 2/3020; trace opens: 1.

Proxy materially-lower eligible accepted epochs: [].
Proxy availability: 1509/1509; trace/native matched accepted count: 964.
Independent oracle evaluated: 11/11 selected input-only epochs; proxy objective evaluated: 1057 eligible accepted epochs.
Applicability classification: `OBSERVED_ACCEPTED_WRAPPED_SOLUTION_AVAILABILITY`. If availability had been zero, that would have been a validated poor-applicability result rather than an automatic unsupported status; observed availability here is 1057/1509.

Trace conversion is fixed to unwrap ENU yaw, interpolate at absolute solver time, then wrap360(90-yaw); no search, alignment, offset, or epoch deletion was used.

## Paper, source, and equation identity

```json
{
  "equation_map": {
    "Algorithm 1": "CIRCLE_CANDIDATES",
    "Algorithm 2": "ALL_CANDIDATE_COARSE_AND_REFINE",
    "Eq.(46)": "STACKED_CONSTRAINED_WRAPPED_LEAST_SQUARES",
    "Eq.(54)": "SINGLE_BASELINE_OBJECTIVE_WITH_X_EQUALS_D_TIMES_R",
    "Eq.(73)": "COMPLETE_COARSE_OBJECTIVE",
    "Eqs.(5)-(8)": "DD_OBSERVATION_AND_H_MATRIX",
    "Eqs.(56)-(58)": "PHASE_CIRCLE_AND_INTEGER_BOUNDS",
    "Eqs.(59)-(60)": "JOINT_CIRCLE_SYSTEMS",
    "Eqs.(62)-(65)": "V1_V2_CENTERS_PEAKS_DELTA1_DELTA2",
    "Eqs.(66)-(72)": "DELTA3_DELTA4_PROJECTIONS_PC_Q1_Q2",
    "Eqs.(74)-(75)": "SPHERE_CONSTRAINED_UNWRAPPED_REFINEMENT_AND_RECOVERED_PHASE"
  },
  "formal_reproduction_level": "FAITHFUL_ALGORITHM_REPRODUCTION",
  "native_runtime_source_provenance": {
    "code_commit": "407edc840340989b1351d1d1aef050637aacd2df",
    "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
    "git_source_state": {
      "authorized_dirty_runtime_delta_allowed": true,
      "authorized_dirty_runtime_delta_entries": [
        " M configs/paper_rebuild/horizontal_literature/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml",
        " M src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
        "?? configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml",
        "?? scripts/paper_rebuild/run_horizontal_literature_phase2.py",
        "?? src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py",
        "?? src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py"
      ],
      "authorized_dirty_runtime_delta_present": true,
      "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
      "runtime_source_identity_role": "SOURCE_HASHES_PLUS_SOURCE_FINGERPRINT",
      "runtime_source_paths": [
        "configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml",
        "configs/paper_rebuild/horizontal_literature/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml",
        "scripts/paper_rebuild/run_horizontal_literature_phase2.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py"
      ]
    },
    "runtime_source_hashes": {
      "configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml": "ecfeaeddb8707ed5097746db2c6fe03b5c17367084db0ff354f76643b2139ba7",
      "configs/paper_rebuild/horizontal_literature/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml": "0d524fcc219ec580638a30ddf8665f4d67521df99568deffea6360440c4c62c9",
      "scripts/paper_rebuild/run_horizontal_literature_phase2.py": "8810712f2b50bd63587b121fce55ba14ca623fc485f533f6a9703a758268835f",
      "src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py": "ea65b90282fdeee943eca4764da18fb05fcb9a46b9a7cf44d477d3ff60976f2c",
      "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py": "82fccd3a6df1af6dee30739954934d7210339f0c1723a06d6c0b7486d41682a7",
      "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py": "976e837207d7bd05d6d0a9e72406fd8f8244968c60f18e9e0bfd3d94fe9b04a5"
    },
    "source_fingerprint": "03e3b7141de02872991f295f76ebab289b03a7c7873ca3a27bebd8308b4666c3"
  },
  "paper_source": {
    "article_number": 8005315,
    "authors": [
      "Xing Liu",
      "Tarig Ballal",
      "Hui Chen",
      "Tareq Y. Al-Naffouri"
    ],
    "doi": "10.1109/TIM.2022.3193412",
    "journal": "IEEE Transactions on Instrumentation and Measurement",
    "official_code_search": {
      "implementation_lineage": "INDEPENDENT_CLEAN_ROOM_IMPLEMENTATION",
      "result": "NO_ATTRIBUTABLE_OFFICIAL_SOURCE_CODE_OR_SUPPLEMENTARY_IMPLEMENTATION_LOCATED",
      "search_scope": [
        "current_clean_repository",
        "configured_external_source_root",
        "IEEE",
        "author_university_records",
        "arXiv",
        "GitHub",
        "publisher_supplements"
      ],
      "searched": true
    },
    "source_id": "LIU_BALLAL_CHEN_AL_NAFFOURI_TIM_2022_8005315",
    "title": "Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination",
    "typesetting_crosscheck": {
      "role": "TYPESETTING_CROSSCHECK_ONLY",
      "source_id": "ARXIV_2112_14813"
    },
    "volume": 71,
    "year": 2022
  },
  "post_native_runtime_source_provenance": {
    "code_commit": "407edc840340989b1351d1d1aef050637aacd2df",
    "diverged_from_native_for_post_only_code": true,
    "git_source_state": {
      "authorized_dirty_runtime_delta_allowed": true,
      "authorized_dirty_runtime_delta_entries": [
        " M configs/paper_rebuild/horizontal_literature/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml",
        " M src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
        "?? configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml",
        "?? scripts/paper_rebuild/run_horizontal_literature_phase2.py",
        "?? src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py",
        "?? src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py"
      ],
      "authorized_dirty_runtime_delta_present": true,
      "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
      "runtime_source_identity_role": "SOURCE_HASHES_PLUS_SOURCE_FINGERPRINT",
      "runtime_source_paths": [
        "configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml",
        "configs/paper_rebuild/horizontal_literature/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml",
        "scripts/paper_rebuild/run_horizontal_literature_phase2.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py"
      ]
    },
    "runtime_source_hashes": {
      "configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml": "107e2afc8388f58abd45ffac471133c41f37c99dfa0c8bc80e1fc6ac5a858b71",
      "configs/paper_rebuild/horizontal_literature/STANDARD_HEADING_STREAM_SCHEMA_V1.yaml": "0d524fcc219ec580638a30ddf8665f4d67521df99568deffea6360440c4c62c9",
      "scripts/paper_rebuild/run_horizontal_literature_phase2.py": "472f1855696d8f3fa1285f10b0ad751a84b5237afd7a4d83918c270e9804c464",
      "src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py": "ea65b90282fdeee943eca4764da18fb05fcb9a46b9a7cf44d477d3ff60976f2c",
      "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py": "27d5e19bb250da49353700da64bb17c346ecdcb63fa752d4939398c829160965",
      "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py": "976e837207d7bd05d6d0a9e72406fd8f8244968c60f18e9e0bfd3d94fe9b04a5"
    },
    "source_fingerprint": "7ae3e21598578e7c2fba5468c9e888869e52667fdb4610b46d8413abce845988"
  }
}
```

## GPS-L1 eligibility and native failure accounting

```json
{
  "accepted_continuity": {
    "continuity_definition": "segments split when accepted original epoch indices are nonconsecutive",
    "longest_segment_epochs": 285,
    "maximum_gap_seconds": 13.799999999988358,
    "segment_count": 30,
    "valid_count": 1057
  },
  "accepted_coverage": 0.7004638833664678,
  "baseline": {
    "count": 1057,
    "identity_m": 0.35,
    "maximum_absolute_norm_error_m": 1.6653345369377348e-16,
    "maximum_m": 0.35000000000000014,
    "minimum_m": 0.34999999999999987
  },
  "body_yaw": {
    "circular_mean_deg": 64.20774730570591,
    "count": 1057,
    "resultant_length": 0.25143567226938046,
    "wrapsafe_max_abs_about_mean_deg": 179.90106606380817,
    "wrapsafe_rms_about_mean_deg": 88.79015633260836
  },
  "elevation": {
    "count": 1057,
    "max": 87.54583267141803,
    "mean": -3.2980854587514883,
    "median": -18.305467531932607,
    "min": -80.01369406520324,
    "p95": 81.31472327649558,
    "rms": 51.13569583881161
  },
  "failure_code_counts": {
    "INSUFFICIENT_CP_VALID": 11,
    "INSUFFICIENT_DD_DIMENSION": 1,
    "INSUFFICIENT_HALF_CYCLE_VALID": 374,
    "INSUFFICIENT_SATELLITE_STATES": 46,
    "NUMERICAL_FAILURE": 20
  },
  "gps_l1_dd_stage_counts": {
    "common_cp_valid_satellite_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 6.418820410868125,
      "median": 6.0,
      "min": 3.0,
      "p95": 9.0,
      "rms": 6.554355489143456
    },
    "common_half_cycle_valid_satellite_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 4.358515573227303,
      "median": 4.0,
      "min": 2.0,
      "p95": 7.0,
      "rms": 4.555453187576561
    },
    "common_integer_compatible_satellite_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 4.357852882703777,
      "median": 4.0,
      "min": 2.0,
      "p95": 7.0,
      "rms": 4.554798516892896
    },
    "common_pr_cp_valid_satellite_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 6.418820410868125,
      "median": 6.0,
      "min": 3.0,
      "p95": 9.0,
      "rms": 6.554355489143456
    },
    "common_pr_valid_satellite_count": {
      "count": 1509,
      "max": 10.0,
      "mean": 7.960901259111995,
      "median": 8.0,
      "min": 5.0,
      "p95": 9.0,
      "rms": 8.031457370141668
    },
    "common_raw_satellite_count": {
      "count": 1509,
      "max": 10.0,
      "mean": 7.960901259111995,
      "median": 8.0,
      "min": 5.0,
      "p95": 9.0,
      "rms": 8.031457370141668
    },
    "dd_dimension": {
      "count": 1057,
      "max": 8.0,
      "mean": 3.8003784295175023,
      "median": 3.0,
      "min": 3.0,
      "p95": 7.0,
      "rms": 3.967106950805538
    },
    "dd_eligible_satellite_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 3.4446653412856194,
      "median": 4.0,
      "min": 0.0,
      "p95": 7.0,
      "rms": 4.189987750487811
    },
    "elevation_eligible_satellite_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 3.536779324055666,
      "median": 4.0,
      "min": 0.0,
      "p95": 7.0,
      "rms": 4.223149305866672
    },
    "satellite_state_available_count": {
      "count": 1509,
      "max": 9.0,
      "mean": 3.536779324055666,
      "median": 4.0,
      "min": 0.0,
      "p95": 7.0,
      "rms": 4.223149305866672
    }
  },
  "heading": {
    "circular_mean_deg": 334.2077473057059,
    "count": 1057,
    "resultant_length": 0.25143567226938046,
    "wrapsafe_max_abs_about_mean_deg": 179.90106606380814,
    "wrapsafe_rms_about_mean_deg": 88.79015633260836
  }
}
```

## Candidate, refinement, oracle, and runtime evidence

K policy is `ALL_UNIQUE_CANDIDATES`; no best-K truncation was used.

```json
{
  "candidate_and_refinement_statistics": {
    "candidate_search_completion": {
      "accepted_count": 1057,
      "accepted_search_complete_count": 1057,
      "all_accepted_search_complete": true,
      "rejected_incomplete_search_epoch_count": 20
    },
    "circle_count": {
      "count": 1509,
      "max": 28.0,
      "mean": 7.992710404241219,
      "median": 7.0,
      "min": 0.0,
      "p95": 19.0,
      "rms": 10.278784600145883
    },
    "circle_pair_count": {
      "count": 1509,
      "max": 338.0,
      "mean": 38.770046388336645,
      "median": 14.0,
      "min": 0.0,
      "p95": 148.0,
      "rms": 68.88768819720786
    },
    "constrained_objective": {
      "count": 1057,
      "max": 577.2817931131216,
      "mean": 29.708887618134767,
      "median": 4.462057244785509,
      "min": 0.020243735741121933,
      "p95": 211.00123179051204,
      "rms": 79.374257180655
    },
    "degenerate_pair_count": {
      "count": 1509,
      "max": 0.0,
      "mean": 0.0,
      "median": 0.0,
      "min": 0.0,
      "p95": 0.0,
      "rms": 0.0
    },
    "near_tangent_candidate_count": {
      "count": 1509,
      "max": 18.0,
      "mean": 1.5798542080848244,
      "median": 1.0,
      "min": 0.0,
      "p95": 6.0,
      "rms": 2.8270209963347805
    },
    "phase_row_count": {
      "count": 1509,
      "max": 8.0,
      "mean": 2.728959575878065,
      "median": 3.0,
      "min": 0.0,
      "p95": 6.0,
      "rms": 3.3731878526007217
    },
    "raw_candidate_count": {
      "count": 1057,
      "max": 420.0,
      "mean": 67.24976348155155,
      "median": 43.0,
      "min": 12.0,
      "p95": 314.0,
      "rms": 103.62063751226606
    },
    "refined_candidate_count": {
      "count": 1057,
      "max": 420.0,
      "mean": 67.24976348155155,
      "median": 43.0,
      "min": 12.0,
      "p95": 314.0,
      "rms": 103.62063751226606
    },
    "selected_refinement_iterations": {
      "count": 1057,
      "max": 4.0,
      "mean": 2.0179754020813623,
      "median": 2.0,
      "min": 2.0,
      "p95": 2.0,
      "rms": 2.0251493515125945
    },
    "unique_candidate_count": {
      "count": 1057,
      "max": 420.0,
      "mean": 67.24976348155155,
      "median": 43.0,
      "min": 12.0,
      "p95": 314.0,
      "rms": 103.62063751226606
    }
  },
  "objective_oracle_all_comparisons_pass": true,
  "objective_oracle_evaluated_count": 11,
  "objective_oracle_indices": [
    0,
    150,
    300,
    450,
    600,
    750,
    900,
    1050,
    1200,
    1350,
    1500
  ],
  "objective_oracle_not_evaluated_count": 0,
  "objective_oracle_selected_count": 11,
  "runtime_seconds": {
    "count": 1509,
    "max": 0.4750414760001149,
    "mean": 0.037351880182256124,
    "median": 0.017950976000065566,
    "min": 0.001033722999636666,
    "p95": 0.15054738979979446,
    "rms": 0.06815318955215603
  },
  "worker_max_rss_bytes": {
    "count": 1509,
    "max": 179236864.0,
    "mean": 178298383.26838967,
    "median": 178253824.0,
    "min": 176484352.0,
    "p95": 179040256.0,
    "rms": 178299094.61167312
  },
  "workers_1_vs_16_and_resources": {
    "actual_process_count": 16,
    "cache_read_io_probe": {
      "bytes_read": 6472155,
      "combined_read_sha256": "1127fa075242ff63c385ec90a3be18341112572cbaf0e7a3d35b4113dc1bd14f",
      "elapsed_seconds": 0.02528655600053753,
      "file_count": 3,
      "memory_map_mode": "read_only",
      "throughput_bytes_per_second": 255952412.01935202,
      "worker_raw_csv_read_count": 0
    },
    "excluded_fields": [
      "runtime_seconds",
      "worker_pid",
      "worker_max_rss_bytes",
      "shard_id"
    ],
    "peak_per_worker_rss_bytes": 170242048,
    "per_worker_max_rss_bytes": {
      "90793": 170242048,
      "90794": 169652224,
      "90795": 170045440,
      "90796": 169848832,
      "90797": 170045440,
      "90798": 169652224,
      "90799": 169848832,
      "90800": 169848832,
      "90801": 168865792,
      "90802": 169848832,
      "90803": 169848832,
      "90804": 168669184,
      "90805": 169848832,
      "90806": 168669184,
      "90807": 169848832,
      "90808": 169848832
    },
    "probe_worker_failure_count": 0,
    "probe_worker_failures": [],
    "projected_total_worker_rss_bytes": 2723872768,
    "rejection_reasons": [],
    "resource_admission": {
      "admitted": true,
      "checks": {
        "actual_process_count_matches_requested": {
          "observed": 16,
          "passed": true,
          "required": 16
        },
        "adequate_disk_for_deterministic_output_projection": {
          "available_bytes_conservative": 154683572224,
          "passed": true,
          "required_available_bytes": 2723151872
        },
        "maximum20_temperature_available_and_stable": {
          "passed": true,
          "required_for_selected_workers": false,
          "temperature_evidence": {
            "available": false,
            "maximum_absolute_delta_c": null,
            "stability_limit_c": 5.0,
            "stable": false,
            "zone_delta_c": {}
          }
        },
        "maximum20_zero_swap_activity": {
          "passed": true,
          "required_for_selected_workers": false,
          "swap_activity_delta_pages": {
            "in": 0,
            "out": 0
          }
        },
        "positive_cache_read_io": {
          "bytes_read": 6472155,
          "elapsed_seconds": 0.02528655600053753,
          "passed": true,
          "throughput_bytes_per_second": 255952412.01935202
        },
        "projected_rss_below_70_percent_available_ram": {
          "available_ram_bytes_conservative": 22941396992,
          "exclusive_limit_bytes": 16058977894,
          "limit_fraction": 0.7,
          "passed": true,
          "projected_rss_bytes": 2723872768
        },
        "zero_worker_failures": {
          "observed": 0,
          "passed": true,
          "required": 0
        }
      },
      "deterministic_output_size_projection": {
        "bytes_per_epoch": 1048576,
        "disk_safety_reserve_bytes": 1073741824,
        "fixed_bytes": 67108864,
        "formula": "1509*bytes_per_epoch+fixed_bytes+disk_safety_reserve_bytes",
        "paired_epoch_count": 1509,
        "projected_output_bytes": 1649410048,
        "required_available_bytes": 2723151872
      },
      "maximum20_extra_gate_applied": false,
      "rejection_reasons": [],
      "schema": "horizontal_literature.phase2.resource_admission.v1",
      "selected_workers": 16
    },
    "resource_after": {
      "configured_clean_storage": {
        "available_bytes": 154683572224,
        "free_bytes": 154683572224,
        "path": "<CLEAN_ROOT>",
        "total_bytes": 1000185266176
      },
      "cpu_count": 24,
      "load_average_1m_5m_15m": [
        3.48486328125,
        6.06591796875,
        5.93017578125
      ],
      "ram_available_bytes": 22941396992,
      "ram_total_bytes": 25197436928,
      "swap_free_bytes": 68719476736,
      "swap_in_pages": 0,
      "swap_out_pages": 0,
      "swap_total_bytes": 68719476736,
      "swap_used_bytes": 0,
      "thermal": {
        "status": "UNAVAILABLE",
        "zones": []
      }
    },
    "resource_before": {
      "configured_clean_storage": {
        "available_bytes": 154683572224,
        "free_bytes": 154683572224,
        "path": "<CLEAN_ROOT>",
        "total_bytes": 1000185266176
      },
      "cpu_count": 24,
      "load_average_1m_5m_15m": [
        3.70166015625,
        6.15185546875,
        5.95703125
      ],
      "ram_available_bytes": 22944157696,
      "ram_total_bytes": 25197436928,
      "swap_free_bytes": 68719476736,
      "swap_in_pages": 0,
      "swap_out_pages": 0,
      "swap_total_bytes": 68719476736,
      "swap_used_bytes": 0,
      "thermal": {
        "status": "UNAVAILABLE",
        "zones": []
      }
    },
    "sample_original_epoch_indices": [
      0,
      100,
      201,
      301,
      402,
      502,
      603,
      703,
      804,
      904,
      1005,
      1105,
      1206,
      1306,
      1407,
      1508
    ],
    "scientific_comparisons": {
      "0": true,
      "100": true,
      "1005": true,
      "1105": true,
      "1206": true,
      "1306": true,
      "1407": true,
      "1508": true,
      "201": true,
      "301": true,
      "402": true,
      "502": true,
      "603": true,
      "703": true,
      "804": true,
      "904": true
    },
    "scientific_digest": "2d9c392e8b5117e51729f0f5f967374d1140449400ef4a2cbc7eb86e8c42d39a",
    "source_fingerprint": "03e3b7141de02872991f295f76ebab289b03a7c7873ca3a27bebd8308b4666c3",
    "status": "PASS",
    "swap_activity_delta_pages": {
      "in": 0,
      "out": 0
    },
    "worker_pids": [
      90793,
      90794,
      90795,
      90796,
      90797,
      90798,
      90799,
      90800,
      90801,
      90802,
      90803,
      90804,
      90805,
      90806,
      90807,
      90808
    ],
    "worker_selection": {
      "decision": "DEFAULT_16_SELECTED_MAX20_NOT_USED",
      "default_workers": 16,
      "maximum_20_used": false,
      "maximum_workers": 20,
      "selected_workers": 16
    },
    "workers_compared": 16,
    "workers_reference": 1
  }
}
```

## Post-native proxy and fixed-trace metrics

```json
{
  "fixed_evaluator_contract": {
    "base_time_unix_seconds": 1772784000.0,
    "epoch_deleted": false,
    "gps_to_unix_seconds": "315964800 + gps_week*604800 + gps_tow_seconds - leap_seconds",
    "leap_second_evidence": {
      "all_receiver_epoch_values_identical": true,
      "expected_and_observed_leap_seconds": 18,
      "paired_epoch_count_verified": 1509,
      "receiver_epoch_field_count_verified": 3018,
      "source": "COMPACT_CACHE_PAIRED_EPOCHS_R1_R2_LEAP_FIELDS"
    },
    "matched_native_time_must_be_bracketed_by_trace": true,
    "native_epoch_match_gate_seconds": [
      66.0,
      340.0
    ],
    "search_or_alignment": false,
    "time_offset_seconds": 0.0,
    "trace_csv": {
      "exact_columns": [
        "time",
        "lat",
        "lon",
        "height",
        "processed_lat",
        "processed_lon",
        "processed_height",
        "yaw",
        "pitch",
        "roll"
      ],
      "first_column": "time",
      "observed_column_count": 10,
      "timestamp_alias_accepted": false
    },
    "trace_unwrap_domain": "FULL_VALIDATED_MONOTONIC_TRACE_BEFORE_NATIVE_WINDOW_GATE",
    "window_seconds": [
      66.0,
      340.0
    ],
    "yaw": "unwrap_enu_then_interpolate_then_wrap360(90-yaw)"
  },
  "native_minus_proxy_body_yaw_wrapsafe": {
    "circular_wrapsafe_bias_deg": 144.27282779694508,
    "continuity_definition": "segments split when accepted original epoch indices are nonconsecutive",
    "longest_segment_epochs": 285,
    "mae_deg": 105.9365204947798,
    "matched_count": 1057,
    "max_absolute_deg": 179.99748731114653,
    "maximum_gap_seconds": 13.799999999988358,
    "median_absolute_deg": 117.04083937102814,
    "p90_absolute_deg": 176.2554724570363,
    "p95_absolute_deg": 178.05148084694483,
    "p99_absolute_deg": 179.49620619852266,
    "rmse_deg": 120.98227411490542,
    "segment_count": 30,
    "valid_count": 1057,
    "valid_coverage": 1.0,
    "valid_denominator": 1057,
    "wrapsafe_bias_deg": 19.268443725313993
  },
  "native_minus_proxy_heading_wrapsafe": {
    "circular_wrapsafe_bias_deg": 144.27282779694508,
    "continuity_definition": "segments split when accepted original epoch indices are nonconsecutive",
    "longest_segment_epochs": 285,
    "mae_deg": 105.9365204947798,
    "matched_count": 1057,
    "max_absolute_deg": 179.99748731114653,
    "maximum_gap_seconds": 13.799999999988358,
    "median_absolute_deg": 117.04083937102814,
    "p90_absolute_deg": 176.2554724570363,
    "p95_absolute_deg": 178.0514808469448,
    "p99_absolute_deg": 179.49620619852269,
    "rmse_deg": 120.98227411490542,
    "segment_count": 30,
    "valid_count": 1057,
    "valid_coverage": 1.0,
    "valid_denominator": 1057,
    "wrapsafe_bias_deg": 19.268443725313993
  },
  "native_proxy_vector_angle_deg": {
    "count": 1057,
    "max": 172.24157262345673,
    "mean": 95.59588854483489,
    "median": 103.05122472537859,
    "min": 8.304121051207588,
    "p95": 136.7368382906496,
    "rms": 102.2606189938092
  },
  "oracle_gated_proxy_objective_evaluated_count": 11,
  "proxy_length_m": {
    "count": 1509,
    "max": 0.4742458223772615,
    "mean": 0.3504740132398221,
    "median": 0.35125902150330224,
    "min": 0.12037861076216591,
    "p95": 0.39566085108383275,
    "rms": 0.351869745371859
  },
  "proxy_minus_production_objective": {
    "count": 1057,
    "max": 4785.341501573077,
    "mean": 446.8939123194786,
    "median": 327.60955253930007,
    "min": 9.75603372236621,
    "p95": 1220.1024011388215,
    "rms": 663.885128547721
  },
  "proxy_objective_evaluated_count": 1057,
  "trace_native_yaw_error_deg": {
    "circular_wrapsafe_bias_deg": 141.07743603205643,
    "continuity_definition": "segments split when accepted original epoch indices are nonconsecutive",
    "longest_segment_epochs": 285,
    "mae_deg": 105.15307519592537,
    "matched_count": 964,
    "max_absolute_deg": 179.96605423604268,
    "maximum_gap_seconds": 13.799999999988358,
    "median_absolute_deg": 115.82441764111354,
    "p90_absolute_deg": 176.277140202669,
    "p95_absolute_deg": 178.30403175914398,
    "p99_absolute_deg": 179.48903217966563,
    "rmse_deg": 120.52876042302128,
    "segment_count": 25,
    "valid_count": 964,
    "valid_coverage": 0.7036496350364964,
    "valid_denominator": 1370,
    "wrapsafe_bias_deg": 15.432854880527305
  }
}
```

## Fractional-DD descriptive relationships

No phase-bias calibration, correction, selection, or substitution was applied.

```json
{
  "production_epoch_rms": {
    "count": 1057,
    "max": 0.16951748732411961,
    "mean": 0.04342359342562351,
    "median": 0.02742438023141448,
    "min": 3.9077183543808657e-05,
    "p95": 0.1274976011847274,
    "rms": 0.0594417283483267
  },
  "proxy_implied_epoch_rms": {
    "count": 1057,
    "max": 0.43968682590576397,
    "mean": 0.2747217392563736,
    "median": 0.2820716188735627,
    "min": 0.10461531106400851,
    "p95": 0.3666260704611259,
    "rms": 0.280525267269529
  },
  "relationships": {
    "fractional_rms_vs_abs_trace_yaw_error": {
      "paired_count": 964,
      "pearson_correlation": 0.10776367439615221,
      "role": "DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING"
    },
    "fractional_rms_vs_native_objective": {
      "paired_count": 1057,
      "pearson_correlation": 0.6920050716468352,
      "role": "DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING"
    },
    "fractional_rms_vs_proxy_vector_angle": {
      "paired_count": 1057,
      "pearson_correlation": 0.04515066594894081,
      "role": "DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING"
    },
    "fractional_rms_vs_unique_candidate_count": {
      "paired_count": 1057,
      "pearson_correlation": 0.7540178112888336,
      "role": "DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING"
    },
    "proxy_objective_gap_vs_vector_angle": {
      "paired_count": 1057,
      "pearson_correlation": 0.029726359009222925,
      "role": "DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING"
    }
  },
  "stable_group_count": 37,
  "stratified_tracking_and_dimension_statistics": {
    "cycle_slip=false": {
      "epoch_count": 300,
      "production_circular": {
        "circular_mean_cycles": 0.012572715038352653,
        "circular_scatter_cycles": 0.08903190233288262,
        "count": 1294,
        "resultant_length": 0.8551602639587971
      },
      "production_linear": {
        "count": 1294,
        "max": 0.3754401977491284,
        "mean": 0.014907082865225778,
        "median": 0.002919110095535693,
        "min": -0.28026873577448064,
        "p95": 0.163945110630194,
        "rms": 0.09234446447302001
      },
      "production_observation_count": 1294,
      "proxy_circular": {
        "circular_mean_cycles": -0.369534782840459,
        "circular_scatter_cycles": 0.3788277203870877,
        "count": 1294,
        "resultant_length": 0.05884887424568874
      },
      "proxy_linear": {
        "count": 1294,
        "max": 0.49989010953110125,
        "mean": -0.015250400160465562,
        "median": -0.002468972623939969,
        "min": -0.4998545442801259,
        "p95": 0.4705636891464067,
        "rms": 0.30269296952835206
      },
      "proxy_observation_count": 1294
    },
    "cycle_slip=true": {
      "epoch_count": 757,
      "production_circular": {
        "circular_mean_cycles": -0.0072730173704934,
        "circular_scatter_cycles": 0.05528499704217664,
        "count": 2723,
        "resultant_length": 0.9414523643186657
      },
      "production_linear": {
        "count": 2723,
        "max": 0.34514912826091404,
        "mean": -0.007194684111323515,
        "median": -0.0027487253476010665,
        "min": -0.26883363078864164,
        "p95": 0.0837495043785997,
        "rms": 0.056599382920779186
      },
      "production_observation_count": 2723,
      "proxy_circular": {
        "circular_mean_cycles": -0.11958241547467281,
        "circular_scatter_cycles": 0.3421899887840936,
        "count": 2723,
        "resultant_length": 0.09912806420379548
      },
      "proxy_linear": {
        "count": 2723,
        "max": 0.49982218397162903,
        "mean": -0.028531517296045538,
        "median": -0.005892409375595875,
        "min": -0.4999931640781945,
        "p95": 0.4543690298615062,
        "rms": 0.27847188839489045
      },
      "proxy_observation_count": 2723
    },
    "lock_reset=false": {
      "epoch_count": 895,
      "production_circular": {
        "circular_mean_cycles": -0.0010954659684469785,
        "circular_scatter_cycles": 0.07068819567206451,
        "count": 3450,
        "resultant_length": 0.9060749109299047
      },
      "production_linear": {
        "count": 3450,
        "max": 0.3754401977491284,
        "mean": 0.00033741050766618124,
        "median": -0.0011690202855518805,
        "min": -0.28026873577448064,
        "p95": 0.13131192302599345,
        "rms": 0.07267122751826534
      },
      "production_observation_count": 3450,
      "proxy_circular": {
        "circular_mean_cycles": -0.17759676038343805,
        "circular_scatter_cycles": 0.373098884352998,
        "count": 3450,
        "resultant_length": 0.06407168841461183
      },
      "proxy_linear": {
        "count": 3450,
        "max": 0.49989010953110125,
        "mean": -0.02364111579424696,
        "median": -0.00389001798907751,
        "min": -0.4999931640781945,
        "p95": 0.4618859419904677,
        "rms": 0.2881706426604179
      },
      "proxy_observation_count": 3450
    },
    "lock_reset=true": {
      "epoch_count": 162,
      "production_circular": {
        "circular_mean_cycles": -0.0024450146732374954,
        "circular_scatter_cycles": 0.05138589735945123,
        "count": 567,
        "resultant_length": 0.949213447747917
      },
      "production_linear": {
        "count": 567,
        "max": 0.22812959037861447,
        "mean": -0.0025845253244798946,
        "median": -0.0006940772489230085,
        "min": -0.25339371112222864,
        "p95": 0.08450900917684319,
        "rms": 0.05207965354984587
      },
      "production_observation_count": 567,
      "proxy_circular": {
        "circular_mean_cycles": -0.11293131777205409,
        "circular_scatter_cycles": 0.33305867120928484,
        "count": 567,
        "resultant_length": 0.11195788525641374
      },
      "proxy_linear": {
        "count": 567,
        "max": 0.49941716692956106,
        "mean": -0.027977936357358804,
        "median": -0.011743534732231886,
        "min": -0.4975699795501374,
        "p95": 0.4517955395663136,
        "rms": 0.2761015325405303
      },
      "proxy_observation_count": 567
    },
    "low_dd_dimension=false": {
      "epoch_count": 491,
      "production_circular": {
        "circular_mean_cycles": 2.1463625667397473e-05,
        "circular_scatter_cycles": 0.08923870708558299,
        "count": 2319,
        "resultant_length": 0.8545381649587481
      },
      "production_linear": {
        "count": 2319,
        "max": 0.3754401977491284,
        "mean": 0.001969614523983389,
        "median": -0.0008407247435400222,
        "min": -0.28026873577448064,
        "p95": 0.1513898494627156,
        "rms": 0.09041258474158227
      },
      "production_observation_count": 2319,
      "proxy_circular": {
        "circular_mean_cycles": -0.4816224528730034,
        "circular_scatter_cycles": 0.40484529976781364,
        "count": 2319,
        "resultant_length": 0.03935033733676468
      },
      "proxy_linear": {
        "count": 2319,
        "max": 0.49989010953110125,
        "mean": -0.004637668912067466,
        "median": 0.010860327903708722,
        "min": -0.49988637953620696,
        "p95": 0.47047663002688506,
        "rms": 0.30175838967404206
      },
      "proxy_observation_count": 2319
    },
    "low_dd_dimension=true": {
      "epoch_count": 566,
      "production_circular": {
        "circular_mean_cycles": -0.002842596210109095,
        "circular_scatter_cycles": 0.021470472606446595,
        "count": 1698,
        "resultant_length": 0.9909418702504528
      },
      "production_linear": {
        "count": 1698,
        "max": 0.10600108841545186,
        "mean": -0.0028674297341868384,
        "median": -0.0010709686476721991,
        "min": -0.09832391612274449,
        "p95": 0.030683201541229138,
        "rms": 0.021721724194128104
      },
      "production_observation_count": 1698,
      "proxy_circular": {
        "circular_mean_cycles": -0.12276971173895014,
        "circular_scatter_cycles": 0.28832193702356024,
        "count": 1698,
        "resultant_length": 0.19380334197250607
      },
      "proxy_linear": {
        "count": 1698,
        "max": 0.49982218397162903,
        "mean": -0.05104274746624852,
        "median": -0.040656958679501365,
        "min": -0.4999931640781945,
        "p95": 0.4359954522840585,
        "rms": 0.26423633088356463
      },
      "proxy_observation_count": 1698
    },
    "pivot_changed=false": {
      "epoch_count": 1054,
      "production_circular": {
        "circular_mean_cycles": -0.0013166604355126731,
        "circular_scatter_cycles": 0.06832805172918645,
        "count": 4007,
        "resultant_length": 0.9119620594174482
      },
      "production_linear": {
        "count": 4007,
        "max": 0.3754401977491284,
        "mean": -9.313877509641534e-05,
        "median": -0.0010762868222258248,
        "min": -0.28026873577448064,
        "p95": 0.12716266036792442,
        "rms": 0.07021219106940482
      },
      "production_observation_count": 4007,
      "proxy_circular": {
        "circular_mean_cycles": -0.1610561248833619,
        "circular_scatter_cycles": 0.3670823736260671,
        "count": 4007,
        "resultant_length": 0.06995886132114504
      },
      "proxy_linear": {
        "count": 4007,
        "max": 0.49989010953110125,
        "mean": -0.024549261471121384,
        "median": -0.004402946503692107,
        "min": -0.4999931640781945,
        "p95": 0.46093437643419716,
        "rms": 0.28632131968294977
      },
      "proxy_observation_count": 4007
    },
    "pivot_changed=true": {
      "epoch_count": 3,
      "production_circular": {
        "circular_mean_cycles": 0.00716483186224618,
        "circular_scatter_cycles": 0.019127150316473263,
        "count": 10,
        "resultant_length": 0.992804465042466
      },
      "production_linear": {
        "count": 10,
        "max": 0.04594743919851396,
        "mean": 0.007184746427955979,
        "median": 0.0023531948323993745,
        "min": -0.023931122028177043,
        "p95": 0.03853488380232831,
        "rms": 0.020429054224864955
      },
      "production_observation_count": 10,
      "proxy_circular": {
        "circular_mean_cycles": -0.40593749439662274,
        "circular_scatter_cycles": 0.21457330496251137,
        "count": 10,
        "resultant_length": 0.40299674534995134
      },
      "proxy_linear": {
        "count": 10,
        "max": 0.49961844978902814,
        "mean": 0.09435513100089461,
        "median": 0.07814596908934757,
        "min": -0.3463070182137784,
        "p95": 0.49172674993065035,
        "rms": 0.3501607850911699
      },
      "proxy_observation_count": 10
    },
    "subHalfCyc=BOTH_RECEIVERS": {
      "epoch_count": 705,
      "production_circular": {
        "circular_mean_cycles": 0.003001439878048945,
        "circular_scatter_cycles": 0.07616072750193764,
        "count": 2828,
        "resultant_length": 0.8918151308461844
      },
      "production_linear": {
        "count": 2828,
        "max": 0.3754401977491284,
        "mean": 0.004532075432560984,
        "median": 7.963391462295633e-05,
        "min": -0.28026873577448064,
        "p95": 0.13948048802866864,
        "rms": 0.0782208844044356
      },
      "production_observation_count": 2828,
      "proxy_circular": {
        "circular_mean_cycles": -0.3048840834787447,
        "circular_scatter_cycles": 0.3315386057949016,
        "count": 2828,
        "resultant_length": 0.11421286491231386
      },
      "proxy_linear": {
        "count": 2828,
        "max": 0.49989010953110125,
        "mean": -0.03721875875661689,
        "median": -0.03239879494245246,
        "min": -0.4999931640781945,
        "p95": 0.4666329121354778,
        "rms": 0.302469410715073
      },
      "proxy_observation_count": 2828
    },
    "subHalfCyc=GNSS1_ONLY": {
      "epoch_count": 352,
      "production_circular": {
        "circular_mean_cycles": -0.010758568741924946,
        "circular_scatter_cycles": 0.043689200477600255,
        "count": 1189,
        "resultant_length": 0.9630238120433358
      },
      "production_linear": {
        "count": 1189,
        "max": 0.23538969828210554,
        "mean": -0.011032858646605751,
        "median": -0.004771921193916562,
        "min": -0.20009398999883388,
        "p95": 0.05040904535180521,
        "rms": 0.04543548476742827
      },
      "production_observation_count": 1189,
      "proxy_circular": {
        "circular_mean_cycles": 0.039246373620587915,
        "circular_scatter_cycles": 0.2766688539693659,
        "count": 1189,
        "resultant_length": 0.22070006699945843
      },
      "proxy_linear": {
        "count": 1189,
        "max": 0.49962849074029236,
        "mean": 0.006584785835944602,
        "median": 0.04015470980155733,
        "min": -0.49798633218438226,
        "p95": 0.42237718938764596,
        "rms": 0.24435121396472642
      },
      "proxy_observation_count": 1189
    }
  }
}
```

## Paths and reproduction

- Native root: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/03_EXT02_CWLS/C00`
- Native freeze: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/03_EXT02_CWLS/C00/EXT02_C00_NATIVE_FREEZE.json`
- Post-native manifest: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1/EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json`
- Report: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE2_EXT02_C00_REPORT_PROXY_TIME_ASSOCIATION_R1.md`
- Status: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE2_STATUS_PROXY_TIME_ASSOCIATION_R1.json`
- Exact formal invocation (default `full`; produced the frozen native C00 before its post-native failure): `python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT02_CWLS --case-id C00 --trace-mode disabled --workers 16`
- Exact post-only recovery invocation (separate source fingerprint; produces post-native outputs only): `python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --mode post-native-diagnostics --method-id EXT02_CWLS --case-id C00 --trace-mode disabled --workers 16 --post-recovery-id PROXY_TIME_ASSOCIATION_R1`

## Explicit non-use and scope boundary

EXT01 code/output, status baseline/yaw, Go2 yaw, receiver IMU, RTKLIB ordinary position output, final_v23 output, LegSA output, trace online input, and NAV-HPPOSECEF native input were not used. EXT03/EXT04, Classic-18, the common backbone, Canonical-541, per-case tuning, output-only correction, and metric-driven epoch deletion remain out of scope.

## Final supervisor closure amendment

This amendment is authoritative for final Phase 2 closure. It does not alter any native-freeze member or either preserved earlier post-native attempt.

### Terminal decision and identities

- Terminal: `PASS_PHASE2_EXT02_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT`.
- Scientific meaning: faithful implementation validation plus a poor BY2-C00 applicability result; not a paper claim, full-attitude result, independent-truth result, or performance-superiority claim.
- Worktree: `<AUDIT_SOURCE_WORKTREE>`.
- Branch: `stage/clean3-math-repair`.
- Task-start/base HEAD: `407edc840340989b1351d1d1aef050637aacd2df`.
- Bounded EXT02 commit: `b6fac17b91ef33e7e3296de5f439939f3b7a1f5e` (`Add faithful EXT02 C-WLS real BY2 C00 reproduction`).
- Native source fingerprint: `03e3b7141de02872991f295f76ebab289b03a7c7873ca3a27bebd8308b4666c3`.
- Corrected post-native source fingerprint: `7ae3e21598578e7c2fba5468c9e888869e52667fdb4610b46d8413abce845988`.
- Native freeze SHA-256: `c1d8260df693ed213c004ae90f3446e546e88f599b662ec40879711b8b3f060d`.

### Paper/source and equation-to-code map

Formal source: Xing Liu, Tarig Ballal, Hui Chen, and Tareq Y. Al-Naffouri, “Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination,” IEEE Transactions on Instrumentation and Measurement 71 (2022), article 8005315, DOI `10.1109/TIM.2022.3193412`; arXiv `2112.14813` was used only for typesetting cross-check. One focused search of the clean repository, configured external-source root, IEEE/author university records, arXiv, official GitHub surfaces, and linked supplements found no attributable official implementation or supplementary code. The implementation lineage is therefore `INDEPENDENT_CLEAN_ROOM_IMPLEMENTATION`.

| Paper contract | Implementation |
|---|---|
| Eqs. (5)–(8), DD design and units | `ext02_cwls.py:151` and `ext02_cwls.py:247` |
| Special round/wrap interval `(-0.5,0.5]` | `ext02_cwls.py:98` and `ext02_cwls.py:114` |
| Eq. (58), inclusive ambiguity interval | `ext02_cwls.py:313` |
| Eqs. (56)–(72), circles/intersections/tangent handling | `ext02_cwls.py:383`, `ext02_cwls.py:433`, and `ext02_cwls.py:547` |
| Eqs. (46), (54), and (73), full `[phase,code]` covariance objective | `ext02_cwls.py:247` and `ext02_cwls.py:597` |
| Eq. (74), global unit-sphere quadratic subsolver | `ext02_cwls.py:648` and `ext02_cwls.py:827` |
| Eq. (75), half-down phase recovery and alternating refinement | `ext02_cwls.py:822` and `ext02_cwls.py:859` |
| Algorithms 1/2, all-candidate completion and final wrapped-objective selection | `ext02_cwls.py:1019` |
| Shared-pivot correlated DD covariance and raw semantics | `shared_raw_backend.py:931` and the additive native HPPOSECEF-decode gate |

### GPS-L1 input, eligibility, failures, candidates, and refinement

- Exact paired RAWX input rows: 1509; accepted wrapped solutions: 1057; invalid rows: 452; conservation: 1509 = 1057 + 452.
- Accepted availability: 0.7004638833664678.
- Mean common GPS-L1 satellites: raw/code 7.9609, carrier-valid 6.4188, half-cycle/integer-compatible 4.3585; accepted DD dimension median 3, mean 3.8004, range 3–8.
- Failure ledger: `INSUFFICIENT_HALF_CYCLE_VALID=374`, `INSUFFICIENT_SATELLITE_STATES=46`, `INSUFFICIENT_CP_VALID=11`, `INSUFFICIENT_DD_DIMENSION=1`, `NUMERICAL_FAILURE=20`.
- Algorithm-1 totals over all rows: 4118 phase rows, 12061 integer-circle options/circles, 58504 circle pairs, 35732 intersecting pairs, 2384 near-tangent candidates, and 0 degenerate pairs.
- Integer options per phase row: mean 2.92885, median 3, P95 5, range 1–6.
- Raw/unique candidates across all rows: 73848/73848. Accepted epochs refined 71083 candidates; accepted median 43, P95 314, maximum 420. Twenty strict whole-pool failures contained 29 recorded failed candidates and invalidate those epochs.
- `K_policy=ALL_UNIQUE_CANDIDATES`; no candidate truncation or reference-based pruning occurred.
- Selected refinement iterations: median 2, P95 2, maximum 4; direction tolerance `1e-10`, maximum alternating iterations 20.
- All 1057 accepted rows have complete finite candidate searches; no accepted row contains a failed or nonconverged unique candidate.
- Independent input-only objective oracle: 11/11 selected epochs evaluated and passed; zero not evaluated.

### Native and descriptive numerical result

- The imposed 0.350 m baseline identity holds on all 1057 accepted rows; maximum norm error is `1.6653345369377348e-16 m`. This is a hard constraint, not accuracy evidence.
- Native baseline-heading circular mean is 334.2077 degrees with resultant length 0.25144; body-yaw circular mean is 64.2077 degrees. Elevation median is -18.3055 degrees, with range -80.0137 to 87.5458 degrees.
- Wrapped phase RMS has median 0.02742 cycles and P95 0.12750 cycles. Pseudorange residual RMS has median 0.63990 m and P95 2.01494 m.
- Accepted continuity: 30 segments, longest 285 epochs, maximum accepted gap 13.8 s.
- Corrected HPPOSECEF proxy association: 1509/1509 unique nearest common epochs, all signed offsets exactly +2 ms on a 200 ms grid.
- Proxy baseline length: mean 0.350474 m, median 0.351259 m, range 0.120379–0.474246 m. This proxy is same-source solution-level evidence, not truth.
- All 1057 accepted production objectives were evaluated at the proxy direction, including all 11 oracle-gated epochs. Proxy-minus-production objective is strictly positive: minimum 9.7560, median 327.6096; no materially lower proxy objective exists.
- Native-versus-proxy vector-angle mean/median are 95.5959/103.0512 degrees. Native-versus-proxy body-yaw RMSE/MAE/median-absolute are 120.9823/105.9365/117.0408 degrees.
- Fixed same-source trace: 964 matched accepted rows in the 66–340 s window; valid coverage 0.70365 of 1370 window rows; 25 segments; longest 285 epochs; maximum gap 13.8 s. Wrap-safe bias is 15.4329 degrees; RMSE 120.5288; MAE 105.1531; median absolute 115.8244; P90/P95/P99/max 176.2771/178.3040/179.4890/179.9661 degrees.
- Fractional-DD diagnostic groups: 37 stable satellite/pivot/subHalfCyc groups. Fractional RMS versus native objective correlation is 0.6920, versus unique-candidate count 0.7540, versus proxy vector angle 0.0452, and versus absolute trace yaw error 0.1078. These are descriptive only; no bias was calibrated or subtracted.

### Runtime, determinism, tests, and review

- Workers: 16, with all numerical thread variables fixed to 1; 20 workers were not used.
- Native artifact span from attempt identity to freeze: approximately 64 s. Sum of per-epoch worker runtimes: 56.364 s; median 0.01795 s, P95 0.15055 s, maximum 0.47504 s.
- Worker 1 versus 16: identical scientific digest `2d9c392e8b5117e51729f0f5f967374d1140449400ef4a2cbc7eb86e8c42d39a`; 16 actual processes; zero worker failures; stable row order.
- Resource admission: projected worker RSS 2.724 GB versus 22.941 GB available RAM; zero swap activity; positive cache I/O; sufficient storage. Thermal telemetry was unavailable, but the temperature gate was not required because 20 workers were not selected.
- Focused suite: `97 passed`.
- Full active suite: `719 passed, 10 skipped`; 14 existing Matplotlib/Pyparsing warnings.
- Final independent reviewer: `APPROVE`; after the bounded commit was created, the reviewer found no remaining blocker. The verdict supports the terminal strictly as implementation validation plus a BY2-C00 applicability result.

### Immutable recovery lineage and total post-freeze access accounting

- First native attempt `f193ac3a...` stopped before data parsing because DrvFS rejected Linux `RENAME_NOREPLACE`; its 2761-byte temporary identity remains preserved with SHA-256 `e74b5f63830f4a871865e86f2c3494e8dc9bea72e241f1d1276ab105dd76b020`.
- Second native attempt `50ea4e6b...` completed native rows but stopped at Python's default CSV field limit; its full attempt remains preserved.
- Successful native identity `03e3b714...` was atomically finalized before reference access.
- The five primary zero-proxy post diagnostic data files remain immutable. Recovery records their original data plus report/status inventory under SHA-256 `82d205974339cf2f4fcde9d927ab08aa5495ab5d6222835013cbb1b5045d4e60`; only the primary report/status were subsequently amended for final supervisor closure. Recovery `PROXY_TIME_ASSOCIATION_R1` supersedes only the primary proxy association and derived post diagnostics.
- Before native freeze: trace opens 0; HPPOSECEF semantic decode passes/records 0/0.
- Total post-freeze lifecycle access, including failed diagnostics and audit: trace file opens 4; HPPOSECEF receiver-stream decode passes 8; semantic records decoded 12080. The corrected successful recovery itself used 1 trace open and 2 receiver-stream passes/3020 records.

### Exact outputs, commands, and non-run proof

- Authoritative native root: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/03_EXT02_CWLS/C00/`.
- Authoritative corrected post root: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1/`.
- Exact required report: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE2_EXT02_C00_REPORT.md` (amended to point to recovery R1).
- Recovery report: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE2_EXT02_C00_REPORT_PROXY_TIME_ASSOCIATION_R1.md`.
- Exact required status: `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_REPORT/PHASE2_STATUS.json` (amended to authoritative recovery metrics).
- Exact successful native command: `python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --method-id EXT02_CWLS --case-id C00 --trace-mode disabled --workers 16`.
- Exact corrected post command: `python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml --mode post-native-diagnostics --method-id EXT02_CWLS --case-id C00 --trace-mode disabled --workers 16 --post-recovery-id PROXY_TIME_ASSOCIATION_R1`.
- The reviewed Git delta is confined to the ten authorized EXT02 contract/schema/CLI/source/test paths. EXT01 files and outputs are absent from the diff and were neither imported nor run; its frozen result was not modified.
- No EXT03, EXT04, Classic-18, common-backbone, Canonical-541 experiment runner, or Canonical-541 formal matrix was launched. The full unit suite includes Canonical-541 test modules but does not execute that experiment pipeline.
- The two unrelated Canonical helper files remained excluded and byte-identical: SHA-256 `00a54aac97ec54715c47dda9350635aa3ea3e969e5deb152e52e33614a6a6480` and `d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16`.
- No push, merge, tag, branch deletion, phase transition, or GitHub mutation was performed.

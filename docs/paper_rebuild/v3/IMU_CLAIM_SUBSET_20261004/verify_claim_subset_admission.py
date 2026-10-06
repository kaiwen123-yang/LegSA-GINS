from pathlib import Path
import datetime,hashlib,json,subprocess,tempfile,yaml
BASE=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/IMU_V3_FIX_20261004')
CODE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
STAGE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z')
BUILD=BASE/'BUILD_IDENTITY_20261004T063702Z.json'
LIB=BASE/'build/liblegsa_v23_port_core.a'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=json.loads((STAGE/'PREREGISTRATION.json').read_text());build=json.loads(BUILD.read_text())
assert sha(LIB)==build['library_sha256'] and sha(STAGE/'SOLVER')==build['binary_sha256']
configs=sorted((STAGE/'CONFIGS').glob('*.yaml'));assert len(configs)==135
probe_source='''#include <iostream>
#include "legsa_v23_port_core/config/port_config_loader.hpp"
int main(int argc,char**argv){for(int i=1;i<argc;++i){try{
 auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[i]);
 if(o.port_role!="imu_v3_corrected_controlled_replay_solver" || o.imudatalen!=8 ||
    o.data_mode!="semisynthetic" || !o.semisynthetic_data_used || o.synthetic_data_used) return 3;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\\n";return 1;}}
 std::cout<<argc-1<<" admitted\\n";}
'''
with tempfile.TemporaryDirectory(prefix='imu_claim_loader_') as name:
    fixture=Path(name);src=fixture/'probe.cpp';exe=fixture/'probe';src.write_text(probe_source)
    subprocess.run(['g++','-std=c++17','-I'+str(CODE/'cpp/legsa_v23_port_core/include'),str(src),str(LIB),'-o',str(exe)],check=True)
    actual=subprocess.run([str(exe),*map(str,configs)],capture_output=True,text=True)
    assert actual.returncode==0,actual.stderr
    original=next(p for p in configs if '_F04_' in p.name).read_text()
    negatives=[]
    def negative(field,value,base=original):
        lines=base.splitlines(keepends=True);hits=[i for i,l in enumerate(lines) if l.startswith(field+':')]
        assert len(hits)==1;lines[hits[0]]=field+': '+json.dumps(value)+'\n'
        path=fixture/(str(len(negatives))+'.yaml');path.write_text(''.join(lines))
        r=subprocess.run([str(exe),str(path)],capture_output=True,text=True)
        assert r.returncode==1,(field,r.returncode,r.stdout,r.stderr)
        negatives.append({'field':field,'replacement':value,'exit_code':r.returncode,'rejection':r.stderr.strip()})
    for field,value in [('stage_id','WRONG_STAGE'),('protocol_id','WRONG_PROTOCOL'),
                        ('case_id','D60_10s_seed_00'),('case_id','D61_10s_seed_09'),
                        ('semisynthetic_data_used',False),('data_mode','real_clean'),
                        ('run_id','WRONG_PREFIX'),('algorithm_id','AB0000'),
                        ('imudatalen',7),('imu_gap_policy','HOLD_MISSING'),
                        ('synthetic_data_used',True),('trace_used_online',True),
                        ('enable_raw_doppler',False),('enable_go2_horizontal_velocity_prior',False)]:negative(field,value)
    # Actual G-mounted binary execution has no configured estimator, provider, or reference inputs.
    help_result=subprocess.run([str(STAGE/'SOLVER'),'--help'],capture_output=True,text=True)
    assert help_result.returncode==1 and 'unknown or incomplete argument: --help' in help_result.stderr
    usage_result=subprocess.run([str(STAGE/'SOLVER')],capture_output=True,text=True)
    assert usage_result.returncode==2 and 'usage:' in usage_result.stderr
    receipt={'status':'ALL_135_CORRECTED_CONFIGS_NATIVE_LOADER_ADMITTED',
        'native_estimator_invocations':0,'reference_reads':0,'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'preregistration_sha256':sha(STAGE/'PREREGISTRATION.json'),'library_sha256':sha(LIB),
        'binary_sha256':sha(STAGE/'SOLVER'),'positive_configs':135,'positive_stdout':actual.stdout,
        'negative_contract_cases':negatives,'negative_rejections':len(negatives),
        'G_binary_help_execution':{'exit_code':help_result.returncode,'stdout':help_result.stdout,'stderr':help_result.stderr,'help_supported':False},
        'G_binary_noarg_usage_execution':{'exit_code':usage_result.returncode,'stderr':usage_result.stderr},
        'config_pins':{str(p):sha(p) for p in configs},'fixture_source':probe_source,
        'build_receipt_sha256':sha(BUILD),'probe_binary_sha256':sha(exe),
        'helper_sha256':sha(__file__)}
    with (STAGE/'ALL_135_NATIVE_LOADER_ADMISSION.json').open('x') as f:json.dump(receipt,f,indent=2)
    out=Path('/mnt/g/LegSA-GINS-project/修复_20261004/IMU_CLAIM_ALL_135_NATIVE_LOADER_ADMISSION.json')
    with out.open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({'status':receipt['status'],'positive_configs':135,'negative_rejections':len(negatives),'native_estimator_invocations':0}))
